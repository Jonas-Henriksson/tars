"""Notion meeting task extraction and tracking.

Parses meeting notes from Notion pages, extracts tasks (assigned to user and
others), groups them by owner and topic, and persists them for follow-up.

Task data is stored in notion_tracked_tasks.json.
"""
from __future__ import annotations

import json
import logging
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from integrations.notion import get_page_content, is_configured, search_pages

logger = logging.getLogger(__name__)

_TASKS_FILE = Path(__file__).parent.parent / "notion_tracked_tasks.json"


def _load_tasks() -> list[dict]:
    """Load tracked tasks from JSON file."""
    if _TASKS_FILE.exists():
        try:
            return json.loads(_TASKS_FILE.read_text())
        except (json.JSONDecodeError, OSError):
            return []
    return []


def _save_tasks(tasks: list[dict]) -> None:
    """Save tracked tasks to JSON file."""
    _TASKS_FILE.write_text(json.dumps(tasks, indent=2, default=str))


def _extract_tasks_from_text(text: str, source_title: str, source_url: str) -> list[dict]:
    """Extract tasks from meeting note text.

    Looks for patterns like:
    - [x] or [ ] checkbox items
    - "ACTION:" or "TODO:" prefixed lines
    - "@Name: do something" patterns
    - "Name to do something" patterns after task headers

    Returns list of extracted task dicts.
    """
    tasks = []

    lines = text.split("\n")
    current_topic = ""

    for line in lines:
        stripped = line.strip()

        # Track headings as topics
        if stripped.startswith("#"):
            current_topic = stripped.lstrip("#").strip()
            continue

        # Skip empty lines
        if not stripped:
            continue

        task_info = _parse_task_line(stripped)
        if task_info:
            # Use heading as topic; fall back to source page title if empty
            task_info["topic"] = current_topic or source_title
            task_info["source_title"] = source_title
            task_info["source_url"] = source_url
            tasks.append(task_info)

    return tasks


def _parse_task_line(line: str) -> dict | None:
    """Try to parse a single line as a task.

    Returns dict with owner, description, completed fields, or None.
    """
    # Checkbox pattern: [x] or [ ] with optional @owner
    checkbox_match = re.match(r"\[([ xX])\]\s*(.+)", line)
    if checkbox_match:
        completed = checkbox_match.group(1).lower() == "x"
        text = checkbox_match.group(2).strip()
        owner, description = _extract_owner(text)
        return {
            "description": description,
            "owner": owner,
            "completed": completed,
        }

    # ACTION: or TODO: prefix
    action_match = re.match(r"(?:ACTION|TODO|TASK)[:\s]+(.+)", line, re.IGNORECASE)
    if action_match:
        text = action_match.group(1).strip()
        owner, description = _extract_owner(text)
        return {
            "description": description,
            "owner": owner,
            "completed": False,
        }

    # Bullet with @mention: • @Name do something
    mention_match = re.match(r"[•\-\*]\s*@(\w[\w\s]*?)[\s:]+(.+)", line)
    if mention_match:
        return {
            "description": mention_match.group(2).strip(),
            "owner": mention_match.group(1).strip(),
            "completed": False,
        }

    return None


def _extract_owner(text: str) -> tuple[str, str]:
    """Extract @owner from text. Returns (owner, remaining_text)."""
    # @Name at start: "@Jonas: review the doc"
    match = re.match(r"@(\w[\w\s]*?)[\s:]+(.+)", text)
    if match:
        return match.group(1).strip(), match.group(2).strip()

    # @Name anywhere in parentheses: "Review doc (@Jonas)"
    paren_match = re.search(r"\(@(\w[\w\s]*?)\)", text)
    if paren_match:
        owner = paren_match.group(1).strip()
        description = text[:paren_match.start()].strip() + text[paren_match.end():].strip()
        return owner, description.strip()

    return "", text


async def extract_meeting_tasks(page_id: str) -> dict:
    """Extract tasks from a Notion meeting notes page.

    Args:
        page_id: The Notion page ID to parse.

    Returns:
        Dict with extracted tasks grouped by owner.
    """
    if not is_configured():
        raise RuntimeError("Notion is not configured. Set NOTION_API_KEY in .env.")

    page = await get_page_content(page_id)
    raw_tasks = _extract_tasks_from_text(page["content"], page["title"], page["url"])

    if not raw_tasks:
        return {
            "message": f"No tasks found in '{page['title']}'.",
            "page_title": page["title"],
            "tasks": [],
        }

    # Group by owner
    by_owner: dict[str, list] = {}
    for task in raw_tasks:
        owner = task["owner"] or "Unassigned"
        by_owner.setdefault(owner, []).append(task)

    return {
        "page_title": page["title"],
        "page_url": page["url"],
        "page_created_time": page.get("created_time", ""),
        "total_tasks": len(raw_tasks),
        "tasks_by_owner": by_owner,
        "tasks": raw_tasks,
    }


