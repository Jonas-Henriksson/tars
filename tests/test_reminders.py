"""Tests for the reminder system."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest

from integrations.reminders import (
    _reminders,
    create_reminder,
    delete_reminder,
    get_due_reminders,
    get_reminders,
)


@pytest.fixture(autouse=True)
def clean_reminders():
    """Clear reminders before and after each test."""
    _reminders.clear()
    yield
    _reminders.clear()


class TestCreateReminder:
    def test_create_basic_reminder(self):
        future = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
        result = create_reminder(
            chat_id=12345,
            message="Call the dentist",
            remind_at=future,
        )

        assert result["message"] == "Call the dentist"
        assert result["chat_id"] == 12345
        assert result["remind_at"] == future
        assert len(result["id"]) == 8

    def test_create_multiple_reminders(self):
        future1 = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
        future2 = (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat()

        create_reminder(12345, "First", future1)
        create_reminder(12345, "Second", future2)

        result = get_reminders(12345)
        assert result["count"] == 2


class TestGetReminders:
    def test_get_only_future_reminders(self):
        past = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
        future = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()

        create_reminder(12345, "Past reminder", past)
        create_reminder(12345, "Future reminder", future)

        result = get_reminders(12345)
        assert result["count"] == 1
        assert result["reminders"][0]["message"] == "Future reminder"

    def test_get_reminders_only_for_chat(self):
        future = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()

        create_reminder(11111, "User A reminder", future)
        create_reminder(22222, "User B reminder", future)

        result_a = get_reminders(11111)
        assert result_a["count"] == 1
        assert result_a["reminders"][0]["message"] == "User A reminder"

    def test_reminders_sorted_by_time(self):
        later = (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat()
        sooner = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()

        create_reminder(12345, "Later", later)
        create_reminder(12345, "Sooner", sooner)

        result = get_reminders(12345)
        assert result["reminders"][0]["message"] == "Sooner"
        assert result["reminders"][1]["message"] == "Later"


class TestDeleteReminder:
    def test_delete_own_reminder(self):
        future = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
        created = create_reminder(12345, "To delete", future)

        result = delete_reminder(created["id"], chat_id=12345)
        assert result["status"] == "deleted"
        assert get_reminders(12345)["count"] == 0

    def test_cannot_delete_other_users_reminder(self):
        future = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
        created = create_reminder(12345, "Not yours", future)

        with pytest.raises(RuntimeError, match="your own"):
            delete_reminder(created["id"], chat_id=99999)

    def test_delete_nonexistent_reminder(self):
        with pytest.raises(RuntimeError, match="not found"):
            delete_reminder("fakeid", chat_id=12345)


class TestGetDueReminders:
    def test_returns_due_reminders(self):
        past = (datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat()
        future = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()

        create_reminder(12345, "Due now", past)
        create_reminder(12345, "Not yet", future)

        due = get_due_reminders()
        assert len(due) == 1
        assert due[0]["message"] == "Due now"

        # Due reminder should be removed from store
        assert get_reminders(12345)["count"] == 1

    def test_no_due_reminders(self):
        future = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
        create_reminder(12345, "Later", future)

        due = get_due_reminders()
        assert len(due) == 0
