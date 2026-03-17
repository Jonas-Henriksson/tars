"""Reminder system — schedule notifications via Telegram.

Uses an in-memory store with JSON persistence. The Telegram bot's JobQueue
handles the actual scheduling of callback functions.
"""
from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_REMINDERS_PATH = Path(__file__).parent.parent / "reminders.json"

# In-memory store: {reminder_id: reminder_dict}
_reminders: dict[str, dict[str, Any]] = {}


def _load() -> None:
    """Load reminders from disk."""
    global _reminders
    if _REMINDERS_PATH.exists():
        try:
            _reminders = json.loads(_REMINDERS_PATH.read_text())
        except (json.JSONDecodeError, OSError):
            _reminders = {}


def _save() -> None:
    """Persist reminders to disk."""
    try:
        _REMINDERS_PATH.write_text(json.dumps(_reminders, indent=2))
    except OSError:
        logger.exception("Failed to save reminders")


def _format_reminder(reminder: dict[str, Any]) -> dict[str, Any]:
    """Format a reminder for display."""
    return {
        "id": reminder["id"],
        "message": reminder["message"],
        "remind_at": reminder["remind_at"],
        "chat_id": reminder["chat_id"],
        "created": reminder.get("created", ""),
    }


def create_reminder(
    chat_id: int,
    message: str,
    remind_at: str,
) -> dict[str, Any]:
    """Create a new reminder.

    Args:
        chat_id: Telegram chat ID to send the reminder to.
        message: Reminder message text.
        remind_at: ISO 8601 datetime string for when to trigger (e.g. "2025-01-15T10:00:00+00:00").

    Returns:
        Dict with created reminder details.
    """
    reminder_id = uuid.uuid4().hex[:8]
    reminder = {
        "id": reminder_id,
        "chat_id": chat_id,
        "message": message,
        "remind_at": remind_at,
        "created": datetime.now(timezone.utc).isoformat(),
    }
    _reminders[reminder_id] = reminder
    _save()
    return _format_reminder(reminder)


def get_reminders(chat_id: int) -> dict[str, Any]:
    """Get all pending reminders for a chat.

    Args:
        chat_id: Telegram chat ID.

    Returns:
        Dict with "reminders" list and "count".
    """
    now = datetime.now(timezone.utc).isoformat()
    pending = [
        _format_reminder(r)
        for r in _reminders.values()
        if r["chat_id"] == chat_id and r["remind_at"] > now
    ]
    pending.sort(key=lambda r: r["remind_at"])
    return {"reminders": pending, "count": len(pending)}


def delete_reminder(reminder_id: str, chat_id: int) -> dict[str, Any]:
    """Delete a reminder.

    Args:
        reminder_id: The reminder ID to delete.
        chat_id: Chat ID (for ownership verification).

    Returns:
        Dict confirming deletion.
    """
    reminder = _reminders.get(reminder_id)
    if reminder is None:
        raise RuntimeError(f"Reminder '{reminder_id}' not found.")
    if reminder["chat_id"] != chat_id:
        raise RuntimeError("You can only delete your own reminders.")
    del _reminders[reminder_id]
    _save()
    return {"status": "deleted", "id": reminder_id}


def get_due_reminders() -> list[dict[str, Any]]:
    """Get all reminders that are due now and remove them from the store.

    Returns:
        List of due reminder dicts.
    """
    now = datetime.now(timezone.utc).isoformat()
    due = []
    to_remove = []
    for rid, reminder in _reminders.items():
        if reminder["remind_at"] <= now:
            due.append(reminder)
            to_remove.append(rid)
    for rid in to_remove:
        del _reminders[rid]
    if to_remove:
        _save()
    return due


# Load on import
_load()
