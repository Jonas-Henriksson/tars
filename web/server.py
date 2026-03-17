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

from fastapi import FastAPI, Request
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

STRATEGIC LAYER — You also have executive-grade strategic tools:
- Meeting prep: Before any meeting, use meeting_prep or next_meeting_brief \
to get attendee profiles, past interactions, open tasks, pending decisions, \
and talking points. Use when the user says "prep me" or has an upcoming meeting.
- Decision register: Use log_decision to record important decisions with \
rationale and stakeholders. Use get_decisions to review pending or past decisions. \
When the user says "we decided to..." or "let's decide", use these tools.
- Strategic initiatives & OKRs: Use create_initiative, get_initiatives to \
track quarterly goals, milestones, and key results. Use when discussing \
strategy, goals, OKRs, or quarterly planning.
- Proactive alerts: Use get_alerts to surface bottlenecks, overdue escalations, \
calendar conflicts, relationship health issues, initiative risks, and stale \
decisions. Use when the user asks "anything I should worry about", "what needs \
my attention", or at the start of the day.

AGILE WORK BREAKDOWN — You use Scrum methodology to structure deliverables:
  Initiative (strategic goal) → Epic (large deliverable) → \
User Story ("As a [role], I want [goal], so that [benefit]") → Task.

BE PRAGMATIC — Not everything belongs in an epic. The team handles a mix of:
1. Structured deliverables (features, projects, migrations) — USE epics & stories. \
These benefit from the full hierarchy so team members understand the bigger picture.
2. Operational / admin duties (hiring, vendor management, recurring processes, \
compliance, ad-hoc requests) — these can live as standalone tasks without forcing \
them into an epic. Don't over-structure work that doesn't need it.

WHEN TO USE EPICS: If work is part of a larger delivery, spans multiple tasks, \
or would benefit from team members understanding the broader context. \
WHEN NOT TO: One-off admin tasks, quick asks, recurring operational duties, \
or anything where the epic overhead adds friction without adding clarity.

- Epics: Use create_epic for significant deliverables. Link to initiatives \
via initiative_id when they serve a strategic goal.
- User Stories: Use create_story for value slices within epics. \
Best practice: "As a [role], I want [goal], so that [benefit]". \
T-shirt sizes (XS–XL) and acceptance criteria help scope work clearly.
- Linking tasks: Use link_task_to_story to connect delegated tasks to stories, \
giving the assignee full context on why this task matters.
- When the user delegates structured work, suggest which epic/story it fits. \
For operational tasks, just track them as smart tasks — no epic needed.

TEAM PORTFOLIO — Per-member portfolio view across all work types:
- get_team_portfolio: Every member's epics, stories, AND standalone tasks. \
Shows overload, blocked items, and unlinked tasks (which may be fine for \
operational work, or may indicate deliverables that need structuring).
- get_member_portfolio: Detailed view for one person's full plate.
Use when the user says "show me the team overview", "who is working on what", \
"what's everyone's workload", or wants to steer priorities.

IMPORTANT — When the user references a decision, initiative, epic, or story by name \
(e.g. "update the EMEA initiative" or "mark the onboarding epic as in progress"), \
first call the relevant get_ tool to find the matching ID, \
then use the update tool with the resolved ID. Never ask the user for an ID directly.

When the user asks about tasks, priorities, delegation, what needs \
attention, who owns what, or any question about their work — use the \
intelligence tools. Start with get_intel for a broad overview or \
get_smart_tasks for filtered queries. Use daily_briefing for end-of-day \
summaries. Use search_intel to find specific information across all \
scanned pages. Use get_alerts for proactive risk scanning.

When using tools, tell the user what you're doing (e.g. "Let me check \
your priority matrix..." or "Pulling up your intelligence profile..."). \
Always confirm before sending emails or creating events.\
"""


