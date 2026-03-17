"""Tests for the daily briefing engine."""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import pytest

from integrations.briefing_daily import (
    _generate_recommendations,
    compile_daily_briefing,
    format_briefing_text,
)


class TestGenerateRecommendations:
    def test_flags_stale_tasks(self):
        sections = {
            "calendar": {"available": True, "count": 0, "events": []},
            "email": {"available": True, "unread_count": 0, "unread": []},
            "notion_activity": {"available": True, "count": 0, "pages": []},
            "task_analysis": {
                "available": True,
                "stale_tasks": [
                    {"id": "t1", "description": "Review doc", "owner": "Alice",
                     "age_days": 5, "status": "open"},
                ],
                "open_tasks": [],
                "by_owner": {},
            },
        }
        recs = _generate_recommendations(sections)
        assert len(recs) >= 1
        assert recs[0]["type"] == "follow_up"
        assert "Alice" in recs[0]["title"]

    def test_flags_critical_stale_tasks(self):
        sections = {
            "calendar": {"available": True, "count": 0, "events": []},
            "email": {"available": True, "unread_count": 0, "unread": []},
            "notion_activity": {"available": True, "count": 0, "pages": []},
            "task_analysis": {
                "available": True,
                "stale_tasks": [
                    {"id": "t1", "description": "Critical thing", "owner": "Bob",
                     "age_days": 10, "status": "open"},
                ],
                "open_tasks": [],
                "by_owner": {},
            },
        }
        recs = _generate_recommendations(sections)
        assert recs[0]["priority"] == "high"

    def test_flags_unassigned_stale_tasks(self):
        sections = {
            "calendar": {"available": True, "count": 0, "events": []},
            "email": {"available": True, "unread_count": 0, "unread": []},
            "notion_activity": {"available": True, "count": 0, "pages": []},
            "task_analysis": {
                "available": True,
                "stale_tasks": [
                    {"id": "t1", "description": "Orphan task", "owner": "Unassigned",
                     "age_days": 4, "status": "open"},
                ],
                "open_tasks": [],
                "by_owner": {},
            },
        }
        recs = _generate_recommendations(sections)
        assert recs[0]["type"] == "stale_task"
        assert "no owner" in recs[0]["detail"]

    def test_flags_owner_with_many_tasks(self):
        sections = {
            "calendar": {"available": True, "count": 0, "events": []},
            "email": {"available": True, "unread_count": 0, "unread": []},
            "notion_activity": {"available": True, "count": 0, "pages": []},
            "task_analysis": {
                "available": True,
                "stale_tasks": [],
                "open_tasks": [],
                "by_owner": {"Jonas": 5},
            },
        }
        recs = _generate_recommendations(sections)
        check_ins = [r for r in recs if r["type"] == "check_in"]
        assert len(check_ins) == 1
        assert "Jonas" in check_ins[0]["title"]

    def test_flags_email_backlog(self):
        sections = {
            "calendar": {"available": True, "count": 0, "events": []},
            "email": {"available": True, "unread_count": 15, "unread": []},
            "notion_activity": {"available": True, "count": 0, "pages": []},
            "task_analysis": {
                "available": True,
                "stale_tasks": [],
                "open_tasks": [],
                "by_owner": {},
            },
        }
        recs = _generate_recommendations(sections)
        email_recs = [r for r in recs if r["type"] == "email_backlog"]
        assert len(email_recs) == 1
        assert "15" in email_recs[0]["detail"]

    def test_flags_meetings_without_actions(self):
        sections = {
            "calendar": {"available": True, "count": 0, "events": []},
            "email": {"available": True, "unread_count": 0, "unread": []},
            "notion_activity": {
                "available": True,
                "count": 1,
                "pages": [{
                    "id": "p1",
                    "title": "Sprint Planning 2025-03-17",
                    "full_content": "Discussed roadmap items and timeline.",
                }],
            },
            "task_analysis": {
                "available": True,
                "stale_tasks": [],
                "open_tasks": [],
                "by_owner": {},
            },
        }
        recs = _generate_recommendations(sections)
        missing = [r for r in recs if r["type"] == "missing_actions"]
        assert len(missing) == 1
        assert "Sprint Planning" in missing[0]["title"]

    def test_no_false_positive_when_meeting_has_tasks(self):
        sections = {
            "calendar": {"available": True, "count": 0, "events": []},
            "email": {"available": True, "unread_count": 0, "unread": []},
            "notion_activity": {
                "available": True,
                "count": 1,
                "pages": [{
                    "id": "p1",
                    "title": "Sprint Planning 2025-03-17",
                    "full_content": "[ ] Review the API spec\n[x] Update docs",
                }],
            },
            "task_analysis": {
                "available": True,
                "stale_tasks": [],
                "open_tasks": [],
                "by_owner": {},
            },
        }
        recs = _generate_recommendations(sections)
        missing = [r for r in recs if r["type"] == "missing_actions"]
        assert len(missing) == 0

    def test_recommendations_sorted_by_priority(self):
        sections = {
            "calendar": {"available": True, "count": 0, "events": []},
            "email": {"available": True, "unread_count": 12, "unread": []},
            "notion_activity": {"available": True, "count": 0, "pages": []},
            "task_analysis": {
                "available": True,
                "stale_tasks": [
                    {"id": "t1", "description": "Old task", "owner": "Alice",
                     "age_days": 8, "status": "open"},
                ],
                "open_tasks": [],
                "by_owner": {},
            },
        }
        recs = _generate_recommendations(sections)
        priorities = [r["priority"] for r in recs]
        order = {"high": 0, "medium": 1, "low": 2}
        assert all(order[priorities[i]] <= order[priorities[i+1]] for i in range(len(priorities)-1))

    def test_empty_data_no_recommendations(self):
        sections = {
            "calendar": {"available": False},
            "email": {"available": False, "unread_count": 0},
            "notion_activity": {"available": False, "pages": []},
            "task_analysis": {
                "available": False,
                "stale_tasks": [],
                "open_tasks": [],
                "by_owner": {},
            },
        }
        recs = _generate_recommendations(sections)
        assert recs == []


