"""Tests for the Notion meeting task extraction and tracking."""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from integrations.notion_tasks import (
    _extract_owner,
    _extract_tasks_from_text,
    _parse_task_line,
    get_tracked_tasks,
    update_task_status,
)


class TestParseTaskLine:
    def test_checkbox_unchecked(self):
        result = _parse_task_line("[ ] Review the document")
        assert result is not None
        assert result["description"] == "Review the document"
        assert result["completed"] is False

    def test_checkbox_checked(self):
        result = _parse_task_line("[x] Review the document")
        assert result is not None
        assert result["completed"] is True

    def test_checkbox_with_owner(self):
        result = _parse_task_line("[ ] @Jonas review the PR")
        assert result is not None
        assert result["owner"] == "Jonas"
        assert result["description"] == "review the PR"

    def test_action_prefix(self):
        result = _parse_task_line("ACTION: Send the report")
        assert result is not None
        assert result["description"] == "Send the report"

    def test_todo_prefix(self):
        result = _parse_task_line("TODO: Fix the bug")
        assert result is not None
        assert result["description"] == "Fix the bug"

    def test_bullet_with_mention(self):
        result = _parse_task_line("• @Alice: prepare slides")
        assert result is not None
        assert result["owner"] == "Alice"
        assert result["description"] == "prepare slides"

    def test_plain_text_returns_none(self):
        assert _parse_task_line("Just a normal sentence") is None

    def test_empty_returns_none(self):
        assert _parse_task_line("") is None


class TestExtractOwner:
    def test_at_prefix(self):
        owner, desc = _extract_owner("@Jonas: review doc")
        assert owner == "Jonas"
        assert desc == "review doc"

    def test_parenthetical_mention(self):
        owner, desc = _extract_owner("Review the doc (@Alice)")
        assert owner == "Alice"
        assert "Review the doc" in desc

    def test_no_owner(self):
        owner, desc = _extract_owner("Just do the thing")
        assert owner == ""
        assert desc == "Just do the thing"


class TestExtractTasksFromText:
    def test_extracts_tasks_with_topics(self):
        text = """# Roadmap Discussion
[ ] @Jonas: finalize the Q2 plan
[x] Review last quarter metrics

# Action Items
ACTION: @Alice prepare the budget
TODO: Send meeting recap"""

        tasks = _extract_tasks_from_text(text, "Weekly Standup", "https://notion.so/standup")
        assert len(tasks) == 4

        # First task under Roadmap Discussion
        assert tasks[0]["topic"] == "Roadmap Discussion"
        assert tasks[0]["owner"] == "Jonas"
        assert not tasks[0]["completed"]

        # Second task completed
        assert tasks[1]["completed"] is True

        # Action items section
        assert tasks[2]["topic"] == "Action Items"
        assert tasks[2]["owner"] == "Alice"

    def test_empty_text_returns_empty(self):
        tasks = _extract_tasks_from_text("", "Empty", "")
        assert tasks == []

    def test_no_tasks_returns_empty(self):
        text = "Just some meeting notes without any tasks."
        tasks = _extract_tasks_from_text(text, "Notes", "")
        assert tasks == []


