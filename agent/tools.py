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
    # Prevent duplicate registrations
    if name in _TOOL_HANDLERS:
        return
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


# ---------------------------------------------------------------------------
# Register Notion tools
# ---------------------------------------------------------------------------

def _register_notion_tools() -> None:
    """Register Notion integration tools."""
    from config import NOTION_API_KEY

    if not NOTION_API_KEY:
        return

    from integrations.notion import (
        get_page_content,
        list_databases,
        query_database,
        search_pages,
    )
    from integrations.notion_tasks import (
        extract_meeting_tasks,
        get_tracked_tasks,
        search_meeting_notes,
        track_meeting_tasks,
        update_task_status,
    )

    async def _handle_search_notion(tool_input: dict) -> dict:
        return await search_pages(
            query=tool_input["query"],
            max_results=tool_input.get("max_results", 10),
        )

    register_tool(
        name="search_notion",
        description=(
            "Search Notion pages by keyword. "
            "Returns page titles, IDs, and URLs."
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
                    "description": "Max pages to return. Default 10.",
                },
            },
            "required": ["query"],
        },
        handler=_handle_search_notion,
    )

    async def _handle_read_notion_page(tool_input: dict) -> dict:
        return await get_page_content(page_id=tool_input["page_id"])

    register_tool(
        name="read_notion_page",
        description=(
            "Read the full content of a Notion page. "
            "Requires the page ID (get it from search_notion first)."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "page_id": {
                    "type": "string",
                    "description": "The Notion page ID.",
                },
            },
            "required": ["page_id"],
        },
        handler=_handle_read_notion_page,
    )

    async def _handle_list_notion_databases(tool_input: dict) -> dict:
        return await list_databases(
            max_results=tool_input.get("max_results", 20),
        )

    register_tool(
        name="list_notion_databases",
        description=(
            "List all Notion databases shared with the integration. "
            "Returns database names and IDs."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "max_results": {
                    "type": "integer",
                    "description": "Max databases to return. Default 20.",
                },
            },
        },
        handler=_handle_list_notion_databases,
    )

    async def _handle_query_notion_database(tool_input: dict) -> dict:
        return await query_database(
            database_id=tool_input["database_id"],
            filter_obj=tool_input.get("filter"),
            max_results=tool_input.get("max_results", 50),
        )

    register_tool(
        name="query_notion_database",
        description=(
            "Query a Notion database to get entries/rows. "
            "Requires the database ID (get it from list_notion_databases). "
            "Optionally provide a Notion filter object."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "database_id": {
                    "type": "string",
                    "description": "The Notion database ID.",
                },
                "filter": {
                    "type": "object",
                    "description": "Optional Notion filter object.",
                },
                "max_results": {
                    "type": "integer",
                    "description": "Max entries to return. Default 50.",
                },
            },
            "required": ["database_id"],
        },
        handler=_handle_query_notion_database,
    )

    async def _handle_extract_meeting_tasks(tool_input: dict) -> dict:
        return await extract_meeting_tasks(page_id=tool_input["page_id"])

    register_tool(
        name="extract_meeting_tasks",
        description=(
            "Extract tasks from a Notion meeting notes page. "
            "Finds action items, TODOs, and checkbox tasks, "
            "identifies owners via @mentions, and groups by owner and topic."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "page_id": {
                    "type": "string",
                    "description": "The Notion page ID containing meeting notes.",
                },
            },
            "required": ["page_id"],
        },
        handler=_handle_extract_meeting_tasks,
    )

    async def _handle_track_meeting_tasks(tool_input: dict) -> dict:
        return await track_meeting_tasks(page_id=tool_input["page_id"])

    register_tool(
        name="track_meeting_tasks",
        description=(
            "Extract tasks from a meeting page and save them for ongoing tracking. "
            "Tasks are persisted and can be queried later with get_tracked_tasks. "
            "Use this when the user wants to track and follow up on meeting action items."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "page_id": {
                    "type": "string",
                    "description": "The Notion page ID containing meeting notes.",
                },
            },
            "required": ["page_id"],
        },
        handler=_handle_track_meeting_tasks,
    )

    async def _handle_get_tracked_tasks(tool_input: dict) -> dict:
        return get_tracked_tasks(
            owner=tool_input.get("owner", ""),
            topic=tool_input.get("topic", ""),
            status=tool_input.get("status", ""),
            include_completed=tool_input.get("include_completed", False),
        )

    register_tool(
        name="get_tracked_tasks",
        description=(
            "Get tracked meeting tasks with optional filters by owner, topic, or status. "
            "Tasks are grouped by owner and by topic. "
            "Use this to check on action items from past meetings."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "owner": {
                    "type": "string",
                    "description": "Filter by task owner name (partial match).",
                },
                "topic": {
                    "type": "string",
                    "description": "Filter by topic/heading (partial match).",
                },
                "status": {
                    "type": "string",
                    "enum": ["open", "done", "followed_up"],
                    "description": "Filter by status.",
                },
                "include_completed": {
                    "type": "boolean",
                    "description": "Include completed tasks. Default false.",
                },
            },
        },
        handler=_handle_get_tracked_tasks,
    )

    async def _handle_update_task_status(tool_input: dict) -> dict:
        return update_task_status(
            task_id=tool_input["task_id"],
            status=tool_input["status"],
        )

    register_tool(
        name="update_tracked_task",
        description=(
            "Update the status of a tracked meeting task. "
            "Use 'done' to mark complete, 'followed_up' after sending a follow-up, "
            "or 'open' to reopen."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "task_id": {
                    "type": "string",
                    "description": "The tracked task ID.",
                },
                "status": {
                    "type": "string",
                    "enum": ["open", "done", "followed_up"],
                    "description": "New status for the task.",
                },
            },
            "required": ["task_id", "status"],
        },
        handler=_handle_update_task_status,
    )

    async def _handle_search_meeting_notes(tool_input: dict) -> dict:
        return await search_meeting_notes(
            query=tool_input["query"],
            max_results=tool_input.get("max_results", 5),
        )

    register_tool(
        name="search_meeting_notes",
        description=(
            "Search Notion for meeting notes by keyword and return content previews. "
            "Good for finding specific meetings or discussions."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search keyword (e.g. 'weekly standup', 'Q1 planning').",
                },
                "max_results": {
                    "type": "integer",
                    "description": "Max pages to return. Default 5.",
                },
            },
            "required": ["query"],
        },
        handler=_handle_search_meeting_notes,
    )


