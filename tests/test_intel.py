"""Tests for the intelligence engine."""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import pytest

from integrations.intel import (
    _build_executive_summary,
    _classify_priority,
    _detect_delegations,
    _detect_topics,
    _estimate_follow_up_date,
    _extract_own_tasks,
    _extract_people,
    _summarize_task,
    get_intel,
    get_smart_tasks,
    update_smart_task,
)


class TestDetectTopics:
    def test_detects_engineering(self):
        topics = _detect_topics("We need to deploy the API by Friday", "Sprint Review")
        assert "engineering" in topics

    def test_detects_multiple_topics(self):
        topics = _detect_topics("budget review and hiring plan", "Planning")
        assert "finance" in topics
        assert "hiring" in topics

    def test_defaults_to_general(self):
        topics = _detect_topics("Had a nice chat", "Coffee break")
        assert topics == ["general"]

    def test_uses_title_for_detection(self):
        topics = _detect_topics("some notes here", "1:1 Performance Review")
        assert "management" in topics


class TestExtractPeople:
    def test_extracts_at_mentions(self):
        people = _extract_people("@Alice will review and @Bob deploys", "Meeting")
        assert "Alice" in people
        assert "Bob" in people

    def test_extracts_from_1on1_title(self):
        people = _extract_people("some content", "1:1 Jonas")
        assert "Jonas" in people

    def test_extracts_from_1on1_with_prefix(self):
        people = _extract_people("", "1:1 with Sarah Smith")
        assert "Sarah Smith" in people

    def test_no_duplicates(self):
        people = _extract_people("@Alice did this and @Alice did that", "Meeting")
        assert people.count("Alice") == 1

    def test_returns_empty_when_no_mentions(self):
        people = _extract_people("No names here", "Notes")
        assert people == []


class TestDetectDelegations:
    def test_detects_checkbox_delegation(self):
        text = "[ ] @Alice: Review the API spec"
        result = _detect_delegations(text)
        assert len(result) == 1
        assert result[0]["owner"] == "Alice"
        assert "Review the API spec" in result[0]["description"]

    def test_detects_action_delegation(self):
        text = "ACTION: @Bob deploy the service"
        result = _detect_delegations(text)
        assert len(result) == 1
        assert result[0]["owner"] == "Bob"

    def test_detects_bullet_delegation(self):
        text = "- @Carol: Send the report"
        result = _detect_delegations(text)
        assert len(result) == 1
        assert result[0]["owner"] == "Carol"

    def test_returns_empty_for_no_delegations(self):
        text = "[ ] Review the document myself"
        result = _detect_delegations(text)
        assert result == []


class TestEstimateFollowUpDate:
    def test_explicit_date(self):
        result = _estimate_follow_up_date("finish by 2025-06-15", "2025-06-01")
        assert result == "2025-06-15"

    def test_asap(self):
        result = _estimate_follow_up_date("need this asap", "2025-06-10T00:00:00Z")
        assert result == "2025-06-11"

    def test_this_week(self):
        # Monday 2025-06-09
        result = _estimate_follow_up_date("do this week", "2025-06-09T00:00:00Z")
        assert result == "2025-06-13"  # Friday

    def test_next_week(self):
        # Monday 2025-06-09
        result = _estimate_follow_up_date("start next week", "2025-06-09T00:00:00Z")
        assert result == "2025-06-16"  # Next Monday

    def test_default_three_days(self):
        result = _estimate_follow_up_date("just do it", "2025-06-10T00:00:00Z")
        assert result == "2025-06-13"