class TestFormatBriefingText:
    def test_formats_complete_briefing(self):
        briefing = {
            "calendar": {
                "available": True,
                "count": 1,
                "events": [{"subject": "Standup", "start": "2025-03-17T09:00:00", "end": "2025-03-17T09:15:00"}],
            },
            "email": {
                "available": True,
                "unread_count": 2,
                "unread": [
                    {"from": "alice@co.com", "subject": "Re: Q1 plan"},
                    {"from": "bob@co.com", "subject": "Invoice"},
                ],
            },
            "notion_activity": {
                "available": True,
                "count": 1,
                "pages": [{"title": "Sprint Planning"}],
            },
            "task_analysis": {
                "available": True,
                "open_count": 3,
                "stale_count": 1,
                "others_open_count": 2,
                "stale_tasks": [
                    {"description": "Review PR", "owner": "Bob", "age_days": 5},
                ],
            },
            "recommendations": [
                {"priority": "high", "title": "Follow up with Bob",
                 "detail": "'Review PR' has been open for 5 days."},
            ],
        }

        text = format_briefing_text(briefing)
        assert "DAILY BRIEFING" in text
        assert "Standup" in text
        assert "09:00" in text
        assert "Sprint Planning" in text
        assert "3 open" in text
        assert "Review PR" in text
        assert "Follow up with Bob" in text
        assert "alice@co.com" in text

    def test_handles_empty_briefing(self):
        briefing = {
            "calendar": {"available": False, "count": 0, "events": []},
            "email": {"available": False, "unread_count": 0, "unread": []},
            "notion_activity": {"available": False, "count": 0, "pages": []},
            "task_analysis": {"available": False, "open_count": 0, "stale_count": 0,
                              "others_open_count": 0, "stale_tasks": []},
            "recommendations": [],
        }
        text = format_briefing_text(briefing)
        assert "DAILY BRIEFING" in text


class TestGetTaskAnalysis:
    def test_identifies_stale_tasks(self, tmp_path):
        old_date = (datetime.now(timezone.utc) - timedelta(days=5)).isoformat()
        tasks = [
            {"id": "t1", "description": "Old task", "owner": "Alice",
             "status": "open", "topic": "X", "created_at": old_date,
             "completed": False, "followed_up": False},
            {"id": "t2", "description": "New task", "owner": "Bob",
             "status": "open", "topic": "Y",
             "created_at": datetime.now(timezone.utc).isoformat(),
             "completed": False, "followed_up": False},
        ]
        tasks_file = tmp_path / "tasks.json"
        tasks_file.write_text(json.dumps(tasks))

        with patch("integrations.notion_tasks._TASKS_FILE", tasks_file):
            from integrations.briefing_daily import _get_task_analysis
            result = _get_task_analysis()

        assert result["open_count"] == 2
        assert result["stale_count"] == 1
        assert result["stale_tasks"][0]["id"] == "t1"
        assert result["stale_tasks"][0]["age_days"] >= 4


class TestCompileDailyBriefing:
    @pytest.mark.asyncio
    async def test_compiles_with_all_sources_unavailable(self):
        with (
            patch("integrations.briefing_daily._get_calendar_section",
                  new_callable=AsyncMock,
                  return_value={"available": False, "events": [], "count": 0}),
            patch("integrations.briefing_daily._get_email_section",
                  new_callable=AsyncMock,
                  return_value={"available": False, "unread": [], "unread_count": 0, "recent": [], "recent_count": 0}),
            patch("integrations.briefing_daily._get_notion_section",
                  new_callable=AsyncMock,
                  return_value={"available": False, "pages": [], "count": 0}),
            patch("integrations.briefing_daily._get_task_analysis",
                  return_value={"available": False, "total": 0, "open_count": 0,
                                "stale_tasks": [], "stale_count": 0, "open_tasks": [],
                                "by_owner": {}, "others_open_count": 0}),
        ):
            result = await compile_daily_briefing()

        assert "calendar" in result
        assert "task_analysis" in result
        assert "recommendations" in result
        assert "generated_at" in result


class TestWebBriefingEndpoints:
    def test_serves_briefing_page(self):
        from fastapi.testclient import TestClient
        from web.server import app
        client = TestClient(app)
        resp = client.get("/briefing")
        assert resp.status_code == 200
        assert "Daily Briefing" in resp.text

    def test_api_briefing_returns_data(self):
        from fastapi.testclient import TestClient
        from web.server import app
        client = TestClient(app)

        mock_briefing = {
            "calendar": {"available": False, "events": [], "count": 0},
            "email": {"available": False, "unread": [], "unread_count": 0},
            "notion_activity": {"available": False, "pages": [], "count": 0},
            "task_analysis": {"available": False, "stale_tasks": [], "open_count": 0},
            "recommendations": [],
            "generated_at": "2025-03-17T18:00:00Z",
        }

        with patch("integrations.briefing_daily.compile_daily_briefing",
                    new_callable=AsyncMock, return_value=mock_briefing):
            resp = client.get("/api/briefing")

        assert resp.status_code == 200
        data = resp.json()
        assert "calendar" in data
        assert "recommendations" in data
