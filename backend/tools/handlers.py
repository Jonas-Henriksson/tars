"""Tool handler registration — bridges existing integrations to unified registry.

All tools are registered here from a single place. This replaces both:
- agent/tools.py (35 Claude-format tools)
- web/server.py REALTIME_TOOLS (55 OpenAI-format tools)
"""
from __future__ import annotations

import logging
from typing import Any

from backend.tools.registry import registry

logger = logging.getLogger(__name__)


def register_all_tools() -> None:
    """Register all available tools with the unified registry.

    Checks which integrations are configured and registers their tools.
    Safe to call multiple times (idempotent).
    """
    _register_calendar_tools()
    _register_task_tools()
    _register_mail_tools()
    _register_reminder_tools()
    _register_notion_tools()
    _register_notion_review_tools()
    _register_briefing_tools()
    _register_intel_tools()
    _register_epic_tools()
    _register_strategic_tools()
    _register_people_tools()
    _register_alert_tools()

    logger.info(
        "Registered %d tools across %d categories",
        len(registry.tool_names),
        len(registry.categories),
    )


# ---------------------------------------------------------------------------
# Calendar
# ---------------------------------------------------------------------------

def _register_calendar_tools() -> None:
    from integrations.ms_auth import is_configured
    if not is_configured():
        return

    from integrations.calendar import get_events, create_event, search_events

    async def _get(args: dict) -> dict:
        return await get_events(
            days=args.get("days", 7),
            max_results=args.get("max_results", 20),
        )

    registry.register(
        name="get_calendar_events",
        description="Get the user's upcoming Microsoft 365 calendar events.",
        parameters={
            "type": "object",
            "properties": {
                "days": {"type": "integer", "description": "Days ahead. Default 7."},
                "max_results": {"type": "integer", "description": "Max events. Default 20."},
            },
        },
        handler=_get,
        category="calendar",
    )

    async def _create(args: dict) -> dict:
        return await create_event(
            subject=args["subject"],
            start_time=args["start_time"],
            end_time=args["end_time"],
            timezone_str=args.get("timezone", "UTC"),
            location=args.get("location", ""),
            body=args.get("body", ""),
            attendees=args.get("attendees"),
        )

    registry.register(
        name="create_calendar_event",
        description="Create a new calendar event. Always confirm details with user first.",
        parameters={
            "type": "object",
            "properties": {
                "subject": {"type": "string", "description": "Event title."},
                "start_time": {"type": "string", "description": "Start in ISO 8601."},
                "end_time": {"type": "string", "description": "End in ISO 8601."},
                "timezone": {"type": "string", "description": "IANA timezone. Default UTC."},
                "location": {"type": "string", "description": "Optional location."},
                "body": {"type": "string", "description": "Optional description."},
                "attendees": {
                    "type": "array", "items": {"type": "string"},
                    "description": "Optional attendee emails.",
                },
            },
            "required": ["subject", "start_time", "end_time"],
        },
        handler=_create,
        category="calendar",
        requires_confirmation=True,
    )

    async def _search(args: dict) -> dict:
        return await search_events(
            query=args["query"],
            days=args.get("days", 30),
            max_results=args.get("max_results", 10),
        )

    registry.register(
        name="search_calendar",
        description="Search calendar events by keyword in the subject.",
        parameters={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search keyword."},
                "days": {"type": "integer", "description": "Days ahead. Default 30."},
                "max_results": {"type": "integer", "description": "Max results. Default 10."},
            },
            "required": ["query"],
        },
        handler=_search,
        category="calendar",
    )


# ---------------------------------------------------------------------------
# Tasks (MS To Do)
# ---------------------------------------------------------------------------

