"""Tests for the TARS agent core."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from tars.agent.core import _get_history, clear_history, run
from tars.agent.tools import TOOL_DEFINITIONS, execute_tool, register_tool


class TestToolRegistry:
    def test_register_tool(self):
        """Registering a tool adds it to definitions and handlers."""
        initial_count = len(TOOL_DEFINITIONS)

        async def dummy_handler(tool_input):
            return {"result": "ok"}

        register_tool(
            name="test_tool",
            description="A test tool",
            input_schema={"type": "object", "properties": {}},
            handler=dummy_handler,
        )

        assert len(TOOL_DEFINITIONS) == initial_count + 1
        assert TOOL_DEFINITIONS[-1]["name"] == "test_tool"

        # Clean up
        TOOL_DEFINITIONS.pop()

    @pytest.mark.asyncio
    async def test_execute_unknown_tool(self):
        """Executing an unknown tool returns an error."""
        result = await execute_tool("nonexistent_tool", {})
        assert "error" in result

    @pytest.mark.asyncio
    async def test_execute_registered_tool(self):
        """Executing a registered tool calls its handler."""
        async def echo_handler(tool_input):
            return {"echo": tool_input.get("message", "")}

        register_tool(
            name="echo_test",
            description="Echoes input",
            input_schema={
                "type": "object",
                "properties": {"message": {"type": "string"}},
            },
            handler=echo_handler,
        )

        result = await execute_tool("echo_test", {"message": "hello"})
        assert result == {"echo": "hello"}

        # Clean up
        TOOL_DEFINITIONS.pop()


class TestConversationHistory:
    def test_get_history_creates_new(self):
        """Getting history for a new chat_id creates an empty list."""
        history = _get_history(999999)
        assert history == []
        clear_history(999999)

    def test_clear_history(self):
        """Clearing history removes it."""
        history = _get_history(888888)
        history.append({"role": "user", "content": "test"})
        clear_history(888888)
        assert _get_history(888888) == []
        clear_history(888888)


class TestAgentRun:
    @pytest.mark.asyncio
    async def test_run_basic_response(self):
        """Agent returns Claude's text response."""
        mock_text_block = MagicMock()
        mock_text_block.type = "text"
        mock_text_block.text = "Hello, I'm TARS."

        mock_response = MagicMock()
        mock_response.stop_reason = "end_turn"
        mock_response.content = [mock_text_block]

        with patch("tars.agent.core.anthropic.Anthropic") as mock_cls:
            mock_client = MagicMock()
            mock_client.messages.create.return_value = mock_response
            mock_cls.return_value = mock_client

            result = await run(12345, "Hello TARS")

        assert result == "Hello, I'm TARS."
        clear_history(12345)

    @pytest.mark.asyncio
    async def test_run_maintains_history(self):
        """Agent maintains conversation history across calls."""
        mock_text_block = MagicMock()
        mock_text_block.type = "text"
        mock_text_block.text = "Response"

        mock_response = MagicMock()
        mock_response.stop_reason = "end_turn"
        mock_response.content = [mock_text_block]

        with patch("tars.agent.core.anthropic.Anthropic") as mock_cls:
            mock_client = MagicMock()
            mock_client.messages.create.return_value = mock_response
            mock_cls.return_value = mock_client

            await run(11111, "First message")
            await run(11111, "Second message")

        history = _get_history(11111)
        # Should have: user1, assistant1, user2, assistant2
        assert len(history) == 4
        assert history[0]["content"] == "First message"
        assert history[2]["content"] == "Second message"
        clear_history(11111)
