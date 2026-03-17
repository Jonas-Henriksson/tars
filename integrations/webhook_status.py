"""Notion webhook status tracking — tracks push health for the UI."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_STATUS_FILE = Path(__file__).parent.parent / "webhook_status.json"

_DEFAULT: dict[str, Any] = {
    "enabled": False,
    "last_event_at": None,
    "last_event_type": None,
    "events_received": 0,
    "last_error": None,
    "last_error_at": None,
    "webhook_secret": None,
}


def _load() -> dict[str, Any]:
    if _STATUS_FILE.exists():
        try:
            return json.loads(_STATUS_FILE.read_text())
        except (json.JSONDecodeError, OSError):
            pass
    return dict(_DEFAULT)


def _save(data: dict[str, Any]) -> None:
    _STATUS_FILE.write_text(json.dumps(data, indent=2, default=str))


def get_status() -> dict[str, Any]:
    """Return webhook status with computed health."""
    data = _load()
    # Compute health: green / amber / red
    if not data.get("enabled"):
        data["health"] = "disabled"
    elif not data.get("last_event_at"):
        data["health"] = "waiting"  # enabled but no events yet
    else:
        try:
            last = datetime.fromisoformat(data["last_event_at"])
            age_minutes = (datetime.now(timezone.utc) - last).total_seconds() / 60
            if age_minutes < 15:
                data["health"] = "green"
            elif age_minutes < 60:
                data["health"] = "amber"
            else:
                data["health"] = "red"
        except (ValueError, TypeError):
            data["health"] = "red"
    # Don't expose the secret
    data.pop("webhook_secret", None)
    return data


def record_event(event_type: str) -> None:
    """Record a successfully received webhook event."""
    data = _load()
    data["last_event_at"] = datetime.now(timezone.utc).isoformat()
    data["last_event_type"] = event_type
    data["events_received"] = data.get("events_received", 0) + 1
    data["last_error"] = None
    data["last_error_at"] = None
    _save(data)


def record_error(error: str) -> None:
    """Record a webhook processing error."""
    data = _load()
    data["last_error"] = error
    data["last_error_at"] = datetime.now(timezone.utc).isoformat()
    _save(data)


def enable(secret: str | None = None) -> dict[str, Any]:
    """Enable webhook receiving."""
    data = _load()
    data["enabled"] = True
    if secret:
        data["webhook_secret"] = secret
    _save(data)
    return get_status()


def disable() -> dict[str, Any]:
    """Disable webhook receiving."""
    data = _load()
    data["enabled"] = False
    _save(data)
    return get_status()


def get_secret() -> str | None:
    """Return the stored webhook secret (for verification)."""
    return _load().get("webhook_secret")