def _register_task_tools() -> None:
    from integrations.ms_auth import is_configured
    if not is_configured():
        return

    from integrations.tasks import get_task_lists, get_tasks, create_task, complete_task

    async def _lists(args: dict) -> dict:
        return await get_task_lists()

    registry.register(
        name="get_task_lists",
        description="Get all Microsoft To Do task lists.",
        parameters={"type": "object", "properties": {}},
        handler=_lists,
        category="tasks",
    )

    async def _get(args: dict) -> dict:
        return await get_tasks(
            list_id=args.get("list_id"),
            include_completed=args.get("include_completed", False),
            max_results=args.get("max_results", 25),
        )

    registry.register(
        name="get_tasks",
        description="Get tasks from a Microsoft To Do list.",
        parameters={
            "type": "object",
            "properties": {
                "list_id": {"type": "string", "description": "Task list ID. Omit for default."},
                "include_completed": {"type": "boolean", "description": "Include completed. Default false."},
                "max_results": {"type": "integer", "description": "Max tasks. Default 25."},
            },
        },
        handler=_get,
        category="tasks",
    )

    async def _create(args: dict) -> dict:
        return await create_task(
            title=args["title"],
            list_id=args.get("list_id"),
            due_date=args.get("due_date", ""),
            importance=args.get("importance", "normal"),
            body=args.get("body", ""),
        )

    registry.register(
        name="create_task",
        description="Create a new task in Microsoft To Do. Confirm with user first.",
        parameters={
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "Task title."},
                "list_id": {"type": "string", "description": "Task list ID. Omit for default."},
                "due_date": {"type": "string", "description": "Due date YYYY-MM-DD."},
                "importance": {"type": "string", "enum": ["low", "normal", "high"]},
                "body": {"type": "string", "description": "Optional description."},
            },
            "required": ["title"],
        },
        handler=_create,
        category="tasks",
        requires_confirmation=True,
    )

    async def _complete(args: dict) -> dict:
        return await complete_task(
            task_id=args["task_id"],
            list_id=args.get("list_id"),
        )

    registry.register(
        name="complete_task",
        description="Mark a task as completed.",
        parameters={
            "type": "object",
            "properties": {
                "task_id": {"type": "string", "description": "The task ID."},
                "list_id": {"type": "string", "description": "Task list ID. Omit for default."},
            },
            "required": ["task_id"],
        },
        handler=_complete,
        category="tasks",
    )


# ---------------------------------------------------------------------------
# Email
# ---------------------------------------------------------------------------

def _register_mail_tools() -> None:
    from integrations.ms_auth import is_configured
    if not is_configured():
        return

    from integrations.mail import get_messages, read_message, send_message, reply_to_message, search_messages

    async def _get(args: dict) -> dict:
        return await get_messages(
            folder=args.get("folder", "inbox"),
            unread_only=args.get("unread_only", False),
            max_results=args.get("max_results", 15),
        )

    registry.register("get_emails", "Get recent emails from Microsoft 365 mailbox.", {
        "type": "object",
        "properties": {
            "folder": {"type": "string", "description": "Mail folder: inbox/sentitems/drafts. Default inbox."},
            "unread_only": {"type": "boolean", "description": "Only unread. Default false."},
            "max_results": {"type": "integer", "description": "Max messages. Default 15."},
        },
    }, _get, category="email")

    async def _read(args: dict) -> dict:
        return await read_message(message_id=args["message_id"])

    registry.register("read_email", "Read the full body of a specific email.", {
        "type": "object",
        "properties": {
            "message_id": {"type": "string", "description": "The email message ID."},
        },
        "required": ["message_id"],
    }, _read, category="email")

    async def _send(args: dict) -> dict:
        return await send_message(
            to=args["to"], subject=args["subject"], body=args["body"],
            cc=args.get("cc"), importance=args.get("importance", "normal"),
        )

    registry.register("send_email", "Send an email. ALWAYS confirm with user first.", {
        "type": "object",
        "properties": {
            "to": {"type": "array", "items": {"type": "string"}, "description": "Recipient emails."},
            "subject": {"type": "string", "description": "Subject line."},
            "body": {"type": "string", "description": "Email body."},
            "cc": {"type": "array", "items": {"type": "string"}, "description": "Optional CC."},
            "importance": {"type": "string", "enum": ["low", "normal", "high"]},
        },
        "required": ["to", "subject", "body"],
    }, _send, category="email", requires_confirmation=True)

    async def _reply(args: dict) -> dict:
        return await reply_to_message(
            message_id=args["message_id"], body=args["body"],
            reply_all=args.get("reply_all", False),
        )

    registry.register("reply_email", "Reply to an email. ALWAYS confirm with user first.", {
        "type": "object",
        "properties": {
            "message_id": {"type": "string", "description": "The message ID."},
            "body": {"type": "string", "description": "Reply body."},
            "reply_all": {"type": "boolean", "description": "Reply to all. Default false."},
        },
        "required": ["message_id", "body"],
    }, _reply, category="email", requires_confirmation=True)

    async def _search(args: dict) -> dict:
        return await search_messages(query=args["query"], max_results=args.get("max_results", 10))

    registry.register("search_emails", "Search emails by keyword.", {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Search keyword."},
            "max_results": {"type": "integer", "description": "Max results. Default 10."},
        },
        "required": ["query"],
    }, _search, category="email")


# ---------------------------------------------------------------------------
# Reminders
# ---------------------------------------------------------------------------

