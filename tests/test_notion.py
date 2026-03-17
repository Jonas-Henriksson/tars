"""Tests for the Notion integration."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# notion.py tests
# ---------------------------------------------------------------------------

class TestIsConfigured:
    def test_returns_true_when_key_set(self):
        with patch("integrations.notion.NOTION_API_KEY", "ntn-test"):
            from integrations.notion import is_configured
            assert is_configured()

    def test_returns_false_when_key_empty(self):
        with patch("integrations.notion.NOTION_API_KEY", ""):
            from integrations.notion import is_configured
            assert not is_configured()


class TestExtractText:
    def test_extracts_plain_text(self):
        from integrations.notion import _extract_text
        rich = [
            {"plain_text": "Hello "},
            {"plain_text": "world"},
        ]
        assert _extract_text(rich) == "Hello world"

    def test_handles_empty_list(self):
        from integrations.notion import _extract_text
        assert _extract_text([]) == ""


class TestExtractBlockText:
    def test_paragraph(self):
        from integrations.notion import _extract_block_text
        block = {"type": "paragraph", "paragraph": {"rich_text": [{"plain_text": "Some text"}]}}
        assert _extract_block_text(block) == "Some text"

    def test_heading(self):
        from integrations.notion import _extract_block_text
        block = {"type": "heading_2", "heading_2": {"rich_text": [{"plain_text": "Title"}]}}
        assert _extract_block_text(block) == "## Title"

    def test_todo_checked(self):
        from integrations.notion import _extract_block_text
        block = {"type": "to_do", "to_do": {"rich_text": [{"plain_text": "Done task"}], "checked": True}}
        assert _extract_block_text(block) == "[x] Done task"

    def test_todo_unchecked(self):
        from integrations.notion import _extract_block_text
        block = {"type": "to_do", "to_do": {"rich_text": [{"plain_text": "Open task"}], "checked": False}}
        assert _extract_block_text(block) == "[ ] Open task"

    def test_bullet(self):
        from integrations.notion import _extract_block_text
        block = {"type": "bulleted_list_item", "bulleted_list_item": {"rich_text": [{"plain_text": "Item"}]}}
        assert _extract_block_text(block) == "• Item"

    def test_divider(self):
        from integrations.notion import _extract_block_text
        block = {"type": "divider", "divider": {}}
        assert _extract_block_text(block) == "---"


class TestFormatPage:
    def test_formats_page(self):
        from integrations.notion import _format_page
        page = {
            "id": "abc-123",
            "url": "https://notion.so/abc",
            "created_time": "2025-01-01T00:00:00Z",
            "last_edited_time": "2025-01-02T00:00:00Z",
            "properties": {
                "Name": {
                    "type": "title",
                    "title": [{"plain_text": "My Page"}],
                },
            },
        }
        result = _format_page(page)
        assert result["id"] == "abc-123"
        assert result["title"] == "My Page"
        assert result["url"] == "https://notion.so/abc"


class TestSearchPages:
    @pytest.mark.asyncio
    async def test_raises_when_not_configured(self):
        with patch("integrations.notion.NOTION_API_KEY", ""):
            from integrations.notion import search_pages
            with pytest.raises(RuntimeError, match="not configured"):
                await search_pages("test")

    @pytest.mark.asyncio
    async def test_returns_pages(self):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {
            "results": [
                {
                    "id": "page-1",
                    "url": "https://notion.so/page-1",
                    "created_time": "2025-01-01T00:00:00Z",
                    "last_edited_time": "2025-01-01T00:00:00Z",
                    "properties": {
                        "title": {"type": "title", "title": [{"plain_text": "Meeting Notes"}]},
                    },
                }
            ],
        }

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with (
            patch("integrations.notion.NOTION_API_KEY", "ntn-test"),
            patch("integrations.notion.httpx.AsyncClient", return_value=mock_client),
        ):
            from integrations.notion import search_pages
            result = await search_pages("meeting")

        assert result["count"] == 1
        assert result["pages"][0]["title"] == "Meeting Notes"


class TestGetPageContent:
    @pytest.mark.asyncio
    async def test_returns_content(self):
        mock_page_resp = MagicMock()
        mock_page_resp.raise_for_status = MagicMock()
        mock_page_resp.json.return_value = {
            "id": "page-1",
            "url": "https://notion.so/page-1",
            "created_time": "2025-01-01T00:00:00Z",
            "last_edited_time": "2025-01-01T00:00:00Z",
            "properties": {
                "title": {"type": "title", "title": [{"plain_text": "Standup"}]},
            },
        }

        mock_blocks_resp = MagicMock()
        mock_blocks_resp.raise_for_status = MagicMock()
        mock_blocks_resp.json.return_value = {
            "results": [
                {"type": "paragraph", "paragraph": {"rich_text": [{"plain_text": "Discussed roadmap"}]}},
                {"type": "to_do", "to_do": {"rich_text": [{"plain_text": "@Jonas review PR"}], "checked": False}},
            ],
        }

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=[mock_page_resp, mock_blocks_resp])
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with (
            patch("integrations.notion.NOTION_API_KEY", "ntn-test"),
            patch("integrations.notion.httpx.AsyncClient", return_value=mock_client),
        ):
            from integrations.notion import get_page_content
            result = await get_page_content("page-1")

        assert result["title"] == "Standup"
        assert "Discussed roadmap" in result["content"]
        assert "@Jonas review PR" in result["content"]


class TestExtractProperties:
    def test_extracts_various_types(self):
        from integrations.notion import _extract_properties
        props = {
            "Name": {"type": "title", "title": [{"plain_text": "Task 1"}]},
            "Status": {"type": "select", "select": {"name": "In Progress"}},
            "Tags": {"type": "multi_select", "multi_select": [{"name": "bug"}, {"name": "urgent"}]},
            "Done": {"type": "checkbox", "checkbox": True},
            "Due": {"type": "date", "date": {"start": "2025-03-15"}},
            "Priority": {"type": "number", "number": 5},
        }
        result = _extract_properties(props)
        assert result["Name"] == "Task 1"
        assert result["Status"] == "In Progress"
        assert result["Tags"] == ["bug", "urgent"]
        assert result["Done"] is True
        assert result["Due"] == "2025-03-15"
        assert result["Priority"] == 5