def _build_voice_prompt() -> str:
    """Build the voice session system prompt, injecting user memory and work context."""
    parts = [TARS_INSTRUCTIONS]

    # Inject user memory if any exists
    try:
        from integrations.memory import get_memory
        mem = get_memory()
        if mem.get("facts") or mem.get("preferences") or mem.get("notes"):
            lines = ["About the user (remembered from past sessions):"]
            if mem.get("facts"):
                lines.append("Facts: " + ", ".join(f"{k}: {v}" for k, v in mem["facts"].items()))
            if mem.get("preferences"):
                lines.append("Preferences: " + "; ".join(f"{k} → {v}" for k, v in mem["preferences"].items()))
            if mem.get("notes"):
                recent = [n["text"] for n in mem["notes"][-5:]]
                lines.append("Notes: " + " | ".join(recent))
            parts.append("\n" + "\n".join(lines))
    except Exception:
        pass

    # Inject brief current work context
    try:
        from integrations.intel import get_intel_summary
        summary = get_intel_summary()
        if summary:
            parts.append(f"\nCurrent work context: {summary}")
    except Exception:
        pass

    # Memory behavior instructions (voice-adapted)
    parts.append(
        "\nMemory: When the user tells you their name, role, timezone, or personal facts — "
        "call remember_fact. When they state a preference — call remember_preference. "
        "When they mention something to remember across sessions — call add_memory_note. "
        "Do this silently without announcing it."
    )

    return "\n".join(parts)


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
        "name": "reply_email",
        "description": "Reply to an email. ALWAYS confirm the reply text with the user first.",
        "parameters": {
            "type": "object",
            "properties": {
                "message_id": {"type": "string", "description": "The message ID to reply to (from get_emails or read_email)."},
                "body": {"type": "string", "description": "Reply body text."},
                "reply_all": {"type": "boolean", "description": "Reply to all recipients. Default false."},
            },
            "required": ["message_id", "body"],
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
        "name": "weekly_review",
        "description": "Get a weekly review summary — task status breakdown, overdue items, delegation patterns, stale tasks, and topic activity. Use when the user asks for a weekly review, status overview, or wants to know how things are going.",
        "parameters": {
            "type": "object",
            "properties": {},
        },
    },
    {
        "type": "function",
        "name": "get_people",
        "description": "Get all people from the knowledge library with their roles, relationships, topics, and task ownership. Use when the user asks 'who works on X' or 'tell me about my team'.",
        "parameters": {
            "type": "object",
            "properties": {},
        },
    },
    {
        "type": "function",
        "name": "get_person",
        "description": "Get a specific person's full profile — role, relationship, org, topics, tasks, and meeting context.",
        "parameters": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "The person's name."},
            },
            "required": ["name"],
        },
    },
    {
        "type": "function",
        "name": "update_person",
        "description": "Update a person's profile — their role, relationship to user, organization, email, or notes.",
        "parameters": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "The person's name."},
                "role": {"type": "string", "description": "Their role/title (e.g. 'Engineering Lead')."},
                "relationship": {"type": "string", "description": "How they relate to the user (e.g. 'Direct report', 'Skip-level', 'External partner')."},
                "organization": {"type": "string", "description": "Their team/dept/org (e.g. 'Platform Engineering')."},
                "notes": {"type": "string", "description": "Free-form notes about this person."},
                "email": {"type": "string", "description": "Their email address."},
            },
            "required": ["name"],
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
    # Meeting prep tools
    {
        "type": "function",
        "name": "meeting_prep",
        "description": "Prepare a context-rich briefing for an upcoming meeting. Shows attendee profiles, past interactions, open tasks, pending decisions, and suggested talking points. If no event_id given, preps for the next meeting.",
        "parameters": {
            "type": "object",
            "properties": {
                "event_id": {"type": "string", "description": "Optional specific calendar event ID. If omitted, preps for next meeting."},
                "minutes_ahead": {"type": "integer", "description": "How far ahead to look for next meeting. Default 30."},
            },
        },
    },
    {
        "type": "function",
        "name": "next_meeting_brief",
        "description": "Quick meeting prep for the very next upcoming meeting. Use when the user says 'prep me for my next meeting' or 'what's my next meeting about'.",
        "parameters": {
            "type": "object",
            "properties": {},
        },
    },
    # Decision tracking tools
    {
        "type": "function",
        "name": "log_decision",
        "description": "Log a decision to the decision register. Records what was decided, why, by whom, and who needs to know. Use when the user says 'we decided to...' or 'log this decision'.",
        "parameters": {
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "What was decided."},
                "rationale": {"type": "string", "description": "Why this decision was made."},
                "decided_by": {"type": "string", "description": "Who made the decision."},
                "stakeholders": {"type": "array", "items": {"type": "string"}, "description": "Who is affected or needs to know."},
                "context": {"type": "string", "description": "Background, alternatives considered."},
                "initiative": {"type": "string", "description": "Linked strategic initiative name."},
                "status": {"type": "string", "enum": ["decided", "pending", "revisit"], "description": "Default 'decided'."},
            },
            "required": ["title"],
        },
    },
    {
        "type": "function",
        "name": "get_decisions",
        "description": "Get decisions from the register. Filter by status (pending, decided, revisit), initiative, or stakeholder. Use when user asks 'what decisions are pending' or 'what did we decide about X'.",
        "parameters": {
            "type": "object",
            "properties": {
                "status": {"type": "string", "enum": ["pending", "decided", "revisit"], "description": "Filter by status."},
                "initiative": {"type": "string", "description": "Filter by linked initiative."},
                "stakeholder": {"type": "string", "description": "Filter by stakeholder name."},
            },
        },
    },
    {
        "type": "function",
        "name": "update_decision",
        "description": "Update a decision — change status, add outcome notes, update stakeholders.",
        "parameters": {
            "type": "object",
            "properties": {
                "decision_id": {"type": "string", "description": "The decision ID."},
                "status": {"type": "string", "enum": ["pending", "decided", "revisit"], "description": "New status."},
                "rationale": {"type": "string", "description": "Updated rationale."},
                "outcome_notes": {"type": "string", "description": "How the decision played out."},
                "title": {"type": "string", "description": "Updated title."},
            },
            "required": ["decision_id"],
        },
    },
    # Strategic initiative tools
    {
        "type": "function",
        "name": "create_initiative",
        "description": "Create a strategic initiative or OKR. Use when the user defines a new goal, objective, or strategic priority for the quarter.",
        "parameters": {
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "Initiative name (e.g. 'Launch EMEA expansion')."},
                "description": {"type": "string", "description": "What this initiative aims to achieve."},
                "owner": {"type": "string", "description": "Who is accountable."},
                "quarter": {"type": "string", "description": "Target quarter (e.g. 'Q1 2026')."},
                "status": {"type": "string", "enum": ["on_track", "at_risk", "off_track", "completed", "paused"], "description": "Default 'on_track'."},
                "priority": {"type": "string", "enum": ["high", "medium", "low"], "description": "Default 'high'."},
                "milestones": {"type": "array", "items": {"type": "string"}, "description": "Key milestones."},
            },
            "required": ["title"],
        },
    },
    {
        "type": "function",
        "name": "get_initiatives",
        "description": "Get strategic initiatives. Filter by status, owner, quarter, or priority. Use when user asks about goals, OKRs, strategic priorities, or 'how are our initiatives doing'.",
        "parameters": {
            "type": "object",
            "properties": {
                "status": {"type": "string", "enum": ["on_track", "at_risk", "off_track", "completed", "paused"], "description": "Filter by status."},
                "owner": {"type": "string", "description": "Filter by owner."},
                "quarter": {"type": "string", "description": "Filter by quarter."},
                "priority": {"type": "string", "enum": ["high", "medium", "low"], "description": "Filter by priority."},
            },
        },
    },
    {
        "type": "function",
        "name": "update_initiative",
        "description": "Update a strategic initiative — change status, owner, priority, or description.",
        "parameters": {
            "type": "object",
            "properties": {
                "initiative_id": {"type": "string", "description": "The initiative ID."},
                "status": {"type": "string", "enum": ["on_track", "at_risk", "off_track", "completed", "paused"], "description": "New status."},
                "owner": {"type": "string", "description": "New owner."},
                "quarter": {"type": "string", "description": "New target quarter."},
                "priority": {"type": "string", "enum": ["high", "medium", "low"], "description": "New priority."},
                "title": {"type": "string", "description": "Updated title."},
                "description": {"type": "string", "description": "Updated description."},
            },
            "required": ["initiative_id"],
        },
    },
    {
        "type": "function",
        "name": "complete_milestone",
        "description": "Mark a milestone as completed on an initiative. Use when user says 'milestone X is done'.",
        "parameters": {
            "type": "object",
            "properties": {
                "initiative_id": {"type": "string", "description": "The initiative ID."},
                "milestone_index": {"type": "integer", "description": "Zero-based index of the milestone."},
            },
            "required": ["initiative_id", "milestone_index"],
        },
    },
    {
        "type": "function",
        "name": "add_key_result",
        "description": "Add a key result (KR) to an initiative. Use when defining measurable outcomes for a strategic goal.",
        "parameters": {
            "type": "object",
            "properties": {
                "initiative_id": {"type": "string", "description": "The parent initiative ID."},
                "description": {"type": "string", "description": "What the KR measures (e.g. 'Revenue reaches $10M ARR')."},
                "target": {"type": "string", "description": "Target value or metric."},
                "current": {"type": "string", "description": "Current value or progress."},
                "owner": {"type": "string", "description": "Who owns this KR."},
            },
            "required": ["initiative_id", "description"],
        },
    },
    {
        "type": "function",
        "name": "update_key_result",
        "description": "Update a key result's progress or status.",
        "parameters": {
            "type": "object",
            "properties": {
                "kr_id": {"type": "string", "description": "The key result ID."},
                "current": {"type": "string", "description": "Updated current value."},
                "status": {"type": "string", "enum": ["in_progress", "achieved", "missed"], "description": "New status."},
            },
            "required": ["kr_id"],
        },
    },
    # Proactive alerts
    {
        "type": "function",
        "name": "get_alerts",
        "description": "Get proactive alerts — bottleneck detection, overdue escalations, calendar conflicts, relationship health, initiative risks, and stale decisions. Use when user asks 'anything I should worry about', 'what needs my attention', or 'any red flags'.",
        "parameters": {
            "type": "object",
            "properties": {},
        },
    },
    # Epics & user stories (Agile work breakdown)
    {
        "type": "function",
        "name": "create_epic",
        "description": "Create an epic — a large body of work that delivers significant value. Epics bridge initiatives and tasks. Use when defining a major deliverable, feature, or workstream. Say 'create an epic for...' or 'we need an epic to track...'.",
        "parameters": {
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "Epic name (e.g. 'User onboarding revamp')."},
                "description": {"type": "string", "description": "What this epic delivers and why it matters."},
                "owner": {"type": "string", "description": "Who is accountable for delivery."},
                "initiative_id": {"type": "string", "description": "Parent initiative ID (optional)."},
                "quarter": {"type": "string", "description": "Target quarter (e.g. 'Q2 2026')."},
                "priority": {"type": "string", "enum": ["high", "medium", "low"], "description": "Default 'high'."},
                "acceptance_criteria": {"type": "array", "items": {"type": "string"}, "description": "Definition of done for the epic."},
            },
            "required": ["title"],
        },
    },
    {
        "type": "function",
        "name": "get_epics",
        "description": "Get epics with optional filters. Shows story progress per epic. Use when user asks about deliverables, epics, 'what are we working on', or 'show me the epics'.",
        "parameters": {
            "type": "object",
            "properties": {
                "status": {"type": "string", "enum": ["backlog", "in_progress", "done", "cancelled"], "description": "Filter by status."},
                "owner": {"type": "string", "description": "Filter by owner."},
                "initiative_id": {"type": "string", "description": "Filter by parent initiative."},
                "quarter": {"type": "string", "description": "Filter by quarter."},
                "priority": {"type": "string", "enum": ["high", "medium", "low"], "description": "Filter by priority."},
            },
        },
    },
    {
        "type": "function",
        "name": "update_epic",
        "description": "Update an epic — change status, owner, priority, or description. When user references an epic by name, first look it up with get_epics.",
        "parameters": {
            "type": "object",
            "properties": {
                "epic_id": {"type": "string", "description": "The epic ID."},
                "title": {"type": "string", "description": "New title."},
                "description": {"type": "string", "description": "New description."},
                "owner": {"type": "string", "description": "New owner."},
                "status": {"type": "string", "enum": ["backlog", "in_progress", "done", "cancelled"], "description": "New status."},
                "priority": {"type": "string", "enum": ["high", "medium", "low"], "description": "New priority."},
                "quarter": {"type": "string", "description": "New quarter."},
                "initiative_id": {"type": "string", "description": "Link to initiative."},
            },
            "required": ["epic_id"],
        },
    },
    {
        "type": "function",
        "name": "create_story",
        "description": "Create a user story within an epic. Best practice: 'As a [role], I want [goal], so that [benefit]'. Use when breaking an epic into deliverable slices.",
        "parameters": {
            "type": "object",
            "properties": {
                "epic_id": {"type": "string", "description": "Parent epic ID."},
                "title": {"type": "string", "description": "Story title (ideally in user story format)."},
                "description": {"type": "string", "description": "Additional context."},
                "owner": {"type": "string", "description": "Who will deliver."},
                "size": {"type": "string", "enum": ["XS", "S", "M", "L", "XL"], "description": "T-shirt size. Default 'M'."},
                "priority": {"type": "string", "enum": ["high", "medium", "low"], "description": "Default 'medium'."},
                "acceptance_criteria": {"type": "array", "items": {"type": "string"}, "description": "Done conditions."},
            },
            "required": ["epic_id", "title"],
        },
    },
    {
        "type": "function",
        "name": "get_stories",
        "description": "Get user stories with optional filters. Use to check what's in progress, blocked, or assigned to someone.",
        "parameters": {
            "type": "object",
            "properties": {
                "epic_id": {"type": "string", "description": "Filter by parent epic."},
                "owner": {"type": "string", "description": "Filter by owner."},
                "status": {"type": "string", "enum": ["backlog", "ready", "in_progress", "in_review", "done", "blocked"], "description": "Filter by status."},
                "priority": {"type": "string", "enum": ["high", "medium", "low"], "description": "Filter by priority."},
                "size": {"type": "string", "enum": ["XS", "S", "M", "L", "XL"], "description": "Filter by size."},
            },
        },
    },
    {
        "type": "function",
        "name": "update_story",
        "description": "Update a user story — change status, owner, size, or priority. First look up with get_stories if referenced by name.",
        "parameters": {
            "type": "object",
            "properties": {
                "story_id": {"type": "string", "description": "The story ID."},
                "title": {"type": "string", "description": "New title."},
                "owner": {"type": "string", "description": "Reassign to this person."},
                "status": {"type": "string", "enum": ["backlog", "ready", "in_progress", "in_review", "done", "blocked"], "description": "New status."},
                "priority": {"type": "string", "enum": ["high", "medium", "low"], "description": "New priority."},
                "size": {"type": "string", "enum": ["XS", "S", "M", "L", "XL"], "description": "New size."},
            },
            "required": ["story_id"],
        },
    },
    {
        "type": "function",
        "name": "link_task_to_story",
        "description": "Link an existing task (smart task or tracked task) to a user story, connecting it into the epic hierarchy.",
        "parameters": {
            "type": "object",
            "properties": {
                "story_id": {"type": "string", "description": "The story ID."},
                "task_id": {"type": "string", "description": "The task ID to link."},
            },
            "required": ["story_id", "task_id"],
        },
    },
    # Team portfolio
    {
        "type": "function",
        "name": "get_team_portfolio",
        "description": "Full team portfolio view — every member's epics, stories, tasks, and workload. Shows overload, blocked items, and unlinked tasks. Use when user asks 'show me the team', 'who is working on what', 'what is everyone's workload', or wants to steer priorities.",
        "parameters": {
            "type": "object",
            "properties": {
                "owner": {"type": "string", "description": "Filter to a specific team member."},
                "quarter": {"type": "string", "description": "Filter epics by quarter."},
                "include_done": {"type": "boolean", "description": "Include completed items. Default false."},
            },
        },
    },
    {
        "type": "function",
        "name": "get_member_portfolio",
        "description": "Detailed portfolio for one team member — their epics, stories, tasks, and workload. Use when asking about a specific person's deliverables, capacity, or 'what is Sarah working on'.",
        "parameters": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Team member name."},
                "include_done": {"type": "boolean", "description": "Include completed items. Default false."},
            },
            "required": ["name"],
        },
    },
    {
        "type": "function",
        "name": "remember_preference",
        "description": "Store a user preference (e.g. response style, language). Call whenever the user states how they want TARS to behave.",
        "parameters": {
            "type": "object",
            "properties": {
                "key": {"type": "string", "description": "Preference name (e.g. 'response_style')."},
                "value": {"type": "string", "description": "Preference value."},
            },
            "required": ["key", "value"],
        },
    },
    {
        "type": "function",
        "name": "remember_fact",
        "description": "Store a key fact about the user (name, role, timezone, team members, etc). Call when the user shares personal or work context.",
        "parameters": {
            "type": "object",
            "properties": {
                "key": {"type": "string", "description": "Fact name (e.g. 'name', 'timezone')."},
                "value": {"type": "string", "description": "Fact value."},
            },
            "required": ["key", "value"],
        },
    },
    {
        "type": "function",
        "name": "add_memory_note",
        "description": "Store an important freeform note to remember across sessions.",
        "parameters": {
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "The note to remember."},
            },
            "required": ["text"],
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
    "reply_email": ("integrations.mail", "reply_to_message"),
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
    "get_intel": ("integrations.intel", "get_intel_voice"),
    "get_smart_tasks": ("integrations.intel", "get_smart_tasks"),
    "update_smart_task": ("integrations.intel", "update_smart_task"),
    "delete_smart_task": ("integrations.intel", "delete_smart_task"),
    "search_intel": ("integrations.intel", "search_intel"),
    "update_tracked_task": ("integrations.notion_tasks", "update_task"),
    "weekly_review": ("integrations.review", "get_weekly_review_voice"),
    "get_people": ("integrations.people", "get_all_people"),
    "get_person": ("integrations.people", "get_person"),
    "update_person": ("integrations.people", "update_person"),
    # Meeting prep
    "meeting_prep": ("integrations.meeting_prep", "get_meeting_prep"),
    "next_meeting_brief": ("integrations.meeting_prep", "get_next_meeting_brief"),
    # Decision tracking
    "log_decision": ("integrations.decisions", "log_decision"),
    "get_decisions": ("integrations.decisions", "get_decisions"),
    "update_decision": ("integrations.decisions", "update_decision"),
    # Strategic initiatives
    "create_initiative": ("integrations.initiatives", "create_initiative"),
    "get_initiatives": ("integrations.initiatives", "get_initiatives"),
    "update_initiative": ("integrations.initiatives", "update_initiative"),
    "complete_milestone": ("integrations.initiatives", "complete_milestone"),
    "add_key_result": ("integrations.initiatives", "add_key_result"),
    "update_key_result": ("integrations.initiatives", "update_key_result"),
    # Proactive alerts
    "get_alerts": ("integrations.alerts", "get_alerts"),
    # Epics & user stories
    "create_epic": ("integrations.epics", "create_epic"),
    "get_epics": ("integrations.epics", "get_epics"),
    "update_epic": ("integrations.epics", "update_epic"),
    "create_story": ("integrations.epics", "create_story"),
    "get_stories": ("integrations.epics", "get_stories"),
    "update_story": ("integrations.epics", "update_story"),
    "link_task_to_story": ("integrations.epics", "link_task_to_story"),
    # Team portfolio
    "get_team_portfolio": ("integrations.team_portfolio", "get_team_portfolio"),
    "get_member_portfolio": ("integrations.team_portfolio", "get_member_portfolio"),
    # User memory
    "remember_preference": ("integrations.memory", "set_preference"),
    "remember_fact": ("integrations.memory", "set_fact"),
    "add_memory_note": ("integrations.memory", "add_note"),
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


