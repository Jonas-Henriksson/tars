"""Tests for the TARS voice call web server."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from web.server import app


client = TestClient(app)


class TestIndex:
    def test_serves_call_page(self):
        resp = client.get("/")
        assert resp.status_code == 200
        assert "TARS" in resp.text
        assert "callBtn" in resp.text


class TestEphemeralToken:
    def test_returns_error_when_no_api_key(self):
        with patch("web.server.OPENAI_API_KEY", ""):
            resp = client.get("/api/token")
        assert resp.status_code == 500
        assert "not configured" in resp.json()["error"]

    def test_returns_token_on_success(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {
            "client_secret": {"value": "eph-token-123"},
            "expires_at": 1234567890,
        }

        async def mock_post(*args, **kwargs):
            return mock_resp

        mock_client = MagicMock()
        mock_client.post = mock_post
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with (
            patch("web.server.OPENAI_API_KEY", "sk-test"),
            patch("web.server.httpx.AsyncClient", return_value=mock_client),
        ):
            resp = client.get("/api/token")

        assert resp.status_code == 200
        data = resp.json()
        assert data["token"] == "eph-token-123"


class TestToolEndpoint:
    def test_unknown_tool_returns_400(self):
        resp = client.post("/api/tool", json={"name": "fake_tool", "arguments": {}})
        assert resp.status_code == 400

    def test_executes_tool_successfully(self):
        mock_result = {"tasks": [{"title": "Test"}], "count": 1, "list_name": "Tasks"}

        with patch("integrations.tasks.get_tasks", new_callable=AsyncMock, return_value=mock_result):
            resp = client.post("/api/tool", json={"name": "get_tasks", "arguments": {}})

        assert resp.status_code == 200
        data = resp.json()
        assert data["result"]["count"] == 1

    def test_returns_error_on_runtime_error(self):
        with patch("integrations.tasks.get_tasks", new_callable=AsyncMock, side_effect=RuntimeError("Not signed in")):
            resp = client.post("/api/tool", json={"name": "get_tasks", "arguments": {}})

        assert resp.status_code == 200
        assert "Not signed in" in resp.json()["error"]


class TestTasksPage:
    def test_serves_tasks_dashboard(self):
        resp = client.get("/tasks")
        assert resp.status_code == 200
        assert "Task Tracker" in resp.text
        assert "summary-strip" in resp.text


class TestTasksAPI:
    def test_get_tasks_returns_data(self):
        mock_result = {
            "tasks": [
                {"id": "a1", "description": "Review PR", "owner": "Jonas", "status": "open",
                 "topic": "Sprint", "source_title": "Standup", "source_url": "", "created_at": "2025-03-17"},
            ],
            "count": 1,
            "by_owner": {"Jonas": [{"id": "a1"}]},
            "by_topic": {"Sprint": [{"id": "a1"}]},
        }

        with patch("integrations.notion_tasks.get_tracked_tasks", return_value=mock_result):
            resp = client.get("/api/tasks?include_completed=true")

        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] == 1
        assert data["tasks"][0]["owner"] == "Jonas"

    def test_get_tasks_with_filters(self):
        mock_result = {"tasks": [], "count": 0, "by_owner": {}, "by_topic": {}}

        with patch("integrations.notion_tasks.get_tracked_tasks", return_value=mock_result) as mock_fn:
            resp = client.get("/api/tasks?owner=Jonas&status=open")

        assert resp.status_code == 200
        mock_fn.assert_called_once_with(
            owner="Jonas", topic="", status="open", include_completed=False,
        )

    def test_update_task_status_success(self):
        mock_result = {
            "message": "Task 'Review PR' updated to 'done'.",
            "task": {"id": "a1", "status": "done", "completed": True},
        }

        with patch("integrations.notion_tasks.update_task_status", return_value=mock_result):
            resp = client.patch("/api/tasks/a1/status", json={"status": "done"})

        assert resp.status_code == 200
        assert resp.json()["task"]["status"] == "done"

    def test_update_task_status_invalid(self):
        resp = client.patch("/api/tasks/a1/status", json={"status": "invalid"})
        assert resp.status_code == 400
        assert "Invalid status" in resp.json()["error"]

    def test_update_task_status_not_found(self):
        mock_result = {"error": "Task not found: xyz"}

        with patch("integrations.notion_tasks.update_task_status", return_value=mock_result):
            resp = client.patch("/api/tasks/xyz/status", json={"status": "done"})

        assert resp.status_code == 404
