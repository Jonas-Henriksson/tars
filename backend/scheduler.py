"""Scheduled background tasks for TARS.

Runs a daily Notion intelligence scan at 04:00 CET.  If the backend starts
and the last scan is older than 24 hours (e.g. machine was asleep overnight),
a catch-up scan runs immediately.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone, timedelta

logger = logging.getLogger(__name__)

_SCAN_HOUR_CET = 4  # 04:00 CET (UTC+1) / CEST (UTC+2)
_STALE_THRESHOLD = timedelta(hours=24)
_task: asyncio.Task | None = None


def _seconds_until_next_run() -> float:
    """Return seconds until next 04:00 CET."""
    try:
        from zoneinfo import ZoneInfo
    except ImportError:
        from backports.zoneinfo import ZoneInfo  # type: ignore[no-redef]

    tz = ZoneInfo("Europe/Berlin")  # CET/CEST
    now = datetime.now(tz)
    target = now.replace(hour=_SCAN_HOUR_CET, minute=0, second=0, microsecond=0)
    if target <= now:
        target += timedelta(days=1)
    return (target - now).total_seconds()


def _last_scan_is_stale() -> bool:
    """Check if the last scan is older than the stale threshold."""
    try:
        from integrations.intel import _load_intel
        intel = _load_intel()
        last = intel.get("last_scan_at")
        if not last:
            return True
        last_dt = datetime.fromisoformat(last)
        if last_dt.tzinfo is None:
            last_dt = last_dt.replace(tzinfo=timezone.utc)
        return (datetime.now(timezone.utc) - last_dt) > _STALE_THRESHOLD
    except Exception:
        return True


async def _run_scan() -> None:
    """Execute a Notion intelligence scan."""
    try:
        from integrations.intel import scan_notion
        logger.info("Scheduled scan: starting Notion intelligence scan...")
        result = await scan_notion(max_pages=50)
        pages = result.get("pages_scanned", 0)
        tasks = result.get("tasks_extracted", 0)
        logger.info("Scheduled scan complete: %d pages scanned, %d tasks extracted.", pages, tasks)
    except Exception:
        logger.exception("Scheduled scan failed.")


async def _scheduler_loop() -> None:
    """Background loop: runs scan at 04:00 CET daily, with catch-up on startup."""
    # Catch-up: if last scan is stale, run immediately
    if _last_scan_is_stale():
        logger.info("Last scan is stale (>24h ago or never). Running catch-up scan...")
        await _run_scan()

    # Daily loop
    while True:
        delay = _seconds_until_next_run()
        hours = delay / 3600
        logger.info("Next scheduled scan in %.1f hours (04:00 CET).", hours)
        await asyncio.sleep(delay)
        await _run_scan()


def start_scheduler() -> None:
    """Start the background scheduler task. Safe to call from an async context."""
    global _task
    if _task is not None and not _task.done():
        logger.warning("Scheduler already running.")
        return
    _task = asyncio.create_task(_scheduler_loop())
    logger.info("Background scheduler started (daily scan at 04:00 CET).")


def stop_scheduler() -> None:
    """Cancel the background scheduler task."""
    global _task
    if _task and not _task.done():
        _task.cancel()
        logger.info("Background scheduler stopped.")
    _task = None
