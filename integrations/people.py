"""People profiles — relationship management backed by intelligence data.

Stores editable person profiles (role, relationship, org, notes) alongside
auto-populated data from Notion scans (mentions, topics, tasks, pages).
Profiles persist to disk and merge with live intel on read.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_PROFILES_FILE = Path(__file__).parent.parent / "people_profiles.json"


def _load_profiles() -> dict[str, dict]:
    """Load saved person profiles from disk."""
    if _PROFILES_FILE.exists():
        try:
            return json.loads(_PROFILES_FILE.read_text())
        except (json.JSONDecodeError, OSError):
            logger.warning("Failed to load people profiles, starting fresh")
    return {}


def _save_profiles(profiles: dict[str, dict]) -> None:
    _PROFILES_FILE.write_text(json.dumps(profiles, indent=2, default=str))


def _get_intel_data() -> dict:
    """Load intel data (best-effort)."""
    try:
        from integrations.intel import get_intel
        return get_intel()
    except Exception:
        return {}


def _infer_role_from_context(name: str, intel: dict) -> dict[str, Any]:
    """Try to infer a person's role, org, and relationship from intel context.

    Looks at page titles, topics, task descriptions, and source contexts
    for clues about the person's function.
    """
    hints: dict[str, Any] = {"topics": set(), "context_snippets": []}
    page_index = intel.get("page_index", {})
    smart_tasks = intel.get("smart_tasks", [])
    name_lower = name.lower()

    # Scan pages for context
    for _pid, page in page_index.items():
        page_people = [p.lower() for p in page.get("people", [])]
        if not any(name_lower in p for p in page_people):
            continue

        title = page.get("title", "")
        summary = page.get("summary", "")
        topics = page.get("topics", [])
        for t in topics:
            hints["topics"].add(t)

        # Check if it's a 1:1 meeting (strong relationship signal)
        if "1:1" in title.lower() or "one-on-one" in title.lower():
            hints["is_direct_report_or_manager"] = True
            hints["context_snippets"].append(f"Regular 1:1: {title}")
        else:
            if summary:
                hints["context_snippets"].append(summary[:150])

    # Scan tasks for delegation patterns
    tasks_assigned_to = []
    tasks_assigned_by = []
    for task in smart_tasks:
        owner = task.get("owner", "")
        desc = task.get("description", "")
        context = task.get("source_context", "")
        if name_lower in owner.lower():
            tasks_assigned_to.append(desc)
        elif name_lower in context.lower():
            tasks_assigned_by.append(desc)

    hints["tasks_owned_count"] = len(tasks_assigned_to)
    hints["tasks_mentioned_count"] = len(tasks_assigned_by)

    # Infer role from topic patterns — pick dominant function only
    # Count topic occurrences from pages to weight the inference
    topic_counts: dict[str, int] = {}
    for _pid, page in page_index.items():
        page_people = [p.lower() for p in page.get("people", [])]
        if any(name_lower in p for p in page_people):
            for t in page.get("topics", []):
                topic_counts[t] = topic_counts.get(t, 0) + 1

    # Map topics to functional areas with weights
    function_scores: dict[str, int] = {}
    topic_to_function = {
        "engineering": "Engineering",
        "security": "Security",
        "hiring": "HR / People",
        "budget": "Finance",
        "finance": "Finance",
        "strategy": "Leadership",
        "management": "Leadership",
        "sales": "Commercial",
        "marketing": "Commercial",
        "operations": "Operations",
        "product": "Product",
    }
    for topic, count in topic_counts.items():
        fn = topic_to_function.get(topic)
        if fn:
            function_scores[fn] = function_scores.get(fn, 0) + count

    # Pick top 1-2 functions (the dominant areas)
    sorted_fns = sorted(function_scores.items(), key=lambda x: -x[1])
    top_functions = [fn for fn, _score in sorted_fns[:2]] if sorted_fns else []
    hints["inferred_function"] = ", ".join(top_functions) if top_functions else ""
    hints["topics"] = sorted(hints["topics"])

    # Determine relationship type
    if hints.get("is_direct_report_or_manager"):
        hints["inferred_relationship"] = "Direct report or manager (has 1:1s)"
    elif tasks_assigned_to:
        hints["inferred_relationship"] = "Delegate / team member (receives tasks)"
    elif tasks_assigned_by:
        hints["inferred_relationship"] = "Collaborator (mentioned in task context)"
    else:
        hints["inferred_relationship"] = "Mentioned in documents"

    return hints


def get_all_people() -> dict[str, Any]:
    """Get all people with merged intel + saved profile data.

    Returns profiles enriched with:
    - Auto-populated intel data (mentions, pages, topics, tasks)
    - Inferred role/relationship from context analysis
    - User-edited fields (role, relationship, org, notes)
    """
    intel = _get_intel_data()
    profiles = _load_profiles()
    intel_people = intel.get("people", {})
    page_index = intel.get("page_index", {})
    smart_tasks = intel.get("smart_tasks", [])

    # Merge: start from intel people, overlay saved profiles
    all_names = set(intel_people.keys()) | set(profiles.keys())
    result = {}

    for name in sorted(all_names):
        # Base from saved profile
        saved = profiles.get(name, {})

        # Intel data
        mention_count = intel_people.get(name, 0)

        # Find pages
        pages = []
        for pid, page in page_index.items():
            page_people = page.get("people", [])
            if any(name.lower() in p.lower() for p in page_people):
                pages.append({
                    "title": page.get("title", ""),
                    "url": page.get("url", ""),
                    "topics": page.get("topics", []),
                    "last_edited": page.get("last_edited", ""),
                })

        # Find tasks
        tasks_owned = []
        for task in smart_tasks:
            if name.lower() in task.get("owner", "").lower():
                tasks_owned.append({
                    "id": task.get("id"),
                    "description": task.get("description", ""),
                    "status": task.get("status", ""),
                    "quadrant": task.get("priority", {}).get("quadrant"),
                    "follow_up_date": task.get("follow_up_date", ""),
                })

        # Infer from context if no saved data
        inferred = _infer_role_from_context(name, intel)

        profile = {
            "name": name,
            "mentions": mention_count,
            # Editable fields — saved values take precedence over inferred
            "role": saved.get("role") or inferred.get("inferred_function", ""),
            "relationship": saved.get("relationship") or inferred.get("inferred_relationship", ""),
            "organization": saved.get("organization", ""),
            "notes": saved.get("notes", ""),
            "email": saved.get("email", ""),
            # Auto-populated
            "topics": inferred.get("topics", []),
            "pages": pages,
            "pages_count": len(pages),
            "tasks_owned": tasks_owned,
            "tasks_count": len(tasks_owned),
            "context_snippets": inferred.get("context_snippets", [])[:5],
            "has_one_on_ones": inferred.get("is_direct_report_or_manager", False),
            # Meta
            "is_saved": name in profiles,
            "last_updated": saved.get("last_updated", ""),
        }
        result[name] = profile

    return {
        "people": result,
        "count": len(result),
    }


def get_person(name: str) -> dict[str, Any]:
    """Get a single person's full profile."""
    all_people = get_all_people()
    people = all_people.get("people", {})

    # Try exact match first, then case-insensitive
    if name in people:
        return people[name]
    for key, profile in people.items():
        if key.lower() == name.lower():
            return profile

    return {"error": f"Person not found: {name}"}