class TestClassifyPriority:
    def test_urgent_important_is_q1(self):
        result = _classify_priority("urgent strategy decision needed", is_delegated=False)
        assert result["quadrant"] == 1
        assert result["urgent"] is True
        assert result["important"] is True

    def test_important_not_urgent_is_q2(self):
        result = _classify_priority("review the roadmap for next quarter", is_delegated=False)
        assert result["quadrant"] == 2
        assert result["important"] is True
        assert result["urgent"] is False

    def test_urgent_not_important_is_q3(self):
        result = _classify_priority("blocker on a small fix", is_delegated=False)
        assert result["quadrant"] == 3
        assert result["urgent"] is True
        assert result["important"] is False

    def test_neither_is_q4(self):
        result = _classify_priority("maybe look into this sometime", is_delegated=False)
        assert result["quadrant"] == 4

    def test_old_task_becomes_urgent(self):
        result = _classify_priority("some task", is_delegated=False, age_days=8)
        assert result["urgent"] is True

    def test_delegated_old_becomes_urgent(self):
        result = _classify_priority("send the file", is_delegated=True, age_days=4)
        assert result["urgent"] is True


class TestExtractOwnTasks:
    def test_extracts_unchecked_tasks(self):
        text = "[ ] Write the proposal\n[x] Done thing"
        tasks = _extract_own_tasks(text, "Notes")
        assert len(tasks) == 1
        assert "Write the proposal" in tasks[0]["description"]

    def test_skips_delegated_looking_tasks(self):
        text = "[ ] Alice will send the report"
        tasks = _extract_own_tasks(text, "Notes")
        assert len(tasks) == 0

    def test_skips_short_tasks(self):
        text = "[ ] Hi"
        tasks = _extract_own_tasks(text, "Notes")
        assert len(tasks) == 0

    def test_at_mention_tasks_handled_by_delegation(self):
        # @mention tasks are caught by _detect_delegations, not _extract_own_tasks
        text = "[ ] @Bob review this"
        delegations = _detect_delegations(text)
        assert len(delegations) == 1
        assert delegations[0]["owner"] == "Bob"


class TestBuildExecutiveSummary:
    def test_empty_intel(self):
        intel = {"smart_tasks": [], "topics": {}}
        summary = _build_executive_summary(intel)
        assert summary["total_open"] == 0
        assert summary["matrix"]["q1_count"] == 0

    def test_categorizes_tasks(self):
        now = datetime.now(timezone.utc)
        intel = {
            "smart_tasks": [
                {
                    "id": "t1",
                    "description": "urgent strategy decision",
                    "owner": "Alice",
                    "delegated": True,
                    "follow_up_date": (now + timedelta(days=1)).strftime("%Y-%m-%d"),
                    "status": "open",
                    "created_at": now.isoformat(),
                    "topics": ["strategy"],
                    "priority": {},
                    "source_title": "Meeting",
                    "source_url": "",
                },
            ],
            "topics": {"strategy": 3},
        }
        summary = _build_executive_summary(intel)
        assert summary["total_open"] == 1
        assert summary["matrix"]["q1_count"] == 1

    def test_excludes_done_tasks(self):
        now = datetime.now(timezone.utc)
        intel = {
            "smart_tasks": [
                {
                    "id": "t1",
                    "description": "urgent strategy decision",
                    "owner": "Alice",
                    "delegated": True,
                    "follow_up_date": (now + timedelta(days=1)).strftime("%Y-%m-%d"),
                    "status": "done",
                    "created_at": now.isoformat(),
                    "topics": ["strategy"],
                    "priority": {},
                    "source_title": "Meeting",
                    "source_url": "",
                },
            ],
            "topics": {},
        }
        summary = _build_executive_summary(intel)
        assert summary["total_open"] == 0


class TestSummarizeTask:
    def test_returns_expected_fields(self):
        task = {
            "id": "abc",
            "description": "Do X",
            "owner": "Alice",
            "delegated": True,
            "follow_up_date": "2025-06-15",
            "source_title": "Meeting",
            "age_days": 3,
            "priority": {"quadrant": 1, "quadrant_label": "Do first"},
            "topics": ["engineering"],
            "status": "open",
        }
        result = _summarize_task(task)
        assert result["id"] == "abc"
        assert result["quadrant"] == 1
        assert result["owner"] == "Alice"


