"""Microsoft Graph API client for TARS.

Thin wrapper around httpx for calling Microsoft Graph endpoints.
All methods require a valid access token obtained via ms365_auth.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx

logger = logging.getLogger(__name__)

GRAPH_BASE = "https://graph.microsoft.com/v1.0"


async def _graph_request(
    method: str,
    endpoint: str,
    token: str,
    *,
    json_body: dict | None = None,
    params: dict | None = None,
) -> dict[str, Any]:
    """Make an authenticated request to Microsoft Graph."""
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    url = f"{GRAPH_BASE}{endpoint}"
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.request(
            method, url, headers=headers, json=json_body, params=params
        )
        if response.status_code >= 400:
            logger.error("Graph API error %d: %s", response.status_code, response.text)
            return {"error": f"Graph API error {response.status_code}: {response.text}"}
        if response.status_code == 204:
            return {"success": True}
        return response.json()


# ── Calendar ──────────────────────────────────────────────────────────


async def get_calendar_events(
    token: str, days: int = 7, max_events: int = 20
) -> dict[str, Any]:
    """Get upcoming calendar events."""
    now = datetime.now(timezone.utc)
    end = now + timedelta(days=days)
    params = {
        "startDateTime": now.isoformat(),
        "endDateTime": end.isoformat(),
        "$top": str(max_events),
        "$orderby": "start/dateTime",
        "$select": "subject,start,end,location,organizer,isAllDay",
    }
    return await _graph_request("GET", "/me/calendarView", token, params=params)


async def create_calendar_event(
    token: str,
    subject: str,
    start: str,
    end: str,
    *,
    body: str = "",
    location: str = "",
    attendees: list[str] | None = None,
    timezone_name: str = "UTC",
) -> dict[str, Any]:
    """Create a new calendar event."""
    event: dict[str, Any] = {
        "subject": subject,
        "start": {"dateTime": start, "timeZone": timezone_name},
        "end": {"dateTime": end, "timeZone": timezone_name},
    }
    if body:
        event["body"] = {"contentType": "text", "content": body}
    if location:
        event["location"] = {"displayName": location}
    if attendees:
        event["attendees"] = [
            {"emailAddress": {"address": a}, "type": "required"} for a in attendees
        ]
    return await _graph_request("POST", "/me/events", token, json_body=event)


# ── Mail ──────────────────────────────────────────────────────────────


async def get_mail_messages(
    token: str, folder: str = "inbox", top: int = 10
) -> dict[str, Any]:
    """Get recent mail messages from a folder."""
    params = {
        "$top": str(top),
        "$orderby": "receivedDateTime desc",
        "$select": "subject,from,receivedDateTime,isRead,bodyPreview",
    }
    endpoint = f"/me/mailFolders/{folder}/messages"
    return await _graph_request("GET", endpoint, token, params=params)


async def send_mail(
    token: str,
    to: list[str],
    subject: str,
    body: str,
    *,
    cc: list[str] | None = None,
) -> dict[str, Any]:
    """Send an email."""
    message: dict[str, Any] = {
        "subject": subject,
        "body": {"contentType": "text", "content": body},
        "toRecipients": [{"emailAddress": {"address": a}} for a in to],
    }
    if cc:
        message["ccRecipients"] = [{"emailAddress": {"address": a}} for a in cc]
    return await _graph_request(
        "POST", "/me/sendMail", token, json_body={"message": message}
    )


async def reply_to_mail(
    token: str, message_id: str, comment: str
) -> dict[str, Any]:
    """Reply to an email."""
    return await _graph_request(
        "POST",
        f"/me/messages/{message_id}/reply",
        token,
        json_body={"comment": comment},
    )


# ── User Profile ──────────────────────────────────────────────────────


async def get_me(token: str) -> dict[str, Any]:
    """Get the authenticated user's profile."""
    return await _graph_request("GET", "/me", token)
