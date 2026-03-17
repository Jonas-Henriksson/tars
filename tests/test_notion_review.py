"""Tests for the Notion page review system."""
from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

import pytest

from integrations.notion_review import (
    add_known_names,
    check_title_consistency,
    find_name_issues,
    get_known_names,
    remove_known_names,
)


# ---------------------------------------------------------------------------
# Known names management
# ---------------------------------------------------------------------------

class TestKnownNames:
    def test_add_names(self, tmp_path):
        state_file = tmp_path / "state.json"
        with patch("integrations.notion_review._STATE_FILE", state_file):
            result = add_known_names(["Jonas", "Alice", "Bob"])
        assert result["total"] == 3
        assert "Jonas" in result["names"]

    def test_add_deduplicates(self, tmp_path):
        state_file = tmp_path / "state.json"
        with patch("integrations.notion_review._STATE_FILE", state_file):
            add_known_names(["Jonas", "Alice"])
            result = add_known_names(["Jonas", "Bob"])
        assert result["total"] == 3
        assert result["added"] == ["Bob"]

    def test_remove_names(self, tmp_path):
        state_file = tmp_path / "state.json"
        with patch("integrations.notion_review._STATE_FILE", state_file):
            add_known_names(["Jonas", "Alice", "Bob"])
            result = remove_known_names(["Alice"])
        assert result["removed"] == ["Alice"]
        assert result["total"] == 2

    def test_get_names(self, tmp_path):
        state_file = tmp_path / "state.json"
        with patch("integrations.notion_review._STATE_FILE", state_file):
            add_known_names(["Jonas", "Alice"])
            result = get_known_names()
        assert result["count"] == 2
        assert "Jonas" in result["names"]


# ---------------------------------------------------------------------------
# Name spell-checking
# ---------------------------------------------------------------------------

class TestFindNameIssues:
    def test_detects_misspelling(self):
        text = "Jon will handle the deployment."
        issues = find_name_issues(text, ["Jonas"])
        assert len(issues) == 1
        assert issues[0]["found"] == "Jon"
        assert issues[0]["suggested"] == "Jonas"

    def test_exact_match_no_issue(self):
        text = "Jonas will handle the deployment."
        issues = find_name_issues(text, ["Jonas"])
        assert len(issues) == 0

    def test_multiple_misspellings(self):
        text = "Alise and Joans met yesterday."
        issues = find_name_issues(text, ["Alice", "Jonas"])
        found_names = {i["found"] for i in issues}
        assert "Alise" in found_names
        assert "Joans" in found_names

    def test_ignores_common_words(self):
        text = "The Meeting was about Action items for Next steps."
        issues = find_name_issues(text, ["Jonas", "Alice"])
        assert len(issues) == 0

    def test_empty_known_names(self):
        text = "Jon and Alise discussed things."
        issues = find_name_issues(text, [])
        assert len(issues) == 0

    def test_includes_context(self):
        text = "Today Joans reviewed the PR and gave feedback."
        issues = find_name_issues(text, ["Jonas"])
        assert len(issues) == 1
        assert "Joans" in issues[0]["context"]

    def test_no_false_positive_on_distant_names(self):
        text = "The System handled the request."
        issues = find_name_issues(text, ["Jonas"])
        assert len(issues) == 0


# ---------------------------------------------------------------------------
# Title consistency
# ---------------------------------------------------------------------------

class TestCheckTitleConsistency:
    def test_empty_title(self):
        issues = check_title_consistency("", "content")
        assert any(i["type"] == "missing_title" for i in issues)

    def test_untitled(self):
        issues = check_title_consistency("Untitled", "content")
        assert any(i["type"] == "missing_title" for i in issues)

    def test_one_on_one_missing_name(self):
        issues = check_title_consistency("1:1 - 2025-03-15", "content")
        assert any(i["type"] == "one_on_one_missing_name" for i in issues)

    def test_one_on_one_with_name(self):
        issues = check_title_consistency("1:1 Jonas - 2025-03-15", "content")
        assert not any(i["type"] == "one_on_one_missing_name" for i in issues)

    def test_meeting_missing_date(self):
        issues = check_title_consistency("Sprint Planning", "content")
        assert any(i["type"] == "meeting_missing_date" for i in issues)

    def test_meeting_with_date(self):
        issues = check_title_consistency("Sprint Planning 2025-03-15", "content")
        assert not any(i["type"] == "meeting_missing_date" for i in issues)

    def test_meeting_with_month_date(self):
        issues = check_title_consistency("Sprint Planning - March 15", "content")
        assert not any(i["type"] == "meeting_missing_date" for i in issues)

    def test_non_meeting_no_date_needed(self):
        issues = check_title_consistency("Project Architecture", "content")
        assert not any(i["type"] == "meeting_missing_date" for i in issues)


