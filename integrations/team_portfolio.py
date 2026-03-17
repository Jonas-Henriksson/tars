"""Team portfolio view — per-member workload, epics, stories, and tasks.

Provides a scrum-master-grade overview of the entire team's deliverables
broken down by person, combining data from:
- Epics & user stories (integrations.epics)
- Smart tasks (integrations.intel)
- Tracked meeting tasks (integrations.notion_tasks)
- Strategic initiatives (integrations.initiatives)
- People profiles (integrations.people)

Use this to steer priorities, detect overload, and ensure every piece
of work maps to a cohesive delivery plan.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)


def get_team_portfolio(
    owner: str = "",
    quarter: str = "",
    include_done: bool = False,
) -> dict[str, Any]:
    """Build a full team portfolio view grouped by team member.

    Each member's section includes:
    - Epics they own (with story progress)
    - User stories assigned to them (with status)
    - Smart tasks and tracked tasks (operational work)
    - Workload summary (total items, blocked, overdue)
    - Unlinked tasks (tasks not attached to any epic/story)

    Args:
        owner: Filter to a specific team member.
        quarter: Filter epics/initiatives by quarter.
        include_done: Include completed items. Default false.
    """
    # Gather all data sources
    epics_data = _get_epics_data()
    stories_data = _get_stories_data()
    smart_tasks = _get_smart_tasks(include_done)
    tracked_tasks = _get_tracked_tasks(include_done)
    initiatives = _get_initiatives()
    people = _get_people()

    epics = epics_data.get("epics", [])
    stories = stories_data.get("stories", [])

    # Apply quarter filter to epics
    if quarter:
        q_lower = quarter.lower()
        epics = [e for e in epics if q_lower in e.get("quarter", "").lower()]

    # Build initiative lookup
    init_map = {i["id"]: i for i in initiatives}

    # Collect all owners across all data sources
    all_owners: set[str] = set()
    for e in epics:
        all_owners.add(e.get("owner", "Unassigned"))
    for s in stories:
        all_owners.add(s.get("owner", "Unassigned"))
    for t in smart_tasks:
        all_owners.add(t.get("owner", "Unassigned"))
    for t in tracked_tasks:
        all_owners.add(t.get("owner", "Unassigned"))

    # Filter to specific owner if requested
    if owner:
        owner_l = owner.lower()
        all_owners = {o for o in all_owners if owner_l in o.lower()}

    now = datetime.now(timezone.utc)
    portfolio: dict[str, dict] = {}

    # Build linked task ID set (tasks that belong to a story)
    linked_task_ids: set[str] = set()
    for s in stories:
        for tid in s.get("linked_task_ids", []):
            linked_task_ids.add(tid)

    for person in sorted(all_owners):
        if person == "Unassigned":
            continue

        person_l = person.lower()

        # Epics owned by this person
        person_epics = [
            e for e in epics
            if person_l in e.get("owner", "").lower()
            and (include_done or e.get("status") not in ("done", "cancelled"))
        ]

        # Stories owned by this person
        person_stories = [
            s for s in stories
            if person_l in s.get("owner", "").lower()
            and (include_done or s.get("status") != "done")
        ]

        # Smart tasks for this person
        person_smart = [
            t for t in smart_tasks
            if person_l in t.get("owner", "").lower()
        ]

        # Tracked tasks for this person
        person_tracked = [
            t for t in tracked_tasks
            if person_l in t.get("owner", "").lower()
        ]

        # Unlinked tasks (not attached to any story)
        unlinked_smart = [
            t for t in person_smart
            if t.get("id") not in linked_task_ids
        ]
        unlinked_tracked = [
            t for t in person_tracked
            if t.get("id") not in linked_task_ids
        ]

        # Workload metrics
        blocked_stories = sum(1 for s in person_stories if s.get("status") == "blocked")
        overdue_tasks = 0
        for t in person_smart:
            fud = t.get("follow_up_date", "")
            if fud:
                try:
                    due = datetime.fromisoformat(fud)
                    if due.tzinfo is None:
                        due = due.replace(tzinfo=timezone.utc)
                    if due < now:
                        overdue_tasks += 1
                except (ValueError, TypeError):
                    pass

        total_items = (
            len(person_epics) + len(person_stories) +
            len(person_smart) + len(person_tracked)
        )

        # Get person profile info
        profile = people.get(person, {})

        # Enrich epics with their stories and initiative context
        enriched_epics = []
        for ep in person_epics:
            eid = ep["id"]
            ep_stories = [
                {
                    "id": s["id"],
                    "title": s.get("title", ""),
                    "status": s.get("status", ""),
                    "owner": s.get("owner", ""),
                    "size": s.get("size", ""),
                    "priority": s.get("priority", ""),
                }
                for s in stories
                if s.get("epic_id") == eid
                and (include_done or s.get("status") != "done")
            ]
            init_title = ""
            if ep.get("initiative_id"):
                init = init_map.get(ep["initiative_id"])
                if init:
                    init_title = init.get("title", "")

            enriched_epics.append({
                "id": ep["id"],
                "title": ep.get("title", ""),
                "status": ep.get("status", ""),
                "priority": ep.get("priority", ""),
                "quarter": ep.get("quarter", ""),
                "initiative": init_title,
                "stories": ep_stories,
                "story_count": len(ep_stories),
                "progress": ep.get("progress", ""),
            })

        portfolio[person] = {
            "name": person,
            "role": profile.get("role", ""),
            "relationship": profile.get("relationship", ""),
            "epics": enriched_epics,
            "stories": [
                {
                    "id": s["id"],
                    "title": s.get("title", ""),
                    "epic_title": _get_epic_title(s.get("epic_id", ""), epics),
                    "status": s.get("status", ""),
                    "size": s.get("size", ""),
                    "priority": s.get("priority", ""),
                }
                for s in person_stories
            ],
            "smart_tasks": [
                {
                    "id": t["id"],
                    "description": t.get("description", ""),
                    "status": t.get("status", ""),
                    "quadrant": t.get("priority", {}).get("quadrant"),
                    "follow_up_date": t.get("follow_up_date", ""),
                }
                for t in person_smart
            ],
            "tracked_tasks": [
                {
                    "id": t["id"],
                    "description": t.get("description", ""),
                    "status": t.get("status", "open"),
                    "source_title": t.get("source_title", ""),
                }
                for t in person_tracked
            ],
            "unlinked_tasks": len(unlinked_smart) + len(unlinked_tracked),
            "workload": {
                "total_items": total_items,
                "epics": len(person_epics),
                "stories": len(person_stories),
                "smart_tasks": len(person_smart),
                "tracked_tasks": len(person_tracked),
                "blocked": blocked_stories,
                "overdue": overdue_tasks,
                "unlinked": len(unlinked_smart) + len(unlinked_tracked),
            },
        }

    # Build voice summary
    members = [p for p in portfolio.values()]
    members.sort(key=lambda m: m["workload"]["total_items"], reverse=True)

    overloaded = [m for m in members if m["workload"]["total_items"] >= 7]
    blocked = [m for m in members if m["workload"]["blocked"] > 0]
    unlinked_total = sum(m["workload"]["unlinked"] for m in members)

    parts = [f"Team portfolio: {len(members)} member{'s' if len(members) != 1 else ''}"]
    if overloaded:
        names = ", ".join(m["name"] for m in overloaded[:2])
        parts.append(f"{names} {'are' if len(overloaded) > 1 else 'is'} heavily loaded")
    if blocked:
        parts.append(f"{len(blocked)} member{'s' if len(blocked) != 1 else ''} with blocked stories")
    if unlinked_total:
        parts.append(f"{unlinked_total} task{'s' if unlinked_total != 1 else ''} not linked to any epic")

    return {
        "portfolio": portfolio,
        "member_count": len(portfolio),
        "total_epics": len(epics),
        "total_stories": len(stories),
        "unlinked_tasks": unlinked_total,
        "voice_summary": ". ".join(parts) + ".",
    }


def get_member_portfolio(name: str, include_done: bool = False) -> dict[str, Any]:
    """Get a detailed portfolio view for a single team member.

    Args:
        name: Team member name.
        include_done: Include completed items.
    """
    result = get_team_portfolio(owner=name, include_done=include_done)
    portfolio = result.get("portfolio", {})

    if not portfolio:
        return {
            "error": f"No work items found for: {name}",
            "voice_summary": f"I don't have any tracked work for {name}.",
        }

    # Return the single member's data
    member = list(portfolio.values())[0]
    wl = member["workload"]

    parts = [f"{name} has {wl['total_items']} active items"]
    if wl["epics"]:
        parts.append(f"{wl['epics']} epic{'s' if wl['epics'] != 1 else ''}")
    if wl["stories"]:
        parts.append(f"{wl['stories']} stor{'ies' if wl['stories'] != 1 else 'y'}")
    if wl["smart_tasks"]:
        parts.append(f"{wl['smart_tasks']} task{'s' if wl['smart_tasks'] != 1 else ''}")
    if wl["overdue"]:
        parts.append(f"{wl['overdue']} overdue")
    if wl["blocked"]:
        parts.append(f"{wl['blocked']} blocked")
    if wl["unlinked"]:
        parts.append(f"{wl['unlinked']} task{'s' if wl['unlinked'] != 1 else ''} not linked to an epic")

    return {
        "member": member,
        "voice_summary": ", ".join(parts) + ".",
    }


def _get_epic_title(epic_id: str, epics: list[dict]) -> str:
    for e in epics:
        if e.get("id") == epic_id:
            return e.get("title", "")
    return ""


# ---------------------------------------------------------------------------
# Data access helpers (best-effort, never crash)
# ---------------------------------------------------------------------------

def _get_epics_data() -> dict:
    try:
        from integrations.epics import get_epics
        return get_epics()
    except Exception:
        return {"epics": []}


def _get_stories_data() -> dict:
    try:
        from integrations.epics import get_stories
        return get_stories()
    except Exception:
        return {"stories": []}


def _get_smart_tasks(include_done: bool = False) -> list[dict]:
    try:
        from integrations.intel import get_intel
        intel = get_intel()
        tasks = intel.get("smart_tasks", [])
        if not include_done:
            tasks = [t for t in tasks if t.get("status") != "done"]
        return tasks
    except Exception:
        return []


def _get_tracked_tasks(include_done: bool = False) -> list[dict]:
    try:
        from integrations.notion_tasks import get_tracked_tasks
        result = get_tracked_tasks(include_completed=include_done)
        return result.get("tasks", [])
    except Exception:
        return []


def _get_initiatives() -> list[dict]:
    try:
        from integrations.initiatives import get_initiatives
        result = get_initiatives()
        return result.get("initiatives", [])
    except Exception:
        return []


def _get_people() -> dict:
    try:
        from integrations.people import get_all_people
        result = get_all_people()
        return result.get("people", {})
    except Exception:
        return {}