def _register_reminder_tools() -> None:
    from integrations.reminders import create_reminder, get_reminders, delete_reminder

    async def _create(args: dict) -> dict:
        chat_id = args.pop("_chat_id", 0)
        return create_reminder(chat_id=chat_id, message=args["message"], remind_at=args["remind_at"])

    registry.register("create_reminder", "Set a reminder for a specific time.", {
        "type": "object",
        "properties": {
            "message": {"type": "string", "description": "Reminder message."},
            "remind_at": {"type": "string", "description": "When to remind, ISO 8601 with timezone."},
        },
        "required": ["message", "remind_at"],
    }, _create, category="reminders", inject_chat_id=True, requires_confirmation=True)

    async def _get(args: dict) -> dict:
        chat_id = args.pop("_chat_id", 0)
        return get_reminders(chat_id)

    registry.register("get_reminders", "Get all pending reminders.", {
        "type": "object", "properties": {},
    }, _get, category="reminders", inject_chat_id=True)

    async def _delete(args: dict) -> dict:
        chat_id = args.pop("_chat_id", 0)
        return delete_reminder(reminder_id=args["reminder_id"], chat_id=chat_id)

    registry.register("delete_reminder", "Delete a pending reminder.", {
        "type": "object",
        "properties": {
            "reminder_id": {"type": "string", "description": "The reminder ID."},
        },
        "required": ["reminder_id"],
    }, _delete, category="reminders", inject_chat_id=True)


# ---------------------------------------------------------------------------
# Notion
# ---------------------------------------------------------------------------

def _register_notion_tools() -> None:
    from config import NOTION_API_KEY
    if not NOTION_API_KEY:
        return

    from integrations.notion import search_pages, get_page_content, list_databases, query_database
    from integrations.notion_tasks import (
        extract_meeting_tasks, track_meeting_tasks, get_tracked_tasks,
        search_meeting_notes, update_task_status, update_task,
    )

    async def _search(args: dict) -> dict:
        return await search_pages(query=args["query"], max_results=args.get("max_results", 10))

    registry.register("search_notion", "Search Notion pages by keyword.", {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Search keyword."},
            "max_results": {"type": "integer", "description": "Max pages. Default 10."},
        },
        "required": ["query"],
    }, _search, category="notion")

    async def _read(args: dict) -> dict:
        return await get_page_content(page_id=args["page_id"])

    registry.register("read_notion_page", "Read the full content of a Notion page.", {
        "type": "object",
        "properties": {"page_id": {"type": "string", "description": "The Notion page ID."}},
        "required": ["page_id"],
    }, _read, category="notion")

    async def _list_db(args: dict) -> dict:
        return await list_databases(max_results=args.get("max_results", 20))

    registry.register("list_notion_databases", "List all Notion databases.", {
        "type": "object",
        "properties": {"max_results": {"type": "integer", "description": "Max databases. Default 20."}},
    }, _list_db, category="notion")

    async def _query_db(args: dict) -> dict:
        return await query_database(
            database_id=args["database_id"],
            filter_obj=args.get("filter"),
            max_results=args.get("max_results", 50),
        )

    registry.register("query_notion_database", "Query a Notion database.", {
        "type": "object",
        "properties": {
            "database_id": {"type": "string", "description": "The database ID."},
            "filter": {"type": "object", "description": "Optional Notion filter."},
            "max_results": {"type": "integer", "description": "Max entries. Default 50."},
        },
        "required": ["database_id"],
    }, _query_db, category="notion")

    async def _extract(args: dict) -> dict:
        return await extract_meeting_tasks(page_id=args["page_id"])

    registry.register("extract_meeting_tasks", "Extract tasks from meeting notes page.", {
        "type": "object",
        "properties": {"page_id": {"type": "string", "description": "Notion page ID."}},
        "required": ["page_id"],
    }, _extract, category="notion")

    async def _track(args: dict) -> dict:
        return await track_meeting_tasks(page_id=args["page_id"])

    registry.register("track_meeting_tasks", "Extract and save meeting tasks for tracking.", {
        "type": "object",
        "properties": {"page_id": {"type": "string", "description": "Notion page ID."}},
        "required": ["page_id"],
    }, _track, category="notion")

    async def _get_tracked(args: dict) -> dict:
        return get_tracked_tasks(
            owner=args.get("owner", ""), topic=args.get("topic", ""),
            status=args.get("status", ""), include_completed=args.get("include_completed", False),
        )

    registry.register("get_tracked_tasks", "Get tracked meeting tasks with filters.", {
        "type": "object",
        "properties": {
            "owner": {"type": "string", "description": "Filter by owner."},
            "topic": {"type": "string", "description": "Filter by topic."},
            "status": {"type": "string", "enum": ["open", "done", "followed_up"]},
            "include_completed": {"type": "boolean", "description": "Include completed. Default false."},
        },
    }, _get_tracked, category="notion")

    async def _search_notes(args: dict) -> dict:
        return await search_meeting_notes(query=args["query"], max_results=args.get("max_results", 5))

    registry.register("search_meeting_notes", "Search Notion for meeting notes.", {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Search keyword."},
            "max_results": {"type": "integer", "description": "Max pages. Default 5."},
        },
        "required": ["query"],
    }, _search_notes, category="notion")

    async def _update_tracked(args: dict) -> dict:
        fields = {k: v for k, v in args.items() if k != "task_id" and v}
        if "status" in fields:
            return update_task_status(task_id=args["task_id"], status=fields["status"])
        return update_task(task_id=args["task_id"], **fields)

    registry.register("update_tracked_task", "Update a tracked meeting task.", {
        "type": "object",
        "properties": {
            "task_id": {"type": "string", "description": "The task ID."},
            "status": {"type": "string", "enum": ["open", "done", "followed_up"]},
            "owner": {"type": "string", "description": "Reassign to person."},
            "topic": {"type": "string", "description": "New topic."},
            "description": {"type": "string", "description": "Updated description."},
            "follow_up_date": {"type": "string", "description": "Follow-up date YYYY-MM-DD."},
        },
        "required": ["task_id"],
    }, _update_tracked, category="notion")


