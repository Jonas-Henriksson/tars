"""Strategic initiatives & OKR tracking.

Tracks quarterly goals, key results, and strategic initiatives with:
- Progress tracking (manual or auto-linked from tasks)
- Owner assignment and accountability
- Milestone tracking
- Initiative-to-task linkage
- Status health indicators (on track, at risk, off track)
"""
from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_DATA_FILE = Path(__file__).parent.parent / "initiatives.json"


def _load_data() -> dict:
    if _DATA_FILE.exists():
        try:
            return json.loads(_DATA_FILE.read_text())
        except (json.JSONDecodeError, OSError):
            logger.warning("Failed to load initiatives, starting fresh")
    return {"initiatives": [], "key_results": []}


def _save_data(data: dict) -> None:
    _DATA_FILE.write_text(json.dumps(data, indent=2, default=str))


def create_initiative(
    title: str,
    description: str = "",
    owner: str = "",
    quarter: str = "",
    status: str = "on_track",
    priority: str = "high",
    milestones: list[str] | None = None,
    theme_id: str = "",
    source: str = "confirmed",
) -> dict[str, Any]:
    """Create a new strategic initiative.

    Args:
        title: Initiative name (e.g. "Launch EMEA expansion").
        description: What this initiative aims to achieve.
        owner: Who is accountable.
        quarter: Target quarter (e.g. "Q1 2026").
        status: on_track | at_risk | off_track | completed | paused.
        priority: high | medium | low.
        milestones: Key milestones as text list.
        theme_id: Parent theme ID (links to themes.json).
        source: "confirmed" (human-created/approved) | "auto" (AI-proposed).
    """
    data = _load_data()

    initiative = {
        "id": uuid.uuid4().hex[:8],
        "title": title,
        "description": description,
        "owner": owner or "Me",
        "quarter": quarter,
        "status": status,
        "priority": priority,
        "milestones": [
            {"text": m, "completed": False}
            for m in (milestones or [])
        ],
        "key_result_ids": [],
        "theme_id": theme_id,
        "source": source if source in ("confirmed", "auto") else "confirmed",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }

    data["initiatives"].append(initiative)
    _save_data(data)

    return {
        "message": f"Initiative created: {title}",
        "initiative": initiative,
        "voice_summary": f"Created strategic initiative '{title}'"
                         f"{', owned by ' + owner if owner else ''}"
                         f"{', targeting ' + quarter if quarter else ''}.",
    }


def get_initiatives(
    status: str = "",
    owner: str = "",
    quarter: str = "",
    priority: str = "",
) -> dict[str, Any]:
    """Get strategic initiatives with optional filters.

    Args:
        status: Filter by status (on_track, at_risk, off_track, completed, paused).
        owner: Filter by owner.
        quarter: Filter by quarter (e.g. "Q1 2026").
        priority: Filter by priority.
    """
    data = _load_data()
    initiatives = data.get("initiatives", [])

    if status:
        initiatives = [i for i in initiatives if i.get("status") == status]
    if owner:
        owner_lower = owner.lower()
        initiatives = [i for i in initiatives if owner_lower in i.get("owner", "").lower()]
    if quarter:
        initiatives = [i for i in initiatives if quarter.lower() in i.get("quarter", "").lower()]
    if priority:
        initiatives = [i for i in initiatives if i.get("priority") == priority]

    # Enrich with linked task counts
    try:
        from integrations.intel import get_intel
        intel = get_intel()
        smart_tasks = intel.get("smart_tasks", [])
    except Exception:
        smart_tasks = []

    for initiative in initiatives:
        title_lower = initiative.get("title", "").lower()
        title_words = [w for w in title_lower.split() if len(w) > 3]

        linked_tasks = [
            t for t in smart_tasks
            if t.get("status") != "done"
            and any(
                word in t.get("description", "").lower()
                or word in t.get("topic", "").lower()
                for word in title_words
            )
        ]
        initiative["linked_task_count"] = len(linked_tasks)

        # Milestone progress
        milestones = initiative.get("milestones", [])
        done = sum(1 for m in milestones if m.get("completed"))
        initiative["milestone_progress"] = (
            f"{done}/{len(milestones)}" if milestones else "no milestones"
        )

    # Sort: at_risk first, then on_track, then rest
    status_order = {"at_risk": 0, "off_track": 1, "on_track": 2, "paused": 3, "completed": 4}
    initiatives.sort(key=lambda i: status_order.get(i.get("status", ""), 5))

    # Voice summary
    at_risk = sum(1 for i in initiatives if i.get("status") == "at_risk")
    off_track = sum(1 for i in initiatives if i.get("status") == "off_track")
    on_track = sum(1 for i in initiatives if i.get("status") == "on_track")

    parts = [f"{len(initiatives)} strategic initiative{'s' if len(initiatives) != 1 else ''}"]
    if on_track:
        parts.append(f"{on_track} on track")
    if at_risk:
        parts.append(f"{at_risk} at risk")
    if off_track:
        parts.append(f"{off_track} off track")

    return {
        "initiatives": initiatives,
        "count": len(initiatives),
        "on_track": on_track,
        "at_risk": at_risk,
        "off_track": off_track,
        "voice_summary": ". ".join(parts) + ".",
    }