# ---------------------------------------------------------------------------
# Register Notion review tools
# ---------------------------------------------------------------------------

def _register_notion_review_tools() -> None:
    """Register Notion page review and consistency tools."""
    from config import NOTION_API_KEY

    if not NOTION_API_KEY:
        return

    from integrations.notion_review import (
        add_known_names,
        get_known_names,
        get_review_state,
        remove_known_names,
        review_page,
        review_recent_pages,
    )

    async def _handle_review_recent_pages(tool_input: dict) -> dict:
        return await review_recent_pages(
            auto_fix=tool_input.get("auto_fix", False),
        )

    register_tool(
        name="review_notion_pages",
        description=(
            "Review all Notion pages edited since the last review. "
            "Checks for title consistency (dates in meeting titles, names in 1:1 titles), "
            "name spelling errors against known names, and structural issues. "
            "Set auto_fix=true to automatically correct spelling in content."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "auto_fix": {
                    "type": "boolean",
                    "description": (
                        "Automatically fix detected spelling issues. Default false. "
                        "When false, only reports issues without changing anything."
                    ),
                },
            },
        },
        handler=_handle_review_recent_pages,
    )

    async def _handle_review_page(tool_input: dict) -> dict:
        return await review_page(
            page_id=tool_input["page_id"],
            auto_fix=tool_input.get("auto_fix", False),
        )

    register_tool(
        name="review_notion_page",
        description=(
            "Review a specific Notion page for consistency and spelling issues. "
            "Checks title format, name spelling against known names, and structure. "
            "Set auto_fix=true to automatically correct issues."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "page_id": {
                    "type": "string",
                    "description": "The Notion page ID to review.",
                },
                "auto_fix": {
                    "type": "boolean",
                    "description": "Auto-fix detected issues. Default false.",
                },
            },
            "required": ["page_id"],
        },
        handler=_handle_review_page,
    )

    async def _handle_add_known_names(tool_input: dict) -> dict:
        return add_known_names(names=tool_input["names"])

    register_tool(
        name="add_known_names",
        description=(
            "Add names to the known names list for spell-checking. "
            "These are the canonical spellings of people's names that TARS "
            "will use to detect and fix misspellings in Notion pages. "
            "E.g. add 'Jonas', 'Alice', 'Björk' so that 'Jon', 'Alise', 'Bjork' get flagged."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "names": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of canonical name spellings to add.",
                },
            },
            "required": ["names"],
        },
        handler=_handle_add_known_names,
    )

    async def _handle_remove_known_names(tool_input: dict) -> dict:
        return remove_known_names(names=tool_input["names"])

    register_tool(
        name="remove_known_names",
        description="Remove names from the known names spell-check list.",
        input_schema={
            "type": "object",
            "properties": {
                "names": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Names to remove.",
                },
            },
            "required": ["names"],
        },
        handler=_handle_remove_known_names,
    )

    async def _handle_get_known_names(tool_input: dict) -> dict:
        return get_known_names()

    register_tool(
        name="get_known_names",
        description="Get the current list of known names used for spell-checking Notion pages.",
        input_schema={"type": "object", "properties": {}},
        handler=_handle_get_known_names,
    )

    async def _handle_get_review_state(tool_input: dict) -> dict:
        return get_review_state()

    register_tool(
        name="get_notion_review_state",
        description=(
            "Get the current Notion review state — when pages were last reviewed, "
            "how many known names are configured, etc."
        ),
        input_schema={"type": "object", "properties": {}},
        handler=_handle_get_review_state,
    )