# ---------------------------------------------------------------------------
# Full page review
# ---------------------------------------------------------------------------

class TestReviewPage:
    @pytest.mark.asyncio
    async def test_reports_title_and_name_issues(self):
        mock_page = {
            "id": "p1",
            "title": "Sprint Planning",
            "url": "https://notion.so/p1",
            "content": "Jon will present the roadmap.\nAlise takes notes.",
            "block_count": 2,
        }
        mock_blocks = [
            {"id": "b1", "type": "paragraph", "text": "Jon will present the roadmap.", "has_children": False},
            {"id": "b2", "type": "paragraph", "text": "Alise takes notes.", "has_children": False},
        ]
        state = {"last_reviewed_at": None, "known_names": ["Jonas", "Alice"], "title_patterns": {}, "reviewed_pages": []}

        with (
            patch("integrations.notion_review.is_configured", return_value=True),
            patch("integrations.notion_review.get_page_content", new_callable=AsyncMock, return_value=mock_page),
            patch("integrations.notion_review.get_page_blocks", new_callable=AsyncMock, return_value=mock_blocks),
            patch("integrations.notion_review._load_state", return_value=state),
        ):
            from integrations.notion_review import review_page
            result = await review_page("p1", auto_fix=False)

        # Should find: meeting_missing_date in title + name issues in blocks
        assert result["issue_count"] >= 2
        types = {i["type"] for i in result["issues"]}
        assert "meeting_missing_date" in types or "name_spelling" in types

    @pytest.mark.asyncio
    async def test_auto_fix_applies_spelling_corrections(self):
        mock_page = {
            "id": "p1",
            "title": "Notes",
            "url": "https://notion.so/p1",
            "content": "Joans presented.",
            "block_count": 1,
        }
        mock_blocks = [
            {"id": "b1", "type": "paragraph", "text": "Joans presented.", "has_children": False},
        ]
        state = {"last_reviewed_at": None, "known_names": ["Jonas"], "title_patterns": {}, "reviewed_pages": []}

        with (
            patch("integrations.notion_review.is_configured", return_value=True),
            patch("integrations.notion_review.get_page_content", new_callable=AsyncMock, return_value=mock_page),
            patch("integrations.notion_review.get_page_blocks", new_callable=AsyncMock, return_value=mock_blocks),
            patch("integrations.notion_review._load_state", return_value=state),
            patch("integrations.notion_review.update_block_text", new_callable=AsyncMock) as mock_update,
        ):
            from integrations.notion_review import review_page
            result = await review_page("p1", auto_fix=True)

        assert result["fix_count"] >= 1
        mock_update.assert_called()
        call_args = mock_update.call_args
        assert "Jonas" in call_args[0][1]  # new_text contains corrected name


class TestReviewRecentPages:
    @pytest.mark.asyncio
    async def test_reviews_new_pages(self):
        mock_pages = {
            "pages": [
                {"id": "p1", "title": "Standup", "url": "https://notion.so/p1",
                 "created_time": "2025-01-01", "last_edited_time": "2025-03-17"},
            ],
            "count": 1,
        }
        mock_review = {
            "page_id": "p1", "title": "Standup", "url": "https://notion.so/p1",
            "issues": [], "fixes_applied": [], "issue_count": 0, "fix_count": 0,
        }
        state = {"last_reviewed_at": None, "known_names": [], "title_patterns": {}, "reviewed_pages": []}

        with (
            patch("integrations.notion_review.is_configured", return_value=True),
            patch("integrations.notion_review.get_recently_edited_pages", new_callable=AsyncMock, return_value=mock_pages),
            patch("integrations.notion_review.review_page", new_callable=AsyncMock, return_value=mock_review),
            patch("integrations.notion_review._load_state", return_value=state),
            patch("integrations.notion_review._save_state"),
        ):
            from integrations.notion_review import review_recent_pages
            result = await review_recent_pages()

        assert result["pages_checked"] == 1
        assert result["last_reviewed_at"] is not None

    @pytest.mark.asyncio
    async def test_no_pages_since_last_review(self):
        mock_pages = {"pages": [], "count": 0}
        state = {"last_reviewed_at": "2025-03-17T00:00:00Z", "known_names": [], "title_patterns": {}, "reviewed_pages": []}

        with (
            patch("integrations.notion_review.is_configured", return_value=True),
            patch("integrations.notion_review.get_recently_edited_pages", new_callable=AsyncMock, return_value=mock_pages),
            patch("integrations.notion_review._load_state", return_value=state),
        ):
            from integrations.notion_review import review_recent_pages
            result = await review_recent_pages()

        assert result["pages_checked"] == 0
        assert "No new" in result["message"]
