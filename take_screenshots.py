"""
Screenshot workflow for Manufacturing Location Analyzer.
Launches the Streamlit app, enables example data (12 items), navigates each page,
and saves full-page screenshots for visual review.

Usage:
    python take_screenshots.py [round_label]
    # e.g. python take_screenshots.py round0
"""
import subprocess
import sys
import time
import os
from pathlib import Path

from playwright.sync_api import sync_playwright

SCREENSHOTS_DIR = Path(__file__).parent / "screenshots"
APP_FILE = Path(__file__).parent / "landed_cost_app.py"
PORT = 8501
BASE_URL = f"http://localhost:{PORT}"

# Pages to screenshot — (nav_button_text, page_label, extra_wait_seconds)
PAGES = [
    ("Landed Cost Analysis", "model", 6),
    ("Required Investments", "investment", 4),
    ("Financial Configuration", "financial", 3),
    ("Analysis Summary", "executive", 5),
    ("Pre-study", "prestudy", 3),
    ("Transfer Feasibility", "transfer", 3),
    ("Proposal", "proposal", 3),
    ("Actuals vs. Plan", "actuals", 3),
    ("About & Methodology", "about", 3),
    ("User Guide", "guide", 3),
    ("Changelog & Contact", "changelog", 3),
]


def wait_for_server(url, timeout=90):
    """Wait until the Streamlit server is responding."""
    import urllib.request
    start = time.time()
    while time.time() - start < timeout:
        try:
            urllib.request.urlopen(url, timeout=3)
            return True
        except Exception:
            time.sleep(1)
    return False


def wait_for_app_loaded(page, timeout=30000):
    """Wait for Streamlit app to fully render (sidebar + main content visible)."""
    try:
        # Wait for sidebar to be visible
        page.wait_for_selector('[data-testid="stSidebar"]', timeout=timeout)
        # Wait for main block container
        page.wait_for_selector('[data-testid="stMainBlockContainer"]', timeout=timeout)
        # Wait for any button in sidebar (nav buttons)
        page.wait_for_selector('[data-testid="stSidebar"] button', timeout=timeout)
        # Extra settle time for rendering
        page.wait_for_timeout(3000)
    except Exception as e:
        print(f"  Warning: wait_for_app_loaded: {e}")
        page.wait_for_timeout(5000)


def take_screenshots(round_label="round0"):
    out_dir = SCREENSHOTS_DIR / round_label
    out_dir.mkdir(parents=True, exist_ok=True)

    # Kill any existing Streamlit on this port
    subprocess.run(["pkill", "-f", f"streamlit.*{PORT}"], capture_output=True)
    time.sleep(1)

    # Start Streamlit server
    print(f"Starting Streamlit on port {PORT}...")
    proc = subprocess.Popen(
        [
            sys.executable, "-m", "streamlit", "run", str(APP_FILE),
            "--server.port", str(PORT),
            "--server.headless", "true",
            "--server.enableCORS", "false",
            "--server.enableXsrfProtection", "false",
            "--browser.gatherUsageStats", "false",
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    try:
        if not wait_for_server(BASE_URL):
            print("ERROR: Streamlit server did not start in time.")
            proc.terminate()
            return

        print("Server is up. Launching browser...")

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                viewport={"width": 1920, "height": 1080},
                device_scale_factor=2,
            )
            page = context.new_page()

            # Load the app and wait for it to fully render
            page.goto(BASE_URL, wait_until="networkidle", timeout=60000)
            wait_for_app_loaded(page, timeout=30000)

            # Enable "Load example data" checkbox
            print("Enabling example data...")
            try:
                checkbox_label = page.locator('label:has-text("Load example data")')
                if checkbox_label.count() > 0:
                    checkbox_label.first.click()
                    # Wait for rerun — Streamlit will reload with 12 items
                    page.wait_for_timeout(8000)
                    wait_for_app_loaded(page, timeout=30000)
                    print("  Example data enabled (12 items)")
                else:
                    print("  WARNING: Could not find 'Load example data' checkbox")
            except Exception as e:
                print(f"  WARNING: Failed to enable example data: {e}")

            print(f"\nTaking screenshots for {round_label}...")

            for btn_text, page_label, extra_wait in PAGES:
                print(f"  -> {page_label} ({btn_text})")

                # Click sidebar nav button
                try:
                    sidebar = page.locator('[data-testid="stSidebar"]')
                    btn = sidebar.locator(f'button:has-text("{btn_text}")')
                    if btn.count() > 0:
                        btn.first.click()
                        page.wait_for_timeout(extra_wait * 1000)
                    else:
                        print(f"     WARNING: nav button '{btn_text}' not found")
                except Exception as e:
                    print(f"     WARNING: click failed: {e}")

                # Full-page screenshot
                page.screenshot(
                    path=str(out_dir / f"{page_label}.png"),
                    full_page=True,
                )

                # For the model page, also screenshot item tabs
                if page_label == "model":
                    _screenshot_item_tabs(page, out_dir)

            # Viewport-only screenshot of model page
            try:
                sidebar = page.locator('[data-testid="stSidebar"]')
                btn = sidebar.locator('button:has-text("Landed Cost Analysis")')
                if btn.count() > 0:
                    btn.first.click()
                    page.wait_for_timeout(4000)
                page.screenshot(
                    path=str(out_dir / "model_viewport.png"),
                    full_page=False,
                )
            except Exception:
                pass

            browser.close()

        print(f"\nScreenshots saved to {out_dir}")
        _list_screenshots(out_dir)

    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()


def _screenshot_item_tabs(page, out_dir):
    """Click through item tabs on the model page and screenshot a few."""
    try:
        tabs = page.locator('[data-baseweb="tab"]')
        count = tabs.count()
        if count == 0:
            print("     No item tabs found")
            return

        print(f"     Found {count} tabs, screenshotting key ones...")

        # Screenshot items 1, 2, 6 and Portfolio Summary
        indices = [0, 1]
        if count > 6:
            indices.append(5)  # Item 6
        if count > 1:
            indices.append(count - 1)  # Portfolio Summary (last tab)

        for i in indices:
            if i >= count:
                continue
            tab = tabs.nth(i)
            label = tab.inner_text().strip()
            tab.click()
            page.wait_for_timeout(3000)
            safe_name = label.lower().replace(' ', '_').replace('/', '_')
            page.screenshot(
                path=str(out_dir / f"model_tab_{safe_name}.png"),
                full_page=True,
            )
            print(f"       Tab: {label}")
    except Exception as e:
        print(f"     WARNING: tab screenshots failed: {e}")


def _list_screenshots(out_dir):
    """Print summary of captured screenshots."""
    files = sorted(out_dir.glob("*.png"))
    total_kb = 0
    print(f"\nCaptured {len(files)} screenshots:")
    for f in files:
        size_kb = f.stat().st_size / 1024
        total_kb += size_kb
        print(f"  {f.name:50s} {size_kb:>8.0f} KB")
    print(f"  {'Total':50s} {total_kb:>8.0f} KB")


if __name__ == "__main__":
    label = sys.argv[1] if len(sys.argv) > 1 else "round0"
    take_screenshots(label)