@app.get("/settings")
async def settings_page():
    """Serve the settings / configuration page."""
    return FileResponse(_STATIC_DIR / "settings.html")


@app.get("/people")
async def people_page():
    """Serve the people / contacts page."""
    return FileResponse(_STATIC_DIR / "people.html")


@app.get("/review")
async def review_page():
    """Serve the weekly review page."""
    return FileResponse(_STATIC_DIR / "review.html")


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
                    "instructions": _build_voice_prompt(),
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


@app.get("/api/settings/status")
async def get_integration_status():
    """Get connection status for all integrations."""
    from config import (
        OPENAI_API_KEY as _oai,
        ANTHROPIC_API_KEY as _ant,
        NOTION_API_KEY as _notion,
        MS_CLIENT_ID as _ms_id,
        MS_TENANT_ID as _ms_tid,
        TELEGRAM_BOT_TOKEN as _tg,
    )

    statuses = {}

    # Microsoft 365
    ms_configured = bool(_ms_id and _ms_tid)
    ms_signed_in = False
    ms_user = None
    if ms_configured:
        try:
            from integrations.ms_auth import get_token_silent
            token = get_token_silent()
            ms_signed_in = token is not None
        except Exception:
            pass
    statuses["microsoft365"] = {
        "configured": ms_configured,
        "signed_in": ms_signed_in,
        "user": ms_user,
        "services": ["Calendar", "Email", "To Do"],
    }

    # Notion
    notion_configured = bool(_notion)
    statuses["notion"] = {
        "configured": notion_configured,
        "services": ["Pages", "Meeting Notes", "Intelligence Scan"],
    }

    # OpenAI
    statuses["openai"] = {
        "configured": bool(_oai),
        "services": ["Voice (Realtime)", "Whisper", "TTS"],
    }

    # Anthropic
    statuses["anthropic"] = {
        "configured": bool(_ant),
        "services": ["Intelligence Extraction (Haiku)"],
    }

    # Telegram
    statuses["telegram"] = {
        "configured": bool(_tg),
        "services": ["Bot", "Reminders"],
    }

    return JSONResponse(statuses)


