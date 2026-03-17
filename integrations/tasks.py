"""Microsoft To Do tasks integration — list, create, and complete tasks."""
from __future__ import annotations

import logging
from typing import Any

from integrations.ms_auth import get_token_silent
from integrations.ms_graph import graph_get, graph_post

logger = logging.getLogger(__name__)


def _require_token() -> str:
    """Get a valid token or raise with a helpful message."""
    token = get_token_silent()
    if token is None:
        raise RuntimeError(
            "Not signed in to Microsoft 365. "
            "Use /login to connect your account first."
        )
    return token


def _format_task(task: dict[str, Any]) -> dict[str, Any]:
    """Extract key fields from a Graph API task object."""
    due = task.get("dueDateTime")
    return {
        "id": task.get("id", ""),
        "title": task.get("title", "(No title)"),
        "status": task.get("status", "notStarted"),
        "importance": task.get("importance", "normal"),
        "due_date": due.get("dateTime", "")[:10] if due else "",
        "body": task.get("body", {}).get("content", ""),
        "created": task.get("createdDateTime", ""),
    }


def _format_task_list(task_list: dict[str, Any]) -> dict[str, Any]:
    """Extract key fields from a Graph API task list object."""
    return {
        "id": task_list.get("id", ""),
        "name": task_list.get("displayName", "(Unnamed)"),
        "is_default": task_list.get("wellknownListName") == "defaultList",
    }


async def get_task_lists() -> dict[str, Any]:
    """Get all task lists for the user.

    Returns:
        Dict with "lists" and "count".
    """
    token = _require_token()
    data = await graph_get("/me/todo/lists", token)
    lists = [_format_task_list(tl) for tl in data.get("value", [])]
    return {"lists": lists, "count": len(lists)}


async def get_tasks(
    list_id: str | None = None,
    include_completed: bool = False,
    max_results: int = 25,
) -> dict[str, Any]:
    """Get tasks from a task list.

    Args:
        list_id: Task list ID. If None, uses the default "Tasks" list.
        include_completed: Whether to include completed tasks.
        max_results: Max tasks to return.

    Returns:
        Dict with "tasks" list and "count".
    """
    token = _require_token()

    if list_id is None:
        # Find the default task list
        lists_data = await graph_get("/me/todo/lists", token)
        default_list = None
        for tl in lists_data.get("value", []):
            if tl.get("wellknownListName") == "defaultList":
                default_list = tl
                break
        if default_list is None:
            # Fall back to first list
            lists = lists_data.get("value", [])
            if not lists:
                return {"tasks": [], "count": 0, "list_name": "Tasks"}
            default_list = lists[0]
        list_id = default_list["id"]
        list_name = default_list.get("displayName", "Tasks")
    else:
        list_name = list_id  # Will be the ID if specified directly

    params: dict[str, str] = {"$top": str(max_results)}
    if not include_completed:
        params["$filter"] = "status ne 'completed'"

    data = await graph_get(f"/me/todo/lists/{list_id}/tasks", token, params)
    tasks = [_format_task(t) for t in data.get("value", [])]

    return {"tasks": tasks, "count": len(tasks), "list_name": list_name}


async def create_task(
    title: str,
    list_id: str | None = None,
    due_date: str = "",
    importance: str = "normal",
    body: str = "",
) -> dict[str, Any]:
    """Create a new task.

    Args:
        title: Task title.
        list_id: Task list ID. If None, uses the default list.
        due_date: Optional due date (YYYY-MM-DD format).
        importance: "low", "normal", or "high".
        body: Optional task description.

    Returns:
        Dict with created task details.
    """
    token = _require_token()

    if list_id is None:
        lists_data = await graph_get("/me/todo/lists", token)
        for tl in lists_data.get("value", []):
            if tl.get("wellknownListName") == "defaultList":
                list_id = tl["id"]
                break
        if list_id is None:
            lists = lists_data.get("value", [])
            if not lists:
                raise RuntimeError("No task lists found.")
            list_id = lists[0]["id"]

    task_body: dict[str, Any] = {
        "title": title,
        "importance": importance,
    }

    if due_date:
        task_body["dueDateTime"] = {
            "dateTime": f"{due_date}T00:00:00",
            "timeZone": "UTC",
        }

    if body:
        task_body["body"] = {"contentType": "text", "content": body}

    data = await graph_post(f"/me/todo/lists/{list_id}/tasks", token, task_body)
    return _format_task(data)


async def complete_task(task_id: str, list_id: str | None = None) -> dict[str, Any]:
    """Mark a task as completed.

    Args:
        task_id: The task ID.
        list_id: Task list ID. If None, uses the default list.

    Returns:
        Dict with updated task details.
    """
    token = _require_token()

    if list_id is None:
        lists_data = await graph_get("/me/todo/lists", token)
        for tl in lists_data.get("value", []):
            if tl.get("wellknownListName") == "defaultList":
                list_id = tl["id"]
                break
        if list_id is None:
            lists = lists_data.get("value", [])
            if not lists:
                raise RuntimeError("No task lists found.")
            list_id = lists[0]["id"]

    # Graph API uses PATCH for updates, but we can use POST-like approach
    # We need to add a PATCH method to ms_graph
    from integrations.ms_graph import graph_patch

    data = await graph_patch(
        f"/me/todo/lists/{list_id}/tasks/{task_id}",
        token,
        {"status": "completed"},
    )
    return _format_task(data)
