"""Intelligence engine — scans Notion to build a profile of the user's work.

Analyzes all accessible Notion pages to extract:
- Topics the user covers and their frequency
- People the user interacts with
- Delegated tasks and follow-up timelines
- Recurring meetings and patterns
- Smart task list with priority matrix (Eisenhower: urgent/important)

Persists intelligence data in notion_intel.json.
"""
from __future__ import annotations

import json
import logging
import re
import uuid
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_INTEL_FILE = Path(__file__).parent.parent / "notion_intel.json"


def _load_intel() -> dict:
    if _INTEL_FILE.exists():
        try:
            return json.loads(_INTEL_FILE.read_text())
        except (json.JSONDecodeError, OSError):
            pass
    return _empty_intel()


def _save_intel(data: dict) -> None:
    _INTEL_FILE.write_text(json.dumps(data, indent=2, default=str))


def _empty_intel() -> dict:
    return {
        "last_scan_at": None,
        "pages_scanned": 0,
        "topics": {},
        "people": {},
        "smart_tasks": [],
        "executive_summary": {},
        "scan_history": [],
    }


# -----------------------------------------------------------------------
# Content analysis helpers
# -----------------------------------------------------------------------

_TOPIC_KEYWORDS = {
    "strategy": ["strategy", "roadmap", "vision", "objective", "okr", "goal", "initiative"],
    "engineering": ["engineering", "technical", "architecture", "api", "deploy", "release", "sprint", "code", "bug", "feature"],
    "product": ["product", "ux", "design", "user story", "prototype", "wireframe", "requirement"],
    "finance": ["budget", "revenue", "cost", "forecast", "invoice", "financial", "p&l"],
    "hiring": ["hiring", "interview", "candidate", "recruitment", "onboarding", "headcount"],
    "operations": ["operations", "process", "workflow", "sop", "compliance", "audit"],
    "sales": ["sales", "pipeline", "deal", "prospect", "customer", "contract", "pricing"],
    "marketing": ["marketing", "campaign", "brand", "content", "launch", "event"],
    "management": ["1:1", "performance", "feedback", "team", "leadership", "delegation"],
    "planning": ["planning", "quarterly", "annual", "timeline", "milestone", "deadline"],
}


def _detect_topics(text: str, title: str) -> list[str]:
    """Detect topic categories from page content and title."""
    combined = (title + " " + text).lower()
    found = []
    for topic, keywords in _TOPIC_KEYWORDS.items():
        if any(kw in combined for kw in keywords):
            found.append(topic)
    return found or ["general"]


def _extract_people(text: str, title: str) -> list[str]:
    """Extract people mentions from text."""
    people = set()
    # @mentions
    for m in re.findall(r"@([A-Z][a-z]+(?:\s[A-Z][a-z]+)?)", text):
        people.add(m.strip())
    # 1:1 title pattern: "1:1 Name" or "1:1 with Name"
    m = re.search(r"1[:\-]1\s+(?:with\s+)?([A-Z][a-z]+(?:\s[A-Z][a-z]+)?)", title)
    if m:
        people.add(m.group(1).strip())
    return sorted(people)


def _detect_delegations(text: str) -> list[dict]:
    """Detect delegated tasks: items assigned to other people."""
    delegations = []

    # Patterns: "[ ] @Name: do something", "ACTION: @Name do something"
    patterns = [
        re.compile(r"\[[ ]\]\s*@(\w[\w\s]*?)[\s:]+(.+)"),
        re.compile(r"(?:ACTION|TODO|TASK)[:\s]+@(\w[\w\s]*?)[\s:]+(.+)", re.IGNORECASE),
        re.compile(r"[•\-\*]\s*@(\w[\w\s]*?)[\s:]+(.+)"),
    ]

    for pattern in patterns:
        for match in pattern.finditer(text):
            owner = match.group(1).strip()
            desc = match.group(2).strip()
            if owner and desc:
                delegations.append({"owner": owner, "description": desc})

    return delegations


