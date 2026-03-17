"""Web server for TARS voice call interface.

Serves the call UI, provides ephemeral tokens for OpenAI Realtime API,
and executes tool calls on behalf of the voice session.

Usage:
    python -m web.server
    Then open http://localhost:8080 in your browser.
"""
from __future__ import annotations

import json
import logging

import httpx
from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from config import OPENAI_API_KEY

logger = logging.getLogger(__name__)

app = FastAPI(title="TARS Voice Call")

# TARS system instructions for the Realtime API
TARS_INSTRUCTIONS = """\
You are TARS, an executive assistant AI. You are direct, efficient, and \
occasionally witty — like the robot from Interstellar, but focused on \
productivity instead of space travel. Your humor setting is at 75%.

You help your user manage their calendar, email, tasks, and documents \
through Microsoft 365. Keep responses concise and conversational — you're \
in a voice call, so be natural and don't use markdown or bullet points. \
Speak like a helpful, slightly witty colleague.

When using tools, tell the user what you're doing (e.g. "Let me check \
your calendar..." or "Creating that task now..."). Always confirm before \
sending emails or creating events.\
"""

# Tool definitions for the Realtime API (OpenAI function calling format)
REALTIME_TOOLS = [
    {
        "type": "function",
        "name": "get_calendar_events",
        "description": "Get the user's upcoming Microsoft 365 calendar events.",
        "parameters": {
            "type": "object",
            "properties": {
                "days": {"type": "integer", "description": "Days ahead to look. Default 7."},
            },
        },
    },
    {
        "type": "function",
        "name": "create_calendar_event",
        "description": "Create a new calendar event. Confirm details with user first.",
        "parameters": {
            "type": "object",
            "properties": {
                "subject": {"type": "string", "description": "Event title."},
                "start_time": {"type": "string", "description": "Start in ISO 8601 (e.g. '2025-01-15T10:00:00')."},
                "end_time": {"type": "string", "description": "End in ISO 8601."},
                "timezone": {"type": "string", "description": "IANA timezone. Default 'UTC'."},
                "location": {"type": "string", "description": "Optional location."},
                "attendees": {"type": "array", "items": {"type": "string"}, "description": "Optional attendee emails."},
            },
            "required": ["subject", "start_time", "end_time"],
        },
    },
    {
        "type": "function",
        "name": "search_calendar",
        "description": "Search calendar events by keyword in the subject.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search keyword."},
                "days": {"type": "integer", "description": "Days ahead to search. Default 30."},
            },
            "required": ["query"],
        },
    },
    {
        "type": "function",
        "name": "get_tasks",
        "description": "Get tasks from Microsoft To Do.",
        "parameters": {
            "type": "object",
            "properties": {
                "include_completed": {"type": "boolean", "description": "Include completed tasks. Default false."},
            },
        },
    },
    {
        "type": "function",
        "name": "create_task",
        "description": "Create a new task in Microsoft To Do. Confirm with user first.",
        "parameters": {
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "Task title."},
                "due_date": {"type": "string", "description": "Due date YYYY-MM-DD."},
                "importance": {"type": "string", "enum": ["low", "normal", "high"], "description": "Default 'normal'."},
                "body": {"type": "string", "description": "Optional description."},
            },
            "required": ["title"],
        },
    },
    {
        "type": "function",
        "name": "complete_task",
        "description": "Mark a task as completed. Requires task ID from get_tasks.",
        "parameters": {
            "type": "object",
            "properties": {
                "task_id": {"type": "string", "description": "The task ID."},
            },
            "required": ["task_id"],
        },
    },
    {
        "type": "function",
        "name": "get_emails",
        "description": "Get recent emails from the inbox.",
        "parameters": {
            "type": "object",
            "properties": {
                "unread_only": {"type": "boolean", "description": "Only unread. Default false."},
                "max_results": {"type": "integer", "description": "Max emails. Default 15."},
            },
        },
    },
    {
        "type": "function",
        "name": "read_email",
        "description": "Read the full body of a specific email.",
        "parameters": {
            "type": "object",
            "properties": {
                "message_id": {"type": "string", "description": "The email message ID."},
            },
            "required": ["message_id"],
        },
    },
    {
        "type": "function",
        "name": "send_email",
        "description": "Send an email. ALWAYS confirm recipient, subject, and body with user first.",
        "parameters": {
            "type": "object",
            "properties": {
                "to": {"type": "array", "items": {"type": "string"}, "description": "Recipient emails."},
                "subject": {"type": "string", "description": "Subject line."},
                "body": {"type": "string", "description": "Email body."},
                "cc": {"type": "array", "items": {"type": "string"}, "description": "Optional CC emails."},
            },
            "required": ["to", "subject", "body"],
        },
    },
    {
        "type": "function",
        "name": "search_emails",
        "description": "Search emails by keyword.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search keyword."},
                "max_results": {"type": "integer", "description": "Max results. Default 10."},
            },
            "required": ["query"],
        },
    },
    {
        "type": "function",
        "name": "search_notion",
        "description": "Search Notion pages by keyword.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search keyword."},
                "max_results": {"type": "integer", "description": "Max pages. Default 10."},
            },
            "required": ["query"],
        },
    },
    {
        "type": "function",
        "name": "read_notion_page",
        "description": "Read the full content of a Notion page.",
        "parameters": {
            "type": "object",
            "properties": {
                "page_id": {"type": "string", "description": "The Notion page ID."},
            },
            "required": ["page_id"],
        },
    },
    {
        "type": "function",
        "name": "extract_meeting_tasks",
        "description": "Extract tasks from a Notion meeting notes page, grouped by owner and topic.",
        "parameters": {
            "type": "object",
            "properties": {
                "page_id": {"type": "string", "description": "The Notion page ID with meeting notes."},
            },
            "required": ["page_id"],
        },
    },
    {
        "type": "function",
        "name": "track_meeting_tasks",
        "description": "Extract and save tasks from a meeting page for ongoing tracking and follow-up.",
        "parameters": {
            "type": "object",
            "properties": {
                "page_id": {"type": "string", "description": "The Notion page ID with meeting notes."},
            },
            "required": ["page_id"],
        },
    },
    {
        "type": "function",
        "name": "get_tracked_tasks",
        "description": "Get tracked meeting tasks. Filter by owner, topic, or status.",
        "parameters": {
            "type": "object",
            "properties": {
                "owner": {"type": "string", "description": "Filter by owner name."},
                "topic": {"type": "string", "description": "Filter by topic."},
                "status": {"type": "string", "enum": ["open", "done", "followed_up"], "description": "Filter by status."},
            },
        },
    },
    {
        "type": "function",
        "name": "search_meeting_notes",
        "description": "Search Notion for meeting notes and return content previews.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search keyword."},
                "max_results": {"type": "integer", "description": "Max pages. Default 5."},
            },
            "required": ["query"],
        },
    },
]

