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
import re
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
    linked_type: str = "",
    linked_id: str = "",
    linked_title: str = "",
    source: str = "manual",
    source_page_id: str = "",
    source_title: str = "",
    source_url: str = "",
    requested_by: str = "",
    requested_from: str = "",
    request_reason: str = "",
    from_workstream: str = "",
) -> dict[str, Any]:
    """Log a new decision.

    Args:
        title: What was decided.
        rationale: Why this decision was made.
        decided_by: Who made the decision.
        stakeholders: Who is affected or needs to know.
        context: Background or alternatives considered.
        initiative: Link to a strategic initiative (by name or ID).
        status: decided | pending | revisit | request.
        linked_type: Hierarchy entity type (initiative/epic/story/task).
        linked_id: ID of the linked hierarchy item.
        linked_title: Title of the linked hierarchy item.
        source: How this decision was created (manual/voice/notion/request).
        source_page_id: Notion page ID if imported.
        requested_by: Who needs this decision made.
        requested_from: Who should make it.
        request_reason: Why it's needed / what's blocked.
        from_workstream: Which workstream/task triggered this.
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
        "linked_type": linked_type,
        "linked_id": linked_id,
        "linked_title": linked_title,
        "source": source,
        "source_page_id": source_page_id,
        "source_title": source_title,
        "source_url": source_url,
        "requested_by": requested_by,
        "requested_from": requested_from,
        "request_reason": request_reason,
        "from_workstream": from_workstream,
    }

    decisions.append(decision)
    _save_decisions(decisions)

    status_label = {
        "decided": "Decision logged",
        "pending": "Pending decision tracked",
        "revisit": "Decision flagged for revisit",
        "request": "Decision requested",
    }.get(status, "Decision logged")

    return {
        "message": f"{status_label}: {title}",
        "decision": decision,
        "voice_summary": f"{status_label}. '{title}'. "
                         f"{'Because ' + rationale + '. ' if rationale else ''}"
                         f"{'Involves ' + ', '.join(stakeholders) + '.' if stakeholders else ''}",
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
    request = sum(1 for d in decisions if d.get("status") == "request")

    parts = [f"You have {len(decisions)} decisions on record"]
    if request:
        parts.append(f"{request} decision requests pending")
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
        "request_count": request,
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
    linked_type: str = "",
    linked_id: str = "",
    linked_title: str = "",
    source: str = "",
    source_page_id: str = "",
    requested_by: str = "",
    requested_from: str = "",
    request_reason: str = "",
    from_workstream: str = "",
) -> dict[str, Any]:
    """Update an existing decision.

    Args:
        decision_id: The decision ID.
        status: New status (pending, decided, revisit, request).
        rationale: Updated rationale.
        outcome_notes: Notes on how the decision played out.
        stakeholders: Updated stakeholder list.
        initiative: Link to initiative.
        title: Updated title.
        linked_type: Hierarchy entity type.
        linked_id: ID of linked hierarchy item.
        linked_title: Title of linked hierarchy item.
        source: How this decision was created.
        source_page_id: Notion page ID if imported.
        requested_by: Who needs this decision.
        requested_from: Who should make it.
        request_reason: Why it's needed / what's blocked.
        from_workstream: Which workstream/task triggered this.
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
            for field in ("linked_type", "linked_id", "linked_title", "source",
                          "source_page_id", "requested_by", "requested_from",
                          "request_reason", "from_workstream"):
                val = locals()[field]
                if val:
                    d[field] = val
            d["updated_at"] = datetime.now(timezone.utc).isoformat()
            _save_decisions(decisions)

            status_label = {
                "decided": "decided",
                "pending": "pending",
                "revisit": "flagged for revisit",
                "request": "requested",
            }.get(d.get("status", ""), d.get("status", ""))

            parts = [f"Updated decision: {d.get('title', '')}"]
            if status:
                parts.append(f"now {status_label}")
            if outcome_notes:
                parts.append("outcome notes added")

            return {
                "message": "Decision updated.",
                "decision": d,
                "voice_summary": ". ".join(parts) + ".",
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


_ISO_TS_TAIL = re.compile(
    r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}[\.\d]*(?:[+-]\d{2}:\d{2}|Z)?$'
)


def _clean_page_title(raw: str) -> str:
    """Strip trailing ISO timestamps from Notion page titles."""
    return _ISO_TS_TAIL.sub("", raw).strip() or raw


def import_notion_decisions() -> dict[str, Any]:
    """Preview decisions from the Notion knowledge graph for import.

    Reads scanned Notion page data and returns decisions not yet in the register.
    """
    from integrations.intel import _load_intel

    intel = _load_intel()
    page_index = intel.get("page_index", {})
    existing = _load_decisions()
    existing_titles = {d.get("title", "").strip().lower() for d in existing}

    candidates: list[dict] = []
    for page_id, page in page_index.items():
        page_title = _clean_page_title(page.get("title", ""))
        last_edited = page.get("last_edited", "")
        for dec in page.get("decisions", []):
            # Normalise string-format decisions from LLM extraction
            if isinstance(dec, str):
                dec = {"text": dec, "by": ""}
            elif not isinstance(dec, dict):
                continue
            text = dec.get("text", "").strip()
            if not text:
                continue
            already = text.lower() in existing_titles
            candidates.append({
                "text": text,
                "by": dec.get("by", ""),
                "page_id": page_id,
                "page_title": page_title,
                "last_edited": last_edited,
                "already_imported": already,
            })

    return {"decisions": candidates, "count": len(candidates)}


def commit_notion_import(items: list[dict]) -> dict[str, Any]:
    """Import selected Notion decisions into the decision register.

    Args:
        items: List of dicts with keys: text, by, page_id, page_title.
    """
    imported: list[dict] = []
    for item in items:
        result = log_decision(
            title=item.get("text", ""),
            decided_by=item.get("by", ""),
            source="notion",
            source_page_id=item.get("page_id", ""),
            status="decided",
        )
        if "decision" in result:
            imported.append(result["decision"])

    return {
        "imported": len(imported),
        "decisions": imported,
        "message": f"Imported {len(imported)} decisions from Notion.",
    }
