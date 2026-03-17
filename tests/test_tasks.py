"""Tests for Microsoft To Do tasks integration."""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from integrations.tasks import _format_task, _format_task_list, create_task, get_task_lists, get_tasks


class TestFormatTask:
    def test_format_basic_task(self):
        raw = {
            "id": "task1",
            "title": "Buy groceries",
            "status": "notStarted",
            "importance": "high",
            "dueDateTime": {"dateTime": "2025-01-20T00:00:00", "timeZone": "UTC"},
            "body": {"contentType": "text", "content": "Milk, eggs, bread"},
            "createdDateTime": "2025-01-15T10:00:00Z",
        }
        result = _format_task(raw)

        assert result["title"] == "Buy groceries"
        assert result["status"] == "notStarted"
        assert result["importance"] == "high"
        assert result["due_date"] == "2025-01-20"
        assert result["body"] == "Milk, eggs, bread"

    def test_format_task_no_due_date(self):
        raw = {"id": "task2", "title": "Someday task"}
        result = _format_task(raw)

        assert result["title"] == "Someday task"
        assert result["due_date"] == ""


class TestFormatTaskList:
    def test_format_default_list(self):
        raw = {"id": "list1", "displayName": "Tasks", "wellknownListName": "defaultList"}
        result = _format_task_list(raw)

        assert result["name"] == "Tasks"
        assert result["is_default"] is True

    def test_format_custom_list(self):
        raw = {"id": "list2", "displayName": "Shopping"}
        result = _format_task_list(raw)

        assert result["name"] == "Shopping"
        assert result["is_default"] is False


class TestGetTaskLists:
    @pytest.mark.asyncio
    async def test_get_task_lists_success(self):
        mock_data = {
            "value": [
                {"id": "l1", "displayName": "Tasks", "wellknownListName": "defaultList"},
                {"id": "l2", "displayName": "Work"},
            ]
        }

        with (
            patch("integrations.tasks.get_token_silent", return_value="fake-token"),
            patch("integrations.tasks.graph_get", new_callable=AsyncMock, return_value=mock_data),
        ):
            result = await get_task_lists()

        assert result["count"] == 2
        assert result["lists"][0]["name"] == "Tasks"


class TestGetTasks:
    @pytest.mark.asyncio
    async def test_get_tasks_default_list(self):
        mock_lists = {
            "value": [{"id": "default-id", "displayName": "Tasks", "wellknownListName": "defaultList"}]
        }
        mock_tasks = {
            "value": [
                {"id": "t1", "title": "Do laundry", "status": "notStarted"},
                {"id": "t2", "title": "Call dentist", "status": "notStarted"},
            ]
        }

        async def mock_get(endpoint, token, params=None):
            if "lists" in endpoint and "tasks" not in endpoint.split("lists/")[-1]:
                return mock_lists
            return mock_tasks

        with (
            patch("integrations.tasks.get_token_silent", return_value="fake-token"),
            patch("integrations.tasks.graph_get", side_effect=mock_get),
        ):
            result = await get_tasks()

        assert result["count"] == 2
        assert result["tasks"][0]["title"] == "Do laundry"
        assert result["list_name"] == "Tasks"

    @pytest.mark.asyncio
    async def test_get_tasks_not_signed_in(self):
        with patch("integrations.tasks.get_token_silent", return_value=None):
            with pytest.raises(RuntimeError, match="Not signed in"):
                await get_tasks()


class TestCreateTask:
    @pytest.mark.asyncio
    async def test_create_task_success(self):
        mock_lists = {
            "value": [{"id": "default-id", "displayName": "Tasks", "wellknownListName": "defaultList"}]
        }
        created = {
            "id": "new-task",
            "title": "Review PR",
            "status": "notStarted",
            "importance": "high",
            "dueDateTime": {"dateTime": "2025-01-20T00:00:00", "timeZone": "UTC"},
            "body": {"contentType": "text", "content": ""},
            "createdDateTime": "2025-01-15T10:00:00Z",
        }

        with (
            patch("integrations.tasks.get_token_silent", return_value="fake-token"),
            patch("integrations.tasks.graph_get", new_callable=AsyncMock, return_value=mock_lists),
            patch("integrations.tasks.graph_post", new_callable=AsyncMock, return_value=created),
        ):
            result = await create_task(
                title="Review PR",
                due_date="2025-01-20",
                importance="high",
            )

        assert result["title"] == "Review PR"
        assert result["importance"] == "high"
