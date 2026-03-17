"""Tests for daily briefing integration."""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from integrations.briefing import get_briefing


class TestGetBriefing:
    @pytest.mark.asyncio
    async def test_briefing_combines_all_sources(self):
        mock_calendar = {"events": [{"subject": "Standup"}], "count": 1}
        mock_tasks = {"tasks": [{"title": "Review PR"}], "count": 1, "list_name": "Tasks"}
        mock_mail = {"messages": [{"subject": "Hello"}], "count": 1}

        with (
            patch("integrations.briefing.get_events", new_callable=AsyncMock, return_value=mock_calendar),
            patch("integrations.briefing.get_tasks", new_callable=AsyncMock, return_value=mock_tasks),
            patch("integrations.briefing.get_messages", new_callable=AsyncMock, return_value=mock_mail),
        ):
            result = await get_briefing()

        assert result["calendar"]["count"] == 1
        assert result["calendar"]["events"][0]["subject"] == "Standup"
        assert result["tasks"]["count"] == 1
        assert result["tasks"]["items"][0]["title"] == "Review PR"
        assert result["email"]["count"] == 1
        assert result["email"]["unread"][0]["subject"] == "Hello"
