"""Meeting prep — pre-meeting briefs with attendee context and talking points.

Generates a context-rich briefing before any upcoming meeting by pulling:
- Attendee profiles, roles, and recent interactions
- Past meetings with the same people or topic
- Open tasks related to attendees
- Suggested talking points and questions
- Pending decisions that may be relevant
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone, timedelta
from typing import Any

logger = logging.getLogger(__name__)


async def get_meeting_prep(event_id: str = "", minutes_ahead: int = 30) -> dict[str, Any]:
    """Prepare a briefing for an upcoming meeting.

    If event_id is provided, preps for that specific event.
    Otherwise, preps for the next meeting within minutes_ahead.

    Returns context-rich brief with attendee profiles, history,
    open tasks, and suggested talking points.
    """
    # Get the target meeting
    event = None
    if event_id:
        event = await _find_event_by_id(event_id)
    else:
        event = await _find_next_event(minutes_ahead)

    if not event:
        return {
            "available": False,
            "reason": "No upcoming meeting found" if not event_id else f"Event {event_id} not found",
            "voice_summary": "I couldn't find an upcoming meeting to prepare for.",
        }

    subject = event.get("subject", "Untitled meeting")
    attendees = event.get("attendees", [])
    start = event.get("start", "")

    # Build prep sections in parallel
    attendee_profiles = _get_attendee_profiles(attendees)
    related_history = _find_meeting_history(subject, attendees)
    open_items = _get_open_items_for_attendees(attendees)
    pending_decisions = _get_pending_decisions_for_context(subject, attendees)
    talking_points = _generate_talking_points(
        event, attendee_profiles, related_history, open_items, pending_decisions,
    )

    # Time until meeting
    time_until = ""
    if start:
        try:
            start_dt = datetime.fromisoformat(start)
            if start_dt.tzinfo is None:
                start_dt = start_dt.replace(tzinfo=timezone.utc)
            delta = start_dt - datetime.now(timezone.utc)
            mins = int(delta.total_seconds() / 60)
            if mins > 0:
                time_until = f"in {mins} minutes" if mins < 60 else f"in {mins // 60}h {mins % 60}m"
            else:
                time_until = "now"
        except (ValueError, TypeError):
            pass

    voice_parts = [f"Prep for '{subject}'"]
    if time_until:
        voice_parts.append(f"starting {time_until}")
    if attendees:
        names = [_extract_name(a) for a in attendees[:5]]
        voice_parts.append(f"with {', '.join(names)}")
    if talking_points:
        voice_parts.append(f"I have {len(talking_points)} talking points ready")
    if open_items:
        voice_parts.append(f"and {len(open_items)} open items to discuss")

    return {
        "available": True,
        "event": event,
        "time_until": time_until,
        "attendee_profiles": attendee_profiles,
        "related_meetings": related_history,
        "open_items": open_items,
        "pending_decisions": pending_decisions,
        "talking_points": talking_points,
        "voice_summary": ". ".join(voice_parts) + ".",
    }


async def get_next_meeting_brief() -> dict[str, Any]:
    """Quick version — just prep the very next meeting."""
    return await get_meeting_prep(minutes_ahead=480)  # Look 8 hours ahead


async def _find_event_by_id(event_id: str) -> dict | None:
    """Find a specific calendar event by ID."""
    try:
        from integrations.calendar import get_events
        data = await get_events(days=7, max_results=50)
        for evt in data.get("events", []):
            if evt.get("id") == event_id:
                return evt
    except Exception as exc:
        logger.debug("Calendar not available: %s", exc)
    return None


async def _find_next_event(minutes_ahead: int) -> dict | None:
    """Find the next upcoming calendar event."""
    try:
        from integrations.calendar import get_events
        data = await get_events(days=1, max_results=20)
        now = datetime.now(timezone.utc)
        cutoff = now + timedelta(minutes=minutes_ahead)

        for evt in data.get("events", []):
            start = evt.get("start", "")
            if not start:
                continue
            try:
                start_dt = datetime.fromisoformat(start)
                if start_dt.tzinfo is None:
                    start_dt = start_dt.replace(tzinfo=timezone.utc)
                # Event is in the future or just started (within last 5 min)
                if start_dt >= now - timedelta(minutes=5) and start_dt <= cutoff:
                    return evt
            except (ValueError, TypeError):
                continue

        # If nothing within cutoff, return the next future event
        for evt in data.get("events", []):
            start = evt.get("start", "")
            if not start:
                continue
            try:
                start_dt = datetime.fromisoformat(start)
                if start_dt.tzinfo is None:
                    start_dt = start_dt.replace(tzinfo=timezone.utc)
                if start_dt > now:
                    return evt
            except (ValueError, TypeError):
                continue
    except Exception as exc:
        logger.debug("Calendar not available: %s", exc)
    return None


def _extract_name(attendee: str | dict) -> str:
    """Extract a display name from an attendee (email or dict)."""
    if isinstance(attendee, dict):
        return attendee.get("name", attendee.get("email", "Unknown"))
    # If it's an email, take the part before @
    if "@" in str(attendee):
        return str(attendee).split("@")[0].replace(".", " ").title()
    return str(attendee)


def _extract_email(attendee: str | dict) -> str:
    """Extract email from an attendee."""
    if isinstance(attendee, dict):
        return attendee.get("email", "")
    return str(attendee) if "@" in str(attendee) else ""


def _get_attendee_profiles(attendees: list) -> list[dict]:
    """Get profiles for meeting attendees from people data."""
    try:
        from integrations.people import get_all_people
        all_people = get_all_people()
        people = all_people.get("people", {})
    except Exception:
        people = {}

    profiles = []
    for att in attendees:
        name = _extract_name(att)
        email = _extract_email(att)

        # Try to match by name (case-insensitive partial match)
        matched = None
        for pname, profile in people.items():
            if (name.lower() in pname.lower() or pname.lower() in name.lower()
                    or (email and email.lower() == profile.get("email", "").lower())):
                matched = profile
                break

        if matched:
            profiles.append({
                "name": matched.get("name", name),
                "email": email or matched.get("email", ""),
                "role": matched.get("role", ""),
                "relationship": matched.get("relationship", ""),
                "organization": matched.get("organization", ""),
                "open_tasks": len(matched.get("tasks_owned", [])),
                "topics": matched.get("topics", [])[:5],
                "has_one_on_ones": matched.get("has_one_on_ones", False),
                "notes": matched.get("notes", ""),
                "last_interaction": _get_last_interaction(matched),
            })
        else:
            profiles.append({
                "name": name,
                "email": email,
                "role": "",
                "relationship": "",
                "organization": "",
                "open_tasks": 0,
                "topics": [],
                "has_one_on_ones": False,
                "notes": "",
                "last_interaction": "",
            })

    return profiles


def _get_last_interaction(profile: dict) -> str:
    """Find the most recent interaction with a person."""
    pages = profile.get("pages", [])
    if not pages:
        return ""
    # Pages should have last_edited
    latest = ""
    latest_title = ""
    for p in pages:
        edited = p.get("last_edited", "")
        if edited > latest:
            latest = edited
            latest_title = p.get("title", "")
    if latest:
        try:
            dt = datetime.fromisoformat(latest)
            days_ago = (datetime.now(timezone.utc) - dt.replace(tzinfo=timezone.utc)).days
            if days_ago == 0:
                return f"Today — {latest_title}"
            elif days_ago == 1:
                return f"Yesterday — {latest_title}"
            else:
                return f"{days_ago} days ago — {latest_title}"
        except (ValueError, TypeError):
            pass
    return ""


def _find_meeting_history(subject: str, attendees: list) -> list[dict]:
    """Find past meetings with similar topics or attendees."""
    try:
        from integrations.intel import get_intel
        intel = get_intel()
        page_index = intel.get("page_index", {})
    except Exception:
        return []

    attendee_names = [_extract_name(a).lower() for a in attendees]
    subject_words = [w.lower() for w in subject.split() if len(w) > 3]
    results = []

    for _pid, page in page_index.items():
        title = page.get("title", "")
        page_people = [p.lower() for p in page.get("people", [])]

        # Score by attendee overlap and subject similarity
        people_overlap = sum(
            1 for name in attendee_names
            if any(name in pp for pp in page_people)
        )
        subject_overlap = sum(
            1 for word in subject_words
            if word in title.lower()
        )

        if people_overlap >= 1 or subject_overlap >= 1:
            results.append({
                "title": title,
                "url": page.get("url", ""),
                "last_edited": page.get("last_edited", ""),
                "topics": page.get("topics", []),
                "relevance": people_overlap * 2 + subject_overlap,
            })

    results.sort(key=lambda x: x["relevance"], reverse=True)
    return results[:5]


def _get_open_items_for_attendees(attendees: list) -> list[dict]:
    """Get open tasks owned by or related to meeting attendees."""
    try:
        from integrations.intel import get_intel
        intel = get_intel()
        smart_tasks = intel.get("smart_tasks", [])
    except Exception:
        return []

    attendee_names = [_extract_name(a).lower() for a in attendees]
    items = []

    for task in smart_tasks:
        if task.get("status") == "done":
            continue
        owner = task.get("owner", "").lower()
        if any(name in owner for name in attendee_names):
            items.append({
                "description": task.get("description", ""),
                "owner": task.get("owner", ""),
                "status": task.get("status", "open"),
                "quadrant": task.get("priority", {}).get("quadrant", 4),
                "follow_up_date": task.get("follow_up_date", ""),
            })

    # Sort by priority (Q1 first)
    items.sort(key=lambda x: x.get("quadrant", 4))
    return items[:10]


def _get_pending_decisions_for_context(subject: str, attendees: list) -> list[dict]:
    """Get pending decisions related to the meeting context."""
    try:
        from integrations.decisions import get_decisions
        result = get_decisions(status="pending")
        decisions = result.get("decisions", [])
    except Exception:
        return []

    attendee_names = [_extract_name(a).lower() for a in attendees]
    subject_lower = subject.lower()
    relevant = []

    for d in decisions:
        title_lower = d.get("title", "").lower()
        stakeholders = [s.lower() for s in d.get("stakeholders", [])]

        # Match by subject or stakeholder overlap
        if (any(word in title_lower for word in subject_lower.split() if len(word) > 3)
                or any(name in s for name in attendee_names for s in stakeholders)):
            relevant.append(d)

    return relevant[:5]


def _generate_talking_points(
    event: dict,
    profiles: list[dict],
    history: list[dict],
    open_items: list[dict],
    decisions: list[dict],
) -> list[dict]:
    """Generate suggested talking points for the meeting."""
    points = []

    # From open items — tasks that need discussion
    for item in open_items[:3]:
        owner = item.get("owner", "someone")
        desc = item.get("description", "")
        if item.get("quadrant") == 1:
            points.append({
                "type": "urgent_task",
                "point": f"Urgent: Check status of '{desc}' with {owner}",
                "priority": "high",
            })
        elif item.get("follow_up_date"):
            points.append({
                "type": "follow_up",
                "point": f"Follow up with {owner} on '{desc}'",
                "priority": "medium",
            })

    # From pending decisions
    for d in decisions[:2]:
        points.append({
            "type": "decision",
            "point": f"Decision needed: {d.get('title', '')}",
            "priority": "high",
        })

    # From attendee context — people with many open tasks
    for profile in profiles:
        if profile.get("open_tasks", 0) >= 3:
            points.append({
                "type": "workload",
                "point": f"{profile['name']} has {profile['open_tasks']} open tasks — check capacity",
                "priority": "medium",
            })

    # From history — recurring themes
    if history:
        common_topics = {}
        for h in history:
            for t in h.get("topics", []):
                common_topics[t] = common_topics.get(t, 0) + 1
        top_topics = sorted(common_topics.items(), key=lambda x: -x[1])[:2]
        for topic, count in top_topics:
            if count >= 2:
                points.append({
                    "type": "recurring_topic",
                    "point": f"Recurring topic: {topic} (discussed {count} times before)",
                    "priority": "low",
                })

    # Sort by priority
    priority_order = {"high": 0, "medium": 1, "low": 2}
    points.sort(key=lambda p: priority_order.get(p.get("priority", "low"), 3))

    return points