@app.get("/api/people")
async def get_people():
    """Get all people with merged intel + saved profile data."""
    from integrations.people import get_all_people

    try:
        return JSONResponse(get_all_people())
    except Exception as exc:
        logger.exception("Failed to get people data")
        return JSONResponse({"error": str(exc)}, status_code=500)


@app.get("/api/people/{name}")
async def get_person(name: str):
    """Get a single person's full profile."""
    from integrations.people import get_person as _get

    result = _get(name)
    if "error" in result:
        return JSONResponse(result, status_code=404)
    return JSONResponse(result)


class PersonUpdate(BaseModel):
    role: str = None
    relationship: str = None
    organization: str = None
    notes: str = None
    email: str = None


@app.patch("/api/people/{name}")
async def update_person(name: str, body: PersonUpdate):
    """Update a person's editable profile fields."""
    from integrations.people import update_person as _update

    fields = {k: v for k, v in body.dict().items() if v is not None}
    if not fields:
        return JSONResponse({"error": "No fields to update"}, status_code=400)
    result = _update(name, **fields)
    return JSONResponse(result)


class PersonCreate(BaseModel):
    name: str
    role: str = ""
    relationship: str = ""
    organization: str = ""
    notes: str = ""
    email: str = ""


@app.post("/api/people")
async def add_person(body: PersonCreate):
    """Manually add a person."""
    from integrations.people import add_person as _add

    fields = {k: v for k, v in body.dict().items() if k != "name" and v}
    result = _add(body.name, **fields)
    if "error" in result:
        return JSONResponse(result, status_code=409)
    return JSONResponse(result, status_code=201)


