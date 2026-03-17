"""Epics & user stories — Agile work breakdown structure.

Bridges the gap between strategic initiatives and atomic tasks using
standard Scrum/Agile methodology:

    Initiative (strategic goal)
      └── Epic (large deliverable / body of work)
            └── User Story (specific user-facing value)
                  └── Task (atomic work item, linked from smart_tasks / tracked_tasks)

Epics and stories are owned by team members, enabling a per-person
portfolio view of priorities, workload, and delivery progress.
"""
from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_DATA_FILE = Path(__file__).parent.parent / "epics.json"

# Valid statuses following Scrum best practices
EPIC_STATUSES = ("backlog", "in_progress", "done", "cancelled")
STORY_STATUSES = ("backlog", "ready", "in_progress", "in_review", "done", "blocked")
STORY_SIZES = ("XS", "S", "M", "L", "XL")


def _load_data() -> dict:
    if _DATA_FILE.exists():
        try:
            return json.loads(_DATA_FILE.read_text())
        except (json.JSONDecodeError, OSError):
            logger.warning("Failed to load epics data, starting fresh")
    return {"epics": [], "stories": []}


def _save_data(data: dict) -> None:
    _DATA_FILE.write_text(json.dumps(data, indent=2, default=str))


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Epics
# ---------------------------------------------------------------------------

def create_epic(
    title: str,
    description: str = "",
    owner: str = "",
    initiative_id: str = "",
    quarter: str = "",
    priority: str = "high",
    acceptance_criteria: list[str] | None = None,
) -> dict[str, Any]:
    """Create a new epic — a large body of work that delivers significant value.

    Args:
        title: Epic name (e.g. "User onboarding revamp").
        description: What this epic delivers and why it matters.
        owner: Who is accountable for delivery.
        initiative_id: Optional parent strategic initiative ID.
        quarter: Target quarter (e.g. "Q2 2026").
        priority: high | medium | low.
        acceptance_criteria: Definition of done for the whole epic.
    """
    data = _load_data()

    epic = {
        "id": uuid.uuid4().hex[:8],
        "title": title,
        "description": description,
        "owner": owner or "Unassigned",
        "initiative_id": initiative_id,
        "quarter": quarter,
        "status": "backlog",
        "priority": priority,
        "acceptance_criteria": acceptance_criteria or [],
        "created_at": _now(),
        "updated_at": _now(),
    }

    data["epics"].append(epic)
    _save_data(data)

    return {
        "message": f"Epic created: {title}",
        "epic": epic,
        "voice_summary": f"Created epic '{title}'"
                         f"{', owned by ' + owner if owner else ''}"
                         f"{', targeting ' + quarter if quarter else ''}.",
    }


def get_epics(
    status: str = "",
    owner: str = "",
    initiative_id: str = "",
    quarter: str = "",
    priority: str = "",
) -> dict[str, Any]:
    """Get epics with optional filters.

    Args:
        status: Filter by status (backlog, in_progress, done, cancelled).
        owner: Filter by owner.
        initiative_id: Filter by parent initiative.
        quarter: Filter by quarter.
        priority: Filter by priority.
    """
    data = _load_data()
    epics = data.get("epics", [])
    stories = data.get("stories", [])

    if status:
        epics = [e for e in epics if e.get("status") == status]
    if owner:
        owner_l = owner.lower()
        epics = [e for e in epics if owner_l in e.get("owner", "").lower()]
    if initiative_id:
        epics = [e for e in epics if e.get("initiative_id") == initiative_id]
    if quarter:
        epics = [e for e in epics if quarter.lower() in e.get("quarter", "").lower()]
    if priority:
        epics = [e for e in epics if e.get("priority") == priority]

    # Enrich with story counts and progress
    for epic in epics:
        eid = epic["id"]
        epic_stories = [s for s in stories if s.get("epic_id") == eid]
        done_stories = [s for s in epic_stories if s.get("status") == "done"]
        blocked_stories = [s for s in epic_stories if s.get("status") == "blocked"]
        epic["story_count"] = len(epic_stories)
        epic["stories_done"] = len(done_stories)
        epic["stories_blocked"] = len(blocked_stories)
        epic["progress"] = (
            f"{len(done_stories)}/{len(epic_stories)}"
            if epic_stories else "no stories"
        )

    # Sort: in_progress first, then backlog, then done
    status_order = {"in_progress": 0, "backlog": 1, "done": 2, "cancelled": 3}
    epics.sort(key=lambda e: status_order.get(e.get("status", ""), 4))

    in_prog = sum(1 for e in epics if e.get("status") == "in_progress")
    backlog = sum(1 for e in epics if e.get("status") == "backlog")
    done = sum(1 for e in epics if e.get("status") == "done")

    parts = [f"{len(epics)} epic{'s' if len(epics) != 1 else ''}"]
    if in_prog:
        parts.append(f"{in_prog} in progress")
    if backlog:
        parts.append(f"{backlog} in backlog")
    if done:
        parts.append(f"{done} done")

    return {
        "epics": epics,
        "count": len(epics),
        "in_progress": in_prog,
        "backlog": backlog,
        "done": done,
        "voice_summary": ", ".join(parts) + ".",
    }