# ---------------------------------------------------------------------------
# Notion review
# ---------------------------------------------------------------------------

def _register_notion_review_tools() -> None:
    from config import NOTION_API_KEY
    if not NOTION_API_KEY:
        return

    from integrations.notion_review import review_recent_pages, review_page, add_known_names, get_known_names

    async def _review_all(args: dict) -> dict:
        return await review_recent_pages(auto_fix=args.get("auto_fix", False))

    registry.register("review_notion_pages", "Review Notion pages for consistency.", {
        "type": "object",
        "properties": {"auto_fix": {"type": "boolean", "description": "Auto-fix issues. Default false."}},
    }, _review_all, category="notion")

    async def _review_one(args: dict) -> dict:
        return await review_page(page_id=args["page_id"], auto_fix=args.get("auto_fix", False))

    registry.register("review_notion_page", "Review a specific Notion page.", {
        "type": "object",
        "properties": {
            "page_id": {"type": "string", "description": "Notion page ID."},
            "auto_fix": {"type": "boolean", "description": "Auto-fix. Default false."},
        },
        "required": ["page_id"],
    }, _review_one, category="notion")

    async def _add_names(args: dict) -> dict:
        return add_known_names(names=args["names"])

    registry.register("add_known_names", "Add names to spell-check list.", {
        "type": "object",
        "properties": {"names": {"type": "array", "items": {"type": "string"}}},
        "required": ["names"],
    }, _add_names, category="notion")

    async def _get_names(args: dict) -> dict:
        return get_known_names()

    registry.register("get_known_names", "Get the known names spell-check list.", {
        "type": "object", "properties": {},
    }, _get_names, category="notion")


# ---------------------------------------------------------------------------
# Briefing
# ---------------------------------------------------------------------------

def _register_briefing_tools() -> None:
    from integrations.briefing_daily import compile_daily_briefing, format_briefing_text

    async def _briefing(args: dict) -> dict:
        briefing = await compile_daily_briefing()
        briefing["formatted"] = format_briefing_text(briefing)
        return briefing

    registry.register("daily_briefing", "Compile a comprehensive daily briefing.", {
        "type": "object", "properties": {},
    }, _briefing, category="briefing")

    try:
        from integrations.review import get_weekly_review_voice

        async def _weekly(args: dict) -> dict:
            return get_weekly_review_voice()

        registry.register("weekly_review", "Get weekly review summary.", {
            "type": "object", "properties": {},
        }, _weekly, category="briefing")
    except ImportError:
        pass


# ---------------------------------------------------------------------------
# Intelligence
# ---------------------------------------------------------------------------

