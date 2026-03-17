"""Decision register — track decisions with rationale, stakeholders, and outcomes.

Provides a governance layer for CEOs to:
- Log decisions with context, rationale, and who was involved
- Track decision status (pending, decided, revisit)
- Link decisions to initiatives and tasks
- Review decision history for accountability
"""
from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_DATA_FILE = Path(__file__).parent.parent / "decisions.json"


def _load_decisions() -> list[dict]:
    if _DATA_FILE.exists():
        try:
            return json.loads(_DATA_FILE.read_text())
        except (json.JSONDecodeError, OSError):
            logger.warning("Failed to load decisions, starting fresh")
    return []


def _save_decisions(decisions: list[dict]) -> None:
    _DATA_FILE.write_text(json.dumps(decisions, indent=2, default=str))


def log_decision(
    title: str,
    rationale: str = "",
    decided_by: str = "",
    stakeholders: list[str] | None = None,
    context: str = "",
    initiative: str = "",
    status: str = "decided",
) -> dict[str, Any]:
    """Log a new decision.

    Args:
        title: What was decided.
        rationale: Why this decision was made.
        decided_by: Who made the decision.
        stakeholders: Who is affected or needs to know.
        context: Background or alternatives considered.
        initiative: Link to a strategic initiative (by name or ID).
        status: decided | pending | revisit.
    """
    decisions = _load_decisions()

    decision = {
        "id": uuid.uuid4().hex[:8],
        "title": title,
        "rationale": rationale,
        "decided_by": decided_by or "Me",
        "stakeholders": stakeholders or [],
        "context": context,
        "initiative": initiative,
        "status": status,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "outcome_notes": "",
    }

    decisions.append(decision)
    _save_decisions(decisions)

    status_label = {
        "decided": "Decision logged",
        "pending": "Pending decision tracked",
        "revisit": "Decision flagged for revisit",
    }.get(status, "Decision logged")

    return {
        "message": f"{status_label}: {title}",
        "decision": decision,
        "voice_summary": f"{status_label}. '{title}'. "
                         f"{'Rationale: ' + rationale + '. ' if rationale else ''}"
                         f"{'Stakeholders: ' + ', '.join(stakeholders) + '.' if stakeholders else ''}",
    }


def get_decisions(
    status: str = "",
    initiative: str = "",
    stakeholder: str = "",
    limit: int = 20,
) -> dict[str, Any]:
    """Get decisions with optional filters.

    Args:
        status: Filter by status (pending, decided, revisit).
        initiative: Filter by linked initiative.
        stakeholder: Filter by stakeholder name.
        limit: Max results.
    """
    decisions = _load_decisions()

    if status:
        decisions = [d for d in decisions if d.get("status") == status]
    if initiative:
        initiative_lower = initiative.lower()
        decisions = [
            d for d in decisions
            if initiative_lower in d.get("initiative", "").lower()
        ]
    if stakeholder:
        stakeholder_lower = stakeholder.lower()
        decisions = [
            d for d in decisions
            if any(stakeholder_lower in s.lower() for s in d.get("stakeholders", []))
            or stakeholder_lower in d.get("decided_by", "").lower()
        ]

    # Sort newest first
    decisions.sort(key=lambda d: d.get("created_at", ""), reverse=True)
    decisions = decisions[:limit]

    # Build voice summary
    pending = sum(1 for d in decisions if d.get("status") == "pending")
    decided = sum(1 for d in decisions if d.get("status") == "decided")
    revisit = sum(1 for d in decisions if d.get("status") == "revisit")

    parts = [f"You have {len(decisions)} decisions on record"]
    if pending:
        parts.append(f"{pending} pending")
    if revisit:
        parts.append(f"{revisit} flagged for revisit")

    return {
        "decisions": decisions,
        "count": len(decisions),
        "pending_count": pending,
        "decided_count": decided,
        "revisit_count": revisit,
        "voice_summary": ". ".join(parts) + ".",
    }


def update_decision(
    decision_id: str,
    status: str = "",
    rationale: str = "",
    outcome_notes: str = "",
    stakeholders: list[str] | None = None,
    initiative: str = "",
    title: str = "",
) -> dict[str, Any]:
    """Update an existing decision.

    Args:
        decision_id: The decision ID.
        status: New status (pending, decided, revisit).
        rationale: Updated rationale.
        outcome_notes: Notes on how the decision played out.
        stakeholders: Updated stakeholder list.
        initiative: Link to initiative.
        title: Updated title.
    """
    decisions = _load_decisions()

    for d in decisions:
        if d.get("id") == decision_id:
            if status:
                d["status"] = status
            if rationale:
                d["rationale"] = rationale
            if outcome_notes:
                d["outcome_notes"] = outcome_notes
            if stakeholders is not None:
                d["stakeholders"] = stakeholders
            if initiative:
                d["initiative"] = initiative
            if title:
                d["title"] = title
            d["updated_at"] = datetime.now(timezone.utc).isoformat()
            _save_decisions(decisions)
            return {
                "message": "Decision updated.",
                "decision": d,
            }

    return {"error": f"Decision not found: {decision_id}"}


def delete_decision(decision_id: str) -> dict[str, Any]:
    """Delete a decision from the register."""
    decisions = _load_decisions()
    original_count = len(decisions)
    decisions = [d for d in decisions if d.get("id") != decision_id]

    if len(decisions) == original_count:
        return {"error": f"Decision not found: {decision_id}"}

    _save_decisions(decisions)
    return {"message": "Decision deleted.", "id": decision_id}


def get_decision_summary() -> dict[str, Any]:
    """Get a high-level summary of the decision register for voice briefings."""
    decisions = _load_decisions()

    pending = [d for d in decisions if d.get("status") == "pending"]
    revisit = [d for d in decisions if d.get("status") == "revisit"]
    recent = sorted(decisions, key=lambda d: d.get("created_at", ""), reverse=True)[:3]

    parts = []
    if pending:
        parts.append(f"{len(pending)} decision{'s' if len(pending) != 1 else ''} pending")
        for d in pending[:2]:
            parts.append(f"'{d.get('title', '')}'")
    if revisit:
        parts.append(f"{len(revisit)} flagged for revisit")

    if not parts:
        parts.append("No pending decisions")

    return {
        "pending": pending,
        "pending_count": len(pending),
        "revisit": revisit,
        "revisit_count": len(revisit),
        "recent": recent,
        "total": len(decisions),
        "voice_summary": ". ".join(parts) + ".",
    }