# ---------------------------------------------------------------------------
# Register daily briefing tool
# ---------------------------------------------------------------------------

def _register_briefing_tools() -> None:
    """Register the end-of-day briefing tool (always available)."""
    from integrations.briefing_daily import compile_daily_briefing, format_briefing_text

    async def _handle_daily_briefing(tool_input: dict) -> dict:
        briefing = await compile_daily_briefing()
        briefing["formatted"] = format_briefing_text(briefing)
        return briefing

    register_tool(
        name="daily_briefing",
        description=(
            "Compile a comprehensive end-of-day briefing. Summarizes the day's meetings, "
            "Notion activity, tracked tasks (including stale items), email, and generates "
            "proactive recommendations: follow-ups, status checks, proposed next steps, "
            "and items that need attention. Use this when the user asks for a daily summary, "
            "end-of-day review, or wants to know what needs attention."
        ),
        input_schema={"type": "object", "properties": {}},
        handler=_handle_daily_briefing,
    )


# ---------------------------------------------------------------------------
# Register intelligence tools
# ---------------------------------------------------------------------------

def _register_intel_tools() -> None:
    """Register intelligence scanner and executive summary tools."""
    from config import NOTION_API_KEY

    if not NOTION_API_KEY:
        return

    from integrations.intel import get_intel, get_smart_tasks, scan_notion, update_smart_task

    async def _handle_scan_notion(tool_input: dict) -> dict:
        return await scan_notion(
            max_pages=tool_input.get("max_pages", 50),
        )

    register_tool(
        name="scan_notion",
        description=(
            "Scan all accessible Notion pages to build intelligence about topics, "
            "people, delegations, and tasks. Creates a smart task list with "
            "Eisenhower priority matrix and estimated follow-up dates. "
            "Use this to build or refresh the executive summary."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "max_pages": {
                    "type": "integer",
                    "description": "Max pages to scan. Default 50.",
                },
            },
        },
        handler=_handle_scan_notion,
    )

    async def _handle_get_intel(tool_input: dict) -> dict:
        return get_intel()

    register_tool(
        name="get_intel",
        description=(
            "Get the full intelligence profile: topics, people, smart tasks, "
            "and executive summary with Eisenhower matrix. "
            "Run scan_notion first if data is stale."
        ),
        input_schema={"type": "object", "properties": {}},
        handler=_handle_get_intel,
    )

    async def _handle_get_smart_tasks(tool_input: dict) -> dict:
        return get_smart_tasks(
            owner=tool_input.get("owner", ""),
            topic=tool_input.get("topic", ""),
            quadrant=tool_input.get("quadrant", 0),
            include_done=tool_input.get("include_done", False),
        )

    register_tool(
        name="get_smart_tasks",
        description=(
            "Get smart tasks with optional filters by owner, topic, or "
            "Eisenhower quadrant (1=Do first, 2=Schedule, 3=Delegate, 4=Defer). "
            "Tasks include priority classification and follow-up dates."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "owner": {
                    "type": "string",
                    "description": "Filter by task owner name.",
                },
                "topic": {
                    "type": "string",
                    "description": "Filter by topic category.",
                },
                "quadrant": {
                    "type": "integer",
                    "description": "Filter by Eisenhower quadrant (1-4). 0 for all.",
                },
                "include_done": {
                    "type": "boolean",
                    "description": "Include completed tasks. Default false.",
                },
            },
        },
        handler=_handle_get_smart_tasks,
    )

    async def _handle_update_smart_task(tool_input: dict) -> dict:
        return update_smart_task(
            task_id=tool_input["task_id"],
            status=tool_input.get("status", ""),
            follow_up_date=tool_input.get("follow_up_date", ""),
        )

    register_tool(
        name="update_smart_task",
        description=(
            "Update a smart task's status or follow-up date. "
            "Use status 'done' to mark complete, 'open' to reopen."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "task_id": {
                    "type": "string",
                    "description": "The smart task ID.",
                },
                "status": {
                    "type": "string",
                    "enum": ["open", "done"],
                    "description": "New status.",
                },
                "follow_up_date": {
                    "type": "string",
                    "description": "New follow-up date (YYYY-MM-DD).",
                },
            },
            "required": ["task_id"],
        },
        handler=_handle_update_smart_task,
    )