def update_epic(
    epic_id: str,
    title: str = "",
    description: str = "",
    owner: str = "",
    status: str = "",
    priority: str = "",
    quarter: str = "",
    initiative_id: str = "",
    acceptance_criteria: list[str] | None = None,
) -> dict[str, Any]:
    """Update an epic.

    Args:
        epic_id: The epic ID.
        title: New title.
        description: New description.
        owner: New owner.
        status: New status (backlog, in_progress, done, cancelled).
        priority: New priority.
        quarter: New target quarter.
        initiative_id: Link to a different initiative.
        acceptance_criteria: Updated acceptance criteria.
    """
    data = _load_data()

    for e in data["epics"]:
        if e.get("id") == epic_id:
            if title:
                e["title"] = title
            if description:
                e["description"] = description
            if owner:
                e["owner"] = owner
            if status:
                e["status"] = status
            if priority:
                e["priority"] = priority
            if quarter:
                e["quarter"] = quarter
            if initiative_id:
                e["initiative_id"] = initiative_id
            if acceptance_criteria is not None:
                e["acceptance_criteria"] = acceptance_criteria
            e["updated_at"] = _now()
            _save_data(data)

            status_label = e.get("status", "").replace("_", " ")
            return {
                "message": "Epic updated.",
                "epic": e,
                "voice_summary": f"Updated '{e.get('title', '')}', now {status_label}.",
            }

    return {"error": f"Epic not found: {epic_id}"}


def delete_epic(epic_id: str) -> dict[str, Any]:
    """Delete an epic and its user stories."""
    data = _load_data()
    original = len(data.get("epics", []))
    data["epics"] = [e for e in data.get("epics", []) if e.get("id") != epic_id]
    data["stories"] = [s for s in data.get("stories", []) if s.get("epic_id") != epic_id]

    if len(data.get("epics", [])) == original:
        return {"error": f"Epic not found: {epic_id}"}

    _save_data(data)
    return {"message": "Epic and its stories deleted.", "id": epic_id}


# ---------------------------------------------------------------------------
# User Stories
# ---------------------------------------------------------------------------

def create_story(
    epic_id: str,
    title: str,
    description: str = "",
    owner: str = "",
    size: str = "M",
    priority: str = "medium",
    acceptance_criteria: list[str] | None = None,
) -> dict[str, Any]:
    """Create a user story within an epic.

    Best practice: write stories as "As a [role], I want [goal], so that [benefit]".

    Args:
        epic_id: Parent epic ID.
        title: Story title (ideally in user story format).
        description: Additional details, context, or technical notes.
        owner: Who will deliver this story.
        size: T-shirt size estimate (XS, S, M, L, XL).
        priority: high | medium | low.
        acceptance_criteria: Specific conditions that must be met.
    """
    data = _load_data()

    # Verify epic exists
    epic = None
    for e in data["epics"]:
        if e.get("id") == epic_id:
            epic = e
            break
    if not epic:
        return {"error": f"Epic not found: {epic_id}"}

    story = {
        "id": uuid.uuid4().hex[:8],
        "epic_id": epic_id,
        "title": title,
        "description": description,
        "owner": owner or epic.get("owner", "Unassigned"),
        "size": size if size in STORY_SIZES else "M",
        "priority": priority,
        "status": "backlog",
        "acceptance_criteria": acceptance_criteria or [],
        "linked_task_ids": [],
        "created_at": _now(),
        "updated_at": _now(),
    }

    data["stories"].append(story)
    _save_data(data)

    return {
        "message": f"Story added to '{epic.get('title', '')}'",
        "story": story,
        "voice_summary": f"Added story '{title}' to epic '{epic.get('title', '')}'"
                         f"{', assigned to ' + owner if owner else ''}, size {size}.",
    }


