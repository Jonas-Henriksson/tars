"""Microsoft 365 Calendar integration — read and create events."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from integrations.ms_auth import get_token_silent
from integrations.ms_graph import graph_get, graph_post

logger = logging.getLogger(__name__)


def _require_token() -> str:
    """Get a valid token or raise with a helpful message."""
    token = get_token_silent()
    if token is None:
        raise RuntimeError(
            "Not signed in to Microsoft 365. "
            "Use /login to connect your account first."
        )
    return token


def _format_event(event: dict[str, Any]) -> dict[str, Any]:
    """Extract key fields from a Graph API event object."""
    start = event.get("start", {})
    end = event.get("end", {})
    return {
        "id": event.get("id", ""),
        "subject": event.get("subject", "(No subject)"),
        "start": start.get("dateTime", ""),
        "end": end.get("dateTime", ""),
        "timezone": start.get("timeZone", "UTC"),
        "location": event.get("location", {}).get("displayName", ""),
        "is_online": event.get("isOnlineMeeting", False),
        "organizer": event.get("organizer", {}).get("emailAddress", {}).get("name", ""),
        "web_link": event.get("webLink", ""),
    }


async def get_events(days: int = 7, max_results: int = 20) -> dict[str, Any]:
    """Get upcoming calendar events.

    Args:
        days: Number of days ahead to look (default 7).
        max_results: Max events to return (default 20).

    Returns:
        Dict with "events" list and "count" int.
    """
    token = _require_token()

    now = datetime.now(timezone.utc)
    end = now + timedelta(days=days)

    params = {
        "startDateTime": now.isoformat(),
        "endDateTime": end.isoformat(),
        "$top": str(max_results),
        "$orderby": "start/dateTime",
        "$select": "subject,start,end,location,isOnlineMeeting,organizer,webLink",
    }

    data = await graph_get("/me/calendarView", token, params)
    events = [_format_event(e) for e in data.get("value", [])]

    return {"events": events, "count": len(events)}


async def create_event(
    subject: str,
    start_time: str,
    end_time: str,
    timezone_str: str = "UTC",
    location: str = "",
    body: str = "",
    attendees: list[str] | None = None,
) -> dict[str, Any]:
    """Create a new calendar event.

    Args:
        subject: Event title.
        start_time: ISO 8601 datetime string (e.g. "2025-01-15T10:00:00").
        end_time: ISO 8601 datetime string.
        timezone_str: IANA timezone (e.g. "Europe/Stockholm").
        location: Optional location string.
        body: Optional event description.
        attendees: Optional list of email addresses.

    Returns:
        Dict with created event details.
    """
    token = _require_token()

    event_body: dict[str, Any] = {
        "subject": subject,
        "start": {"dateTime": start_time, "timeZone": timezone_str},
        "end": {"dateTime": end_time, "timeZone": timezone_str},
    }

    if location:
        event_body["location"] = {"displayName": location}

    if body:
        event_body["body"] = {"contentType": "text", "content": body}

    if attendees:
        event_body["attendees"] = [
            {
                "emailAddress": {"address": email},
                "type": "required",
            }
            for email in attendees
        ]

    data = await graph_post("/me/events", token, event_body)
    return _format_event(data)
