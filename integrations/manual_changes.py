"""Manual changes registry — tracks user edits to prevent auto-overwrite.

When users manually edit task titles, epic details, people profiles, or
delete/complete items, those changes are recorded here. The auto-populate
and enrichment systems consult this registry to:

1. Never re-create deleted items
2. Never overwrite manually-edited fields
3. Provide manual context to LLM for smarter enrichment decisions
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_REGISTRY_FILE = Path(__file__).parent.parent / "manual_changes.json"


def _load() -> dict[str, Any]:
    if _REGISTRY_FILE.exists():
        try:
            return json.loads(_REGISTRY_FILE.read_text())
        except (json.JSONDecodeError, OSError):
            pass
    return {
        "deleted_task_ids": [],
        "deleted_epic_ids": [],
        "deleted_story_ids": [],
        "edited_task_ids": [],
        "edited_epic_ids": [],
        "edited_people": [],
        "completed_task_ids": [],
    }


def _save(data: dict[str, Any]) -> None:
    _REGISTRY_FILE.write_text(json.dumps(data, indent=2, default=str))


def record_task_deleted(task_id: str) -> None:
    """Record that a task was manually deleted — don't re-create it."""
    data = _load()
    if task_id not in data["deleted_task_ids"]:
        data["deleted_task_ids"].append(task_id)
    _save(data)


def record_task_completed(task_id: str) -> None:
    """Record that a task was manually completed."""
    data = _load()
    if task_id not in data["completed_task_ids"]:
        data["completed_task_ids"].append(task_id)
    _save(data)


def record_task_edited(task_id: str) -> None:
    """Record that a task title/description was manually edited."""
    data = _load()
    if task_id not in data["edited_task_ids"]:
        data["edited_task_ids"].append(task_id)
    _save(data)


def record_epic_deleted(epic_id: str) -> None:
    """Record that an epic was manually deleted — don't re-create it."""
    data = _load()
    if epic_id not in data["deleted_epic_ids"]:
        data["deleted_epic_ids"].append(epic_id)
    _save(data)


def record_epic_edited(epic_id: str) -> None:
    """Record that an epic was manually edited."""
    data = _load()
    if epic_id not in data["edited_epic_ids"]:
        data["edited_epic_ids"].append(epic_id)
    _save(data)


def record_story_deleted(story_id: str) -> None:
    """Record that a story was manually deleted."""
    data = _load()
    if story_id not in data["deleted_story_ids"]:
        data["deleted_story_ids"].append(story_id)
    _save(data)


def record_person_edited(name: str) -> None:
    """Record that a person profile was manually edited."""
    data = _load()
    if name not in data["edited_people"]:
        data["edited_people"].append(name)
    _save(data)


def get_deleted_task_ids() -> set[str]:
    return set(_load().get("deleted_task_ids", []))


def get_completed_task_ids() -> set[str]:
    return set(_load().get("completed_task_ids", []))


def get_edited_task_ids() -> set[str]:
    return set(_load().get("edited_task_ids", []))


def get_deleted_epic_ids() -> set[str]:
    return set(_load().get("deleted_epic_ids", []))


def get_edited_epic_ids() -> set[str]:
    return set(_load().get("edited_epic_ids", []))


def get_deleted_story_ids() -> set[str]:
    return set(_load().get("deleted_story_ids", []))


def get_edited_people() -> set[str]:
    return set(_load().get("edited_people", []))
