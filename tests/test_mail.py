"""Tests for Microsoft 365 mail integration."""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from integrations.mail import _format_message, get_messages, read_message, reply_to_message, search_messages, send_message


class TestFormatMessage:
    def test_format_basic_message(self):
        raw = {
            "id": "msg1",
            "subject": "Quarterly report",
            "from": {"emailAddress": {"name": "Alice", "address": "alice@example.com"}},
            "receivedDateTime": "2025-01-15T09:30:00Z",
            "isRead": False,
            "bodyPreview": "Please find attached...",
            "hasAttachments": True,
            "importance": "high",
        }
        result = _format_message(raw)

        assert result["subject"] == "Quarterly report"
        assert result["from_name"] == "Alice"
        assert result["from_email"] == "alice@example.com"
        assert result["is_read"] is False
        assert result["has_attachments"] is True
        assert result["importance"] == "high"

    def test_format_minimal_message(self):
        raw = {"id": "msg2"}
        result = _format_message(raw)

        assert result["subject"] == "(No subject)"
        assert result["from_name"] == ""
        assert result["is_read"] is False


class TestGetMessages:
    @pytest.mark.asyncio
    async def test_get_inbox(self):
        mock_data = {
            "value": [
                {
                    "id": "m1",
                    "subject": "Hello",
                    "from": {"emailAddress": {"name": "Bob", "address": "bob@test.com"}},
                    "receivedDateTime": "2025-01-15T10:00:00Z",
                    "isRead": True,
                    "bodyPreview": "Hi there",
                    "hasAttachments": False,
                    "importance": "normal",
                },
            ]
        }

        with (
            patch("integrations.mail.get_token_silent", return_value="fake-token"),
            patch("integrations.mail.graph_get", new_callable=AsyncMock, return_value=mock_data),
        ):
            result = await get_messages()

        assert result["count"] == 1
        assert result["messages"][0]["subject"] == "Hello"

    @pytest.mark.asyncio
    async def test_get_messages_unread_only(self):
        mock_data = {"value": []}

        with (
            patch("integrations.mail.get_token_silent", return_value="fake-token"),
            patch("integrations.mail.graph_get", new_callable=AsyncMock, return_value=mock_data) as mock_get,
        ):
            await get_messages(unread_only=True)

        params = mock_get.call_args[0][2] if len(mock_get.call_args[0]) > 2 else mock_get.call_args[1].get("params", {})
        assert "$filter" in params
        assert "isRead eq false" in params["$filter"]

    @pytest.mark.asyncio
    async def test_get_messages_not_signed_in(self):
        with patch("integrations.mail.get_token_silent", return_value=None):
            with pytest.raises(RuntimeError, match="Not signed in"):
                await get_messages()


class TestReadMessage:
    @pytest.mark.asyncio
    async def test_read_full_message(self):
        mock_data = {
            "id": "msg1",
            "subject": "Details",
            "from": {"emailAddress": {"name": "Alice", "address": "alice@test.com"}},
            "receivedDateTime": "2025-01-15T09:00:00Z",
            "isRead": True,
            "bodyPreview": "Here are the details...",
            "hasAttachments": False,
            "importance": "normal",
            "body": {"contentType": "text", "content": "Here are the full details of the project."},
            "toRecipients": [{"emailAddress": {"address": "me@test.com"}}],
            "ccRecipients": [{"emailAddress": {"address": "boss@test.com"}}],
        }

        with (
            patch("integrations.mail.get_token_silent", return_value="fake-token"),
            patch("integrations.mail.graph_get", new_callable=AsyncMock, return_value=mock_data),
        ):
            result = await read_message("msg1")

        assert result["body"] == "Here are the full details of the project."
        assert result["to"] == ["me@test.com"]
        assert result["cc"] == ["boss@test.com"]


class TestSendMessage:
    @pytest.mark.asyncio
    async def test_send_basic_email(self):
        with (
            patch("integrations.mail.get_token_silent", return_value="fake-token"),
            patch("integrations.mail.graph_post", new_callable=AsyncMock, return_value={}) as mock_post,
        ):
            result = await send_message(
                to=["bob@test.com"],
                subject="Meeting notes",
                body="Here are the notes from today.",
            )

        assert result["status"] == "sent"
        assert result["to"] == ["bob@test.com"]

        call_body = mock_post.call_args[0][2]
        assert call_body["message"]["subject"] == "Meeting notes"
        assert len(call_body["message"]["toRecipients"]) == 1

    @pytest.mark.asyncio
    async def test_send_with_cc(self):
        with (
            patch("integrations.mail.get_token_silent", return_value="fake-token"),
            patch("integrations.mail.graph_post", new_callable=AsyncMock, return_value={}) as mock_post,
        ):
            await send_message(
                to=["bob@test.com"],
                subject="FYI",
                body="See below.",
                cc=["alice@test.com"],
            )

        call_body = mock_post.call_args[0][2]
        assert len(call_body["message"]["ccRecipients"]) == 1
        assert call_body["message"]["ccRecipients"][0]["emailAddress"]["address"] == "alice@test.com"


class TestReplyToMessage:
    @pytest.mark.asyncio
    async def test_reply_success(self):
        with (
            patch("integrations.mail.get_token_silent", return_value="fake-token"),
            patch("integrations.mail.graph_post", new_callable=AsyncMock, return_value={}) as mock_post,
        ):
            result = await reply_to_message("msg1", "Thanks for the update.")

        assert result["status"] == "replied"
        assert result["reply_all"] is False
        # Should call reply endpoint, not replyAll
        assert "/reply" in mock_post.call_args[0][0]
        assert "/replyAll" not in mock_post.call_args[0][0]

    @pytest.mark.asyncio
    async def test_reply_all(self):
        with (
            patch("integrations.mail.get_token_silent", return_value="fake-token"),
            patch("integrations.mail.graph_post", new_callable=AsyncMock, return_value={}) as mock_post,
        ):
            result = await reply_to_message("msg1", "Noted.", reply_all=True)

        assert result["reply_all"] is True
        assert "/replyAll" in mock_post.call_args[0][0]


class TestSearchMessages:
    @pytest.mark.asyncio
    async def test_search_success(self):
        mock_data = {
            "value": [
                {
                    "id": "s1",
                    "subject": "Q1 Budget Report",
                    "from": {"emailAddress": {"name": "Finance", "address": "finance@test.com"}},
                    "receivedDateTime": "2025-01-10T08:00:00Z",
                    "isRead": True,
                    "bodyPreview": "Attached is the Q1 budget...",
                    "hasAttachments": True,
                    "importance": "normal",
                },
            ]
        }

        with (
            patch("integrations.mail.get_token_silent", return_value="fake-token"),
            patch("integrations.mail.graph_get", new_callable=AsyncMock, return_value=mock_data) as mock_get,
        ):
            result = await search_messages("budget")

        assert result["count"] == 1
        assert result["query"] == "budget"
        assert result["messages"][0]["subject"] == "Q1 Budget Report"