def update_initiative(
    initiative_id: str,
    title: str = "",
    description: str = "",
    owner: str = "",
    quarter: str = "",
    status: str = "",
    priority: str = "",
    theme_id: str | None = None,
) -> dict[str, Any]:
    """Update a strategic initiative.

    Args:
        initiative_id: The initiative ID.
        title: New title.
        description: New description.
        owner: New owner.
        quarter: New target quarter.
        status: New status (on_track, at_risk, off_track, completed, paused).
        priority: New priority (high, medium, low).
        theme_id: Link to a different theme (pass "" to unlink).
    """
    data = _load_data()

    for i in data["initiatives"]:
        if i.get("id") == initiative_id:
            if title:
                i["title"] = title
            if description:
                i["description"] = description
            if owner:
                i["owner"] = owner
            if quarter:
                i["quarter"] = quarter
            if status:
                i["status"] = status
            if priority:
                i["priority"] = priority
            if theme_id is not None:
                i["theme_id"] = theme_id
            i["updated_at"] = datetime.now(timezone.utc).isoformat()
            _save_data(data)

            status_label = {
                "on_track": "on track",
                "at_risk": "at risk",
                "off_track": "off track",
                "completed": "completed",
                "paused": "paused",
            }.get(i.get("status", ""), i.get("status", ""))

            return {
                "message": "Initiative updated.",
                "initiative": i,
                "voice_summary": f"Updated {i.get('title', '')}. It's now {status_label}.",
            }

    return {"error": f"Initiative not found: {initiative_id}"}


def complete_milestone(initiative_id: str, milestone_index: int) -> dict[str, Any]:
    """Mark a milestone as completed.

    Args:
        initiative_id: The initiative ID.
        milestone_index: Zero-based index of the milestone.
    """
    data = _load_data()

    for i in data["initiatives"]:
        if i.get("id") == initiative_id:
            milestones = i.get("milestones", [])
            if 0 <= milestone_index < len(milestones):
                milestones[milestone_index]["completed"] = True
                milestones[milestone_index]["completed_at"] = datetime.now(timezone.utc).isoformat()
                i["updated_at"] = datetime.now(timezone.utc).isoformat()
                _save_data(data)

                done = sum(1 for m in milestones if m.get("completed"))
                return {
                    "message": f"Milestone completed: {milestones[milestone_index]['text']}",
                    "progress": f"{done}/{len(milestones)}",
                    "initiative": i,
                    "voice_summary": f"Milestone done, {done} of {len(milestones)} complete.",
                }
            if not milestones:
                return {"error": "This initiative has no milestones."}
            return {"error": f"Milestone index {milestone_index} out of range (0-{len(milestones)-1})"}

    return {"error": f"Initiative not found: {initiative_id}"}


def add_key_result(
    initiative_id: str,
    description: str,
    target: str = "",
    current: str = "",
    owner: str = "",
) -> dict[str, Any]:
    """Add a key result to an initiative.

    Args:
        initiative_id: The parent initiative ID.
        description: What the key result measures (e.g. "Revenue reaches $10M ARR").
        target: Target value or metric.
        current: Current value or progress.
        owner: Who owns this KR.
    """
    data = _load_data()

    # Verify initiative exists
    initiative = None
    for i in data["initiatives"]:
        if i.get("id") == initiative_id:
            initiative = i
            break
    if not initiative:
        return {"error": f"Initiative not found: {initiative_id}"}

    kr = {
        "id": uuid.uuid4().hex[:8],
        "initiative_id": initiative_id,
        "description": description,
        "target": target,
        "current": current,
        "owner": owner or initiative.get("owner", ""),
        "status": "in_progress",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }

    data.setdefault("key_results", []).append(kr)
    initiative.setdefault("key_result_ids", []).append(kr["id"])
    initiative["updated_at"] = datetime.now(timezone.utc).isoformat()
    _save_data(data)

    return {
        "message": f"Key result added to '{initiative.get('title', '')}'",
        "key_result": kr,
        "voice_summary": f"Added key result, {description}"
                         f"{', targeting ' + target if target else ''}.",
    }