# ---------------------------------------------------------------------------
# Register epic & user story tools
# ---------------------------------------------------------------------------

def _register_epic_tools() -> None:
    """Register Agile epics, user stories, and team portfolio tools."""
    from integrations.epics import (
        create_epic,
        create_story,
        delete_epic,
        delete_story,
        get_epics,
        get_stories,
        link_task_to_story,
        update_epic,
        update_story,
    )
    from integrations.team_portfolio import get_member_portfolio, get_team_portfolio

    async def _handle_create_epic(tool_input: dict) -> dict:
        return create_epic(
            title=tool_input["title"],
            description=tool_input.get("description", ""),
            owner=tool_input.get("owner", ""),
            initiative_id=tool_input.get("initiative_id", ""),
            quarter=tool_input.get("quarter", ""),
            priority=tool_input.get("priority", "high"),
            acceptance_criteria=tool_input.get("acceptance_criteria"),
        )

    register_tool(
        name="create_epic",
        description=(
            "Create an epic — a large body of work that delivers significant value. "
            "Epics sit between strategic initiatives and individual tasks. "
            "Use when defining a major deliverable, feature, or workstream. "
            "Optionally link to a parent initiative."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "title": {
                    "type": "string",
                    "description": "Epic name (e.g. 'User onboarding revamp').",
                },
                "description": {
                    "type": "string",
                    "description": "What this epic delivers and why it matters.",
                },
                "owner": {
                    "type": "string",
                    "description": "Who is accountable for delivery.",
                },
                "initiative_id": {
                    "type": "string",
                    "description": "Parent strategic initiative ID (optional).",
                },
                "quarter": {
                    "type": "string",
                    "description": "Target quarter (e.g. 'Q2 2026').",
                },
                "priority": {
                    "type": "string",
                    "enum": ["high", "medium", "low"],
                    "description": "Default 'high'.",
                },
                "acceptance_criteria": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Definition of done for the whole epic.",
                },
            },
            "required": ["title"],
        },
        handler=_handle_create_epic,
    )

    async def _handle_get_epics(tool_input: dict) -> dict:
        return get_epics(
            status=tool_input.get("status", ""),
            owner=tool_input.get("owner", ""),
            initiative_id=tool_input.get("initiative_id", ""),
            quarter=tool_input.get("quarter", ""),
            priority=tool_input.get("priority", ""),
        )

    register_tool(
        name="get_epics",
        description=(
            "Get epics with optional filters. Shows story progress for each epic. "
            "Use when user asks about deliverables, epics, or 'what are we working on'."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "status": {
                    "type": "string",
                    "enum": ["backlog", "in_progress", "done", "cancelled"],
                    "description": "Filter by status.",
                },
                "owner": {
                    "type": "string",
                    "description": "Filter by owner.",
                },
                "initiative_id": {
                    "type": "string",
                    "description": "Filter by parent initiative.",
                },
                "quarter": {
                    "type": "string",
                    "description": "Filter by quarter.",
                },
                "priority": {
                    "type": "string",
                    "enum": ["high", "medium", "low"],
                    "description": "Filter by priority.",
                },
            },
        },
        handler=_handle_get_epics,
    )

    async def _handle_update_epic(tool_input: dict) -> dict:
        return update_epic(
            epic_id=tool_input["epic_id"],
            title=tool_input.get("title", ""),
            description=tool_input.get("description", ""),
            owner=tool_input.get("owner", ""),
            status=tool_input.get("status", ""),
            priority=tool_input.get("priority", ""),
            quarter=tool_input.get("quarter", ""),
            initiative_id=tool_input.get("initiative_id", ""),
            acceptance_criteria=tool_input.get("acceptance_criteria"),
        )

    register_tool(
        name="update_epic",
        description=(
            "Update an epic — change status, owner, priority, or description. "
            "When the user references an epic by name, first look it up with "
            "get_epics to find the ID."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "epic_id": {
                    "type": "string",
                    "description": "The epic ID.",
                },
                "title": {"type": "string", "description": "New title."},
                "description": {"type": "string", "description": "New description."},
                "owner": {"type": "string", "description": "New owner."},
                "status": {
                    "type": "string",
                    "enum": ["backlog", "in_progress", "done", "cancelled"],
                    "description": "New status.",
                },
                "priority": {
                    "type": "string",
                    "enum": ["high", "medium", "low"],
                    "description": "New priority.",
                },
                "quarter": {"type": "string", "description": "New quarter."},
                "initiative_id": {"type": "string", "description": "Link to initiative."},
                "acceptance_criteria": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Updated acceptance criteria.",
                },
            },
            "required": ["epic_id"],
        },
        handler=_handle_update_epic,
    )

    async def _handle_create_story(tool_input: dict) -> dict:
        return create_story(
            epic_id=tool_input["epic_id"],
            title=tool_input["title"],
            description=tool_input.get("description", ""),
            owner=tool_input.get("owner", ""),
            size=tool_input.get("size", "M"),
            priority=tool_input.get("priority", "medium"),
            acceptance_criteria=tool_input.get("acceptance_criteria"),
        )

    register_tool(
        name="create_story",
        description=(
            "Create a user story within an epic. Best practice: write as "
            "'As a [role], I want [goal], so that [benefit]'. "
            "Use when breaking an epic into deliverable slices of user value."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "epic_id": {
                    "type": "string",
                    "description": "Parent epic ID.",
                },
                "title": {
                    "type": "string",
                    "description": "Story title (ideally in user story format).",
                },
                "description": {
                    "type": "string",
                    "description": "Additional context or technical notes.",
                },
                "owner": {
                    "type": "string",
                    "description": "Who will deliver this story.",
                },
                "size": {
                    "type": "string",
                    "enum": ["XS", "S", "M", "L", "XL"],
                    "description": "T-shirt size estimate. Default 'M'.",
                },
                "priority": {
                    "type": "string",
                    "enum": ["high", "medium", "low"],
                    "description": "Default 'medium'.",
                },
                "acceptance_criteria": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Conditions that must be met for completion.",
                },
            },
            "required": ["epic_id", "title"],
        },
        handler=_handle_create_story,
    )

    async def _handle_get_stories(tool_input: dict) -> dict:
        return get_stories(
            epic_id=tool_input.get("epic_id", ""),
            owner=tool_input.get("owner", ""),
            status=tool_input.get("status", ""),
            priority=tool_input.get("priority", ""),
            size=tool_input.get("size", ""),
        )

    register_tool(
        name="get_stories",
        description=(
            "Get user stories with optional filters. "
            "Use when checking what stories are in progress, blocked, or assigned."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "epic_id": {"type": "string", "description": "Filter by parent epic."},
                "owner": {"type": "string", "description": "Filter by owner."},
                "status": {
                    "type": "string",
                    "enum": ["backlog", "ready", "in_progress", "in_review", "done", "blocked"],
                    "description": "Filter by status.",
                },
                "priority": {
                    "type": "string",
                    "enum": ["high", "medium", "low"],
                    "description": "Filter by priority.",
                },
                "size": {
                    "type": "string",
                    "enum": ["XS", "S", "M", "L", "XL"],
                    "description": "Filter by size.",
                },
            },
        },
        handler=_handle_get_stories,
    )

    async def _handle_update_story(tool_input: dict) -> dict:
        return update_story(
            story_id=tool_input["story_id"],
            title=tool_input.get("title", ""),
            description=tool_input.get("description", ""),
            owner=tool_input.get("owner", ""),
            status=tool_input.get("status", ""),
            priority=tool_input.get("priority", ""),
            size=tool_input.get("size", ""),
            acceptance_criteria=tool_input.get("acceptance_criteria"),
        )

    register_tool(
        name="update_story",
        description=(
            "Update a user story — change status, owner, size, or priority. "
            "When the user references a story by name, first look it up with "
            "get_stories to find the ID."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "story_id": {"type": "string", "description": "The story ID."},
                "title": {"type": "string", "description": "New title."},
                "description": {"type": "string", "description": "New description."},
                "owner": {"type": "string", "description": "Reassign to this person."},
                "status": {
                    "type": "string",
                    "enum": ["backlog", "ready", "in_progress", "in_review", "done", "blocked"],
                    "description": "New status.",
                },
                "priority": {
                    "type": "string",
                    "enum": ["high", "medium", "low"],
                    "description": "New priority.",
                },
                "size": {
                    "type": "string",
                    "enum": ["XS", "S", "M", "L", "XL"],
                    "description": "New size estimate.",
                },
                "acceptance_criteria": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Updated acceptance criteria.",
                },
            },
            "required": ["story_id"],
        },
        handler=_handle_update_story,
    )

    async def _handle_link_task(tool_input: dict) -> dict:
        return link_task_to_story(
            story_id=tool_input["story_id"],
            task_id=tool_input["task_id"],
        )

    register_tool(
        name="link_task_to_story",
        description=(
            "Link an existing task (smart task or tracked task) to a user story. "
            "Use this to connect delegated tasks into the epic/story hierarchy."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "story_id": {"type": "string", "description": "The story ID."},
                "task_id": {"type": "string", "description": "The task ID to link."},
            },
            "required": ["story_id", "task_id"],
        },
        handler=_handle_link_task,
    )

    async def _handle_team_portfolio(tool_input: dict) -> dict:
        return get_team_portfolio(
            owner=tool_input.get("owner", ""),
            quarter=tool_input.get("quarter", ""),
            include_done=tool_input.get("include_done", False),
        )

    register_tool(
        name="get_team_portfolio",
        description=(
            "Get a full team portfolio view — every team member's epics, stories, "
            "tasks, and workload in one view. Shows who is overloaded, what's blocked, "
            "and which tasks are not linked to any epic. "
            "Use when the user asks 'show me the team overview', 'who is working on what', "
            "'what is everyone's workload', or wants to steer team priorities."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "owner": {
                    "type": "string",
                    "description": "Filter to a specific team member.",
                },
                "quarter": {
                    "type": "string",
                    "description": "Filter epics by quarter.",
                },
                "include_done": {
                    "type": "boolean",
                    "description": "Include completed items. Default false.",
                },
            },
        },
        handler=_handle_team_portfolio,
    )

    async def _handle_member_portfolio(tool_input: dict) -> dict:
        return get_member_portfolio(
            name=tool_input["name"],
            include_done=tool_input.get("include_done", False),
        )

    register_tool(
        name="get_member_portfolio",
        description=(
            "Get a detailed portfolio view for one team member — their epics, stories, "
            "tasks, workload, and items not yet linked to an epic. "
            "Use when asking about a specific person's deliverables or capacity."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "Team member name.",
                },
                "include_done": {
                    "type": "boolean",
                    "description": "Include completed items. Default false.",
                },
            },
            "required": ["name"],
        },
        handler=_handle_member_portfolio,
    )