@app.delete("/api/people/{name}")
async def delete_person(name: str):
    """Remove a person's saved profile."""
    from integrations.people import delete_person as _delete

    result = _delete(name)
    if "error" in result:
        return JSONResponse(result, status_code=404)
    return JSONResponse(result)


@app.get("/api/memory")
async def get_memory_api():
    """Return all stored user memory (facts, preferences, notes)."""
    from integrations.memory import get_memory
    return JSONResponse(get_memory())


class MemoryFactBody(BaseModel):
    key: str
    value: str


class MemoryNoteBody(BaseModel):
    text: str


@app.put("/api/memory/fact")
async def set_memory_fact(body: MemoryFactBody):
    from integrations.memory import set_fact
    return JSONResponse(set_fact(body.key, body.value))


@app.put("/api/memory/preference")
async def set_memory_pref(body: MemoryFactBody):
    from integrations.memory import set_preference
    return JSONResponse(set_preference(body.key, body.value))


@app.post("/api/memory/note")
async def add_memory_note_api(body: MemoryNoteBody):
    from integrations.memory import add_note
    return JSONResponse(add_note(body.text))


@app.delete("/api/memory/note/{index}")
async def delete_memory_note_api(index: int):
    from integrations.memory import delete_note
    result = delete_note(index)
    if not result.get("ok"):
        return JSONResponse(result, status_code=400)
    return JSONResponse(result)


@app.delete("/api/memory/fact/{key}")
async def delete_memory_fact(key: str):
    from integrations.memory import _load, _save
    data = _load()
    if key in data.get("facts", {}):
        del data["facts"][key]
        _save(data)
    return JSONResponse({"ok": True})


@app.delete("/api/memory/preference/{key}")
async def delete_memory_pref(key: str):
    from integrations.memory import _load, _save
    data = _load()
    if key in data.get("preferences", {}):
        del data["preferences"][key]
        _save(data)
    return JSONResponse({"ok": True})


@app.delete("/api/memory")
async def clear_memory_api():
    from integrations.memory import clear_memory
    return JSONResponse(clear_memory())


# ── Notion Webhook Push ──────────────────────────────────────────────

@app.get("/api/webhook/status")
async def webhook_status():
    """Return current webhook health and stats."""
    from integrations.webhook_status import get_status
    return JSONResponse(get_status())


class WebhookEnableBody(BaseModel):
    secret: str = ""


@app.post("/api/webhook/enable")
async def webhook_enable(body: WebhookEnableBody):
    from integrations.webhook_status import enable
    return JSONResponse(enable(body.secret or None))


@app.post("/api/webhook/disable")
async def webhook_disable():
    from integrations.webhook_status import disable
    return JSONResponse(disable())


@app.get("/api/tunnel/status")
async def tunnel_status():
    """Return current Cloudflare Tunnel status."""
    status_file = Path(__file__).parent.parent / "tunnel_status.json"
    if status_file.exists():
        try:
            data = json.loads(status_file.read_text())
            return JSONResponse(data)
        except (json.JSONDecodeError, OSError):
            pass
    return JSONResponse({"running": False, "url": None})


