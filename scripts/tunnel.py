#!/usr/bin/env python3
"""Tunnel manager for TARS — supports Cloudflare and ngrok.

Provides a public HTTPS URL so Notion can push webhook events to TARS,
while keeping everything running on your local machine.

Usage:
    # Auto-detect best available tunnel (tries Cloudflare first, falls back to ngrok):
    python -m scripts.tunnel

    # Force ngrok:
    python -m scripts.tunnel --provider ngrok

    # Force Cloudflare:
    python -m scripts.tunnel --provider cloudflare

    # Named Cloudflare tunnel (requires CF account):
    python -m scripts.tunnel --provider cloudflare --name tars --hostname tars.yourdomain.com

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
import threading
import urllib.request
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger(__name__)

_ROOT = Path(__file__).parent.parent
_STATUS_FILE = _ROOT / "tunnel_status.json"


# ── Helpers ───────────────────────────────────────────────────────────

def _is_windows() -> bool:
    return platform.system().lower() == "windows"


def _save_status(data: dict) -> None:
    _STATUS_FILE.write_text(json.dumps(data, indent=2))


def _load_status() -> dict:
    if _STATUS_FILE.exists():
        try:
            return json.loads(_STATUS_FILE.read_text())
        except (json.JSONDecodeError, OSError):
            pass
    return {}


def _print_tunnel_active(tunnel_url: str, port: int, provider: str) -> None:
    webhook_url = tunnel_url + "/api/notion/webhook"
    log.info("=" * 60)
    log.info("TUNNEL ACTIVE (%s)", provider)
    log.info("=" * 60)
    log.info("Public URL:  %s", tunnel_url)
    log.info("Webhook URL: %s", webhook_url)
    log.info("")
    log.info("Next steps:")
    log.info("  1. Go to notion.so/my-integrations")
    log.info("  2. Select your integration → Webhooks → add URL above")
    log.info("  3. In TARS Settings: enable push")
    log.info("=" * 60)
    _save_status({
        "running": True,
        "url": tunnel_url,
        "webhook_url": webhook_url,
        "type": provider,
        "port": port,
    })
    try:
        from integrations.webhook_status import enable
        enable()
    except Exception:
        pass


def _setup_signals(on_exit):
    signal.signal(signal.SIGINT, on_exit)
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, on_exit)


# ── Cloudflare ────────────────────────────────────────────────────────

_CF_BASE = "https://github.com/cloudflare/cloudflared/releases/latest/download/"


def _cf_binary_name() -> str:
    return "cloudflared.exe" if _is_windows() else "cloudflared"


def _cf_download_url() -> str:
    system = platform.system().lower()
    machine = platform.machine().lower()
    if system == "windows":
        return _CF_BASE + ("cloudflared-windows-amd64.exe" if "64" in machine else "cloudflared-windows-386.exe")
    if system == "darwin":
        return _CF_BASE + ("cloudflared-darwin-arm64.tgz" if "arm" in machine else "cloudflared-darwin-amd64.tgz")
    return _CF_BASE + ("cloudflared-linux-arm64" if "arm" in machine else "cloudflared-linux-amd64")


def _find_cloudflared() -> str | None:
    path = shutil.which("cloudflared")
    if path:
        return path
    local = _ROOT / "bin" / _cf_binary_name()
    if local.exists():
        return str(local)
    return None


def install_cloudflared() -> str | None:
    existing = _find_cloudflared()
    if existing:
        return existing
    url = _cf_download_url()
    log.info("Downloading cloudflared for %s/%s...", platform.system(), platform.machine())
    bin_dir = _ROOT / "bin"
    bin_dir.mkdir(exist_ok=True)
    target = bin_dir / _cf_binary_name()
    try:
        urllib.request.urlretrieve(url, str(target))
        if not _is_windows():
            target.chmod(0o755)
        log.info("Installed cloudflared to %s", target)
        return str(target)
    except Exception as e:
        log.warning("Could not install cloudflared: %s", e)
        return None


def run_cloudflare_tunnel(port: int = 8080) -> None:
    cloudflared = install_cloudflared()
    if not cloudflared:
        log.error("cloudflared not available — try --provider ngrok")
        sys.exit(1)

    cmd = [cloudflared, "tunnel", "--url", f"http://localhost:{port}"]
    log.info("Starting Cloudflare tunnel to localhost:%d...", port)
    log.info("Press Ctrl+C to stop.\n")

    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    tunnel_url = None
    url_printed = False

    def _read_stream(stream):
        for line in iter(stream.readline, ""):
            line = line.strip()
            if not line:
                continue
            nonlocal tunnel_url, url_printed
            if (".trycloudflare.com" in line or "cfargotunnel.com" in line):
                for word in line.split():
                    if word.startswith("https://"):
                        tunnel_url = word.rstrip("/")
                        break
            if any(kw in line.lower() for kw in ["err", "warn", "registered", "trycloudflare", "thank you", "failed"]):
                log.info("  [cloudflared] %s", line)

    threading.Thread(target=_read_stream, args=(proc.stdout,), daemon=True).start()
    threading.Thread(target=_read_stream, args=(proc.stderr,), daemon=True).start()

    def _shutdown(sig, frame):
        log.info("\nShutting down tunnel...")
        proc.terminate()
        _save_status({"running": False, "url": None})
        sys.exit(0)

    _setup_signals(_shutdown)

    while proc.poll() is None:
        if tunnel_url and not url_printed:
            url_printed = True
            _print_tunnel_active(tunnel_url, port, "cloudflare")
        import time; time.sleep(0.5)

    _save_status({"running": False, "url": None})
    rc = proc.returncode
    if rc != 0:
        log.error("cloudflared exited with code %d", rc)
        log.info("Tip: if you see a TLS/certificate error, try: python -m scripts.tunnel --provider ngrok")


def run_named_cf_tunnel(name: str, hostname: str, port: int = 8080) -> None:
    cloudflared = install_cloudflared()
    if not cloudflared:
        sys.exit(1)

    result = subprocess.run([cloudflared, "tunnel", "list", "--output", "json"], capture_output=True, text=True)
    tunnel_exists = False
    if result.returncode == 0:
        try:
            tunnel_exists = any(t.get("name") == name for t in json.loads(result.stdout))
        except json.JSONDecodeError:
            pass

    if not tunnel_exists:
        log.info("Creating tunnel '%s'...", name)
        subprocess.run([cloudflared, "tunnel", "create", name], check=True)
        subprocess.run([cloudflared, "tunnel", "route", "dns", name, hostname], check=True)

    _print_tunnel_active(f"https://{hostname}", port, "cloudflare-named")

    def _shutdown(sig, frame):
        log.info("\nShutting down...")
        _save_status({"running": False, "url": None})
        sys.exit(0)

    _setup_signals(_shutdown)
    subprocess.run([cloudflared, "tunnel", "run", "--url", f"http://localhost:{port}", name])


# ── ngrok ─────────────────────────────────────────────────────────────

_NGROK_BASE = "https://bin.equinox.io/c/bNyj1mQVY4c/"


def _ngrok_binary_name() -> str:
    return "ngrok.exe" if _is_windows() else "ngrok"


def _ngrok_download_url() -> str:
    system = platform.system().lower()
    machine = platform.machine().lower()
    # Use the stable release zip
    if system == "windows":
        arch = "amd64" if "64" in machine else "386"
        return f"https://bin.equinox.io/c/bNyj1mQVY4c/ngrok-stable-windows-{arch}.zip"
    if system == "darwin":
        arch = "arm64" if "arm" in machine else "amd64"
        return f"https://bin.equinox.io/c/bNyj1mQVY4c/ngrok-stable-darwin-{arch}.zip"
    arch = "arm64" if "arm" in machine else "amd64"
    return f"https://bin.equinox.io/c/bNyj1mQVY4c/ngrok-stable-linux-{arch}.tgz"


def _find_ngrok() -> str | None:
    path = shutil.which("ngrok")
    if path:
        return path
    local = _ROOT / "bin" / _ngrok_binary_name()
    if local.exists():
        return str(local)
    return None


def install_ngrok() -> str | None:
    existing = _find_ngrok()
    if existing:
        return existing

    log.info("Downloading ngrok for %s/%s...", platform.system(), platform.machine())
    bin_dir = _ROOT / "bin"
    bin_dir.mkdir(exist_ok=True)
    url = _ngrok_download_url()
    archive = bin_dir / ("ngrok-dl.zip" if url.endswith(".zip") else "ngrok-dl.tgz")

    try:
        urllib.request.urlretrieve(url, str(archive))
    except Exception as e:
        log.warning("Could not download ngrok: %s", e)
        return None

    # Extract
    import zipfile, tarfile
    target_dir = bin_dir
    try:
        if archive.suffix == ".zip":
            with zipfile.ZipFile(str(archive)) as z:
                z.extractall(str(target_dir))
        else:
            with tarfile.open(str(archive)) as t:
                t.extractall(str(target_dir))
        archive.unlink()
    except Exception as e:
        log.warning("Could not extract ngrok: %s", e)
        return None

    binary = bin_dir / _ngrok_binary_name()
    if binary.exists():
        if not _is_windows():
            binary.chmod(0o755)
        log.info("Installed ngrok to %s", binary)
        return str(binary)

    log.warning("ngrok binary not found after extraction")
    return None


def run_ngrok_tunnel(port: int = 8080, authtoken: str | None = None) -> None:
    ngrok = _find_ngrok()

    if not ngrok:
        log.info("ngrok not found in PATH or bin/ — attempting download...")
        ngrok = install_ngrok()

    if not ngrok:
        log.error("ngrok not available. Install it from https://ngrok.com/download")
        log.error("Then run: ngrok config add-authtoken <your-token>")
        sys.exit(1)

    # Set authtoken if provided
    if authtoken:
        subprocess.run([ngrok, "config", "add-authtoken", authtoken], check=True)

    # Check if authtoken is configured
    result = subprocess.run([ngrok, "config", "check"], capture_output=True, text=True)
    if result.returncode != 0 or "authtoken" not in (result.stdout + result.stderr).lower():
        # Try to run anyway — ngrok will print a helpful error if token is missing
        pass

    cmd = [ngrok, "http", str(port), "--log", "stdout", "--log-format", "json"]
    log.info("Starting ngrok tunnel to localhost:%d...", port)
    log.info("Press Ctrl+C to stop.\n")

    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    tunnel_url = None
    url_printed = False

    def _read_ngrok(stream):
        nonlocal tunnel_url, url_printed
        for line in iter(stream.readline, ""):
            line = line.strip()
            if not line:
                continue
            # ngrok JSON log lines
            try:
                entry = json.loads(line)
                msg = entry.get("msg", "")
                url = entry.get("url", "")
                if url and url.startswith("https://"):
                    tunnel_url = url.rstrip("/")
                if "started tunnel" in msg.lower() and entry.get("url", "").startswith("https://"):
                    tunnel_url = entry["url"].rstrip("/")
                if any(kw in msg.lower() for kw in ["err", "failed", "auth"]):
                    log.info("  [ngrok] %s", msg)
            except json.JSONDecodeError:
                # Plain text line — look for URL
                if "ngrok-free.app" in line or "ngrok.io" in line or "ngrok-free.dev" in line:
                    for word in line.split():
                        if word.startswith("https://") and "ngrok" in word:
                            tunnel_url = word.rstrip("/")
                if any(kw in line.lower() for kw in ["err", "failed", "auth", "forwarding"]):
                    log.info("  [ngrok] %s", line)

    threading.Thread(target=_read_ngrok, args=(proc.stdout,), daemon=True).start()
    threading.Thread(target=_read_ngrok, args=(proc.stderr,), daemon=True).start()

    # Also poll ngrok's local API for the URL (most reliable method)
    def _poll_ngrok_api():
        nonlocal tunnel_url
        import time
        for _ in range(20):  # try for 10s
            time.sleep(0.5)
            try:
                with urllib.request.urlopen("http://127.0.0.1:4040/api/tunnels", timeout=1) as resp:
                    data = json.loads(resp.read())
                    for t in data.get("tunnels", []):
                        url = t.get("public_url", "")
                        if url.startswith("https://"):
                            tunnel_url = url.rstrip("/")
                            return
            except Exception:
                pass

    threading.Thread(target=_poll_ngrok_api, daemon=True).start()

    def _shutdown(sig, frame):
        log.info("\nShutting down tunnel...")
        proc.terminate()
        _save_status({"running": False, "url": None})
        sys.exit(0)

    _setup_signals(_shutdown)

    import time
    while proc.poll() is None:
        if tunnel_url and not url_printed:
            url_printed = True
            _print_tunnel_active(tunnel_url, port, "ngrok")
        time.sleep(0.5)

    _save_status({"running": False, "url": None})
    rc = proc.returncode
    if rc != 0:
        log.error("ngrok exited with code %d", rc)
        log.info("If you see an auth error, run: ngrok config add-authtoken <your-token>")


# ── Status ────────────────────────────────────────────────────────────

def show_status() -> None:
    status = _load_status()
    if not status or not status.get("running"):
        log.info("No tunnel running.")
        log.info("Start one with:  python -m scripts.tunnel")
        return
    log.info("Tunnel active:")
    log.info("  Provider:    %s", status.get("type", "unknown"))
    log.info("  Public URL:  %s", status.get("url", "?"))
    log.info("  Webhook URL: %s", status.get("webhook_url", "?"))
    log.info("  Port:        %s", status.get("port", "?"))


# ── Entry point ───────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="TARS Tunnel Manager (Cloudflare or ngrok)")
    parser.add_argument("--port", type=int, default=8080, help="Local server port (default: 8080)")
    parser.add_argument("--provider", choices=["cloudflare", "ngrok", "auto"], default="auto",
                        help="Tunnel provider (default: auto — tries Cloudflare, falls back to ngrok)")
    parser.add_argument("--authtoken", type=str, help="ngrok auth token (saves to config)")
    parser.add_argument("--name", type=str, help="Named Cloudflare tunnel")
    parser.add_argument("--hostname", type=str, help="Custom hostname for named CF tunnel")
    parser.add_argument("--status", action="store_true", help="Show current tunnel status")
    args = parser.parse_args()

    if args.status:
        show_status()
        return

    provider = args.provider

    if provider == "auto":
        # Try Cloudflare first; if it fails use ngrok
        log.info("Auto mode: trying Cloudflare first, ngrok as fallback")
        cf = install_cloudflared()
        provider = "cloudflare" if cf else "ngrok"
        if not cf:
            log.info("cloudflared not available — using ngrok")

    if provider == "cloudflare":
        if args.name:
            if not args.hostname:
                log.error("--hostname required with --name")
                sys.exit(1)
            run_named_cf_tunnel(args.name, args.hostname, args.port)
        else:
            run_cloudflare_tunnel(args.port)
    else:
        run_ngrok_tunnel(args.port, authtoken=args.authtoken)


if __name__ == "__main__":
    main()