def _estimate_follow_up_date(text: str, page_date: str) -> str | None:
    """Estimate when to follow up based on context clues."""
    text_lower = text.lower()

    # Explicit date mentions
    date_match = re.search(r"by\s+(\d{4}-\d{2}-\d{2})", text)
    if date_match:
        return date_match.group(1)

    # Relative time expressions
    try:
        base = datetime.fromisoformat(page_date.replace("Z", "+00:00")) if page_date else datetime.now(timezone.utc)
    except (ValueError, TypeError):
        base = datetime.now(timezone.utc)

    if any(w in text_lower for w in ["tomorrow", "asap", "urgent", "immediately"]):
        return (base + timedelta(days=1)).strftime("%Y-%m-%d")
    if any(w in text_lower for w in ["this week", "end of week", "eow", "friday"]):
        days_until_friday = (4 - base.weekday()) % 7 or 7
        return (base + timedelta(days=days_until_friday)).strftime("%Y-%m-%d")
    if any(w in text_lower for w in ["next week", "next monday"]):
        days_until_monday = (7 - base.weekday()) % 7 or 7
        return (base + timedelta(days=days_until_monday)).strftime("%Y-%m-%d")
    if any(w in text_lower for w in ["next month", "end of month", "eom"]):
        return (base + timedelta(days=30)).strftime("%Y-%m-%d")

    # Default: follow up in 3 business days for delegated items
    return (base + timedelta(days=3)).strftime("%Y-%m-%d")


def _classify_priority(text: str, is_delegated: bool, age_days: int = 0) -> dict:
    """Classify task using Eisenhower matrix: urgent x important.

    Returns dict with 'urgent', 'important', and 'quadrant'.
    Quadrant 1: Urgent + Important (Do first)
    Quadrant 2: Not urgent + Important (Schedule)
    Quadrant 3: Urgent + Not important (Delegate)
    Quadrant 4: Not urgent + Not important (Eliminate)
    """
    text_lower = text.lower()

    # Urgency signals
    urgent_keywords = ["asap", "urgent", "immediately", "critical", "blocker",
                       "blocked", "deadline", "overdue", "today", "tomorrow",
                       "this week", "eow"]
    urgent = any(kw in text_lower for kw in urgent_keywords) or age_days >= 7

    # Importance signals
    important_keywords = ["strategy", "revenue", "customer", "launch", "decision",
                          "budget", "contract", "leadership", "roadmap", "key",
                          "milestone", "critical path", "risk", "escalat"]
    important = any(kw in text_lower for kw in important_keywords)

    # Delegated items are typically Q3 unless explicitly important
    if is_delegated and not important:
        urgent = urgent or age_days >= 3

    if urgent and important:
        quadrant = 1
        label = "Do first"
    elif not urgent and important:
        quadrant = 2
        label = "Schedule"
    elif urgent and not important:
        quadrant = 3
        label = "Delegate"
    else:
        quadrant = 4
        label = "Eliminate/defer"

    return {
        "urgent": urgent,
        "important": important,
        "quadrant": quadrant,
        "quadrant_label": label,
    }


# -----------------------------------------------------------------------
# Main scan
# -----------------------------------------------------------------------