def _register_intel_tools() -> None:
    from config import NOTION_API_KEY
    if not NOTION_API_KEY:
        return

    from integrations.intel import (
        scan_notion, get_intel, get_smart_tasks, update_smart_task,
        delete_smart_task, search_intel,
    )

    async def _scan(args: dict) -> dict:
        return await scan_notion(max_pages=args.get("max_pages", 50))

    registry.register("scan_notion", "Scan Notion pages to build intelligence profile.", {
        "type": "object",
        "properties": {"max_pages": {"type": "integer", "description": "Max pages. Default 50."}},
    }, _scan, category="intelligence")

    async def _get_intel(args: dict) -> dict:
        return get_intel()

    registry.register("get_intel", "Get the full intelligence profile.", {
        "type": "object", "properties": {},
    }, _get_intel, category="intelligence")

    async def _get_tasks(args: dict) -> dict:
        return get_smart_tasks(
            owner=args.get("owner", ""), topic=args.get("topic", ""),
            quadrant=args.get("quadrant", 0), include_done=args.get("include_done", False),
        )

    registry.register("get_smart_tasks", "Get smart tasks with Eisenhower filters.", {
        "type": "object",
        "properties": {
            "owner": {"type": "string", "description": "Filter by owner."},
            "topic": {"type": "string", "description": "Filter by topic."},
            "quadrant": {"type": "integer", "description": "Eisenhower quadrant 1-4. 0 for all."},
            "include_done": {"type": "boolean", "description": "Include completed. Default false."},
        },
    }, _get_tasks, category="intelligence")

    async def _update_task(args: dict) -> dict:
        return update_smart_task(
            task_id=args["task_id"],
            status=args.get("status", ""),
            follow_up_date=args.get("follow_up_date", ""),
            owner=args.get("owner", ""),
            quadrant=args.get("quadrant", 0),
            description=args.get("description", ""),
            steps=args.get("steps", ""),
        )

    registry.register("update_smart_task", "Update a smart task.", {
        "type": "object",
        "properties": {
            "task_id": {"type": "string"},
            "status": {"type": "string", "enum": ["open", "done"]},
            "follow_up_date": {"type": "string", "description": "YYYY-MM-DD."},
            "owner": {"type": "string", "description": "Reassign to person."},
            "quadrant": {"type": "integer", "description": "Eisenhower quadrant 1-4."},
            "description": {"type": "string"},
            "steps": {"type": "string"},
        },
        "required": ["task_id"],
    }, _update_task, category="intelligence")

    async def _delete_task(args: dict) -> dict:
        return delete_smart_task(task_id=args["task_id"])

    registry.register("delete_smart_task", "Delete a smart task.", {
        "type": "object",
        "properties": {"task_id": {"type": "string"}},
        "required": ["task_id"],
    }, _delete_task, category="intelligence", requires_confirmation=True)

    async def _search(args: dict) -> dict:
        return search_intel(query=args["query"], max_results=args.get("max_results", 10))

    registry.register("search_intel", "Search the intelligence knowledge base.", {
        "type": "object",
        "properties": {
            "query": {"type": "string"},
            "max_results": {"type": "integer", "description": "Max results. Default 10."},
        },
        "required": ["query"],
    }, _search, category="intelligence")


# ---------------------------------------------------------------------------
# Epics & stories
# ---------------------------------------------------------------------------

