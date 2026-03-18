"""Notification system — sends proactive messages via Telegram.

Sends scan completion summaries, webhook push notifications, and other
proactive alerts to the user's Telegram chat. Uses the Telegram Bot API
directly via httpx (no dependency on python-telegram-bot Application).

The owner chat_id is persisted so notifications work even when only
the web server is running (without the Telegram polling bot).
"""
from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# ── SSE broadcast for desktop app notifications ──────────────────────
# Subscribers are asyncio.Queues that receive notification dicts.

_subscribers: list[asyncio.Queue] = []


def subscribe() -> asyncio.Queue:
    """Add a new SSE subscriber. Returns a Queue that receives notification events."""
    q: asyncio.Queue = asyncio.Queue(maxsize=50)
    _subscribers.append(q)
    return q


def unsubscribe(q: asyncio.Queue) -> None:
    """Remove an SSE subscriber."""
    try:
        _subscribers.remove(q)
    except ValueError:
        pass


async def _broadcast(event: dict) -> None:
    """Push a notification event to all SSE subscribers."""
    for q in list(_subscribers):
        try:
            q.put_nowait(event)
        except asyncio.QueueFull:
            pass  # Drop if consumer is too slow

_STATE_FILE = Path(__file__).parent.parent / "notification_state.json"


def _load_state() -> dict[str, Any]:
    if _STATE_FILE.exists():
        try:
            return json.loads(_STATE_FILE.read_text())
        except (json.JSONDecodeError, OSError):
            pass
    return {"owner_chat_id": None, "enabled": True}


def _save_state(state: dict[str, Any]) -> None:
    _STATE_FILE.write_text(json.dumps(state, indent=2))


def set_owner_chat_id(chat_id: int) -> None:
    """Store the owner's Telegram chat ID for proactive notifications."""
    state = _load_state()
    state["owner_chat_id"] = chat_id
    _save_state(state)
    logger.info("Owner chat ID set to %s", chat_id)


def get_owner_chat_id() -> int | None:
    """Get the stored owner chat ID."""
    return _load_state().get("owner_chat_id")


def set_enabled(enabled: bool) -> None:
    """Enable or disable notifications."""
    state = _load_state()
    state["enabled"] = enabled
    _save_state(state)


def is_enabled() -> bool:
    return _load_state().get("enabled", True)


async def send_telegram(message: str) -> bool:
    """Send a Telegram message to the owner.

    Uses the Bot API directly via httpx. Works independently of
    the python-telegram-bot Application/polling loop.
    """
    state = _load_state()
    chat_id = state.get("owner_chat_id")
    if not chat_id:
        logger.debug("No owner chat_id set, skipping notification")
        return False

    if not state.get("enabled", True):
        return False

    try:
        from config import TELEGRAM_BOT_TOKEN
        if not TELEGRAM_BOT_TOKEN:
            return False

        import httpx
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
                json={
                    "chat_id": chat_id,
                    "text": message,
                    "parse_mode": "Markdown",
                },
            )
            if resp.status_code == 200:
                return True
            logger.warning("Telegram API returned %d: %s", resp.status_code, resp.text)
            return False
    except Exception as e:
        logger.warning("Failed to send Telegram notification: %s", e)
        return False


# -----------------------------------------------------------------------
# Pre-built notification messages
# -----------------------------------------------------------------------

async def notify_scan_complete(scan_result: dict) -> bool:
    """Send a notification summarizing a completed scan."""
    pages = scan_result.get("pages_scanned", 0)
    new_tasks = scan_result.get("new_tasks", 0) or scan_result.get("new_tasks_added", 0)
    topics = scan_result.get("topics_found", 0)
    people = scan_result.get("people_found", 0)

    # Enrichment summary
    enrichment = scan_result.get("enrichment", {})
    epics_created = enrichment.get("epics", {}).get("created", 0)
    stories_created = enrichment.get("epics", {}).get("stories", 0)
    steps_enriched = enrichment.get("smart_steps", {}).get("updated", 0)

    lines = ["*Scan Complete*"]
    lines.append(f"Pages scanned: {pages}")
    if new_tasks:
        lines.append(f"New tasks: {new_tasks}")
    if topics:
        lines.append(f"Topics: {topics}")
    if people:
        lines.append(f"People: {people}")
    if epics_created:
        lines.append(f"Epics created: {epics_created}")
    if stories_created:
        lines.append(f"Stories created: {stories_created}")
    if steps_enriched:
        lines.append(f"Tasks enriched with smart steps: {steps_enriched}")

    text = "\n".join(lines)

    # Broadcast to desktop SSE subscribers
    await _broadcast({
        "type": "scan_complete",
        "title": "Scan Complete",
        "body": f"{pages} pages scanned" + (f", {new_tasks} new tasks" if new_tasks else ""),
        "detail": text,
    })

    return await send_telegram(text)


async def notify_webhook_push(page_title: str, page_url: str = "") -> bool:
    """Send a notification when Notion pushes new content via webhook."""
    msg = f"*New Notion Update*\n{page_title}"
    if page_url:
        msg += f"\n[Open in Notion]({page_url})"

    # Broadcast to desktop SSE subscribers
    await _broadcast({
        "type": "webhook_push",
        "title": "New Notion Update",
        "body": page_title,
        "url": page_url,
    })

    return await send_telegram(msg)


async def notify_generic(title: str, body: str) -> bool:
    """Send a generic notification to all channels (Telegram + desktop)."""
    await _broadcast({"type": "generic", "title": title, "body": body})
    return await send_telegram(f"*{title}*\n{body}")