def get_stories(
    epic_id: str = "",
    owner: str = "",
    status: str = "",
    priority: str = "",
    size: str = "",
) -> dict[str, Any]:
    """Get user stories with optional filters.

    Args:
        epic_id: Filter by parent epic.
        owner: Filter by owner.
        status: Filter by status.
        priority: Filter by priority.
        size: Filter by t-shirt size.
    """
    data = _load_data()
    stories = data.get("stories", [])

    if epic_id:
        stories = [s for s in stories if s.get("epic_id") == epic_id]
    if owner:
        owner_l = owner.lower()
        stories = [s for s in stories if owner_l in s.get("owner", "").lower()]
    if status:
        stories = [s for s in stories if s.get("status") == status]
    if priority:
        stories = [s for s in stories if s.get("priority") == priority]
    if size:
        stories = [s for s in stories if s.get("size") == size.upper()]

    # Enrich with epic title
    epics_map = {e["id"]: e.get("title", "") for e in data.get("epics", [])}
    for story in stories:
        story["epic_title"] = epics_map.get(story.get("epic_id", ""), "")

    # Sort by status progression
    status_order = {
        "blocked": 0, "in_progress": 1, "in_review": 2,
        "ready": 3, "backlog": 4, "done": 5,
    }
    stories.sort(key=lambda s: status_order.get(s.get("status", ""), 6))

    in_prog = sum(1 for s in stories if s.get("status") == "in_progress")
    blocked = sum(1 for s in stories if s.get("status") == "blocked")
    done = sum(1 for s in stories if s.get("status") == "done")

    parts = [f"{len(stories)} user stor{'ies' if len(stories) != 1 else 'y'}"]
    if in_prog:
        parts.append(f"{in_prog} in progress")
    if blocked:
        parts.append(f"{blocked} blocked")
    if done:
        parts.append(f"{done} done")

    return {
        "stories": stories,
        "count": len(stories),
        "in_progress": in_prog,
        "blocked": blocked,
        "done": done,
        "voice_summary": ", ".join(parts) + ".",
    }


def update_story(
    story_id: str,
    title: str = "",
    description: str = "",
    owner: str = "",
    status: str = "",
    priority: str = "",
    size: str = "",
    acceptance_criteria: list[str] | None = None,
) -> dict[str, Any]:
    """Update a user story.

    Args:
        story_id: The story ID.
        title: New title.
        description: New description.
        owner: New owner.
        status: New status (backlog, ready, in_progress, in_review, done, blocked).
        priority: New priority.
        size: New size estimate.
        acceptance_criteria: Updated acceptance criteria.
    """
    data = _load_data()

    for s in data["stories"]:
        if s.get("id") == story_id:
            if title:
                s["title"] = title
            if description:
                s["description"] = description
            if owner:
                s["owner"] = owner
            if status:
                s["status"] = status
            if priority:
                s["priority"] = priority
            if size:
                s["size"] = size.upper() if size.upper() in STORY_SIZES else s.get("size", "M")
            if acceptance_criteria is not None:
                s["acceptance_criteria"] = acceptance_criteria
            s["updated_at"] = _now()
            _save_data(data)

            status_label = s.get("status", "").replace("_", " ")
            return {
                "message": "Story updated.",
                "story": s,
                "voice_summary": f"Updated story '{s.get('title', '')}', now {status_label}.",
            }

    return {"error": f"Story not found: {story_id}"}


def link_task_to_story(story_id: str, task_id: str) -> dict[str, Any]:
    """Link an existing smart task or tracked task to a user story.

    Args:
        story_id: The story to link to.
        task_id: The task ID to link.
    """
    data = _load_data()

    for s in data["stories"]:
        if s.get("id") == story_id:
            linked = s.setdefault("linked_task_ids", [])
            if task_id in linked:
                return {"message": "Task already linked.", "story_id": story_id, "task_id": task_id}
            linked.append(task_id)
            s["updated_at"] = _now()
            _save_data(data)
            return {
                "message": f"Task linked to story '{s.get('title', '')}'.",
                "story": s,
                "voice_summary": f"Linked task to story '{s.get('title', '')}'.",
            }

    return {"error": f"Story not found: {story_id}"}


def delete_story(story_id: str) -> dict[str, Any]:
    """Delete a user story."""
    data = _load_data()
    original = len(data.get("stories", []))
    data["stories"] = [s for s in data.get("stories", []) if s.get("id") != story_id]

    if len(data.get("stories", [])) == original:
        return {"error": f"Story not found: {story_id}"}

    _save_data(data)
    return {"message": "Story deleted.", "id": story_id}
