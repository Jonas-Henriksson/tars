"""End-of-day briefing — compiles a comprehensive daily summary.

Pulls together calendar events, Notion meeting notes, tracked tasks,
emails, and generates proactive recommendations. Designed to function
like a professional executive assistant's end-of-day debrief.

The briefing includes:
- Day summary: meetings attended, topics covered
- Action items: explicit tasks extracted from today's notes
- Follow-up items: tasks assigned to others needing a nudge
- Stale tasks: items with no progress that need attention
- Proactive suggestions: proposed next steps, risks, opportunities
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

logger = logging.getLogger(__name__)


async def compile_daily_briefing() -> dict[str, Any]:
    """Compile a full end-of-day briefing.

    Gathers data from all available sources and structures it into
    sections suitable for an executive summary.

    Returns:
        Dict with structured briefing sections.
    """
    sections: dict[str, Any] = {}

    # 1. Today's calendar
    sections["calendar"] = await _get_calendar_section()

    # 2. Today's Notion activity
    sections["notion_activity"] = await _get_notion_section()

    # 3. Tracked tasks analysis
    sections["task_analysis"] = _get_task_analysis()

    # 4. Email summary
    sections["email"] = await _get_email_section()

    # 5. Proactive recommendations
    sections["recommendations"] = _generate_recommendations(sections)

    # 6. Meta
    sections["generated_at"] = datetime.now(timezone.utc).isoformat()

    return sections


async def _get_calendar_section() -> dict:
    """Get today's calendar events."""
    try:
        from integrations.calendar import get_events
        data = await get_events(days=1, max_results=20)
        return {
            "events": data.get("events", []),
            "count": data.get("count", 0),
            "available": True,
        }
    except Exception as exc:
        logger.debug("Calendar not available: %s", exc)
        return {"events": [], "count": 0, "available": False, "reason": str(exc)}


async def _get_email_section() -> dict:
    """Get today's email activity."""
    try:
        from integrations.mail import get_messages
        unread = await get_messages(unread_only=True, max_results=15)
        recent = await get_messages(unread_only=False, max_results=10)
        return {
            "unread": unread.get("messages", []),
            "unread_count": unread.get("count", 0),
            "recent": recent.get("messages", []),
            "recent_count": recent.get("count", 0),
            "available": True,
        }
    except Exception as exc:
        logger.debug("Email not available: %s", exc)
        return {"unread": [], "unread_count": 0, "recent": [], "recent_count": 0,
                "available": False, "reason": str(exc)}


async def _get_notion_section() -> dict:
    """Get Notion pages edited today."""
    try:
        from integrations.notion import get_recently_edited_pages, is_configured
        if not is_configured():
            return {"pages": [], "count": 0, "available": False, "reason": "Not configured"}

        today_start = datetime.now(timezone.utc).replace(
            hour=0, minute=0, second=0, microsecond=0,
        ).isoformat()

        data = await get_recently_edited_pages(since=today_start, max_results=20)
        pages = data.get("pages", [])

        # Get content previews for each page
        pages_with_content = []
        from integrations.notion import get_page_content
        for page in pages[:10]:  # Limit to 10 to avoid API rate limits
            try:
                content = await get_page_content(page["id"])
                page["content_preview"] = content["content"][:600]
                page["full_content"] = content["content"]
            except Exception:
                page["content_preview"] = ""
                page["full_content"] = ""
            pages_with_content.append(page)

        return {
            "pages": pages_with_content,
            "count": len(pages_with_content),
            "available": True,
        }
    except Exception as exc:
        logger.debug("Notion not available: %s", exc)
        return {"pages": [], "count": 0, "available": False, "reason": str(exc)}