@app.post("/api/notion/webhook")
async def notion_webhook(request: Request):
    """Receive Notion webhook events and trigger incremental scans.

    Notion sends:
    - A verification challenge on first setup (respond with challenge value)
    - page.content_updated, comment.created, etc. for real events
    """
    import hmac
    import hashlib
    from integrations.webhook_status import get_secret, record_event, record_error

    body_bytes = await request.body()

    # Verify HMAC signature if a secret is configured
    secret = get_secret()
    if secret:
        sig_header = request.headers.get("x-notion-signature", "")
        expected = "v0=" + hmac.HMAC(
            secret.encode(), body_bytes, hashlib.sha256
        ).hexdigest()
        if not hmac.compare_digest(sig_header, expected):
            record_error("Invalid signature")
            return JSONResponse({"error": "Invalid signature"}, status_code=401)

    try:
        payload = json.loads(body_bytes)
    except json.JSONDecodeError:
        record_error("Invalid JSON payload")
        return JSONResponse({"error": "Invalid JSON"}, status_code=400)

    # Handle Notion verification challenge
    if "challenge" in payload:
        record_event("verification")
        return JSONResponse({"challenge": payload["challenge"]})

    event_type = payload.get("type", "unknown")
    record_event(event_type)

    # Trigger incremental scan in background for content events
    if event_type in ("page.content_updated", "page.created", "page.properties_updated"):
        async def _background_scan():
            try:
                from integrations.intel import scan_notion
                await scan_notion(max_pages=10, full_scan=False)
                logger.info("Webhook-triggered incremental scan complete")
            except Exception as exc:
                logger.warning("Webhook-triggered scan failed: %s", exc)
                record_error(f"Scan failed: {exc}")

        asyncio.create_task(_background_scan())

    return JSONResponse({"ok": True})


@app.get("/api/review/weekly")
async def get_weekly_review():
    """Get weekly review data — task trends, delegation patterns, stale items."""
    from integrations.intel import get_intel as _get_intel
    from integrations.notion_tasks import get_tracked_tasks as _get_tracked
    from datetime import datetime, timezone, timedelta

    try:
        intel = _get_intel()
        smart_tasks = intel.get("smart_tasks", [])
        scan_history = intel.get("scan_history", [])
        topics = intel.get("topics", {})
        people = intel.get("people", {})

        now = datetime.now(timezone.utc)
        week_ago = now - timedelta(days=7)

        # Task status breakdown
        open_tasks = [t for t in smart_tasks if t.get("status") != "done"]
        done_tasks = [t for t in smart_tasks if t.get("status") == "done"]

        # Quadrant distribution
        quadrant_counts = {1: 0, 2: 0, 3: 0, 4: 0}
        for t in open_tasks:
            q = t.get("priority", {}).get("quadrant", 4)
            quadrant_counts[q] = quadrant_counts.get(q, 0) + 1

        # Overdue tasks
        overdue = []
        for t in open_tasks:
            fud = t.get("follow_up_date", "")
            if fud:
                try:
                    due = datetime.fromisoformat(fud)
                    if due.tzinfo is None:
                        due = due.replace(tzinfo=timezone.utc)
                    if due < now:
                        days_overdue = (now - due).days
                        overdue.append({
                            "id": t.get("id"),
                            "description": t.get("description", ""),
                            "owner": t.get("owner", ""),
                            "follow_up_date": fud,
                            "days_overdue": days_overdue,
                        })
                except (ValueError, TypeError):
                    pass
        overdue.sort(key=lambda x: x["days_overdue"], reverse=True)

        # Delegation breakdown
        delegation = {}
        for t in open_tasks:
            owner = t.get("owner", "Unassigned")
            delegation.setdefault(owner, {"count": 0, "overdue": 0, "tasks": []})
            delegation[owner]["count"] += 1
            delegation[owner]["tasks"].append({
                "description": t.get("description", "")[:80],
                "status": t.get("status"),
                "quadrant": t.get("priority", {}).get("quadrant"),
            })
            fud = t.get("follow_up_date", "")
            if fud:
                try:
                    due = datetime.fromisoformat(fud)
                    if due.tzinfo is None:
                        due = due.replace(tzinfo=timezone.utc)
                    if due < now:
                        delegation[owner]["overdue"] += 1
                except (ValueError, TypeError):
                    pass

        # Tracked tasks stats
        tracked_all = _get_tracked(include_completed=True)
        tracked_open = _get_tracked()
        tracked_tasks_list = tracked_all.get("tasks", [])

        # Stale tracked tasks (open > 7 days)
        stale_tracked = []
        for t in tracked_open.get("tasks", []):
            created = t.get("created_at", "")
            if created:
                try:
                    cdt = datetime.fromisoformat(created)
                    if cdt.tzinfo is None:
                        cdt = cdt.replace(tzinfo=timezone.utc)
                    age = (now - cdt).days
                    if age >= 7:
                        stale_tracked.append({
                            "id": t.get("id"),
                            "description": t.get("description", ""),
                            "owner": t.get("owner", ""),
                            "age_days": age,
                        })
                except (ValueError, TypeError):
                    pass
        stale_tracked.sort(key=lambda x: x["age_days"], reverse=True)

        return JSONResponse({
            "period": {
                "start": week_ago.isoformat(),
                "end": now.isoformat(),
            },
            "smart_tasks": {
                "total": len(smart_tasks),
                "open": len(open_tasks),
                "done": len(done_tasks),
                "quadrants": quadrant_counts,
                "overdue": overdue,
                "overdue_count": len(overdue),
            },
            "tracked_tasks": {
                "total": len(tracked_tasks_list),
                "open": tracked_open.get("count", 0),
                "stale": stale_tracked,
                "stale_count": len(stale_tracked),
            },
            "delegation": delegation,
            "topics": topics,
            "people": people,
            "scan_history": scan_history[-7:],  # Last 7 scans
        })

    except Exception as exc:
        logger.exception("Failed to get weekly review")
        return JSONResponse({"error": str(exc)}, status_code=500)


# ---------------------------------------------------------------------------
# Meeting prep API
# ---------------------------------------------------------------------------

@app.get("/api/meeting-prep")
async def api_meeting_prep(event_id: str = "", minutes_ahead: int = 480):
    """Get meeting prep for a specific event or the next upcoming meeting."""
    from integrations.meeting_prep import get_meeting_prep

    try:
        result = await get_meeting_prep(
            event_id=event_id, minutes_ahead=minutes_ahead,
        )
        return JSONResponse(result)
    except Exception as exc:
        logger.exception("Failed to get meeting prep")
        return JSONResponse({"error": str(exc)}, status_code=500)


# ---------------------------------------------------------------------------
# Decision register API
# ---------------------------------------------------------------------------