def _register_epic_tools() -> None:
    from integrations.epics import (
        create_epic, get_epics, update_epic, delete_epic,
        create_story, get_stories, update_story, delete_story,
        link_task_to_story,
    )
    from integrations.team_portfolio import get_team_portfolio, get_member_portfolio

    async def _ce(a: dict) -> dict:
        return create_epic(
            title=a["title"], description=a.get("description", ""),
            owner=a.get("owner", ""), initiative_id=a.get("initiative_id", ""),
            quarter=a.get("quarter", ""), priority=a.get("priority", "high"),
            acceptance_criteria=a.get("acceptance_criteria"),
            source_title=a.get("source_title", ""),
            source_url=a.get("source_url", ""),
            source_page_id=a.get("source_page_id", ""),
        )

    registry.register("create_epic", "Create an epic — a large deliverable.", {
        "type": "object",
        "properties": {
            "title": {"type": "string"},
            "description": {"type": "string"},
            "owner": {"type": "string"},
            "initiative_id": {"type": "string"},
            "quarter": {"type": "string"},
            "priority": {"type": "string", "enum": ["high", "medium", "low"]},
            "acceptance_criteria": {"type": "array", "items": {"type": "string"}},
            "source_title": {"type": "string", "description": "Origin meeting/page title"},
            "source_url": {"type": "string", "description": "Origin page URL"},
            "source_page_id": {"type": "string", "description": "Origin page ID"},
        },
        "required": ["title"],
    }, _ce, category="agile")

    async def _ge(a: dict) -> dict:
        return get_epics(
            status=a.get("status", ""), owner=a.get("owner", ""),
            initiative_id=a.get("initiative_id", ""), quarter=a.get("quarter", ""),
            priority=a.get("priority", ""),
        )

    registry.register("get_epics", "Get epics with optional filters.", {
        "type": "object",
        "properties": {
            "status": {"type": "string", "enum": ["backlog", "in_progress", "done", "cancelled"]},
            "owner": {"type": "string"},
            "initiative_id": {"type": "string"},
            "quarter": {"type": "string"},
            "priority": {"type": "string", "enum": ["high", "medium", "low"]},
        },
    }, _ge, category="agile")

    async def _ue(a: dict) -> dict:
        return update_epic(
            epic_id=a["epic_id"], title=a.get("title", ""),
            description=a.get("description", ""), owner=a.get("owner", ""),
            status=a.get("status", ""), priority=a.get("priority", ""),
            quarter=a.get("quarter", ""), initiative_id=a.get("initiative_id", ""),
            acceptance_criteria=a.get("acceptance_criteria"),
        )

    registry.register("update_epic", "Update an epic.", {
        "type": "object",
        "properties": {
            "epic_id": {"type": "string"},
            "title": {"type": "string"}, "description": {"type": "string"},
            "owner": {"type": "string"},
            "status": {"type": "string", "enum": ["backlog", "in_progress", "done", "cancelled"]},
            "priority": {"type": "string", "enum": ["high", "medium", "low"]},
            "quarter": {"type": "string"}, "initiative_id": {"type": "string"},
            "acceptance_criteria": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["epic_id"],
    }, _ue, category="agile")

    async def _cs(a: dict) -> dict:
        return create_story(
            epic_id=a["epic_id"], title=a["title"],
            description=a.get("description", ""), owner=a.get("owner", ""),
            size=a.get("size", "M"), priority=a.get("priority", "medium"),
            acceptance_criteria=a.get("acceptance_criteria"),
            source_title=a.get("source_title", ""),
            source_url=a.get("source_url", ""),
            source_page_id=a.get("source_page_id", ""),
        )

    registry.register("create_story", "Create a user story within an epic.", {
        "type": "object",
        "properties": {
            "epic_id": {"type": "string"},
            "title": {"type": "string"},
            "description": {"type": "string"}, "owner": {"type": "string"},
            "size": {"type": "string", "enum": ["XS", "S", "M", "L", "XL"]},
            "priority": {"type": "string", "enum": ["high", "medium", "low"]},
            "acceptance_criteria": {"type": "array", "items": {"type": "string"}},
            "source_title": {"type": "string", "description": "Origin meeting/page title"},
            "source_url": {"type": "string", "description": "Origin page URL"},
            "source_page_id": {"type": "string", "description": "Origin page ID"},
        },
        "required": ["epic_id", "title"],
    }, _cs, category="agile")

    async def _gs(a: dict) -> dict:
        return get_stories(
            epic_id=a.get("epic_id", ""), owner=a.get("owner", ""),
            status=a.get("status", ""), priority=a.get("priority", ""),
            size=a.get("size", ""),
        )

    registry.register("get_stories", "Get user stories with filters.", {
        "type": "object",
        "properties": {
            "epic_id": {"type": "string"}, "owner": {"type": "string"},
            "status": {"type": "string", "enum": ["backlog", "ready", "in_progress", "in_review", "done", "blocked"]},
            "priority": {"type": "string", "enum": ["high", "medium", "low"]},
            "size": {"type": "string", "enum": ["XS", "S", "M", "L", "XL"]},
        },
    }, _gs, category="agile")

    async def _us(a: dict) -> dict:
        return update_story(
            story_id=a["story_id"], title=a.get("title", ""),
            description=a.get("description", ""), owner=a.get("owner", ""),
            status=a.get("status", ""), priority=a.get("priority", ""),
            size=a.get("size", ""), acceptance_criteria=a.get("acceptance_criteria"),
        )

    registry.register("update_story", "Update a user story.", {
        "type": "object",
        "properties": {
            "story_id": {"type": "string"}, "title": {"type": "string"},
            "description": {"type": "string"}, "owner": {"type": "string"},
            "status": {"type": "string", "enum": ["backlog", "ready", "in_progress", "in_review", "done", "blocked"]},
            "priority": {"type": "string", "enum": ["high", "medium", "low"]},
            "size": {"type": "string", "enum": ["XS", "S", "M", "L", "XL"]},
            "acceptance_criteria": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["story_id"],
    }, _us, category="agile")

    async def _lt(a: dict) -> dict:
        return link_task_to_story(story_id=a["story_id"], task_id=a["task_id"])

    registry.register("link_task_to_story", "Link a task to a user story.", {
        "type": "object",
        "properties": {
            "story_id": {"type": "string"}, "task_id": {"type": "string"},
        },
        "required": ["story_id", "task_id"],
    }, _lt, category="agile")

    async def _tp(a: dict) -> dict:
        return get_team_portfolio(
            owner=a.get("owner", ""), quarter=a.get("quarter", ""),
            include_done=a.get("include_done", False),
        )

    registry.register("get_team_portfolio", "Team-wide workload view.", {
        "type": "object",
        "properties": {
            "owner": {"type": "string"}, "quarter": {"type": "string"},
            "include_done": {"type": "boolean"},
        },
    }, _tp, category="agile")

    async def _mp(a: dict) -> dict:
        return get_member_portfolio(name=a["name"], include_done=a.get("include_done", False))

    registry.register("get_member_portfolio", "One member's portfolio view.", {
        "type": "object",
        "properties": {
            "name": {"type": "string"}, "include_done": {"type": "boolean"},
        },
        "required": ["name"],
    }, _mp, category="agile")


# ---------------------------------------------------------------------------
# Strategic (decisions, initiatives)
# ---------------------------------------------------------------------------

def _register_strategic_tools() -> None:
    from integrations.decisions import log_decision, get_decisions, update_decision
    from integrations.initiatives import (
        create_initiative, get_initiatives, update_initiative,
        complete_milestone, add_key_result, update_key_result,
    )
    from integrations.meeting_prep import get_meeting_prep, get_next_meeting_brief

    # Decisions
    async def _log(a: dict) -> dict:
        return log_decision(
            title=a["title"], rationale=a.get("rationale", ""),
            decided_by=a.get("decided_by", ""), stakeholders=a.get("stakeholders"),
            context=a.get("context", ""), initiative=a.get("initiative", ""),
            status=a.get("status", "decided"),
        )

    registry.register("log_decision", "Log a decision to the register.", {
        "type": "object",
        "properties": {
            "title": {"type": "string"}, "rationale": {"type": "string"},
            "decided_by": {"type": "string"},
            "stakeholders": {"type": "array", "items": {"type": "string"}},
            "context": {"type": "string"}, "initiative": {"type": "string"},
            "status": {"type": "string", "enum": ["decided", "pending", "revisit"]},
        },
        "required": ["title"],
    }, _log, category="strategic")

    async def _gd(a: dict) -> dict:
        return get_decisions(
            status=a.get("status", ""), initiative=a.get("initiative", ""),
            stakeholder=a.get("stakeholder", ""),
        )

    registry.register("get_decisions", "Get decisions with filters.", {
        "type": "object",
        "properties": {
            "status": {"type": "string", "enum": ["pending", "decided", "revisit"]},
            "initiative": {"type": "string"}, "stakeholder": {"type": "string"},
        },
    }, _gd, category="strategic")

    async def _ud(a: dict) -> dict:
        return update_decision(
            decision_id=a["decision_id"], status=a.get("status", ""),
            rationale=a.get("rationale", ""), outcome_notes=a.get("outcome_notes", ""),
            title=a.get("title", ""),
        )

    registry.register("update_decision", "Update a decision.", {
        "type": "object",
        "properties": {
            "decision_id": {"type": "string"},
            "status": {"type": "string", "enum": ["pending", "decided", "revisit"]},
            "rationale": {"type": "string"}, "outcome_notes": {"type": "string"},
            "title": {"type": "string"},
        },
        "required": ["decision_id"],
    }, _ud, category="strategic")

    # Initiatives
    async def _ci(a: dict) -> dict:
        return create_initiative(
            title=a["title"], description=a.get("description", ""),
            owner=a.get("owner", ""), quarter=a.get("quarter", ""),
            status=a.get("status", "on_track"), priority=a.get("priority", "high"),
            milestones=a.get("milestones"),
            source_title=a.get("source_title", ""),
            source_url=a.get("source_url", ""),
            source_page_id=a.get("source_page_id", ""),
        )

    registry.register("create_initiative", "Create a strategic initiative.", {
        "type": "object",
        "properties": {
            "title": {"type": "string"}, "description": {"type": "string"},
            "owner": {"type": "string"}, "quarter": {"type": "string"},
            "status": {"type": "string", "enum": ["on_track", "at_risk", "off_track", "completed", "paused"]},
            "priority": {"type": "string", "enum": ["high", "medium", "low"]},
            "milestones": {"type": "array", "items": {"type": "string"}},
            "source_title": {"type": "string", "description": "Origin meeting/page title"},
            "source_url": {"type": "string", "description": "Origin page URL"},
            "source_page_id": {"type": "string", "description": "Origin page ID"},
        },
        "required": ["title"],
    }, _ci, category="strategic")

    async def _gi(a: dict) -> dict:
        return get_initiatives(
            status=a.get("status", ""), owner=a.get("owner", ""),
            quarter=a.get("quarter", ""), priority=a.get("priority", ""),
        )

    registry.register("get_initiatives", "Get strategic initiatives.", {
        "type": "object",
        "properties": {
            "status": {"type": "string", "enum": ["on_track", "at_risk", "off_track", "completed", "paused"]},
            "owner": {"type": "string"}, "quarter": {"type": "string"},
            "priority": {"type": "string", "enum": ["high", "medium", "low"]},
        },
    }, _gi, category="strategic")

    async def _ui(a: dict) -> dict:
        return update_initiative(
            initiative_id=a["initiative_id"], title=a.get("title", ""),
            description=a.get("description", ""), owner=a.get("owner", ""),
            quarter=a.get("quarter", ""), status=a.get("status", ""),
            priority=a.get("priority", ""),
        )

    registry.register("update_initiative", "Update a strategic initiative.", {
        "type": "object",
        "properties": {
            "initiative_id": {"type": "string"},
            "title": {"type": "string"}, "description": {"type": "string"},
            "owner": {"type": "string"}, "quarter": {"type": "string"},
            "status": {"type": "string", "enum": ["on_track", "at_risk", "off_track", "completed", "paused"]},
            "priority": {"type": "string", "enum": ["high", "medium", "low"]},
        },
        "required": ["initiative_id"],
    }, _ui, category="strategic")

    async def _cm(a: dict) -> dict:
        return complete_milestone(initiative_id=a["initiative_id"], milestone_index=a["milestone_index"])

    registry.register("complete_milestone", "Mark a milestone as completed.", {
        "type": "object",
        "properties": {
            "initiative_id": {"type": "string"},
            "milestone_index": {"type": "integer", "description": "Zero-based index."},
        },
        "required": ["initiative_id", "milestone_index"],
    }, _cm, category="strategic")

    async def _akr(a: dict) -> dict:
        return add_key_result(
            initiative_id=a["initiative_id"], description=a["description"],
            target=a.get("target", ""), current=a.get("current", ""),
            owner=a.get("owner", ""),
        )

    registry.register("add_key_result", "Add a key result to an initiative.", {
        "type": "object",
        "properties": {
            "initiative_id": {"type": "string"}, "description": {"type": "string"},
            "target": {"type": "string"}, "current": {"type": "string"},
            "owner": {"type": "string"},
        },
        "required": ["initiative_id", "description"],
    }, _akr, category="strategic")

    async def _ukr(a: dict) -> dict:
        return update_key_result(
            kr_id=a["kr_id"], current=a.get("current", ""),
            status=a.get("status", ""), description=a.get("description", ""),
        )

    registry.register("update_key_result", "Update a key result.", {
        "type": "object",
        "properties": {
            "kr_id": {"type": "string"},
            "current": {"type": "string"},
            "status": {"type": "string", "enum": ["in_progress", "achieved", "missed"]},
            "description": {"type": "string"},
        },
        "required": ["kr_id"],
    }, _ukr, category="strategic")

    # Meeting prep
    async def _mp(a: dict) -> dict:
        return await get_meeting_prep(
            event_id=a.get("event_id", ""),
            minutes_ahead=a.get("minutes_ahead", 30),
        )

    registry.register("meeting_prep", "Prepare briefing for an upcoming meeting.", {
        "type": "object",
        "properties": {
            "event_id": {"type": "string", "description": "Specific event ID. Omit for next meeting."},
            "minutes_ahead": {"type": "integer", "description": "How far ahead to look. Default 30."},
        },
    }, _mp, category="strategic")

    async def _nmb(a: dict) -> dict:
        return await get_next_meeting_brief()

    registry.register("next_meeting_brief", "Quick prep for the next meeting.", {
        "type": "object", "properties": {},
    }, _nmb, category="strategic")


# ---------------------------------------------------------------------------
# People
# ---------------------------------------------------------------------------

def _register_people_tools() -> None:
    from integrations.people import get_all_people, get_person, update_person

    async def _all(a: dict) -> dict:
        return get_all_people()

    registry.register("get_people", "Get all people profiles.", {
        "type": "object", "properties": {},
    }, _all, category="people")

    async def _one(a: dict) -> dict:
        return get_person(a["name"])

    registry.register("get_person", "Get a specific person's profile.", {
        "type": "object",
        "properties": {"name": {"type": "string"}},
        "required": ["name"],
    }, _one, category="people")

    async def _update(a: dict) -> dict:
        name = a.pop("name")
        fields = {k: v for k, v in a.items() if v}
        return update_person(name, **fields)

    registry.register("update_person", "Update a person's profile.", {
        "type": "object",
        "properties": {
            "name": {"type": "string"},
            "role": {"type": "string"}, "relationship": {"type": "string"},
            "organization": {"type": "string"}, "notes": {"type": "string"},
            "email": {"type": "string"},
        },
        "required": ["name"],
    }, _update, category="people")


# ---------------------------------------------------------------------------
# Alerts
# ---------------------------------------------------------------------------

def _register_alert_tools() -> None:
    from integrations.alerts import get_alerts

    async def _alerts(a: dict) -> dict:
        return await get_alerts()

    registry.register("get_alerts", "Get proactive alerts — bottlenecks, overdue, risks.", {
        "type": "object", "properties": {},
    }, _alerts, category="alerts")