async def track_meeting_tasks(page_id: str) -> dict:
    """Extract and save tasks from a meeting page for ongoing tracking.

    Args:
        page_id: The Notion page ID.

    Returns:
        Dict with saved task count and summary.
    """
    extracted = await extract_meeting_tasks(page_id)

    if not extracted["tasks"]:
        return extracted

    existing = _load_tasks()
    now = datetime.now(timezone.utc).isoformat()
    page_created = extracted.get("page_created_time", "")
    added = 0

    for task in extracted["tasks"]:
        task_entry = {
            "id": uuid.uuid4().hex[:8],
            "description": task["description"],
            "owner": task["owner"] or "Unassigned",
            "topic": task["topic"],
            "source_title": task["source_title"],
            "source_url": task["source_url"],
            "source_page_id": page_id,
            "completed": task["completed"],
            "status": "done" if task["completed"] else "open",
            "followed_up": False,
            "created_at": page_created or now,
            "scanned_at": now,
        }
        existing.append(task_entry)
        added += 1

    _save_tasks(existing)

    return {
        "message": f"Tracked {added} tasks from '{extracted['page_title']}'.",
        "added": added,
        "tasks_by_owner": extracted["tasks_by_owner"],
    }


def get_tracked_tasks(owner: str = "", topic: str = "",
                      status: str = "", include_completed: bool = False) -> dict:
    """Get tracked meeting tasks with optional filters.

    Args:
        owner: Filter by task owner name (case-insensitive partial match).
        topic: Filter by topic (case-insensitive partial match).
        status: Filter by status: 'open', 'done', 'followed_up'.
        include_completed: Include completed tasks. Default false.

    Returns:
        Dict with tasks grouped by owner and topic.
    """
    tasks = _load_tasks()

    # Apply filters
    if not include_completed and not status:
        tasks = [t for t in tasks if t.get("status") != "done"]
    if owner:
        owner_lower = owner.lower()
        tasks = [t for t in tasks if owner_lower in t.get("owner", "").lower()]
    if topic:
        topic_lower = topic.lower()
        tasks = [t for t in tasks if topic_lower in t.get("topic", "").lower()]
    if status:
        tasks = [t for t in tasks if t.get("status") == status]

    # Group by owner
    by_owner: dict[str, list] = {}
    for t in tasks:
        by_owner.setdefault(t.get("owner", "Unassigned"), []).append(t)

    # Group by topic
    by_topic: dict[str, list] = {}
    for t in tasks:
        by_topic.setdefault(t.get("topic", "General"), []).append(t)

    return {
        "tasks": tasks,
        "count": len(tasks),
        "by_owner": by_owner,
        "by_topic": by_topic,
    }


def update_task_status(task_id: str, status: str) -> dict:
    """Update the status of a tracked task.

    Args:
        task_id: The task ID.
        status: New status: 'open', 'done', or 'followed_up'.

    Returns:
        Updated task dict.
    """
    tasks = _load_tasks()
    for task in tasks:
        if task["id"] == task_id:
            task["status"] = status
            if status == "done":
                task["completed"] = True
            elif status == "followed_up":
                task["followed_up"] = True
            _save_tasks(tasks)
            return {"message": f"Task '{task['description'][:50]}' updated to '{status}'.", "task": task}

    return {"error": f"Task not found: {task_id}"}


def update_task(task_id: str, **fields) -> dict:
    """Update arbitrary fields on a tracked task.

    Supports: owner, topic, description, status, follow_up_date.
    """
    tasks = _load_tasks()
    for task in tasks:
        if task["id"] == task_id:
            for key in ("owner", "topic", "description", "status", "follow_up_date"):
                if key in fields and fields[key] is not None:
                    task[key] = fields[key]
            if "status" in fields:
                if fields["status"] == "done":
                    task["completed"] = True
                elif fields["status"] == "open":
                    task["completed"] = False
            _save_tasks(tasks)
            return {"message": "Task updated.", "task": task}
    return {"error": f"Task not found: {task_id}"}


def get_owner_frequencies() -> list[dict]:
    """Get owners sorted by task count (most frequent first)."""
    tasks = _load_tasks()
    counts: dict[str, int] = {}
    for t in tasks:
        owner = t.get("owner", "Unassigned")
        counts[owner] = counts.get(owner, 0) + 1
    return sorted(
        [{"name": k, "count": v} for k, v in counts.items()],
        key=lambda x: x["count"],
        reverse=True,
    )


async def search_meeting_notes(query: str, max_results: int = 5) -> dict:
    """Search Notion for meeting notes and return summaries.

    Args:
        query: Search text (e.g. "weekly standup", "Q1 planning").
        max_results: Max pages to return.

    Returns:
        Dict with matching pages and their content previews.
    """
    if not is_configured():
        raise RuntimeError("Notion is not configured. Set NOTION_API_KEY in .env.")

    results = await search_pages(query, max_results=max_results)

    pages_with_preview = []
    for page in results["pages"]:
        try:
            content = await get_page_content(page["id"])
            preview = content["content"][:500]
            if len(content["content"]) > 500:
                preview += "..."
            page["content_preview"] = preview
        except Exception as exc:
            page["content_preview"] = f"(Could not load content: {exc})"
        pages_with_preview.append(page)

    return {"pages": pages_with_preview, "count": len(pages_with_preview)}
