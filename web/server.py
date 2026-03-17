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
from pathlib import Path

import httpx
import asyncio

from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from config import OPENAI_API_KEY

logger = logging.getLogger(__name__)

_STATIC_DIR = Path(__file__).parent / "static"

app = FastAPI(title="TARS Voice Call")

# Serve static assets (JS libraries, etc.) at /static/js/
_JS_DIR = _STATIC_DIR / "js"
if _JS_DIR.is_dir():
    app.mount("/static/js", StaticFiles(directory=_JS_DIR), name="static-js")

# TARS system instructions for the Realtime API
TARS_INSTRUCTIONS = """\
You are TARS, an executive assistant AI. You are direct, efficient, and \
occasionally witty — like the robot from Interstellar, but focused on \
productivity instead of space travel. Your humor setting is at 75%.

You help your user manage their calendar, email, tasks, and documents \
through Microsoft 365. Keep responses concise and conversational — you're \
in a voice call, so be natural and don't use markdown or bullet points. \
Speak like a helpful, slightly witty colleague.

IMPORTANT — You have access to a full intelligence library built from \
Notion page scans. This includes:
- An Eisenhower priority matrix with tasks classified as Do First, \
Schedule, Delegate, or Defer
- Smart tasks with owners, topics, follow-up dates, delegation tracking, \
and source context from meeting notes
- People and topic analysis showing who works on what
- Tracked meeting tasks with status history
- An end-of-day briefing compiler with calendar, tasks, email, and \
proactive recommendations

When the user asks about tasks, priorities, delegation, what needs \
attention, who owns what, or any question about their work — use the \
intelligence tools. Start with get_intel for a broad overview or \
get_smart_tasks for filtered queries. Use daily_briefing for end-of-day \
summaries. Use search_intel to find specific information across all \
scanned pages.

When using tools, tell the user what you're doing (e.g. "Let me check \
your priority matrix..." or "Pulling up your intelligence profile..."). \
Always confirm before sending emails or creating events.\
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
                "include_completed": {"type": "boolean", "description": "Include completed tasks. Default false."},
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
    {
        "type": "function",
        "name": "review_notion_pages",
        "description": "Review all Notion pages edited since last review. Checks title consistency, name spelling, and structure. Set auto_fix to true to auto-correct issues.",
        "parameters": {
            "type": "object",
            "properties": {
                "auto_fix": {"type": "boolean", "description": "Auto-fix spelling issues. Default false."},
            },
        },
    },
    {
        "type": "function",
        "name": "review_notion_page",
        "description": "Review a specific Notion page for consistency and spelling issues.",
        "parameters": {
            "type": "object",
            "properties": {
                "page_id": {"type": "string", "description": "The Notion page ID."},
                "auto_fix": {"type": "boolean", "description": "Auto-fix issues. Default false."},
            },
            "required": ["page_id"],
        },
    },
    {
        "type": "function",
        "name": "add_known_names",
        "description": "Add names to the spell-check list so TARS can detect misspellings in Notion.",
        "parameters": {
            "type": "object",
            "properties": {
                "names": {"type": "array", "items": {"type": "string"}, "description": "Canonical name spellings."},
            },
            "required": ["names"],
        },
    },
    {
        "type": "function",
        "name": "daily_briefing",
        "description": "Compile a comprehensive end-of-day briefing with meetings, tasks, recommendations, and proactive follow-up suggestions.",
        "parameters": {
            "type": "object",
            "properties": {},
        },
    },
    {
        "type": "function",
        "name": "scan_notion",
        "description": "Scan all Notion pages to build intelligence: topics, people, delegations, smart tasks with Eisenhower priority matrix.",
        "parameters": {
            "type": "object",
            "properties": {
                "max_pages": {"type": "integer", "description": "Max pages to scan. Default 50."},
            },
        },
    },
    {
        "type": "function",
        "name": "get_intel",
        "description": "Get the intelligence profile with executive summary, priority matrix, follow-ups, and topic coverage.",
        "parameters": {
            "type": "object",
            "properties": {},
        },
    },
    {
        "type": "function",
        "name": "get_smart_tasks",
        "description": "Get smart tasks filtered by owner, topic, or Eisenhower quadrant (1=Do first, 2=Schedule, 3=Delegate, 4=Defer). Returns tasks with descriptions, owners, follow-up dates, source context, and priority classification.",
        "parameters": {
            "type": "object",
            "properties": {
                "owner": {"type": "string", "description": "Filter by owner name."},
                "topic": {"type": "string", "description": "Filter by topic."},
                "quadrant": {"type": "integer", "description": "Eisenhower quadrant 1-4. 0 for all."},
                "include_done": {"type": "boolean", "description": "Include completed tasks. Default false."},
            },
        },
    },
    {
        "type": "function",
        "name": "update_smart_task",
        "description": "Update a smart task. Can change status, follow-up date, owner (reassign/delegate), quadrant (re-prioritize), description, or action steps.",
        "parameters": {
            "type": "object",
            "properties": {
                "task_id": {"type": "string", "description": "The task ID."},
                "status": {"type": "string", "enum": ["open", "done"], "description": "New status. Use 'done' to mark complete."},
                "follow_up_date": {"type": "string", "description": "New follow-up date YYYY-MM-DD."},
                "owner": {"type": "string", "description": "Reassign task to this person."},
                "quadrant": {"type": "integer", "description": "Move to Eisenhower quadrant 1-4."},
                "description": {"type": "string", "description": "Updated task description."},
                "steps": {"type": "string", "description": "Action steps, one per line."},
            },
            "required": ["task_id"],
        },
    },
    {
        "type": "function",
        "name": "delete_smart_task",
        "description": "Permanently delete a smart task. Confirm with user before deleting.",
        "parameters": {
            "type": "object",
            "properties": {
                "task_id": {"type": "string", "description": "The task ID to delete."},
            },
            "required": ["task_id"],
        },
    },
    {
        "type": "function",
        "name": "update_tracked_task",
        "description": "Update a tracked meeting task. Can change owner (reassign), status, topic, description, or follow-up date.",
        "parameters": {
            "type": "object",
            "properties": {
                "task_id": {"type": "string", "description": "The task ID."},
                "status": {"type": "string", "enum": ["open", "done", "followed_up"], "description": "New status."},
                "owner": {"type": "string", "description": "Reassign to this person."},
                "topic": {"type": "string", "description": "New topic."},
                "description": {"type": "string", "description": "Updated description."},
                "follow_up_date": {"type": "string", "description": "Follow-up date YYYY-MM-DD."},
            },
            "required": ["task_id"],
        },
    },
    {
        "type": "function",
        "name": "search_intel",
        "description": "Search the intelligence knowledge base — all scanned Notion page content, topics, people, and tasks. Use this to answer questions about what was discussed in meetings, who said what, project status, etc.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search keyword or phrase."},
                "max_results": {"type": "integer", "description": "Max results. Default 10."},
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
    "review_notion_pages": ("integrations.notion_review", "review_recent_pages"),
    "review_notion_page": ("integrations.notion_review", "review_page"),
    "add_known_names": ("integrations.notion_review", "add_known_names"),
    "daily_briefing": ("integrations.briefing_daily", "compile_daily_briefing"),
    "scan_notion": ("integrations.intel", "scan_notion"),
    "get_intel": ("integrations.intel", "get_intel"),
    "get_smart_tasks": ("integrations.intel", "get_smart_tasks"),
    "update_smart_task": ("integrations.intel", "update_smart_task"),
    "delete_smart_task": ("integrations.intel", "delete_smart_task"),
    "search_intel": ("integrations.intel", "search_intel"),
    "update_tracked_task": ("integrations.notion_tasks", "update_task"),
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


class TaskStatusUpdate(BaseModel):
    status: str


@app.get("/")
async def index():
    """Serve the call UI."""
    return FileResponse(_STATIC_DIR / "call.html")


@app.get("/tasks")
async def tasks_page():
    """Serve the task tracker dashboard."""
    return FileResponse(_STATIC_DIR / "tasks.html")


@app.get("/briefing")
async def briefing_page():
    """Serve the daily briefing dashboard."""
    return FileResponse(_STATIC_DIR / "briefing.html")


@app.get("/executive")
async def executive_page():
    """Serve the executive summary dashboard."""
    return FileResponse(_STATIC_DIR / "executive.html")


@app.get("/graph")
async def graph_page():
    """Serve the graph visualization page."""
    return FileResponse(_STATIC_DIR / "graph.html")


@app.get("/api/intel/graph")
async def get_intel_graph(max_nodes: int = 500, min_edge_weight: int = 1):
    """Build graph nodes and edges for relationship visualization."""
    from integrations.intel import build_graph_data

    try:
        data = build_graph_data(max_nodes=max_nodes, min_edge_weight=min_edge_weight)
        return JSONResponse(data)
    except Exception as exc:
        logger.exception("Failed to build graph data")
        return JSONResponse({"error": str(exc)}, status_code=500)


@app.get("/api/tasks")
async def get_tasks(
    owner: str = "",
    topic: str = "",
    status: str = "",
    include_completed: bool = False,
):
    """Get tracked meeting tasks with optional filters."""
    from integrations.notion_tasks import get_tracked_tasks

    result = get_tracked_tasks(
        owner=owner,
        topic=topic,
        status=status,
        include_completed=include_completed,
    )
    return JSONResponse(result)


@app.get("/api/briefing")
async def get_briefing():
    """Generate and return the daily briefing."""
    from integrations.briefing_daily import compile_daily_briefing

    try:
        briefing = await compile_daily_briefing()
        return JSONResponse(briefing)
    except Exception as exc:
        logger.exception("Failed to compile briefing")
        return JSONResponse({"error": str(exc)}, status_code=500)


class SmartTaskUpdate(BaseModel):
    status: str = ""
    follow_up_date: str = ""
    quadrant: int = 0
    description: str = ""
    owner: str = ""
    steps: str = ""


@app.get("/api/intel")
async def get_intel():
    """Get the intelligence profile and executive summary."""
    from integrations.intel import get_intel as _get_intel

    try:
        data = _get_intel()
        return JSONResponse(data)
    except Exception as exc:
        logger.exception("Failed to get intel")
        return JSONResponse({"error": str(exc)}, status_code=500)


@app.post("/api/intel/scan")
async def scan_intel(max_pages: int = 50, full_scan: bool = False):
    """Trigger a Notion intelligence scan (incremental by default)."""
    from integrations.intel import scan_notion

    try:
        result = await scan_notion(max_pages=max_pages, full_scan=full_scan)
        return JSONResponse(result)
    except RuntimeError as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)
    except Exception as exc:
        logger.exception("Intel scan failed")
        return JSONResponse({"error": str(exc)}, status_code=500)


# Active scan cancellation events keyed by a simple counter
_active_scan_cancel: dict[str, asyncio.Event] = {}


@app.post("/api/intel/scan/stream")
async def scan_intel_stream(max_pages: int = 50, full_scan: bool = False):
    """SSE endpoint that streams scan progress events."""
    import json as _json
    from integrations.intel import scan_notion

    scan_id = str(id(asyncio.current_task()))
    cancel_event = asyncio.Event()
    _active_scan_cancel[scan_id] = cancel_event
    progress_queue: asyncio.Queue = asyncio.Queue()

    def on_progress(msg: dict) -> None:
        msg["scan_id"] = scan_id
        progress_queue.put_nowait(msg)

    async def generate():
        try:
            # Start scan as background task
            scan_task = asyncio.create_task(
                scan_notion(
                    max_pages=max_pages,
                    full_scan=full_scan,
                    on_progress=on_progress,
                    cancel_event=cancel_event,
                )
            )

            # Stream progress events
            while not scan_task.done():
                try:
                    msg = await asyncio.wait_for(progress_queue.get(), timeout=0.5)
                    yield f"data: {_json.dumps(msg)}\n\n"
                except asyncio.TimeoutError:
                    # Send keepalive
                    yield ": keepalive\n\n"

            # Drain remaining progress messages
            while not progress_queue.empty():
                msg = progress_queue.get_nowait()
                yield f"data: {_json.dumps(msg)}\n\n"

            # Get result or error
            result = scan_task.result()
            result["status"] = "complete"
            result["scan_id"] = scan_id
            yield f"data: {_json.dumps(result)}\n\n"

        except Exception as exc:
            yield f"data: {_json.dumps({'status': 'error', 'message': str(exc), 'scan_id': scan_id})}\n\n"
        finally:
            _active_scan_cancel.pop(scan_id, None)

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Scan-Id": scan_id,
        },
    )


@app.post("/api/intel/scan/cancel")
async def cancel_scan(scan_id: str = ""):
    """Cancel an active scan."""
    if scan_id and scan_id in _active_scan_cancel:
        _active_scan_cancel[scan_id].set()
        return JSONResponse({"message": "Scan cancellation requested."})
    # Cancel all active scans if no specific ID
    if not scan_id and _active_scan_cancel:
        for ev in _active_scan_cancel.values():
            ev.set()
        return JSONResponse({"message": f"Cancelled {len(_active_scan_cancel)} active scan(s)."})
    return JSONResponse({"message": "No active scan found."}, status_code=404)


@app.patch("/api/intel/tasks/{task_id}")
async def update_smart_task(task_id: str, body: SmartTaskUpdate):
    """Update a smart task."""
    from integrations.intel import update_smart_task as _update

    result = _update(
        task_id=task_id,
        status=body.status,
        follow_up_date=body.follow_up_date,
        quadrant=body.quadrant,
        description=body.description,
        owner=body.owner,
        steps=body.steps,
    )
    if "error" in result:
        return JSONResponse(result, status_code=404)
    return JSONResponse(result)


@app.delete("/api/intel/tasks/{task_id}")
async def delete_smart_task(task_id: str):
    """Delete a smart task."""
    from integrations.intel import delete_smart_task as _delete

    result = _delete(task_id=task_id)
    if "error" in result:
        return JSONResponse(result, status_code=404)
    return JSONResponse(result)


@app.post("/api/intel/tasks/rewrite-titles")
async def rewrite_task_titles():
    """Use AI to rewrite all open task titles into clear, actionable format."""
    from integrations.intel import rewrite_task_titles as _rewrite

    result = await _rewrite()
    if "error" in result:
        return JSONResponse(result, status_code=500)
    return JSONResponse(result)


@app.patch("/api/tasks/{task_id}/status")
async def update_task_status(task_id: str, body: TaskStatusUpdate):
    """Update a tracked task's status."""
    from integrations.notion_tasks import update_task_status as _update

    if body.status not in ("open", "done", "followed_up"):
        return JSONResponse(
            {"error": f"Invalid status: {body.status}"},
            status_code=400,
        )

    result = _update(task_id=task_id, status=body.status)
    if "error" in result:
        return JSONResponse(result, status_code=404)
    return JSONResponse(result)