class TestGetSmartTasks:
    def test_filters_by_owner(self, tmp_path):
        intel_data = {
            "smart_tasks": [
                {
                    "id": "t1", "description": "task one", "owner": "Alice",
                    "delegated": True, "status": "open",
                    "created_at": datetime.now(timezone.utc).isoformat(),
                    "topics": [], "priority": {}, "follow_up_date": None,
                    "source_title": "", "source_url": "",
                },
                {
                    "id": "t2", "description": "task two", "owner": "Bob",
                    "delegated": True, "status": "open",
                    "created_at": datetime.now(timezone.utc).isoformat(),
                    "topics": [], "priority": {}, "follow_up_date": None,
                    "source_title": "", "source_url": "",
                },
            ],
            "topics": {}, "people": {}, "executive_summary": {},
            "last_scan_at": None, "pages_scanned": 0, "scan_history": [],
        }
        intel_file = tmp_path / "intel.json"
        intel_file.write_text(json.dumps(intel_data))

        with patch("integrations.intel._INTEL_FILE", intel_file):
            result = get_smart_tasks(owner="Alice")

        assert result["count"] == 1
        assert result["tasks"][0]["owner"] == "Alice"

    def test_filters_by_quadrant(self, tmp_path):
        intel_data = {
            "smart_tasks": [
                {
                    "id": "t1", "description": "urgent strategy item", "owner": "Me",
                    "delegated": False, "status": "open",
                    "created_at": datetime.now(timezone.utc).isoformat(),
                    "topics": [], "priority": {}, "follow_up_date": None,
                    "source_title": "", "source_url": "",
                },
                {
                    "id": "t2", "description": "casual task", "owner": "Me",
                    "delegated": False, "status": "open",
                    "created_at": datetime.now(timezone.utc).isoformat(),
                    "topics": [], "priority": {}, "follow_up_date": None,
                    "source_title": "", "source_url": "",
                },
            ],
            "topics": {}, "people": {}, "executive_summary": {},
            "last_scan_at": None, "pages_scanned": 0, "scan_history": [],
        }
        intel_file = tmp_path / "intel.json"
        intel_file.write_text(json.dumps(intel_data))

        with patch("integrations.intel._INTEL_FILE", intel_file):
            result = get_smart_tasks(quadrant=1)

        # Only the urgent+important task should be Q1
        for t in result["tasks"]:
            assert t["quadrant"] == 1


class TestUpdateSmartTask:
    def test_updates_status(self, tmp_path):
        intel_data = {
            "smart_tasks": [
                {
                    "id": "t1", "description": "some task", "owner": "Alice",
                    "delegated": True, "status": "open",
                    "created_at": datetime.now(timezone.utc).isoformat(),
                    "topics": [], "priority": {"quadrant": 3, "quadrant_label": "Delegate"},
                    "follow_up_date": "2025-06-15",
                    "source_title": "Meeting", "source_url": "",
                },
            ],
            "topics": {}, "people": {}, "executive_summary": {},
            "last_scan_at": None, "pages_scanned": 0, "scan_history": [],
        }
        intel_file = tmp_path / "intel.json"
        intel_file.write_text(json.dumps(intel_data))

        with patch("integrations.intel._INTEL_FILE", intel_file):
            result = update_smart_task("t1", status="done")

        assert "message" in result
        assert result["task"]["status"] == "done"

    def test_updates_follow_up_date(self, tmp_path):
        intel_data = {
            "smart_tasks": [
                {
                    "id": "t1", "description": "some task", "owner": "Alice",
                    "delegated": True, "status": "open",
                    "created_at": datetime.now(timezone.utc).isoformat(),
                    "topics": [], "priority": {"quadrant": 3, "quadrant_label": "Delegate"},
                    "follow_up_date": "2025-06-15",
                    "source_title": "Meeting", "source_url": "",
                },
            ],
            "topics": {}, "people": {}, "executive_summary": {},
            "last_scan_at": None, "pages_scanned": 0, "scan_history": [],
        }
        intel_file = tmp_path / "intel.json"
        intel_file.write_text(json.dumps(intel_data))

        with patch("integrations.intel._INTEL_FILE", intel_file):
            result = update_smart_task("t1", follow_up_date="2025-07-01")

        assert result["task"]["follow_up_date"] == "2025-07-01"

    def test_returns_error_for_unknown_task(self, tmp_path):
        intel_data = {
            "smart_tasks": [],
            "topics": {}, "people": {}, "executive_summary": {},
            "last_scan_at": None, "pages_scanned": 0, "scan_history": [],
        }
        intel_file = tmp_path / "intel.json"
        intel_file.write_text(json.dumps(intel_data))

        with patch("integrations.intel._INTEL_FILE", intel_file):
            result = update_smart_task("nonexistent")

        assert "error" in result