def _register_memory_tools() -> None:
    from integrations.memory import (
        get_memory, set_preference, set_fact, add_note, delete_note, clear_memory
    )

    async def _handle_remember_preference(tool_input: dict) -> dict:
        return set_preference(tool_input["key"], tool_input["value"])

    register_tool(
        name="remember_preference",
        description=(
            "Store a user preference so TARS remembers it across sessions "
            "(e.g. response style, language, how brief to be, format). "
            "Call this whenever the user states how they want TARS to behave."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "key": {"type": "string", "description": "Short label for the preference (e.g. 'response_style')."},
                "value": {"type": "string", "description": "The preference value (e.g. 'concise bullet points')."},
            },
            "required": ["key", "value"],
        },
        handler=_handle_remember_preference,
    )

    async def _handle_remember_fact(tool_input: dict) -> dict:
        return set_fact(tool_input["key"], tool_input["value"])

    register_tool(
        name="remember_fact",
        description=(
            "Store a personal fact about the user to remember across sessions "
            "(e.g. name, role, timezone, company, key team members). "
            "Call this when the user shares personal or work context."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "key": {"type": "string", "description": "Short label (e.g. 'name', 'role', 'timezone')."},
                "value": {"type": "string", "description": "The fact value."},
            },
            "required": ["key", "value"],
        },
        handler=_handle_remember_fact,
    )

    async def _handle_add_memory_note(tool_input: dict) -> dict:
        return add_note(tool_input["text"])

    register_tool(
        name="add_memory_note",
        description=(
            "Store an important freeform note to remember across sessions "
            "(e.g. 'Board meeting is April 15', 'User prefers no meetings on Fridays', "
            "'Partner is called Anna'). Use for context that doesn't fit a structured field."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "The note to remember."},
            },
            "required": ["text"],
        },
        handler=_handle_add_memory_note,
    )

    async def _handle_get_memory(tool_input: dict) -> dict:
        return get_memory()

    register_tool(
        name="get_memory",
        description="Retrieve all stored preferences, facts, and notes about the user.",
        input_schema={"type": "object", "properties": {}},
        handler=_handle_get_memory,
    )

    async def _handle_delete_memory_note(tool_input: dict) -> dict:
        return delete_note(tool_input["index"])

    register_tool(
        name="delete_memory_note",
        description="Delete a stored memory note by its index (0-based). Use get_memory first to see notes.",
        input_schema={
            "type": "object",
            "properties": {
                "index": {"type": "integer", "description": "0-based index of the note to delete."},
            },
            "required": ["index"],
        },
        handler=_handle_delete_memory_note,
    )

    async def _handle_clear_memory(tool_input: dict) -> dict:
        return clear_memory()

    register_tool(
        name="clear_memory",
        description="Wipe all stored user memory (preferences, facts, and notes). Use only if user asks to forget everything.",
        input_schema={"type": "object", "properties": {}},
        handler=_handle_clear_memory,
    )


