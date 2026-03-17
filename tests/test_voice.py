"""Tests for voice transcription integration."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from integrations.voice import is_configured, transcribe


class TestIsConfigured:
    def test_configured_when_key_set(self):
        with patch("integrations.voice.OPENAI_API_KEY", "sk-test"):
            assert is_configured() is True

    def test_not_configured_when_empty(self):
        with patch("integrations.voice.OPENAI_API_KEY", ""):
            assert is_configured() is False


class TestTranscribe:
    @pytest.mark.asyncio
    async def test_transcribe_not_configured(self):
        with patch("integrations.voice.OPENAI_API_KEY", ""):
            with pytest.raises(RuntimeError, match="not configured"):
                await transcribe("/fake/path.ogg")

    @pytest.mark.asyncio
    async def test_transcribe_success(self):
        mock_result = MagicMock()
        mock_result.text = "Hello TARS, what's on my calendar?"
        mock_result.language = "en"

        mock_client = MagicMock()
        mock_client.audio.transcriptions.create.return_value = mock_result

        with (
            patch("integrations.voice.OPENAI_API_KEY", "sk-test"),
            patch("integrations.voice.OpenAI", return_value=mock_client),
            patch("builtins.open", MagicMock()),
        ):
            result = await transcribe("/fake/path.ogg")

        assert result["text"] == "Hello TARS, what's on my calendar?"
        assert result["language"] == "en"