def update_person(name: str, **fields) -> dict[str, Any]:
    """Update a person's editable profile fields.

    Editable fields: role, relationship, organization, notes, email.
    """
    profiles = _load_profiles()

    # Find or create profile
    existing = profiles.get(name, {})
    allowed = {"role", "relationship", "organization", "notes", "email"}

    for key, value in fields.items():
        if key in allowed:
            existing[key] = value

    existing["last_updated"] = datetime.now(timezone.utc).isoformat()
    profiles[name] = existing
    _save_profiles(profiles)

    return {"message": "Profile updated.", "name": name, "fields": {k: v for k, v in fields.items() if k in allowed}}


def add_person(name: str, **fields) -> dict[str, Any]:
    """Manually add a person who may not exist in intel data."""
    profiles = _load_profiles()
    if name in profiles:
        return {"error": f"Person already exists: {name}"}

    allowed = {"role", "relationship", "organization", "notes", "email"}
    profile = {k: v for k, v in fields.items() if k in allowed}
    profile["last_updated"] = datetime.now(timezone.utc).isoformat()
    profile["manually_added"] = True
    profiles[name] = profile
    _save_profiles(profiles)

    return {"message": "Person added.", "name": name}


def rename_person(old_name: str, new_name: str) -> dict[str, Any]:
    """Rename a person across all data sources. If new_name already exists, merge.

    Updates: people_profiles.json, notion_tracked_tasks.json, notion_intel.json.
    Returns summary of changes made.
    """
    old_name = old_name.strip()
    new_name = new_name.strip()
    if not new_name:
        return {"error": "New name cannot be empty."}
    if old_name == new_name:
        return {"error": "Names are identical."}

    changes: dict[str, Any] = {"old_name": old_name, "new_name": new_name}

    # --- 1. People profiles ---
    profiles = _load_profiles()
    old_profile = profiles.pop(old_name, {})
    if new_name in profiles:
        # Merge: keep existing new_name fields, fill gaps from old
        merged = profiles[new_name]
        for key in ("role", "relationship", "organization", "notes", "email"):
            if not merged.get(key) and old_profile.get(key):
                merged[key] = old_profile[key]
        # Append notes if both have them
        if old_profile.get("notes") and merged.get("notes"):
            merged["notes"] = merged["notes"].rstrip() + "\n" + old_profile["notes"]
        merged["last_updated"] = datetime.now(timezone.utc).isoformat()
        profiles[new_name] = merged
        changes["profiles"] = "merged"
    elif old_profile:
        old_profile["last_updated"] = datetime.now(timezone.utc).isoformat()
        profiles[new_name] = old_profile
        changes["profiles"] = "renamed"
    else:
        changes["profiles"] = "no_profile"
    _save_profiles(profiles)

    # --- 2. Tracked tasks (owner field) ---
    from integrations.notion_tasks import _load_tasks, _save_tasks
    tasks = _load_tasks()
    task_count = 0
    for task in tasks:
        if task.get("owner", "").lower() == old_name.lower():
            task["owner"] = new_name
            task_count += 1
    if task_count:
        _save_tasks(tasks)
    changes["tasks_updated"] = task_count

    # --- 3. Intel data (people counter + page_index people lists + smart_tasks) ---
    try:
        from integrations.intel import _load_intel, _save_intel
        intel = _load_intel()
        intel_changed = False

        # People counter
        people = intel.get("people", {})
        if old_name in people:
            old_count = people.pop(old_name)
            people[new_name] = people.get(new_name, 0) + old_count
            intel_changed = True

        # Page index — rename in each page's people list
        for _pid, page in intel.get("page_index", {}).items():
            page_people = page.get("people", [])
            renamed = False
            for i, p in enumerate(page_people):
                if p.lower() == old_name.lower():
                    page_people[i] = new_name
                    renamed = True
            if renamed:
                # Deduplicate
                page["people"] = list(dict.fromkeys(page_people))
                intel_changed = True

        # Smart tasks
        for task in intel.get("smart_tasks", []):
            if task.get("owner", "").lower() == old_name.lower():
                task["owner"] = new_name
                intel_changed = True

        if intel_changed:
            _save_intel(intel)
        changes["intel_updated"] = intel_changed
    except Exception as exc:
        logger.warning("Failed to update intel data during rename: %s", exc)
        changes["intel_updated"] = False

    changes["message"] = f"Renamed '{old_name}' → '{new_name}'."
    return changes


def delete_person(name: str) -> dict[str, Any]:
    """Remove a person's saved profile (intel data remains)."""
    profiles = _load_profiles()
    if name not in profiles:
        return {"error": f"No saved profile for: {name}"}
    del profiles[name]
    _save_profiles(profiles)
    return {"message": "Profile removed.", "name": name}