class TestGetIntel:
    def test_returns_empty_when_no_data(self, tmp_path):
        intel_file = tmp_path / "intel.json"

        with patch("integrations.intel._INTEL_FILE", intel_file):
            result = get_intel()

        assert result["last_scan_at"] is None
        assert result["smart_tasks"] == []

    def test_rebuilds_executive_summary(self, tmp_path):
        now = datetime.now(timezone.utc)
        intel_data = {
            "smart_tasks": [
                {
                    "id": "t1", "description": "urgent blocker", "owner": "Me",
                    "delegated": False, "status": "open",
                    "created_at": now.isoformat(),
                    "topics": [], "priority": {}, "follow_up_date": None,
                    "source_title": "", "source_url": "",
                },
            ],
            "topics": {"engineering": 5}, "people": {"Alice": 3},
            "executive_summary": {},
            "last_scan_at": now.isoformat(), "pages_scanned": 10,
            "scan_history": [],
        }
        intel_file = tmp_path / "intel.json"
        intel_file.write_text(json.dumps(intel_data))

        with patch("integrations.intel._INTEL_FILE", intel_file):
            result = get_intel()

        assert "executive_summary" in result
        assert result["executive_summary"]["total_open"] == 1


class TestWebIntelEndpoints:
    def test_serves_executive_page(self):
        from fastapi.testclient import TestClient
        from web.server import app
        client = TestClient(app)
        resp = client.get("/executive")
        assert resp.status_code == 200
        assert "Executive Summary" in resp.text

    def test_api_intel_returns_data(self):
        from fastapi.testclient import TestClient
        from web.server import app
        client = TestClient(app)

        mock_intel = {
            "last_scan_at": None,
            "pages_scanned": 0,
            "topics": {},
            "people": {},
            "smart_tasks": [],
            "executive_summary": {},
            "scan_history": [],
        }

        with patch("integrations.intel.get_intel", return_value=mock_intel):
            resp = client.get("/api/intel")

        assert resp.status_code == 200
        data = resp.json()
        assert "topics" in data
        assert "smart_tasks" in data

    def test_api_intel_scan(self):
        from fastapi.testclient import TestClient
        from web.server import app
        client = TestClient(app)

        mock_result = {
            "pages_scanned": 10,
            "topics_found": 3,
            "people_found": 2,
            "new_tasks_added": 5,
            "total_smart_tasks": 5,
            "top_topics": {"engineering": 5},
            "top_people": {"Alice": 3},
            "executive_summary": {},
        }

        with patch("integrations.intel.scan_notion",
                    new_callable=AsyncMock, return_value=mock_result):
            resp = client.post("/api/intel/scan")

        assert resp.status_code == 200
        data = resp.json()
        assert data["pages_scanned"] == 10

    def test_api_update_smart_task(self):
        from fastapi.testclient import TestClient
        from web.server import app
        client = TestClient(app)

        mock_result = {
            "message": "Task updated.",
            "task": {"id": "t1", "status": "done", "description": "X",
                     "owner": "A", "delegated": True, "follow_up_date": None,
                     "source_title": "", "age_days": 0, "quadrant": 3,
                     "quadrant_label": "Delegate", "topics": [],
                     },
        }

        with patch("integrations.intel.update_smart_task", return_value=mock_result):
            resp = client.patch("/api/intel/tasks/t1",
                                json={"status": "done"})

        assert resp.status_code == 200
        assert resp.json()["task"]["status"] == "done"
