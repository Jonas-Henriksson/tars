"""Strategic themes — highest-level grouping in the agile hierarchy.

Themes represent broad strategic investment areas that group related
initiatives. They sit at the top of the agile hierarchy:

    Theme (strategic investment area)
      └── Initiative (strategic goal)
            └── Epic (large deliverable)
                  └── User Story (user-facing value)
                        └── Task (atomic work item)

Examples: "Digital Transformation", "Market Expansion", "Operational Excellence".
"""
from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_DATA_FILE = Path(__file__).parent.parent / "themes.json"

THEME_STATUSES = ("active", "completed", "paused")


def _load_data() -> dict:
    if _DATA_FILE.exists():
        try:
            return json.loads(_DATA_FILE.read_text())
        except (json.JSONDecodeError, OSError):
            logger.warning("Failed to load themes, starting fresh")
    return {"themes": []}


def _save_data(data: dict) -> None:
    _DATA_FILE.write_text(json.dumps(data, indent=2, default=str))


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------

def create_theme(
    title: str,
    description: str = "",
    status: str = "active",
    source: str = "confirmed",
) -> dict[str, Any]:
    """Create a new strategic theme.

    Args:
        title: Theme name (e.g. "Digital Transformation").
        description: What this strategic area covers.
        status: active | completed | paused.
        source: "confirmed" (human-created/approved) | "auto" (AI-proposed).
    """
    data = _load_data()

    theme = {
        "id": uuid.uuid4().hex[:8],
        "title": title,
        "description": description,
        "status": status if status in THEME_STATUSES else "active",
        "source": source if source in ("confirmed", "auto") else "confirmed",
        "created_at": _now(),
        "updated_at": _now(),
    }

    data["themes"].append(theme)
    _save_data(data)

    return {
        "message": f"Theme created: {title}",
        "theme": theme,
        "voice_summary": f"Created strategic theme '{title}'.",
    }


def get_themes(
    status: str = "",
) -> dict[str, Any]:
    """Get strategic themes with optional status filter.

    Args:
        status: Filter by status (active, completed, paused).
    """
    data = _load_data()
    themes = data.get("themes", [])

    if status:
        themes = [t for t in themes if t.get("status") == status]

    # Enrich with initiative counts
    try:
        from integrations.initiatives import get_initiatives
        all_initiatives = get_initiatives().get("initiatives", [])
    except Exception:
        all_initiatives = []

    for theme in themes:
        tid = theme["id"]
        linked = [i for i in all_initiatives if i.get("theme_id") == tid]
        theme["initiative_count"] = len(linked)

    # Sort: active first
    status_order = {"active": 0, "paused": 1, "completed": 2}
    themes.sort(key=lambda t: status_order.get(t.get("status", ""), 3))

    active = sum(1 for t in themes if t.get("status") == "active")

    return {
        "themes": themes,
        "count": len(themes),
        "active": active,
        "voice_summary": f"{len(themes)} strategic theme{'s' if len(themes) != 1 else ''}, {active} active.",
    }


def update_theme(
    theme_id: str,
    title: str = "",
    description: str = "",
    status: str = "",
) -> dict[str, Any]:
    """Update a strategic theme.

    Args:
        theme_id: The theme ID.
        title: New title.
        description: New description.
        status: New status (active, completed, paused).
    """
    data = _load_data()

    for t in data["themes"]:
        if t.get("id") == theme_id:
            if title:
                t["title"] = title
            if description:
                t["description"] = description
            if status and status in THEME_STATUSES:
                t["status"] = status
            t["updated_at"] = _now()
            _save_data(data)

            return {
                "message": "Theme updated.",
                "theme": t,
                "voice_summary": f"Updated theme '{t.get('title', '')}'.",
            }

    return {"error": f"Theme not found: {theme_id}"}


def approve_theme(theme_id: str) -> dict[str, Any]:
    """Approve an auto-generated theme (change source from 'auto' to 'confirmed')."""
    data = _load_data()

    for t in data["themes"]:
        if t.get("id") == theme_id:
            t["source"] = "confirmed"
            t["updated_at"] = _now()
            _save_data(data)
            return {"message": "Theme approved.", "theme": t}

    return {"error": f"Theme not found: {theme_id}"}


def delete_theme(theme_id: str) -> dict[str, Any]:
    """Delete a strategic theme.

    Note: This does NOT delete linked initiatives — they become unlinked.
    """
    data = _load_data()
    original = len(data.get("themes", []))
    data["themes"] = [t for t in data.get("themes", []) if t.get("id") != theme_id]

    if len(data.get("themes", [])) == original:
        return {"error": f"Theme not found: {theme_id}"}

    _save_data(data)
    return {"message": "Theme deleted.", "id": theme_id}