async def scan_notion(max_pages: int = 50) -> dict:
    """Scan all accessible Notion pages to build intelligence.

    Reads page content, extracts topics, people, delegations, and builds
    a smart task list with priority classification and follow-up dates.

    Args:
        max_pages: Max pages to scan.

    Returns:
        Summary of scan results.
    """
    from integrations.notion import get_page_content, get_recently_edited_pages, is_configured

    if not is_configured():
        raise RuntimeError("Notion is not configured. Set NOTION_API_KEY in .env.")

    intel = _load_intel()
    now = datetime.now(timezone.utc)

    # Get all recent pages (sorted by last edited)
    result = await get_recently_edited_pages(since=None, max_results=max_pages)
    pages = result.get("pages", [])

    topic_counter: Counter = Counter()
    people_counter: Counter = Counter()
    new_tasks: list[dict] = []
    existing_task_descs = {t["description"].lower() for t in intel.get("smart_tasks", [])}

    for page in pages:
        try:
            content_data = await get_page_content(page["id"])
        except Exception as exc:
            logger.warning("Failed to read page %s: %s", page["id"], exc)
            continue

        title = content_data.get("title", "")
        content = content_data.get("content", "")
        page_date = page.get("last_edited_time", "")

        if not content.strip():
            continue

        # Detect topics
        topics = _detect_topics(content, title)
        for t in topics:
            topic_counter[t] += 1

        # Detect people
        people = _extract_people(content, title)
        for p in people:
            people_counter[p] += 1

        # Detect delegations -> smart tasks
        delegations = _detect_delegations(content)
        for d in delegations:
            if d["description"].lower() in existing_task_descs:
                continue

            follow_up = _estimate_follow_up_date(
                d["description"], page_date,
            )
            priority = _classify_priority(
                d["description"], is_delegated=True,
            )

            task = {
                "id": uuid.uuid4().hex[:8],
                "description": d["description"],
                "owner": d["owner"],
                "delegated": True,
                "source_title": title,
                "source_url": page.get("url", ""),
                "source_page_id": page["id"],
                "topics": topics,
                "follow_up_date": follow_up,
                "priority": priority,
                "status": "open",
                "created_at": now.isoformat(),
            }
            new_tasks.append(task)
            existing_task_descs.add(d["description"].lower())

        # Also detect user's own tasks (not delegated)
        own_tasks = _extract_own_tasks(content, title)
        for ot in own_tasks:
            if ot["description"].lower() in existing_task_descs:
                continue

            follow_up = _estimate_follow_up_date(ot["description"], page_date)
            priority = _classify_priority(
                ot["description"], is_delegated=False,
            )

            task = {
                "id": uuid.uuid4().hex[:8],
                "description": ot["description"],
                "owner": "Me",
                "delegated": False,
                "source_title": title,
                "source_url": page.get("url", ""),
                "source_page_id": page["id"],
                "topics": topics,
                "follow_up_date": follow_up,
                "priority": priority,
                "status": "open",
                "created_at": now.isoformat(),
            }
            new_tasks.append(task)
            existing_task_descs.add(ot["description"].lower())

    # Merge into intel
    intel["topics"] = dict(topic_counter.most_common())
    intel["people"] = dict(people_counter.most_common())
    intel["smart_tasks"] = intel.get("smart_tasks", []) + new_tasks
    intel["pages_scanned"] = len(pages)
    intel["last_scan_at"] = now.isoformat()
    intel["scan_history"].append({
        "at": now.isoformat(),
        "pages": len(pages),
        "new_tasks": len(new_tasks),
    })
    intel["scan_history"] = intel["scan_history"][-20:]

    # Rebuild executive summary
    intel["executive_summary"] = _build_executive_summary(intel)

    _save_intel(intel)

    return {
        "pages_scanned": len(pages),
        "topics_found": len(intel["topics"]),
        "people_found": len(intel["people"]),
        "new_tasks_added": len(new_tasks),
        "total_smart_tasks": len(intel["smart_tasks"]),
        "top_topics": dict(topic_counter.most_common(5)),
        "top_people": dict(people_counter.most_common(5)),
        "executive_summary": intel["executive_summary"],
    }


def _extract_own_tasks(text: str, title: str) -> list[dict]:
    """Extract tasks assigned to the user (no @mention, or self-referencing)."""
    tasks = []
    for match in re.finditer(r"\[[ ]\]\s*([^@\n].{5,})", text):
        desc = match.group(1).strip()
        # Skip if it looks like someone else's task
        if re.match(r"[A-Z][a-z]+\s+(to|will|should)\s+", desc):
            continue
        tasks.append({"description": desc})
    return tasks


# -----------------------------------------------------------------------
# Executive summary
# -----------------------------------------------------------------------

def _build_executive_summary(intel: dict) -> dict:
    """Build the executive summary from intel data.

    Structures tasks into an Eisenhower matrix and highlights critical items.
    """
    tasks = [t for t in intel.get("smart_tasks", []) if t.get("status") != "done"]
    now = datetime.now(timezone.utc)

    # Recalculate priorities with age
    for task in tasks:
        created = task.get("created_at", "")
        age_days = 0
        if created:
            try:
                age_days = (now - datetime.fromisoformat(created)).days
            except (ValueError, TypeError):
                pass
        task["priority"] = _classify_priority(
            task["description"],
            is_delegated=task.get("delegated", False),
            age_days=age_days,
        )
        task["age_days"] = age_days

    # Eisenhower matrix
    q1 = [t for t in tasks if t["priority"]["quadrant"] == 1]
    q2 = [t for t in tasks if t["priority"]["quadrant"] == 2]
    q3 = [t for t in tasks if t["priority"]["quadrant"] == 3]
    q4 = [t for t in tasks if t["priority"]["quadrant"] == 4]

    # Upcoming follow-ups (next 7 days)
    today = now.strftime("%Y-%m-%d")
    week_out = (now + timedelta(days=7)).strftime("%Y-%m-%d")
    upcoming = [
        t for t in tasks
        if t.get("follow_up_date") and today <= t["follow_up_date"] <= week_out
    ]
    upcoming.sort(key=lambda t: t.get("follow_up_date", ""))

    # Overdue follow-ups
    overdue = [
        t for t in tasks
        if t.get("follow_up_date") and t["follow_up_date"] < today
    ]
    overdue.sort(key=lambda t: t.get("follow_up_date", ""))

    # Delegation summary
    delegated = [t for t in tasks if t.get("delegated")]
    delegation_by_person: dict[str, int] = {}
    for t in delegated:
        delegation_by_person[t.get("owner", "Unknown")] = delegation_by_person.get(t.get("owner", "Unknown"), 0) + 1

    # Topic coverage
    topics = intel.get("topics", {})
    top_topics = sorted(topics.items(), key=lambda x: x[1], reverse=True)[:8]

    return {
        "matrix": {
            "q1_do_first": [_summarize_task(t) for t in q1],
            "q2_schedule": [_summarize_task(t) for t in q2],
            "q3_delegate": [_summarize_task(t) for t in q3],
            "q4_defer": [_summarize_task(t) for t in q4],
            "q1_count": len(q1),
            "q2_count": len(q2),
            "q3_count": len(q3),
            "q4_count": len(q4),
        },
        "upcoming_follow_ups": [_summarize_task(t) for t in upcoming[:10]],
        "overdue_follow_ups": [_summarize_task(t) for t in overdue[:10]],
        "delegation_summary": delegation_by_person,
        "top_topics": dict(top_topics),
        "total_open": len(tasks),
        "total_delegated": len(delegated),
        "total_overdue": len(overdue),
    }


