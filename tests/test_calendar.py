"""Tests for Microsoft 365 calendar integration."""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from integrations.calendar import _format_event, create_event, get_events, search_events


class TestFormatEvent:
    def test_format_basic_event(self):
        """Formats a Graph API event into a clean dict."""
        raw = {
            "id": "abc123",
            "subject": "Team standup",
            "start": {"dateTime": "2025-01-15T09:00:00", "timeZone": "UTC"},
            "end": {"dateTime": "2025-01-15T09:30:00", "timeZone": "UTC"},
            "location": {"displayName": "Room 5"},
            "isOnlineMeeting": True,
            "organizer": {"emailAddress": {"name": "Alice"}},
            "webLink": "https://outlook.office.com/calendar/item/abc123",
        }
        result = _format_event(raw)

        assert result["subject"] == "Team standup"
        assert result["start"] == "2025-01-15T09:00:00"
        assert result["end"] == "2025-01-15T09:30:00"
        assert result["location"] == "Room 5"
        assert result["is_online"] is True
        assert result["organizer"] == "Alice"

    def test_format_minimal_event(self):
        """Handles events with missing optional fields."""
        raw = {"id": "x", "start": {}, "end": {}}
        result = _format_event(raw)

        assert result["subject"] == "(No subject)"
        assert result["location"] == ""
        assert result["organizer"] == ""


class TestGetEvents:
    @pytest.mark.asyncio
    async def test_get_events_success(self):
        """Fetches and formats calendar events."""
        mock_events = {
            "value": [
                {
                    "id": "1",
                    "subject": "Meeting A",
                    "start": {"dateTime": "2025-01-15T10:00:00", "timeZone": "UTC"},
                    "end": {"dateTime": "2025-01-15T11:00:00", "timeZone": "UTC"},
                    "location": {},
                    "isOnlineMeeting": False,
                    "organizer": {"emailAddress": {"name": "Bob"}},
                    "webLink": "",
                },
            ]
        }

        with (
            patch("integrations.calendar.get_token_silent", return_value="fake-token"),
            patch("integrations.calendar.graph_get", new_callable=AsyncMock, return_value=mock_events),
        ):
            result = await get_events(days=7)

        assert result["count"] == 1
        assert result["events"][0]["subject"] == "Meeting A"

    @pytest.mark.asyncio
    async def test_get_events_not_signed_in(self):
        """Raises RuntimeError when not signed in."""
        with patch("integrations.calendar.get_token_silent", return_value=None):
            with pytest.raises(RuntimeError, match="Not signed in"):
                await get_events()


class TestCreateEvent:
    @pytest.mark.asyncio
    async def test_create_event_success(self):
        """Creates an event and returns formatted result."""
        created = {
            "id": "new1",
            "subject": "Lunch",
            "start": {"dateTime": "2025-01-15T12:00:00", "timeZone": "Europe/Stockholm"},
            "end": {"dateTime": "2025-01-15T13:00:00", "timeZone": "Europe/Stockholm"},
            "location": {"displayName": "Cafe"},
            "isOnlineMeeting": False,
            "organizer": {"emailAddress": {"name": "Me"}},
            "webLink": "",
        }

        with (
            patch("integrations.calendar.get_token_silent", return_value="fake-token"),
            patch("integrations.calendar.graph_post", new_callable=AsyncMock, return_value=created),
        ):
            result = await create_event(
                subject="Lunch",
                start_time="2025-01-15T12:00:00",
                end_time="2025-01-15T13:00:00",
                timezone_str="Europe/Stockholm",
                location="Cafe",
            )

        assert result["subject"] == "Lunch"
        assert result["location"] == "Cafe"

    @pytest.mark.asyncio
    async def test_create_event_with_attendees(self):
        """Passes attendees to Graph API."""
        created = {
            "id": "new2",
            "subject": "Review",
            "start": {"dateTime": "2025-01-15T14:00:00", "timeZone": "UTC"},
            "end": {"dateTime": "2025-01-15T15:00:00", "timeZone": "UTC"},
            "location": {},
            "isOnlineMeeting": False,
            "organizer": {"emailAddress": {"name": "Me"}},
            "webLink": "",
        }

        with (
            patch("integrations.calendar.get_token_silent", return_value="fake-token"),
            patch("integrations.calendar.graph_post", new_callable=AsyncMock, return_value=created) as mock_post,
        ):
            await create_event(
                subject="Review",
                start_time="2025-01-15T14:00:00",
                end_time="2025-01-15T15:00:00",
                attendees=["alice@example.com", "bob@example.com"],
            )

        body = mock_post.call_args[0][2]
        assert len(body["attendees"]) == 2
        assert body["attendees"][0]["emailAddress"]["address"] == "alice@example.com"


class TestSearchEvents:
    @pytest.mark.asyncio
    async def test_search_events_success(self):
        mock_data = {
            "value": [
                {
                    "id": "e1",
                    "subject": "Budget Review",
                    "start": {"dateTime": "2025-01-20T14:00:00", "timeZone": "UTC"},
                    "end": {"dateTime": "2025-01-20T15:00:00", "timeZone": "UTC"},
                    "location": {},
                    "isOnlineMeeting": False,
                    "organizer": {"emailAddress": {"name": "CFO"}},
                    "webLink": "",
                },
            ]
        }

        with (
            patch("integrations.calendar.get_token_silent", return_value="fake-token"),
            patch("integrations.calendar.graph_get", new_callable=AsyncMock, return_value=mock_data),
        ):
            result = await search_events("Budget")

        assert result["count"] == 1
        assert result["query"] == "Budget"
        assert result["events"][0]["subject"] == "Budget Review"
