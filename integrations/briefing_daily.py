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

    # 5. Strategic context (initiatives, decisions, alerts)
    sections["strategic"] = _get_strategic_context()

    # 6. New smart tasks from today's scan
    sections["new_tasks_today"] = _get_new_tasks_today()

    # 7. New epics/stories created today
    sections["new_epics_today"] = _get_new_epics_today()

    # 8. Orphaned tasks (not linked to any epic/story)
    sections["orphaned_tasks"] = _get_orphaned_tasks()

    # 9. Proactive recommendations
    sections["recommendations"] = _generate_recommendations(sections)

    # 10. Meta
    sections["generated_at"] = datetime.now(timezone.utc).isoformat()

    # 8. Voice-friendly summary
    sections["voice_summary"] = _build_voice_summary(sections)

    return sections


def _build_voice_summary(sections: dict) -> str:
    """Build a concise narrative summary for voice readback."""
    parts = []

    # Calendar
    cal = sections.get("calendar", {})
    if cal.get("available") and cal.get("count", 0) > 0:
        parts.append(f"You had {cal['count']} calendar event{'s' if cal['count'] != 1 else ''} today")
    elif not cal.get("available"):
        parts.append("Calendar is not connected")

    # Notion activity
    notion = sections.get("notion_activity", {})
    if notion.get("available") and notion.get("count", 0) > 0:
        parts.append(f"{notion['count']} Notion page{'s were' if notion['count'] != 1 else ' was'} edited today")
    elif not notion.get("available"):
        parts.append("Notion is not connected")

    # Tasks
    tasks = sections.get("task_analysis", {})
    if tasks.get("open_count", 0) > 0:
        parts.append(f"{tasks['open_count']} open task{'s' if tasks['open_count'] != 1 else ''}")
        if tasks.get("stale_count", 0) > 0:
            parts.append(f"{tasks['stale_count']} stale and need attention")
        if tasks.get("others_open_count", 0) > 0:
            parts.append(f"{tasks['others_open_count']} delegated to others")

    # Email
    email = sections.get("email", {})
    if email.get("available") and email.get("unread_count", 0) > 0:
        parts.append(f"{email['unread_count']} unread email{'s' if email['unread_count'] != 1 else ''}")
    elif not email.get("available"):
        parts.append("Email is not connected")

    # Strategic context
    strategic = sections.get("strategic", {})
    if strategic.get("available"):
        initiatives = strategic.get("initiatives", {})
        at_risk = initiatives.get("at_risk", 0)
        off_track = initiatives.get("off_track", 0)
        if at_risk or off_track:
            risk_parts = []
            if at_risk:
                risk_parts.append(f"{at_risk} at risk")
            if off_track:
                risk_parts.append(f"{off_track} off track")
            parts.append(f"Strategic initiatives: {', '.join(risk_parts)}")

        decisions = strategic.get("decisions", {})
        pending = decisions.get("pending_count", 0)
        if pending:
            parts.append(f"{pending} decision{'s' if pending != 1 else ''} pending")

    # Recommendations
    recs = sections.get("recommendations", [])
    if recs:
        high = sum(1 for r in recs if r.get("priority") == "high")
        if high:
            parts.append(f"{high} high-priority recommendation{'s' if high != 1 else ''}")
        else:
            parts.append(f"{len(recs)} recommendation{'s' if len(recs) != 1 else ''}")

    if not parts:
        return "No data available yet. Connect your integrations to get started."

    return ". ".join(parts) + "."


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


def _get_strategic_context() -> dict:
    """Get strategic layer data for the briefing."""
    result: dict[str, Any] = {"available": False}

    # Initiatives summary
    try:
        from integrations.initiatives import get_strategic_summary
        summary = get_strategic_summary()
        result["initiatives"] = {
            "total": summary.get("total", 0),
            "at_risk": summary.get("at_risk_count", 0),
            "off_track": summary.get("off_track_count", 0),
            "at_risk_names": [i.get("title", "") for i in summary.get("at_risk", [])],
            "off_track_names": [i.get("title", "") for i in summary.get("off_track", [])],
        }
        result["available"] = True
    except Exception:
        result["initiatives"] = {}

    # Pending decisions
    try:
        from integrations.decisions import get_decision_summary
        dec_summary = get_decision_summary()
        result["decisions"] = {
            "pending_count": dec_summary.get("pending_count", 0),
            "revisit_count": dec_summary.get("revisit_count", 0),
            "pending_titles": [d.get("title", "") for d in dec_summary.get("pending", [])[:3]],
        }
        result["available"] = True
    except Exception:
        result["decisions"] = {}

    return result


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