def _summarize_task(task: dict) -> dict:
    return {
        "id": task.get("id"),
        "description": task.get("description", ""),
        "owner": task.get("owner", ""),
        "delegated": task.get("delegated", False),
        "follow_up_date": task.get("follow_up_date"),
        "source_title": task.get("source_title", ""),
        "age_days": task.get("age_days", 0),
        "quadrant": task.get("priority", {}).get("quadrant"),
        "quadrant_label": task.get("priority", {}).get("quadrant_label", ""),
        "topics": task.get("topics", []),
        "status": task.get("status", "open"),
    }


# -----------------------------------------------------------------------
# Query functions
# -----------------------------------------------------------------------

def get_intel() -> dict:
    """Get the full intelligence data."""
    intel = _load_intel()
    if intel.get("smart_tasks"):
        intel["executive_summary"] = _build_executive_summary(intel)
    return intel


def get_smart_tasks(owner: str = "", topic: str = "", quadrant: int = 0,
                    include_done: bool = False) -> dict:
    """Get smart tasks with optional filters.

    Args:
        owner: Filter by owner.
        topic: Filter by topic.
        quadrant: Filter by Eisenhower quadrant (1-4), 0 for all.
        include_done: Include completed tasks.
    """
    intel = _load_intel()
    tasks = intel.get("smart_tasks", [])
    now = datetime.now(timezone.utc)

    # Recalculate age and priority
    for task in tasks:
        created = task.get("created_at", "")
        age_days = 0
        if created:
            try:
                age_days = (now - datetime.fromisoformat(created)).days
            except (ValueError, TypeError):
                pass
        task["age_days"] = age_days
        task["priority"] = _classify_priority(
            task["description"],
            is_delegated=task.get("delegated", False),
            age_days=age_days,
        )

    if not include_done:
        tasks = [t for t in tasks if t.get("status") != "done"]
    if owner:
        ol = owner.lower()
        tasks = [t for t in tasks if ol in t.get("owner", "").lower()]
    if topic:
        tl = topic.lower()
        tasks = [t for t in tasks if any(tl in tp.lower() for tp in t.get("topics", []))]
    if quadrant:
        tasks = [t for t in tasks if t.get("priority", {}).get("quadrant") == quadrant]

    # Sort: Q1 first, then Q2, Q3, Q4; within quadrant by follow-up date
    tasks.sort(key=lambda t: (
        t.get("priority", {}).get("quadrant", 4),
        t.get("follow_up_date") or "9999",
    ))

    return {"tasks": [_summarize_task(t) for t in tasks], "count": len(tasks)}


def update_smart_task(task_id: str, status: str = "", follow_up_date: str = "") -> dict:
    """Update a smart task's status or follow-up date."""
    intel = _load_intel()
    for task in intel.get("smart_tasks", []):
        if task["id"] == task_id:
            if status:
                task["status"] = status
            if follow_up_date:
                task["follow_up_date"] = follow_up_date
            _save_intel(intel)
            return {"message": f"Task updated.", "task": _summarize_task(task)}
    return {"error": f"Task not found: {task_id}"}