class TrackedTaskUpdate(BaseModel):
    owner: str = None
    topic: str = None
    description: str = None
    status: str = None
    follow_up_date: str = None


@app.patch("/api/tasks/{task_id}")
async def update_tracked_task(task_id: str, body: TrackedTaskUpdate):
    """Update a tracked task's fields."""
    from integrations.notion_tasks import update_task as _update

    fields = {k: v for k, v in body.dict().items() if v is not None}
    if not fields:
        return JSONResponse({"error": "No fields to update"}, status_code=400)
    result = _update(task_id=task_id, **fields)
    if "error" in result:
        return JSONResponse(result, status_code=404)
    return JSONResponse(result)


@app.get("/api/tasks/owners")
async def get_task_owners():
    """Get task owners sorted by frequency."""
    from integrations.notion_tasks import get_owner_frequencies

    return JSONResponse(get_owner_frequencies())


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

        import inspect
        if inspect.iscoroutinefunction(func):
            result = await func(**args)
        else:
            result = func(**args)
        return JSONResponse({"result": result})

    except RuntimeError as exc:
        return JSONResponse({"error": str(exc)})
    except Exception as exc:
        logger.exception("Tool execution failed: %s", req.name)
        return JSONResponse({"error": f"Tool failed: {exc}"})


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
