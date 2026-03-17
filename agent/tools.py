"""Tool definitions and executor for the TARS agent.

Tools are registered here as Claude API tool schemas. The execute_tool
function dispatches tool calls to the appropriate integration module.
"""
from __future__ import annotations

from typing import Any

# Tool definitions in Claude API format.
# Each entry is a dict with "name", "description", and "input_schema".
# Add tools here as integrations are built.
TOOL_DEFINITIONS: list[dict[str, Any]] = []

# Maps tool names to async handler functions.
# Handlers receive the tool input dict and return a result dict.
_TOOL_HANDLERS: dict[str, Any] = {}


def register_tool(name: str, description: str, input_schema: dict, handler) -> None:
    """Register a tool for the agent to use.

    Args:
        name: Tool name (e.g. "get_calendar_events").
        description: What the tool does (shown to Claude).
        input_schema: JSON Schema for the tool's input parameters.
        handler: Async function that executes the tool. Receives input dict, returns result dict.
    """
    TOOL_DEFINITIONS.append({
        "name": name,
        "description": description,
        "input_schema": input_schema,
    })
    _TOOL_HANDLERS[name] = handler


async def execute_tool(name: str, tool_input: dict, *, chat_id: int = 0) -> dict:
    """Execute a registered tool by name.

    Args:
        name: Tool name.
        tool_input: Tool input parameters from Claude.
        chat_id: Telegram chat ID (passed to tools that need it, like reminders).

    Returns:
        Result dict to send back to Claude.
    """
    handler = _TOOL_HANDLERS.get(name)
    if handler is None:
        return {"error": f"Unknown tool: {name}"}
    try:
        # Inject chat_id for tools that need it
        if name in _CHAT_ID_TOOLS:
            tool_input = {**tool_input, "_chat_id": chat_id}
        return await handler(tool_input)
    except RuntimeError as exc:
        return {"error": str(exc)}
    except Exception as exc:
        return {"error": f"Tool '{name}' failed: {exc}"}


# Tools that need chat_id injected
_CHAT_ID_TOOLS: set[str] = set()


# ---------------------------------------------------------------------------
# Register calendar tools
# ---------------------------------------------------------------------------

def _register_calendar_tools() -> None:
    """Register Microsoft 365 calendar tools."""
    from integrations.calendar import create_event, get_events, search_events
    from integrations.ms_auth import is_configured

    if not is_configured():
        return

    async def _handle_get_events(tool_input: dict) -> dict:
        return await get_events(
            days=tool_input.get("days", 7),
            max_results=tool_input.get("max_results", 20),
        )

    register_tool(
        name="get_calendar_events",
        description=(
            "Get the user's upcoming Microsoft 365 calendar events. "
            "Returns a list of events with subject, start/end times, location, and organizer."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "days": {
                    "type": "integer",
                    "description": "Number of days ahead to look. Default 7.",
                },
                "max_results": {
                    "type": "integer",
                    "description": "Maximum number of events to return. Default 20.",
                },
            },
        },
        handler=_handle_get_events,
    )

    async def _handle_create_event(tool_input: dict) -> dict:
        return await create_event(
            subject=tool_input["subject"],
            start_time=tool_input["start_time"],
            end_time=tool_input["end_time"],
            timezone_str=tool_input.get("timezone", "UTC"),
            location=tool_input.get("location", ""),
            body=tool_input.get("body", ""),
            attendees=tool_input.get("attendees"),
        )

    register_tool(
        name="create_calendar_event",
        description=(
            "Create a new event on the user's Microsoft 365 calendar. "
            "Always confirm the details with the user before calling this tool."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "subject": {
                    "type": "string",
                    "description": "Event title.",
                },
                "start_time": {
                    "type": "string",
                    "description": "Start time in ISO 8601 format (e.g. '2025-01-15T10:00:00').",
                },
                "end_time": {
                    "type": "string",
                    "description": "End time in ISO 8601 format.",
                },
                "timezone": {
                    "type": "string",
                    "description": "IANA timezone (e.g. 'Europe/Stockholm'). Default 'UTC'.",
                },
                "location": {
                    "type": "string",
                    "description": "Optional event location.",
                },
                "body": {
                    "type": "string",
                    "description": "Optional event description.",
                },
                "attendees": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Optional list of attendee email addresses.",
                },
            },
            "required": ["subject", "start_time", "end_time"],
        },
        handler=_handle_create_event,
    )

    async def _handle_search_events(tool_input: dict) -> dict:
        return await search_events(
            query=tool_input["query"],
            days=tool_input.get("days", 30),
            max_results=tool_input.get("max_results", 10),
        )

    register_tool(
        name="search_calendar",
        description=(
            "Search calendar events by keyword in the subject. "
            "Searches upcoming events within the specified number of days."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search keyword to match in event subjects.",
                },
                "days": {
                    "type": "integer",
                    "description": "Number of days ahead to search. Default 30.",
                },
                "max_results": {
                    "type": "integer",
                    "description": "Max events to return. Default 10.",
                },
            },
            "required": ["query"],
        },
        handler=_handle_search_events,
    )