def _get_task_analysis() -> dict:
    """Analyze tracked tasks for the briefing."""
    try:
        from integrations.notion_tasks import get_tracked_tasks

        all_tasks = get_tracked_tasks(include_completed=True)
        open_tasks = get_tracked_tasks(status="open")
        followed_up = get_tracked_tasks(status="followed_up")

        tasks_list = all_tasks.get("tasks", [])
        open_list = open_tasks.get("tasks", [])

        # Identify stale tasks (open for more than 3 days with no follow-up)
        now = datetime.now(timezone.utc)
        stale_tasks = []
        for task in open_list:
            created = task.get("created_at", "")
            if not created:
                continue
            try:
                created_dt = datetime.fromisoformat(created)
                age_days = (now - created_dt).days
                if age_days >= 3:
                    task_copy = dict(task)
                    task_copy["age_days"] = age_days
                    stale_tasks.append(task_copy)
            except (ValueError, TypeError):
                continue

        # Sort stale tasks by age (oldest first)
        stale_tasks.sort(key=lambda t: t.get("age_days", 0), reverse=True)

        # Tasks assigned to others that are still open (follow-up candidates)
        others_tasks = [
            t for t in open_list
            if t.get("owner", "").strip() and t.get("owner", "") != "Unassigned"
        ]

        # Group by owner for delegation overview
        by_owner: dict[str, list] = {}
        for t in open_list:
            owner = t.get("owner", "Unassigned")
            by_owner.setdefault(owner, []).append(t)

        return {
            "total": len(tasks_list),
            "open_count": len(open_list),
            "followed_up_count": followed_up.get("count", 0),
            "stale_tasks": stale_tasks,
            "stale_count": len(stale_tasks),
            "others_open": others_tasks,
            "others_open_count": len(others_tasks),
            "by_owner": {k: len(v) for k, v in by_owner.items()},
            "open_tasks": open_list,
            "available": True,
        }
    except Exception as exc:
        logger.debug("Task analysis not available: %s", exc)
        return {"total": 0, "open_count": 0, "stale_tasks": [], "stale_count": 0,
                "available": False, "reason": str(exc)}


def _generate_recommendations(sections: dict) -> list[dict]:
    """Generate proactive recommendations based on all gathered data.

    Analyzes the day's activity and task state to suggest:
    - Follow-ups on stale tasks
    - Status check-ins with task owners
    - Unread emails that may need responses
    - Missing action items from meetings
    - Suggested next steps
    """
    recs: list[dict] = []

    # Stale task follow-ups
    task_data = sections.get("task_analysis", {})
    for task in task_data.get("stale_tasks", [])[:5]:
        age = task.get("age_days", 0)
        owner = task.get("owner", "Unassigned")
        desc = task.get("description", "")

        if owner and owner != "Unassigned":
            recs.append({
                "type": "follow_up",
                "priority": "high" if age >= 7 else "medium",
                "title": f"Follow up with {owner}",
                "detail": f"'{desc}' has been open for {age} days. "
                          f"Consider sending {owner} a status check.",
                "task_id": task.get("id"),
                "suggested_action": "send_email",
            })
        else:
            recs.append({
                "type": "stale_task",
                "priority": "high" if age >= 7 else "medium",
                "title": f"Stale task needs attention",
                "detail": f"'{desc}' has been open for {age} days with no owner. "
                          f"Consider assigning it or defining next steps.",
                "task_id": task.get("id"),
                "suggested_action": "assign_or_close",
            })

    # Owners with multiple open tasks — suggest a check-in
    by_owner = task_data.get("by_owner", {})
    for owner, count in by_owner.items():
        if owner != "Unassigned" and count >= 3:
            recs.append({
                "type": "check_in",
                "priority": "medium",
                "title": f"Check in with {owner}",
                "detail": f"{owner} has {count} open tasks. "
                          f"Consider a quick sync to review priorities and progress.",
                "suggested_action": "schedule_meeting",
            })

    # Unread email pile-up
    email_data = sections.get("email", {})
    unread_count = email_data.get("unread_count", 0)
    if unread_count >= 10:
        recs.append({
            "type": "email_backlog",
            "priority": "medium",
            "title": "Email backlog growing",
            "detail": f"You have {unread_count} unread emails. "
                      f"Consider a triage session to avoid missing important items.",
            "suggested_action": "review_emails",
        })

    # Meetings without action items
    notion_data = sections.get("notion_activity", {})
    for page in notion_data.get("pages", []):
        content = page.get("full_content", "")
        title = page.get("title", "")
        has_tasks = any(
            marker in content.lower()
            for marker in ["[ ]", "[x]", "action:", "todo:", "task:"]
        )
        is_meeting = any(
            kw in title.lower()
            for kw in ["meeting", "standup", "sync", "1:1", "retro",
                        "planning", "review", "check-in", "kickoff"]
        )
        if is_meeting and not has_tasks and content.strip():
            recs.append({
                "type": "missing_actions",
                "priority": "low",
                "title": f"No action items in '{title}'",
                "detail": f"Meeting notes for '{title}' have no explicit tasks. "
                          f"Review the notes and extract any implicit commitments.",
                "page_id": page.get("id"),
                "suggested_action": "extract_tasks",
            })

    # Open tasks with no topic (may need categorization)
    open_tasks = task_data.get("open_tasks", [])
    untopiced = [t for t in open_tasks if not t.get("topic")]
    if len(untopiced) >= 3:
        recs.append({
            "type": "organization",
            "priority": "low",
            "title": "Uncategorized tasks",
            "detail": f"{len(untopiced)} open tasks have no topic. "
                      f"Consider grouping them for better tracking.",
            "suggested_action": "categorize",
        })

    # Sort by priority
    priority_order = {"high": 0, "medium": 1, "low": 2}
    recs.sort(key=lambda r: priority_order.get(r.get("priority", "low"), 3))

    return recs