def update_key_result(
    kr_id: str,
    current: str = "",
    status: str = "",
    description: str = "",
) -> dict[str, Any]:
    """Update a key result's progress.

    Args:
        kr_id: The key result ID.
        current: Updated current value/progress.
        status: in_progress | achieved | missed.
        description: Updated description.
    """
    data = _load_data()

    for kr in data.get("key_results", []):
        if kr.get("id") == kr_id:
            if current:
                kr["current"] = current
            if status:
                kr["status"] = status
            if description:
                kr["description"] = description
            kr["updated_at"] = datetime.now(timezone.utc).isoformat()
            _save_data(data)
            return {
                "message": "Key result updated.",
                "key_result": kr,
                "voice_summary": f"Updated key result, {kr.get('description', '')}. "
                                 f"{'Currently at ' + current + '. ' if current else ''}"
                                 f"{status.replace('_', ' ') + '.' if status else ''}",
            }

    return {"error": f"Key result not found: {kr_id}"}


def approve_initiative(initiative_id: str) -> dict[str, Any]:
    """Approve an auto-generated initiative (change source from 'auto' to 'confirmed')."""
    data = _load_data()

    for i in data["initiatives"]:
        if i.get("id") == initiative_id:
            i["source"] = "confirmed"
            i["updated_at"] = datetime.now(timezone.utc).isoformat()
            _save_data(data)
            return {"message": "Initiative approved.", "initiative": i}

    return {"error": f"Initiative not found: {initiative_id}"}


def delete_initiative(initiative_id: str) -> dict[str, Any]:
    """Delete an initiative and its key results."""
    data = _load_data()
    original = len(data.get("initiatives", []))
    data["initiatives"] = [
        i for i in data.get("initiatives", [])
        if i.get("id") != initiative_id
    ]
    # Also remove linked key results
    data["key_results"] = [
        kr for kr in data.get("key_results", [])
        if kr.get("initiative_id") != initiative_id
    ]

    if len(data.get("initiatives", [])) == original:
        return {"error": f"Initiative not found: {initiative_id}"}

    _save_data(data)
    return {"message": "Initiative deleted.", "id": initiative_id}


def get_strategic_summary() -> dict[str, Any]:
    """Get a high-level strategic summary for voice briefings and dashboards."""
    data = _load_data()
    initiatives = data.get("initiatives", [])
    key_results = data.get("key_results", [])

    at_risk = [i for i in initiatives if i.get("status") == "at_risk"]
    off_track = [i for i in initiatives if i.get("status") == "off_track"]
    on_track = [i for i in initiatives if i.get("status") == "on_track"]

    # KR stats
    kr_achieved = sum(1 for kr in key_results if kr.get("status") == "achieved")
    kr_in_progress = sum(1 for kr in key_results if kr.get("status") == "in_progress")

    parts = []
    if initiatives:
        parts.append(f"{len(initiatives)} strategic initiatives")
        if on_track:
            parts.append(f"{len(on_track)} on track")
        if at_risk:
            parts.append(f"{len(at_risk)} at risk: {', '.join(i['title'] for i in at_risk[:2])}")
        if off_track:
            parts.append(f"{len(off_track)} off track: {', '.join(i['title'] for i in off_track[:2])}")
    else:
        parts.append("No strategic initiatives tracked yet")

    if key_results:
        parts.append(f"{kr_achieved} of {len(key_results)} key results achieved")

    return {
        "initiatives": initiatives,
        "key_results": key_results,
        "total": len(initiatives),
        "on_track": len(on_track),
        "at_risk_count": len(at_risk),
        "at_risk": at_risk,
        "off_track_count": len(off_track),
        "off_track": off_track,
        "kr_total": len(key_results),
        "kr_achieved": kr_achieved,
        "kr_in_progress": kr_in_progress,
        "voice_summary": ". ".join(parts) + ".",
    }
