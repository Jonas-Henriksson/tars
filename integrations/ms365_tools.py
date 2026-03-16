"""MS365 tool definitions and handlers for the TARS agent.

Registers calendar and mail tools with the agent tool registry.
Each handler acquires a token silently and calls the Graph API.
"""
from __future__ import annotations

import json
from typing import Any

from agent.tools import register_tool
from integrations.graph_client import (
    create_calendar_event,
    get_calendar_events,
    get_mail_messages,
    get_me,
    reply_to_mail,
    send_mail,
)
from integrations.ms365_auth import get_token_silent


def _no_token_error() -> dict[str, str]:
    return {"error": "Not authenticated. Use /login to connect Microsoft 365."}


# ── Calendar Tools ────────────────────────────────────────────────────


async def _handle_get_calendar(tool_input: dict) -> dict[str, Any]:
    token = get_token_silent()
    if not token:
        return _no_token_error()
    days = tool_input.get("days", 7)
    result = await get_calendar_events(token, days=days)
    if "error" in result:
        return result
    events = result.get("value", [])
    return {"events": events, "count": len(events)}


async def _handle_create_event(tool_input: dict) -> dict[str, Any]:
    token = get_token_silent()
    if not token:
        return _no_token_error()
    return await create_calendar_event(
        token,
        subject=tool_input["subject"],
        start=tool_input["start"],
        end=tool_input["end"],
        body=tool_input.get("body", ""),
        location=tool_input.get("location", ""),
        attendees=tool_input.get("attendees"),
        timezone_name=tool_input.get("timezone", "UTC"),
    )


# ── Mail Tools ────────────────────────────────────────────────────────


async def _handle_get_mail(tool_input: dict) -> dict[str, Any]:
    token = get_token_silent()
    if not token:
        return _no_token_error()
    folder = tool_input.get("folder", "inbox")
    count = tool_input.get("count", 10)
    result = await get_mail_messages(token, folder=folder, top=count)
    if "error" in result:
        return result
    messages = result.get("value", [])
    return {"messages": messages, "count": len(messages)}


async def _handle_send_mail(tool_input: dict) -> dict[str, Any]:
    token = get_token_silent()
    if not token:
        return _no_token_error()
    return await send_mail(
        token,
        to=tool_input["to"],
        subject=tool_input["subject"],
        body=tool_input["body"],
        cc=tool_input.get("cc"),
    )


async def _handle_reply_mail(tool_input: dict) -> dict[str, Any]:
    token = get_token_silent()
    if not token:
        return _no_token_error()
    return await reply_to_mail(
        token,
        message_id=tool_input["message_id"],
        comment=tool_input["comment"],
    )


# ── Registration ──────────────────────────────────────────────────────


def register_ms365_tools() -> None:
    """Register all MS365 tools with the agent."""

    register_tool(
        name="get_calendar_events",
        description=(
            "Get upcoming calendar events from the user's Microsoft 365 calendar. "
            "Returns events for the next N days."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "days": {
                    "type": "integer",
                    "description": "Number of days ahead to look (default 7).",
                    "default": 7,
                },
            },
            "required": [],
        },
        handler=_handle_get_calendar,
    )

    register_tool(
        name="create_calendar_event",
        description=(
            "Create a new event in the user's Microsoft 365 calendar. "
            "Always confirm details with the user before calling this."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "subject": {"type": "string", "description": "Event title."},
                "start": {
                    "type": "string",
                    "description": "Start datetime in ISO 8601 format (e.g. 2025-01-15T09:00:00).",
                },
                "end": {
                    "type": "string",
                    "description": "End datetime in ISO 8601 format.",
                },
                "body": {"type": "string", "description": "Event description."},
                "location": {"type": "string", "description": "Event location."},
                "attendees": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of attendee email addresses.",
                },
                "timezone": {
                    "type": "string",
                    "description": "Timezone name (default UTC).",
                    "default": "UTC",
                },
            },
            "required": ["subject", "start", "end"],
        },
        handler=_handle_create_event,
    )

    register_tool(
        name="get_mail",
        description=(
            "Get recent emails from the user's Microsoft 365 mailbox."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "folder": {
                    "type": "string",
                    "description": "Mail folder to read from (default 'inbox').",
                    "default": "inbox",
                },
                "count": {
                    "type": "integer",
                    "description": "Number of messages to retrieve (default 10).",
                    "default": 10,
                },
            },
            "required": [],
        },
        handler=_handle_get_mail,
    )

    register_tool(
        name="send_mail",
        description=(
            "Send an email from the user's Microsoft 365 account. "
            "Always confirm recipient, subject, and body with the user before sending."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "to": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of recipient email addresses.",
                },
                "subject": {"type": "string", "description": "Email subject."},
                "body": {"type": "string", "description": "Email body text."},
                "cc": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "CC recipient email addresses.",
                },
            },
            "required": ["to", "subject", "body"],
        },
        handler=_handle_send_mail,
    )

    register_tool(
        name="reply_to_mail",
        description="Reply to an existing email in the user's mailbox.",
        input_schema={
            "type": "object",
            "properties": {
                "message_id": {
                    "type": "string",
                    "description": "The ID of the message to reply to.",
                },
                "comment": {
                    "type": "string",
                    "description": "The reply text.",
                },
            },
            "required": ["message_id", "comment"],
        },
        handler=_handle_reply_mail,
    )