class TestGetTrackedTasks:
    def test_filters_by_owner(self, tmp_path):
        tasks = [
            {"id": "1", "owner": "Jonas", "description": "task 1", "status": "open", "topic": "General"},
            {"id": "2", "owner": "Alice", "description": "task 2", "status": "open", "topic": "General"},
        ]
        tasks_file = tmp_path / "tasks.json"
        tasks_file.write_text(json.dumps(tasks))

        with patch("integrations.notion_tasks._TASKS_FILE", tasks_file):
            result = get_tracked_tasks(owner="Jonas")
        assert result["count"] == 1
        assert result["tasks"][0]["owner"] == "Jonas"

    def test_filters_by_status(self, tmp_path):
        tasks = [
            {"id": "1", "owner": "Jonas", "description": "open task", "status": "open", "topic": "A"},
            {"id": "2", "owner": "Jonas", "description": "done task", "status": "done", "topic": "A"},
        ]
        tasks_file = tmp_path / "tasks.json"
        tasks_file.write_text(json.dumps(tasks))

        with patch("integrations.notion_tasks._TASKS_FILE", tasks_file):
            result = get_tracked_tasks(status="open")
        assert result["count"] == 1
        assert result["tasks"][0]["status"] == "open"

    def test_excludes_completed_by_default(self, tmp_path):
        tasks = [
            {"id": "1", "owner": "A", "description": "open", "status": "open", "topic": "X"},
            {"id": "2", "owner": "B", "description": "done", "status": "done", "topic": "X"},
        ]
        tasks_file = tmp_path / "tasks.json"
        tasks_file.write_text(json.dumps(tasks))

        with patch("integrations.notion_tasks._TASKS_FILE", tasks_file):
            result = get_tracked_tasks()
        assert result["count"] == 1

    def test_groups_by_owner_and_topic(self, tmp_path):
        tasks = [
            {"id": "1", "owner": "Jonas", "description": "t1", "status": "open", "topic": "Planning"},
            {"id": "2", "owner": "Alice", "description": "t2", "status": "open", "topic": "Planning"},
            {"id": "3", "owner": "Jonas", "description": "t3", "status": "open", "topic": "Review"},
        ]
        tasks_file = tmp_path / "tasks.json"
        tasks_file.write_text(json.dumps(tasks))

        with patch("integrations.notion_tasks._TASKS_FILE", tasks_file):
            result = get_tracked_tasks()
        assert "Jonas" in result["by_owner"]
        assert len(result["by_owner"]["Jonas"]) == 2
        assert "Planning" in result["by_topic"]


class TestUpdateTaskStatus:
    def test_updates_status(self, tmp_path):
        tasks = [{"id": "abc", "description": "Test task", "status": "open", "completed": False, "followed_up": False}]
        tasks_file = tmp_path / "tasks.json"
        tasks_file.write_text(json.dumps(tasks))

        with patch("integrations.notion_tasks._TASKS_FILE", tasks_file):
            result = update_task_status("abc", "done")
        assert result["task"]["status"] == "done"
        assert result["task"]["completed"] is True

    def test_marks_followed_up(self, tmp_path):
        tasks = [{"id": "abc", "description": "Test task", "status": "open", "completed": False, "followed_up": False}]
        tasks_file = tmp_path / "tasks.json"
        tasks_file.write_text(json.dumps(tasks))

        with patch("integrations.notion_tasks._TASKS_FILE", tasks_file):
            result = update_task_status("abc", "followed_up")
        assert result["task"]["followed_up"] is True

    def test_returns_error_for_unknown_id(self, tmp_path):
        tasks_file = tmp_path / "tasks.json"
        tasks_file.write_text("[]")

        with patch("integrations.notion_tasks._TASKS_FILE", tasks_file):
            result = update_task_status("nonexistent", "done")
        assert "error" in result


class TestExtractMeetingTasks:
    @pytest.mark.asyncio
    async def test_extracts_and_groups(self):
        mock_page = {
            "id": "page-1",
            "title": "Sprint Planning",
            "url": "https://notion.so/sprint",
            "content": "# Tasks\n[ ] @Jonas: implement feature\n[ ] @Alice: write tests",
            "block_count": 3,
        }

        with patch("integrations.notion_tasks.get_page_content", new_callable=AsyncMock, return_value=mock_page):
            with patch("integrations.notion_tasks.is_configured", return_value=True):
                from integrations.notion_tasks import extract_meeting_tasks
                result = await extract_meeting_tasks("page-1")

        assert result["total_tasks"] == 2
        assert "Jonas" in result["tasks_by_owner"]
        assert "Alice" in result["tasks_by_owner"]

    @pytest.mark.asyncio
    async def test_no_tasks_found(self):
        mock_page = {
            "id": "page-1",
            "title": "Random Notes",
            "url": "https://notion.so/notes",
            "content": "Just some text without tasks.",
            "block_count": 1,
        }

        with patch("integrations.notion_tasks.get_page_content", new_callable=AsyncMock, return_value=mock_page):
            with patch("integrations.notion_tasks.is_configured", return_value=True):
                from integrations.notion_tasks import extract_meeting_tasks
                result = await extract_meeting_tasks("page-1")

        assert result["tasks"] == []
        assert "No tasks found" in result["message"]