# Auto-register tools on import
_register_calendar_tools()
_register_task_tools()
_register_mail_tools()
_register_reminder_tools()
_register_notion_tools()
_register_notion_review_tools()
_register_briefing_tools()
_register_intel_tools()
_register_epic_tools()
_register_memory_tools()


# ── Knowledge repository tools ───────────────────────────────────────

def _register_knowledge_tools() -> None:
    from integrations.knowledge import search_knowledge, add_article

    async def _handle_search_knowledge(tool_input: dict) -> dict:
        results = search_knowledge(tool_input["query"], tool_input.get("company", ""))
        return {"results": results, "count": len(results)}

    register_tool(
        name="search_knowledge",
        description=(
            "Search the business knowledge repository for company news, "
            "quarterly/annual reports, strategy updates, and Capital Markets Day info. "
            "Use when the user asks about company financials, strategy, recent news, "
            "or business context."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query"},
                "company": {"type": "string", "description": "Company name filter (optional)"},
            },
            "required": ["query"],
        },
        handler=_handle_search_knowledge,
    )

    async def _handle_add_knowledge(tool_input: dict) -> dict:
        article = {
            "title": tool_input["title"],
            "date": tool_input["date"],
            "content": tool_input["content"],
            "summary": tool_input.get("summary", ""),
            "source_url": tool_input.get("source_url", ""),
        }
        return add_article(tool_input["company"], tool_input["category"], article)

    register_tool(
        name="add_knowledge_article",
        description=(
            "Add a new article, report, or news item to the knowledge repository. "
            "Use when the user shares company news or reports to remember. "
            "Categories: news, quarterly_reports, annual_reports, cmd, strategy."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "company": {"type": "string", "description": "Company name (e.g. SKF)"},
                "category": {
                    "type": "string",
                    "enum": ["news", "quarterly_reports", "annual_reports", "cmd", "strategy"],
                    "description": "Article category",
                },
                "title": {"type": "string", "description": "Article/report title"},
                "date": {"type": "string", "description": "Date (YYYY-MM-DD)"},
                "content": {"type": "string", "description": "Full content or key details"},
                "summary": {"type": "string", "description": "Brief one-line summary"},
                "source_url": {"type": "string", "description": "Source URL (optional)"},
            },
            "required": ["company", "category", "title", "date", "content"],
        },
        handler=_handle_add_knowledge,
    )