# Map tool names to their handler functions (lazy-loaded)
_TOOL_MAP = {
    "get_calendar_events": ("integrations.calendar", "get_events"),
    "create_calendar_event": ("integrations.calendar", "create_event"),
    "search_calendar": ("integrations.calendar", "search_events"),
    "get_tasks": ("integrations.tasks", "get_tasks"),
    "create_task": ("integrations.tasks", "create_task"),
    "complete_task": ("integrations.tasks", "complete_task"),
    "get_emails": ("integrations.mail", "get_messages"),
    "read_email": ("integrations.mail", "read_message"),
    "send_email": ("integrations.mail", "send_message"),
    "search_emails": ("integrations.mail", "search_messages"),
    "search_notion": ("integrations.notion", "search_pages"),
    "read_notion_page": ("integrations.notion", "get_page_content"),
    "extract_meeting_tasks": ("integrations.notion_tasks", "extract_meeting_tasks"),
    "track_meeting_tasks": ("integrations.notion_tasks", "track_meeting_tasks"),
    "get_tracked_tasks": ("integrations.notion_tasks", "get_tracked_tasks"),
    "search_meeting_notes": ("integrations.notion_tasks", "search_meeting_notes"),
}

# Argument name mapping (Realtime tool params -> our function params)
_ARG_MAP = {
    "create_calendar_event": {"timezone": "timezone_str"},
    "get_emails": {"max_results": "max_results", "unread_only": "unread_only"},
    "read_email": {"message_id": "message_id"},
    "send_email": {"to": "to", "subject": "subject", "body": "body", "cc": "cc"},
    "search_emails": {"query": "query", "max_results": "max_results"},
}


class ToolCallRequest(BaseModel):
    name: str
    arguments: dict


@app.get("/")
async def index():
    """Serve the call UI."""
    return FileResponse("web/static/call.html")


@app.get("/api/token")
async def get_ephemeral_token():
    """Get an ephemeral token for OpenAI Realtime API."""
    if not OPENAI_API_KEY:
        return JSONResponse(
            {"error": "OPENAI_API_KEY not configured"},
            status_code=500,
        )

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                "https://api.openai.com/v1/realtime/sessions",
                headers={
                    "Authorization": f"Bearer {OPENAI_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": "gpt-4o-mini-realtime-preview",
                    "voice": "ash",
                    "instructions": TARS_INSTRUCTIONS,
                    "tools": REALTIME_TOOLS,
                    "turn_detection": {
                        "type": "server_vad",
                        "threshold": 0.5,
                        "silence_duration_ms": 800,
                    },
                },
                timeout=10,
            )
            resp.raise_for_status()
            data = resp.json()

        return JSONResponse({
            "token": data["client_secret"]["value"],
            "expires_at": data.get("expires_at"),
        })

    except httpx.HTTPStatusError as exc:
        logger.exception("Failed to get ephemeral token")
        return JSONResponse(
            {"error": f"OpenAI API error: {exc.response.status_code}"},
            status_code=502,
        )
    except Exception as exc:
        logger.exception("Failed to get ephemeral token")
        return JSONResponse(
            {"error": str(exc)},
            status_code=500,
        )


@app.post("/api/tool")
async def execute_tool(req: ToolCallRequest):
    """Execute a tool call from the Realtime voice session.

    The browser forwards function calls from OpenAI here,
    we execute them, and the browser sends results back to OpenAI.
    """
    tool_info = _TOOL_MAP.get(req.name)
    if tool_info is None:
        return JSONResponse({"error": f"Unknown tool: {req.name}"}, status_code=400)

    module_path, func_name = tool_info

    try:
        import importlib
        module = importlib.import_module(module_path)
        func = getattr(module, func_name)

        # Remap argument names if needed
        args = dict(req.arguments)
        if req.name in _ARG_MAP:
            remapped = {}
            for k, v in args.items():
                new_key = _ARG_MAP[req.name].get(k, k)
                remapped[new_key] = v
            args = remapped

        result = await func(**args)
        return JSONResponse({"result": result})

    except RuntimeError as exc:
        return JSONResponse({"error": str(exc)})
    except Exception as exc:
        logger.exception("Tool execution failed: %s", req.name)
        return JSONResponse({"error": f"Tool failed: {exc}"})


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