def _get_new_tasks_today() -> dict:
    """Get smart tasks created/scanned today."""
    try:
        from integrations.intel import _load_intel
        intel = _load_intel()
        smart_tasks = intel.get("smart_tasks", [])
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        new_tasks = []
        for t in smart_tasks:
            created = t.get("created_at", "") or t.get("scanned_at", "")
            if created and created[:10] == today:
                new_tasks.append({
                    "id": t.get("id", ""),
                    "description": t.get("description", ""),
                    "owner": t.get("owner", ""),
                    "status": t.get("status", "open"),
                    "topics": t.get("topics", []),
                    "source_title": t.get("source_title", ""),
                    "quadrant": t.get("priority", {}).get("quadrant") if isinstance(t.get("priority"), dict) else None,
                })
        return {"tasks": new_tasks, "count": len(new_tasks)}
    except Exception as exc:
        logger.debug("New tasks today not available: %s", exc)
        return {"tasks": [], "count": 0}


def _get_new_epics_today() -> dict:
    """Get epics and stories created today, with full story + linked task data."""
    try:
        from integrations.epics import get_epics
        from integrations.intel import _load_intel
        data = get_epics()
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        # Build task lookup for linked tasks
        intel = _load_intel()
        task_map = {t.get("id"): t for t in intel.get("smart_tasks", []) if t.get("id")}

        new_epics = []
        new_stories = []
        for e in data.get("epics", []):
            stories_data = []
            for s in e.get("stories", []):
                linked_tasks = []
                for tid in s.get("linked_task_ids", []):
                    t = task_map.get(tid)
                    if t:
                        linked_tasks.append({
                            "id": tid,
                            "description": t.get("description", ""),
                            "owner": t.get("owner", ""),
                            "status": t.get("status", "open"),
                        })
                stories_data.append({
                    "id": s.get("id", ""),
                    "title": s.get("title", ""),
                    "owner": s.get("owner", ""),
                    "status": s.get("status", ""),
                    "size": s.get("size", ""),
                    "linked_tasks": linked_tasks,
                })
            if (e.get("created_at", "") or "")[:10] == today:
                new_epics.append({
                    "id": e.get("id", ""),
                    "title": e.get("title", ""),
                    "description": e.get("description", ""),
                    "owner": e.get("owner", ""),
                    "status": e.get("status", ""),
                    "priority": e.get("priority", ""),
                    "quarter": e.get("quarter", ""),
                    "story_count": len(stories_data),
                    "stories": stories_data,
                })
            for s in e.get("stories", []):
                if (s.get("created_at", "") or "")[:10] == today:
                    new_stories.append({
                        "id": s.get("id", ""),
                        "title": s.get("title", ""),
                        "epic_id": e.get("id", ""),
                        "epic_title": e.get("title", ""),
                        "owner": s.get("owner", ""),
                        "status": s.get("status", ""),
                    })
        return {"epics": new_epics, "stories": new_stories,
                "epic_count": len(new_epics), "story_count": len(new_stories)}
    except Exception as exc:
        logger.debug("New epics today not available: %s", exc)
        return {"epics": [], "stories": [], "epic_count": 0, "story_count": 0}


def _get_orphaned_tasks() -> dict:
    """Get tasks not linked to any epic/story (first 20)."""
    try:
        from integrations.epics import get_epics
        from integrations.intel import _load_intel

        # Build set of linked task IDs
        data = get_epics()
        linked_ids: set = set()
        epics_list = []
        for e in data.get("epics", []):
            epics_list.append({"id": e.get("id"), "title": e.get("title", "")})
            for s in e.get("stories", []):
                for tid in s.get("linked_task_ids", []):
                    linked_ids.add(tid)

        intel = _load_intel()
        smart_tasks = intel.get("smart_tasks", [])
        orphaned = []
        for t in smart_tasks:
            if t.get("status") == "done":
                continue
            if t.get("id") and t["id"] not in linked_ids:
                orphaned.append({
                    "id": t.get("id", ""),
                    "description": t.get("description", ""),
                    "owner": t.get("owner", ""),
                    "topics": t.get("topics", []),
                })
                if len(orphaned) >= 20:
                    break

        return {"tasks": orphaned, "count": len(orphaned), "epics": epics_list}
    except Exception as exc:
        logger.debug("Orphaned tasks not available: %s", exc)
        return {"tasks": [], "count": 0, "epics": []}


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