# ---------------------------------------------------------------------------
# Register task tools
# ---------------------------------------------------------------------------

def _register_task_tools() -> None:
    """Register Microsoft To Do task tools."""
    from integrations.ms_auth import is_configured
    from integrations.tasks import complete_task, create_task, get_task_lists, get_tasks

    if not is_configured():
        return

    async def _handle_get_task_lists(tool_input: dict) -> dict:
        return await get_task_lists()

    register_tool(
        name="get_task_lists",
        description=(
            "Get all of the user's Microsoft To Do task lists. "
            "Returns list names and IDs. Use this to find the right list "
            "before getting or creating tasks."
        ),
        input_schema={"type": "object", "properties": {}},
        handler=_handle_get_task_lists,
    )

    async def _handle_get_tasks(tool_input: dict) -> dict:
        return await get_tasks(
            list_id=tool_input.get("list_id"),
            include_completed=tool_input.get("include_completed", False),
            max_results=tool_input.get("max_results", 25),
        )

    register_tool(
        name="get_tasks",
        description=(
            "Get tasks from a Microsoft To Do list. "
            "If no list_id is given, uses the default Tasks list. "
            "By default only shows incomplete tasks."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "list_id": {
                    "type": "string",
                    "description": "Task list ID. Omit to use the default list.",
                },
                "include_completed": {
                    "type": "boolean",
                    "description": "Include completed tasks. Default false.",
                },
                "max_results": {
                    "type": "integer",
                    "description": "Max tasks to return. Default 25.",
                },
            },
        },
        handler=_handle_get_tasks,
    )

    async def _handle_create_task(tool_input: dict) -> dict:
        return await create_task(
            title=tool_input["title"],
            list_id=tool_input.get("list_id"),
            due_date=tool_input.get("due_date", ""),
            importance=tool_input.get("importance", "normal"),
            body=tool_input.get("body", ""),
        )

    register_tool(
        name="create_task",
        description=(
            "Create a new task in Microsoft To Do. "
            "Always confirm the task details with the user before calling this tool."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "title": {
                    "type": "string",
                    "description": "Task title.",
                },
                "list_id": {
                    "type": "string",
                    "description": "Task list ID. Omit to use the default list.",
                },
                "due_date": {
                    "type": "string",
                    "description": "Due date in YYYY-MM-DD format.",
                },
                "importance": {
                    "type": "string",
                    "enum": ["low", "normal", "high"],
                    "description": "Task importance. Default 'normal'.",
                },
                "body": {
                    "type": "string",
                    "description": "Optional task description.",
                },
            },
            "required": ["title"],
        },
        handler=_handle_create_task,
    )

    async def _handle_complete_task(tool_input: dict) -> dict:
        return await complete_task(
            task_id=tool_input["task_id"],
            list_id=tool_input.get("list_id"),
        )

    register_tool(
        name="complete_task",
        description=(
            "Mark a task as completed in Microsoft To Do. "
            "Requires the task ID (get it from get_tasks first)."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "task_id": {
                    "type": "string",
                    "description": "The task ID to complete.",
                },
                "list_id": {
                    "type": "string",
                    "description": "Task list ID. Omit to use the default list.",
                },
            },
            "required": ["task_id"],
        },
        handler=_handle_complete_task,
    )


# ---------------------------------------------------------------------------
# Register mail tools
# ---------------------------------------------------------------------------