_register_knowledge_tools()


# ── Context repository tools ────────────────────────────────────────

def _register_context_tools() -> None:
    from integrations.context_repository import search_context, get_related_context, get_stats, generate_item_summary

    async def _handle_search_context(tool_input: dict) -> dict:
        results = search_context(tool_input["query"], tool_input.get("max_results", 10))
        return {"results": results, "count": len(results)}

    register_tool(
        name="search_context",
        description=(
            "Search the context repository for historical Notion page digests. "
            "Contains rich synthesized summaries of past discussions, decisions, "
            "meeting notes, and project context. Use when the user asks about "
            "past discussions, decisions, or background on a topic."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query (keywords)"},
                "max_results": {"type": "integer", "description": "Max results (default 10)"},
            },
            "required": ["query"],
        },
        handler=_handle_search_context,
    )

    async def _handle_get_related_context(tool_input: dict) -> dict:
        text = get_related_context(
            topics=tool_input.get("topics", []),
            people=tool_input.get("people", []),
            max_results=tool_input.get("max_results", 5),
        )
        return {"context": text}

    register_tool(
        name="get_related_context",
        description=(
            "Get related historical context by topics and/or people. "
            "Returns a formatted summary of past discussions and decisions "
            "relevant to the given topics or people. Use for enriching answers "
            "with historical background."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "topics": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Topics to find related context for",
                },
                "people": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "People to find related context for",
                },
                "max_results": {"type": "integer", "description": "Max entries (default 5)"},
            },
            "required": [],
        },
        handler=_handle_get_related_context,
    )

    async def _handle_get_context_stats(tool_input: dict) -> dict:
        return get_stats()

    register_tool(
        name="get_context_stats",
        description=(
            "Get statistics about the context repository: total entries, "
            "topic distribution, date range. Use when the user asks about "
            "what context or knowledge is available."
        ),
        input_schema={
            "type": "object",
            "properties": {},
            "required": [],
        },
        handler=_handle_get_context_stats,
    )

    async def _handle_get_item_summary(tool_input: dict) -> dict:
        return await generate_item_summary(
            item_type=tool_input.get("item_type", "task"),
            title=tool_input["title"],
            description=tool_input.get("description", ""),
            topics=tool_input.get("topics", []),
            people=tool_input.get("people", []),
            source_page_id=tool_input.get("source_page_id"),
        )

    register_tool(
        name="get_item_summary",
        description=(
            "Generate a smart context summary for a task, epic, or user story. "
            "Synthesizes background from the context repository to explain what "
            "this item is about, why it matters, and what the user should know. "
            "Use when the user asks for details or background on a specific item."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "item_type": {
                    "type": "string",
                    "enum": ["task", "epic", "story"],
                    "description": "Type of item",
                },
                "title": {"type": "string", "description": "Item title"},
                "description": {"type": "string", "description": "Item description"},
                "topics": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Related topics",
                },
                "people": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Related people",
                },
                "source_page_id": {"type": "string", "description": "Notion source page ID"},
            },
            "required": ["item_type", "title"],
        },
        handler=_handle_get_item_summary,
    )


_register_context_tools()