class DecisionCreate(BaseModel):
    title: str
    rationale: str = ""
    decided_by: str = ""
    stakeholders: list[str] = []
    context: str = ""
    initiative: str = ""
    status: str = "decided"


class DecisionUpdate(BaseModel):
    status: str = None
    rationale: str = None
    outcome_notes: str = None
    stakeholders: list[str] = None
    initiative: str = None
    title: str = None


@app.get("/api/decisions")
async def api_get_decisions(
    status: str = "",
    initiative: str = "",
    stakeholder: str = "",
):
    """Get decisions with optional filters."""
    from integrations.decisions import get_decisions as _get

    return JSONResponse(_get(status=status, initiative=initiative, stakeholder=stakeholder))


@app.post("/api/decisions")
async def api_create_decision(body: DecisionCreate):
    """Log a new decision."""
    from integrations.decisions import log_decision

    result = log_decision(
        title=body.title,
        rationale=body.rationale,
        decided_by=body.decided_by,
        stakeholders=body.stakeholders,
        context=body.context,
        initiative=body.initiative,
        status=body.status,
    )
    return JSONResponse(result, status_code=201)


@app.patch("/api/decisions/{decision_id}")
async def api_update_decision(decision_id: str, body: DecisionUpdate):
    """Update a decision."""
    from integrations.decisions import update_decision

    fields = {k: v for k, v in body.dict().items() if v is not None}
    if not fields:
        return JSONResponse({"error": "No fields to update"}, status_code=400)
    result = update_decision(decision_id, **fields)
    if "error" in result:
        return JSONResponse(result, status_code=404)
    return JSONResponse(result)


@app.delete("/api/decisions/{decision_id}")
async def api_delete_decision(decision_id: str):
    """Delete a decision."""
    from integrations.decisions import delete_decision

    result = delete_decision(decision_id)
    if "error" in result:
        return JSONResponse(result, status_code=404)
    return JSONResponse(result)


# ---------------------------------------------------------------------------
# Strategic initiatives API
# ---------------------------------------------------------------------------

class InitiativeCreate(BaseModel):
    title: str
    description: str = ""
    owner: str = ""
    quarter: str = ""
    status: str = "on_track"
    priority: str = "high"
    milestones: list[str] = []


class InitiativeUpdate(BaseModel):
    title: str = None
    description: str = None
    owner: str = None
    quarter: str = None
    status: str = None
    priority: str = None


class KeyResultCreate(BaseModel):
    initiative_id: str
    description: str
    target: str = ""
    current: str = ""
    owner: str = ""


class KeyResultUpdate(BaseModel):
    current: str = None
    status: str = None
    description: str = None


@app.get("/api/initiatives")
async def api_get_initiatives(
    status: str = "",
    owner: str = "",
    quarter: str = "",
    priority: str = "",
):
    """Get strategic initiatives with optional filters."""
    from integrations.initiatives import get_initiatives as _get

    return JSONResponse(_get(status=status, owner=owner, quarter=quarter, priority=priority))


@app.post("/api/initiatives")
async def api_create_initiative(body: InitiativeCreate):
    """Create a new strategic initiative."""
    from integrations.initiatives import create_initiative

    result = create_initiative(
        title=body.title,
        description=body.description,
        owner=body.owner,
        quarter=body.quarter,
        status=body.status,
        priority=body.priority,
        milestones=body.milestones,
    )
    return JSONResponse(result, status_code=201)


@app.patch("/api/initiatives/{initiative_id}")
async def api_update_initiative(initiative_id: str, body: InitiativeUpdate):
    """Update a strategic initiative."""
    from integrations.initiatives import update_initiative

    fields = {k: v for k, v in body.dict().items() if v is not None}
    if not fields:
        return JSONResponse({"error": "No fields to update"}, status_code=400)
    result = update_initiative(initiative_id, **fields)
    if "error" in result:
        return JSONResponse(result, status_code=404)
    return JSONResponse(result)


@app.delete("/api/initiatives/{initiative_id}")
async def api_delete_initiative(initiative_id: str):
    """Delete an initiative."""
    from integrations.initiatives import delete_initiative

    result = delete_initiative(initiative_id)
    if "error" in result:
        return JSONResponse(result, status_code=404)
    return JSONResponse(result)


@app.post("/api/initiatives/{initiative_id}/milestones/{idx}/complete")
async def api_complete_milestone(initiative_id: str, idx: int):
    """Complete a milestone."""
    from integrations.initiatives import complete_milestone

    result = complete_milestone(initiative_id, idx)
    if "error" in result:
        return JSONResponse(result, status_code=404)
    return JSONResponse(result)


@app.post("/api/initiatives/key-results")
async def api_add_key_result(body: KeyResultCreate):
    """Add a key result to an initiative."""
    from integrations.initiatives import add_key_result

    result = add_key_result(
        initiative_id=body.initiative_id,
        description=body.description,
        target=body.target,
        current=body.current,
        owner=body.owner,
    )
    if "error" in result:
        return JSONResponse(result, status_code=404)
    return JSONResponse(result, status_code=201)


@app.patch("/api/initiatives/key-results/{kr_id}")
async def api_update_key_result(kr_id: str, body: KeyResultUpdate):
    """Update a key result."""
    from integrations.initiatives import update_key_result

    fields = {k: v for k, v in body.dict().items() if v is not None}
    if not fields:
        return JSONResponse({"error": "No fields to update"}, status_code=400)
    result = update_key_result(kr_id, **fields)
    if "error" in result:
        return JSONResponse(result, status_code=404)
    return JSONResponse(result)


# ---------------------------------------------------------------------------
# Proactive alerts API
# ---------------------------------------------------------------------------

@app.get("/api/alerts")
async def api_get_alerts():
    """Get proactive alerts — bottlenecks, escalations, conflicts, risks."""
    from integrations.alerts import get_alerts as _get

    try:
        result = await _get()
        return JSONResponse(result)
    except Exception as exc:
        logger.exception("Failed to get alerts")
        return JSONResponse({"error": str(exc)}, status_code=500)


# ---------------------------------------------------------------------------
# Strategic summary API (combines initiatives + decisions + alerts)
# ---------------------------------------------------------------------------