def _register_mail_tools() -> None:
    """Register Microsoft 365 mail tools."""
    from integrations.mail import get_messages, read_message, reply_to_message, search_messages, send_message
    from integrations.ms_auth import is_configured

    if not is_configured():
        return

    async def _handle_get_messages(tool_input: dict) -> dict:
        return await get_messages(
            folder=tool_input.get("folder", "inbox"),
            unread_only=tool_input.get("unread_only", False),
            max_results=tool_input.get("max_results", 15),
        )

    register_tool(
        name="get_emails",
        description=(
            "Get recent emails from the user's Microsoft 365 mailbox. "
            "Returns subject, sender, date, and a preview of each message."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "folder": {
                    "type": "string",
                    "description": "Mail folder: 'inbox', 'sentitems', 'drafts'. Default 'inbox'.",
                },
                "unread_only": {
                    "type": "boolean",
                    "description": "Only return unread messages. Default false.",
                },
                "max_results": {
                    "type": "integer",
                    "description": "Max messages to return. Default 15.",
                },
            },
        },
        handler=_handle_get_messages,
    )

    async def _handle_read_message(tool_input: dict) -> dict:
        return await read_message(message_id=tool_input["message_id"])

    register_tool(
        name="read_email",
        description=(
            "Read the full body of a specific email. "
            "Requires the message ID (get it from get_emails first)."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "message_id": {
                    "type": "string",
                    "description": "The email message ID.",
                },
            },
            "required": ["message_id"],
        },
        handler=_handle_read_message,
    )

    async def _handle_send_message(tool_input: dict) -> dict:
        return await send_message(
            to=tool_input["to"],
            subject=tool_input["subject"],
            body=tool_input["body"],
            cc=tool_input.get("cc"),
            importance=tool_input.get("importance", "normal"),
        )

    register_tool(
        name="send_email",
        description=(
            "Send an email from the user's Microsoft 365 account. "
            "ALWAYS confirm the recipient, subject, and body with the user before sending."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "to": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of recipient email addresses.",
                },
                "subject": {
                    "type": "string",
                    "description": "Email subject line.",
                },
                "body": {
                    "type": "string",
                    "description": "Email body (plain text).",
                },
                "cc": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Optional list of CC email addresses.",
                },
                "importance": {
                    "type": "string",
                    "enum": ["low", "normal", "high"],
                    "description": "Email importance. Default 'normal'.",
                },
            },
            "required": ["to", "subject", "body"],
        },
        handler=_handle_send_message,
    )

    async def _handle_reply_message(tool_input: dict) -> dict:
        return await reply_to_message(
            message_id=tool_input["message_id"],
            body=tool_input["body"],
            reply_all=tool_input.get("reply_all", False),
        )

    register_tool(
        name="reply_email",
        description=(
            "Reply to a specific email. Requires the message ID (get it from get_emails first). "
            "ALWAYS confirm the reply content with the user before sending."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "message_id": {
                    "type": "string",
                    "description": "The message ID to reply to.",
                },
                "body": {
                    "type": "string",
                    "description": "Reply body (plain text).",
                },
                "reply_all": {
                    "type": "boolean",
                    "description": "Reply to all recipients. Default false.",
                },
            },
            "required": ["message_id", "body"],
        },
        handler=_handle_reply_message,
    )

    async def _handle_search_messages(tool_input: dict) -> dict:
        return await search_messages(
            query=tool_input["query"],
            max_results=tool_input.get("max_results", 10),
        )

    register_tool(
        name="search_emails",
        description=(
            "Search emails by keyword. Searches subject, body, and sender. "
            "Returns matching messages sorted by most recent."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search keyword or phrase.",
                },
                "max_results": {
                    "type": "integer",
                    "description": "Max results to return. Default 10.",
                },
            },
            "required": ["query"],
        },
        handler=_handle_search_messages,
    )


# ---------------------------------------------------------------------------
# Register reminder tools
# ---------------------------------------------------------------------------

def _register_reminder_tools() -> None:
    """Register reminder tools (always available, no M365 needed)."""
    from integrations.reminders import create_reminder, delete_reminder, get_reminders

    async def _handle_create_reminder(tool_input: dict) -> dict:
        chat_id = tool_input.pop("_chat_id", 0)
        return create_reminder(
            chat_id=chat_id,
            message=tool_input["message"],
            remind_at=tool_input["remind_at"],
        )

    register_tool(
        name="create_reminder",
        description=(
            "Set a reminder that will notify the user at a specific time via Telegram. "
            "Always confirm the time and message with the user before creating."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "message": {
                    "type": "string",
                    "description": "The reminder message to send.",
                },
                "remind_at": {
                    "type": "string",
                    "description": (
                        "When to send the reminder, in ISO 8601 format with timezone "
                        "(e.g. '2025-01-15T10:00:00+01:00'). "
                        "Ask the user what timezone they're in if unclear."
                    ),
                },
            },
            "required": ["message", "remind_at"],
        },
        handler=_handle_create_reminder,
    )
    _CHAT_ID_TOOLS.add("create_reminder")

    async def _handle_get_reminders(tool_input: dict) -> dict:
        chat_id = tool_input.pop("_chat_id", 0)
        return get_reminders(chat_id)

    register_tool(
        name="get_reminders",
        description="Get all pending reminders for the user.",
        input_schema={"type": "object", "properties": {}},
        handler=_handle_get_reminders,
    )
    _CHAT_ID_TOOLS.add("get_reminders")

    async def _handle_delete_reminder(tool_input: dict) -> dict:
        chat_id = tool_input.pop("_chat_id", 0)
        return delete_reminder(
            reminder_id=tool_input["reminder_id"],
            chat_id=chat_id,
        )

    register_tool(
        name="delete_reminder",
        description=(
            "Delete a pending reminder. Requires the reminder ID "
            "(get it from get_reminders first)."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "reminder_id": {
                    "type": "string",
                    "description": "The reminder ID to delete.",
                },
            },
            "required": ["reminder_id"],
        },
        handler=_handle_delete_reminder,
    )
    _CHAT_ID_TOOLS.add("delete_reminder")


# Auto-register tools on import
_register_calendar_tools()
_register_task_tools()
_register_mail_tools()
_register_reminder_tools()
