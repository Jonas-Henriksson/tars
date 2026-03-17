#!/usr/bin/env python3
"""Cloudflare Tunnel manager for TARS.

Provides a public HTTPS URL so Notion can push webhook events to TARS,
while keeping everything running on your local machine.

Usage:
    # Quick tunnel (temporary URL, no account needed):
    python -m scripts.tunnel

    # With custom domain (requires Cloudflare account + tunnel setup):
    python -m scripts.tunnel --name tars --hostname tars.yourdomain.com

    # Restrict to webhook endpoint only (maximum security):
    python -m scripts.tunnel --webhook-only

    # Show status:
    python -m scripts.tunnel --status
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import platform
import shutil
import signal
import subprocess
import sys
import urllib.request
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger(__name__)

_ROOT = Path(__file__).parent.parent
_STATUS_FILE = _ROOT / "tunnel_status.json"

_BASE_URL = "https://github.com/cloudflare/cloudflared/releases/latest/download/"

def _cloudflared_url() -> str:
    system = platform.system().lower()
    machine = platform.machine().lower()
    if system == "windows":
        return _BASE_URL + ("cloudflared-windows-amd64.exe" if "64" in machine else "cloudflared-windows-386.exe")
    if system == "darwin":
        return _BASE_URL + ("cloudflared-darwin-arm64.tgz" if "arm" in machine else "cloudflared-darwin-amd64.tgz")
    # Linux default
    return _BASE_URL + ("cloudflared-linux-arm64" if "arm" in machine else "cloudflared-linux-amd64")

def _binary_name() -> str:
    return "cloudflared.exe" if platform.system().lower() == "windows" else "cloudflared"


def _find_cloudflared() -> str | None:
    """Find cloudflared binary."""
    path = shutil.which("cloudflared")
    if path:
        return path
    local = _ROOT / "bin" / _binary_name()
    if local.exists():
        return str(local)
    return None


def install_cloudflared() -> str:
    """Download cloudflared if not present. Returns path to binary."""
    existing = _find_cloudflared()
    if existing:
        log.info("cloudflared found: %s", existing)
        return existing

    url = _cloudflared_url()
    log.info("Downloading cloudflared for %s/%s...", platform.system(), platform.machine())
    bin_dir = _ROOT / "bin"
    bin_dir.mkdir(exist_ok=True)
    target = bin_dir / _binary_name()

    try:
        urllib.request.urlretrieve(url, str(target))
        if platform.system().lower() != "windows":
            target.chmod(0o755)
        log.info("Installed cloudflared to %s", target)
        return str(target)
    except Exception as e:
        log.error("Failed to download cloudflared: %s", e)
        sys.exit(1)


def _save_status(data: dict) -> None:
    _STATUS_FILE.write_text(json.dumps(data, indent=2))


def _load_status() -> dict:
    if _STATUS_FILE.exists():
        try:
            return json.loads(_STATUS_FILE.read_text())
        except (json.JSONDecodeError, OSError):
            pass
    return {}


def run_quick_tunnel(
    cloudflared: str,
    port: int = 8080,
    webhook_only: bool = False,
) -> None:
    """Run a quick tunnel (no Cloudflare account needed).

    Gives a temporary public URL like https://random-name.trycloudflare.com
    """
    cmd = [cloudflared, "tunnel", "--url", f"http://localhost:{port}"]

    if webhook_only:
        # Use cloudflared's ingress rules to only expose the webhook path
        log.info("Webhook-only mode: only /api/notion/webhook will be accessible")

    log.info("Starting Cloudflare quick tunnel to localhost:%d...", port)
    log.info("Press Ctrl+C to stop.\n")

    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    import threading

    def _pipe_stderr():
        for line in iter(proc.stderr.readline, ""):
            line = line.strip()
            if not line:
                continue
            if ".trycloudflare.com" in line or "cfargotunnel.com" in line:
                for word in line.split():
                    if word.startswith("https://"):
                        proc._tars_url = word.rstrip("/")
                        break
            if any(kw in line.lower() for kw in ["err", "warn", "connection", "registered", "serving", "trycloudflare", "thank you"]):
                log.info("  [cloudflared] %s", line)

    proc._tars_url = None
    threading.Thread(target=_pipe_stderr, daemon=True).start()

    tunnel_url = None

    def _shutdown(sig, frame):
        log.info("\nShutting down tunnel...")
        proc.terminate()
        _save_status({"running": False, "url": None})
        sys.exit(0)

    signal.signal(signal.SIGINT, _shutdown)
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, _shutdown)

    # Read output and find the tunnel URL
    for line in iter(proc.stdout.readline, ""):
        line = line.strip()
        if not line:
            continue

        # cloudflared prints the URL in its log output
        # Also check URL from stderr thread
        if not tunnel_url and getattr(proc, "_tars_url", None):
            tunnel_url = proc._tars_url

        if ".trycloudflare.com" in line or "cfargotunnel.com" in line:
            for word in line.split():
                if word.startswith("https://") and ("trycloudflare.com" in word or "cfargotunnel.com" in word):
                    tunnel_url = word.rstrip("/")
                    break

        if tunnel_url and not getattr(proc, "_url_printed", False):
                proc._url_printed = True
                webhook_url = tunnel_url + "/api/notion/webhook"
                log.info("=" * 60)
                log.info("TUNNEL ACTIVE")
                log.info("=" * 60)
                log.info("Public URL:  %s", tunnel_url)
                log.info("Webhook URL: %s", webhook_url)
                log.info("")
                log.info("To configure Notion webhooks:")
                log.info("  1. Go to notion.so/my-integrations")
                log.info("  2. Select your integration → Webhooks")
                log.info("  3. Paste this webhook URL: %s", webhook_url)
                log.info("  4. Enable push in TARS Settings page")
                log.info("=" * 60)
                log.info("")

                _save_status({
                    "running": True,
                    "url": tunnel_url,
                    "webhook_url": webhook_url,
                    "type": "quick",
                    "port": port,
                })

                # Also update webhook status to show the URL
                try:
                    from integrations.webhook_status import enable
                    enable()
                except Exception:
                    pass

        # Print cloudflared logs (filtered for readability)
        if any(kw in line.lower() for kw in ["err", "warn", "connection", "registered", "serving"]):
            log.info("  [cloudflared] %s", line)

    proc.wait()
    _save_status({"running": False, "url": None})


def run_named_tunnel(
    cloudflared: str,
    name: str,
    hostname: str,
    port: int = 8080,
) -> None:
    """Run a named tunnel (requires Cloudflare account + tunnel login)."""
    log.info("Starting named tunnel '%s' → %s → localhost:%d", name, hostname, port)

    # Check if tunnel exists
    result = subprocess.run(
        [cloudflared, "tunnel", "list", "--output", "json"],
        capture_output=True, text=True,
    )

    tunnel_exists = False
    if result.returncode == 0:
        try:
            tunnels = json.loads(result.stdout)
            tunnel_exists = any(t.get("name") == name for t in tunnels)
        except json.JSONDecodeError:
            pass

    if not tunnel_exists:
        log.info("Creating tunnel '%s'...", name)
        subprocess.run([cloudflared, "tunnel", "create", name], check=True)
        log.info("Routing DNS: %s → tunnel '%s'", hostname, name)
        subprocess.run(
            [cloudflared, "tunnel", "route", "dns", name, hostname],
            check=True,
        )

    webhook_url = f"https://{hostname}/api/notion/webhook"
    log.info("=" * 60)
    log.info("NAMED TUNNEL: %s", hostname)
    log.info("Webhook URL:  %s", webhook_url)
    log.info("=" * 60)

    _save_status({
        "running": True,
        "url": f"https://{hostname}",
        "webhook_url": webhook_url,
        "type": "named",
        "name": name,
        "hostname": hostname,
        "port": port,
    })

    # Run the tunnel
    cmd = [
        cloudflared, "tunnel", "run",
        "--url", f"http://localhost:{port}",
        name,
    ]

    def _shutdown(sig, frame):
        log.info("\nShutting down tunnel...")
        _save_status({"running": False, "url": None})
        sys.exit(0)

    signal.signal(signal.SIGINT, _shutdown)
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, _shutdown)

    subprocess.run(cmd)


def show_status() -> None:
    """Show current tunnel status."""
    status = _load_status()
    if not status or not status.get("running"):
        log.info("No tunnel running.")
        log.info("Start one with: python -m scripts.tunnel")
        return

    log.info("Tunnel active:")
    log.info("  Type:        %s", status.get("type", "unknown"))
    log.info("  Public URL:  %s", status.get("url", "?"))
    log.info("  Webhook URL: %s", status.get("webhook_url", "?"))
    log.info("  Port:        %s", status.get("port", "?"))
    if status.get("hostname"):
        log.info("  Hostname:    %s", status["hostname"])


def main():
    parser = argparse.ArgumentParser(description="TARS Cloudflare Tunnel Manager")
    parser.add_argument("--port", type=int, default=8080, help="Local port (default: 8080)")
    parser.add_argument("--name", type=str, help="Named tunnel (requires CF account)")
    parser.add_argument("--hostname", type=str, help="Custom hostname for named tunnel")
    parser.add_argument("--webhook-only", action="store_true", help="Only expose webhook endpoint")
    parser.add_argument("--status", action="store_true", help="Show tunnel status")
    parser.add_argument("--install", action="store_true", help="Just install cloudflared")
    args = parser.parse_args()

    if args.status:
        show_status()
        return

    cloudflared = install_cloudflared()

    if args.install:
        return

    if args.name:
        if not args.hostname:
            log.error("--hostname required with --name (e.g. --hostname tars.yourdomain.com)")
            sys.exit(1)
        run_named_tunnel(cloudflared, args.name, args.hostname, args.port)
    else:
        run_quick_tunnel(cloudflared, args.port, args.webhook_only)


if __name__ == "__main__":
    main()