@app.get("/api/strategic-summary")
async def api_strategic_summary():
    """Get a combined strategic overview for the executive dashboard."""
    result = {}

    try:
        from integrations.initiatives import get_strategic_summary
        result["initiatives"] = get_strategic_summary()
    except Exception as exc:
        logger.debug("Initiatives not available: %s", exc)
        result["initiatives"] = {"available": False}

    try:
        from integrations.decisions import get_decision_summary
        result["decisions"] = get_decision_summary()
    except Exception as exc:
        logger.debug("Decisions not available: %s", exc)
        result["decisions"] = {"available": False}

    try:
        from integrations.alerts import get_alerts as _alerts
        alerts_data = await _alerts()
        result["alerts"] = alerts_data
    except Exception as exc:
        logger.debug("Alerts not available: %s", exc)
        result["alerts"] = {"available": False}

    return JSONResponse(result)


# ---------------------------------------------------------------------------
# Epics & user stories API
# ---------------------------------------------------------------------------

class EpicCreate(BaseModel):
    title: str
    description: str = ""
    owner: str = ""
    initiative_id: str = ""
    quarter: str = ""
    priority: str = "high"
    acceptance_criteria: list[str] = []


class EpicUpdate(BaseModel):
    title: str = None
    description: str = None
    owner: str = None
    status: str = None
    priority: str = None
    quarter: str = None
    initiative_id: str = None
    acceptance_criteria: list[str] = None


class StoryCreate(BaseModel):
    epic_id: str
    title: str
    description: str = ""
    owner: str = ""
    size: str = "M"
    priority: str = "medium"
    acceptance_criteria: list[str] = []


class StoryUpdate(BaseModel):
    title: str = None
    description: str = None
    owner: str = None
    status: str = None
    priority: str = None
    size: str = None
    acceptance_criteria: list[str] = None


class LinkTask(BaseModel):
    task_id: str


@app.get("/api/epics")
async def api_get_epics(
    status: str = "",
    owner: str = "",
    initiative_id: str = "",
    quarter: str = "",
    priority: str = "",
):
    """Get epics with optional filters."""
    from integrations.epics import get_epics

    return JSONResponse(get_epics(
        status=status, owner=owner, initiative_id=initiative_id,
        quarter=quarter, priority=priority,
    ))


@app.post("/api/epics")
async def api_create_epic(body: EpicCreate):
    """Create a new epic."""
    from integrations.epics import create_epic

    result = create_epic(
        title=body.title,
        description=body.description,
        owner=body.owner,
        initiative_id=body.initiative_id,
        quarter=body.quarter,
        priority=body.priority,
        acceptance_criteria=body.acceptance_criteria,
    )
    return JSONResponse(result, status_code=201)


@app.patch("/api/epics/{epic_id}")
async def api_update_epic(epic_id: str, body: EpicUpdate):
    """Update an epic."""
    from integrations.epics import update_epic

    fields = {k: v for k, v in body.dict().items() if v is not None}
    if not fields:
        return JSONResponse({"error": "No fields to update"}, status_code=400)
    result = update_epic(epic_id, **fields)
    if "error" in result:
        return JSONResponse(result, status_code=404)
    return JSONResponse(result)


@app.delete("/api/epics/{epic_id}")
async def api_delete_epic(epic_id: str):
    """Delete an epic and its stories."""
    from integrations.epics import delete_epic

    result = delete_epic(epic_id)
    if "error" in result:
        return JSONResponse(result, status_code=404)
    return JSONResponse(result)


@app.get("/api/stories")
async def api_get_stories(
    epic_id: str = "",
    owner: str = "",
    status: str = "",
    priority: str = "",
    size: str = "",
):
    """Get user stories with optional filters."""
    from integrations.epics import get_stories

    return JSONResponse(get_stories(
        epic_id=epic_id, owner=owner, status=status,
        priority=priority, size=size,
    ))


@app.post("/api/stories")
async def api_create_story(body: StoryCreate):
    """Create a new user story."""
    from integrations.epics import create_story

    result = create_story(
        epic_id=body.epic_id,
        title=body.title,
        description=body.description,
        owner=body.owner,
        size=body.size,
        priority=body.priority,
        acceptance_criteria=body.acceptance_criteria,
    )
    if "error" in result:
        return JSONResponse(result, status_code=404)
    return JSONResponse(result, status_code=201)


@app.patch("/api/stories/{story_id}")
async def api_update_story(story_id: str, body: StoryUpdate):
    """Update a user story."""
    from integrations.epics import update_story

    fields = {k: v for k, v in body.dict().items() if v is not None}
    if not fields:
        return JSONResponse({"error": "No fields to update"}, status_code=400)
    result = update_story(story_id, **fields)
    if "error" in result:
        return JSONResponse(result, status_code=404)
    return JSONResponse(result)


@app.delete("/api/stories/{story_id}")
async def api_delete_story(story_id: str):
    """Delete a user story."""
    from integrations.epics import delete_story

    result = delete_story(story_id)
    if "error" in result:
        return JSONResponse(result, status_code=404)
    return JSONResponse(result)


@app.post("/api/stories/{story_id}/link-task")
async def api_link_task(story_id: str, body: LinkTask):
    """Link a task to a user story."""
    from integrations.epics import link_task_to_story

    result = link_task_to_story(story_id, body.task_id)
    if "error" in result:
        return JSONResponse(result, status_code=404)
    return JSONResponse(result)


# ---------------------------------------------------------------------------
# Team portfolio API
# ---------------------------------------------------------------------------

@app.get("/api/portfolio")
async def api_team_portfolio(
    owner: str = "",
    quarter: str = "",
    include_done: bool = False,
):
    """Get team portfolio view — per-member workload breakdown."""
    from integrations.team_portfolio import get_team_portfolio

    try:
        result = get_team_portfolio(
            owner=owner, quarter=quarter, include_done=include_done,
        )
        return JSONResponse(result)
    except Exception as exc:
        logger.exception("Failed to get team portfolio")
        return JSONResponse({"error": str(exc)}, status_code=500)


@app.get("/api/portfolio/{name}")
async def api_member_portfolio(name: str, include_done: bool = False):
    """Get a single member's portfolio view."""
    from integrations.team_portfolio import get_member_portfolio

    result = get_member_portfolio(name=name, include_done=include_done)
    if "error" in result:
        return JSONResponse(result, status_code=404)
    return JSONResponse(result)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
