"""Take screenshots of all TARS pages for UX review using Playwright."""
import asyncio
import sys
import os
from pathlib import Path

# pip install playwright — browsers already installed
from playwright.async_api import async_playwright

BASE_URL = "http://localhost:5173"
SCREENSHOT_DIR = Path(__file__).parent.parent / "screenshots"


async def take_screenshots(round_num: int = 0):
    out_dir = SCREENSHOT_DIR / f"round-{round_num}"
    out_dir.mkdir(parents=True, exist_ok=True)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            viewport={"width": 1440, "height": 900},
            color_scheme="dark",
        )
        page = await context.new_page()

        # ─── Login ───
        print("Logging in...")
        await page.goto(f"{BASE_URL}")
        await page.wait_for_timeout(1000)

        # Check if on login page
        if await page.query_selector('input[type="email"]'):
            await page.fill('input[type="email"]', 'jonas@tars.ai')
            await page.fill('input[type="password"]', 'demo123')
            await page.click('button[type="submit"]')
            await page.wait_for_timeout(2000)

        # Create team if needed (first login)
        team_input = await page.query_selector('input[placeholder*="team" i]')
        if team_input:
            await team_input.fill("Executive Team")
            create_btn = await page.query_selector('button:has-text("Create")')
            if create_btn:
                await create_btn.click()
                await page.wait_for_timeout(1000)

        # Wait for app to load
        await page.wait_for_timeout(2000)

        # ─── Command Center ───
        print("Screenshotting Command Center...")
        await page.goto(f"{BASE_URL}/")
        await page.wait_for_timeout(2000)
        await page.screenshot(path=str(out_dir / "command-center-main.png"), full_page=True)

        # Click first alert to open detail panel
        alert = await page.query_selector('[style*="borderLeft"][style*="cursor: pointer"]')
        if alert:
            await alert.click()
            await page.wait_for_timeout(800)
            await page.screenshot(path=str(out_dir / "command-center-alert-panel.png"), full_page=False)
            # Close panel
            close = await page.query_selector('[style*="position: fixed"] button')
            if close:
                await close.click()
                await page.wait_for_timeout(300)

        # ─── Work page ───
        print("Screenshotting Work page...")
        await page.goto(f"{BASE_URL}/work")
        await page.wait_for_timeout(2000)

        # Matrix view (default or click)
        matrix_btn = await page.query_selector('button:has-text("Matrix")')
        if matrix_btn:
            await matrix_btn.click()
            await page.wait_for_timeout(800)
        await page.screenshot(path=str(out_dir / "work-matrix.png"), full_page=True)

        # Board view
        board_btn = await page.query_selector('button:has-text("Board")')
        if board_btn:
            await board_btn.click()
            await page.wait_for_timeout(800)
        await page.screenshot(path=str(out_dir / "work-board.png"), full_page=True)

        # List view
        list_btn = await page.query_selector('button:has-text("List")')
        if list_btn:
            await list_btn.click()
            await page.wait_for_timeout(800)
        await page.screenshot(path=str(out_dir / "work-list.png"), full_page=True)

        # Timeline view
        timeline_btn = await page.query_selector('button:has-text("Timeline")')
        if timeline_btn:
            await timeline_btn.click()
            await page.wait_for_timeout(800)
        await page.screenshot(path=str(out_dir / "work-timeline.png"), full_page=True)

        # Open a task detail panel
        task_card = await page.query_selector('[style*="borderLeft"][style*="cursor"]')
        if task_card:
            await task_card.click()
            await page.wait_for_timeout(800)
            await page.screenshot(path=str(out_dir / "work-task-panel.png"), full_page=False)
            close = await page.query_selector('[style*="position: fixed"] button')
            if close:
                await close.click()
                await page.wait_for_timeout(300)

        # ─── Strategy page ───
        print("Screenshotting Strategy page...")
        await page.goto(f"{BASE_URL}/strategy")
        await page.wait_for_timeout(2000)

        # Hierarchy tab (default)
        await page.screenshot(path=str(out_dir / "strategy-hierarchy.png"), full_page=True)

        # Health tab
        health_btn = await page.query_selector('button:has-text("Health")')
        if health_btn:
            await health_btn.click()
            await page.wait_for_timeout(1000)
        await page.screenshot(path=str(out_dir / "strategy-health.png"), full_page=True)

        # Decisions tab
        decisions_btn = await page.query_selector('button:has-text("Decisions")')
        if decisions_btn:
            await decisions_btn.click()
            await page.wait_for_timeout(1000)
        await page.screenshot(path=str(out_dir / "strategy-decisions.png"), full_page=True)

        # Portfolio tab
        portfolio_btn = await page.query_selector('button:has-text("Portfolio")')
        if portfolio_btn:
            await portfolio_btn.click()
            await page.wait_for_timeout(1000)
        await page.screenshot(path=str(out_dir / "strategy-portfolio.png"), full_page=True)

        # Click first portfolio member to open panel
        member_card = await page.query_selector('[style*="cursor: pointer"][style*="borderLeft: 3px"]')
        if member_card:
            await member_card.click()
            await page.wait_for_timeout(800)
            await page.screenshot(path=str(out_dir / "strategy-portfolio-panel.png"), full_page=False)
            close = await page.query_selector('[style*="position: fixed"] button')
            if close:
                await close.click()
                await page.wait_for_timeout(300)

        # Review tab
        review_btn = await page.query_selector('button:has-text("Review")')
        if review_btn:
            await review_btn.click()
            await page.wait_for_timeout(1000)
        await page.screenshot(path=str(out_dir / "strategy-review.png"), full_page=True)

        # ─── People page ───
        print("Screenshotting People page...")
        await page.goto(f"{BASE_URL}/people")
        await page.wait_for_timeout(2000)

        # Directory (default)
        await page.screenshot(path=str(out_dir / "people-directory.png"), full_page=True)

        # Click first person to open panel
        person_card = await page.query_selector('[style*="cursor: pointer"][style*="borderRadius"]')
        if person_card:
            await person_card.click()
            await page.wait_for_timeout(800)
            await page.screenshot(path=str(out_dir / "people-directory-panel.png"), full_page=False)
            close = await page.query_selector('[style*="position: fixed"] button')
            if close:
                await close.click()
                await page.wait_for_timeout(300)

        # Graph view
        graph_btn = await page.query_selector('button:has-text("Graph")')
        if graph_btn:
            await graph_btn.click()
            await page.wait_for_timeout(1000)
        await page.screenshot(path=str(out_dir / "people-graph.png"), full_page=True)

        # Meeting Prep view
        prep_btn = await page.query_selector('button:has-text("Meeting Prep")')
        if prep_btn:
            await prep_btn.click()
            await page.wait_for_timeout(1000)
        await page.screenshot(path=str(out_dir / "people-meeting-prep.png"), full_page=True)

        # ─── Settings page ───
        print("Screenshotting Settings page...")
        await page.goto(f"{BASE_URL}/settings")
        await page.wait_for_timeout(1500)
        await page.screenshot(path=str(out_dir / "settings.png"), full_page=True)

        await browser.close()
        print(f"\n✓ Screenshots saved to {out_dir}/")
        for f in sorted(out_dir.glob("*.png")):
            print(f"  {f.name}")


if __name__ == "__main__":
    round_num = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    asyncio.run(take_screenshots(round_num))
