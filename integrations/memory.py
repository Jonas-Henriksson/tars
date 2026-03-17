"""User memory — persists preferences, facts, and notes across sessions."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_MEMORY_FILE = Path(__file__).parent.parent / "user_memory.json"

_DEFAULT: dict[str, Any] = {"preferences": {}, "facts": {}, "notes": []}


def _load() -> dict[str, Any]:
    if _MEMORY_FILE.exists():
        try:
            return json.loads(_MEMORY_FILE.read_text())
        except (json.JSONDecodeError, OSError):
            pass
    return {"preferences": {}, "facts": {}, "notes": []}


def _save(data: dict[str, Any]) -> None:
    _MEMORY_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False))


# ---- Public API ----

def get_memory() -> dict[str, Any]:
    """Return the full user memory object."""
    return _load()


def set_preference(key: str, value: str) -> dict[str, Any]:
    """Store or update a user preference."""
    data = _load()
    data["preferences"][key.strip()] = value.strip()
    _save(data)
    return {"ok": True, "key": key, "value": value}


def set_fact(key: str, value: str) -> dict[str, Any]:
    """Store or update a personal fact about the user."""
    data = _load()
    data["facts"][key.strip()] = value.strip()
    _save(data)
    return {"ok": True, "key": key, "value": value}


def add_note(text: str) -> dict[str, Any]:
    """Append a freeform note to remember across sessions."""
    data = _load()
    note = {"text": text.strip(), "added_at": datetime.now(timezone.utc).isoformat()}
    data["notes"].append(note)
    _save(data)
    return {"ok": True, "note": note, "total_notes": len(data["notes"])}


def delete_note(index: int) -> dict[str, Any]:
    """Remove a note by its 0-based index."""
    data = _load()
    notes = data.get("notes", [])
    if index < 0 or index >= len(notes):
        return {"ok": False, "error": f"Index {index} out of range (have {len(notes)} notes)"}
    removed = notes.pop(index)
    _save(data)
    return {"ok": True, "removed": removed}


def clear_memory() -> dict[str, Any]:
    """Wipe all stored memory."""
    data: dict[str, Any] = {"preferences": {}, "facts": {}, "notes": []}
    _save(data)
    return {"ok": True, "message": "Memory cleared."}