def format_briefing_text(briefing: dict) -> str:
    """Format a briefing dict into readable text for Telegram/chat.

    Args:
        briefing: The compiled briefing dict.

    Returns:
        Formatted text string.
    """
    lines = []
    lines.append("DAILY BRIEFING")
    lines.append("=" * 40)
    lines.append("")

    # Calendar
    cal = briefing.get("calendar", {})
    if cal.get("available") and cal.get("count", 0) > 0:
        lines.append(f"MEETINGS ({cal['count']})")
        lines.append("-" * 20)
        for evt in cal.get("events", []):
            subj = evt.get("subject", "Untitled")
            start = evt.get("start", "")
            end = evt.get("end", "")
            if start:
                start = start.split("T")[-1][:5] if "T" in start else start
            if end:
                end = end.split("T")[-1][:5] if "T" in end else end
            time_str = f"{start}-{end}" if start and end else start
            lines.append(f"  {time_str}  {subj}")
        lines.append("")

    # Notion activity
    notion = briefing.get("notion_activity", {})
    if notion.get("available") and notion.get("count", 0) > 0:
        lines.append(f"PAGES UPDATED TODAY ({notion['count']})")
        lines.append("-" * 20)
        for page in notion.get("pages", []):
            lines.append(f"  {page.get('title', 'Untitled')}")
        lines.append("")

    # Task analysis
    tasks = briefing.get("task_analysis", {})
    if tasks.get("available"):
        lines.append(f"TASKS — {tasks.get('open_count', 0)} open, "
                     f"{tasks.get('stale_count', 0)} stale, "
                     f"{tasks.get('others_open_count', 0)} delegated")
        lines.append("-" * 20)
        stale = tasks.get("stale_tasks", [])
        if stale:
            lines.append("  Stale (need attention):")
            for t in stale[:5]:
                lines.append(f"    [{t.get('age_days', '?')}d] {t.get('description', '')}"
                             f" ({t.get('owner', 'Unassigned')})")
        lines.append("")

    # Email
    email = briefing.get("email", {})
    if email.get("available"):
        lines.append(f"EMAIL — {email.get('unread_count', 0)} unread")
        lines.append("-" * 20)
        for msg in email.get("unread", [])[:5]:
            sender = msg.get("from", "Unknown")
            subj = msg.get("subject", "No subject")
            lines.append(f"  {sender}: {subj}")
        if email.get("unread_count", 0) > 5:
            lines.append(f"  ... and {email['unread_count'] - 5} more")
        lines.append("")

    # Recommendations
    recs = briefing.get("recommendations", [])
    if recs:
        lines.append(f"RECOMMENDATIONS ({len(recs)})")
        lines.append("-" * 20)
        for r in recs:
            priority_mark = {"high": "!!!", "medium": "!!", "low": "!"}.get(
                r.get("priority", ""), "")
            lines.append(f"  {priority_mark} {r.get('title', '')}")
            lines.append(f"     {r.get('detail', '')}")
        lines.append("")

    lines.append("=" * 40)
    return "\n".join(lines)
