"""Tests for voice transcription and TTS integration."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from integrations.voice import is_configured, text_to_speech, transcribe


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


class TestTextToSpeech:
    @pytest.mark.asyncio
    async def test_tts_not_configured(self):
        with patch("integrations.voice.OPENAI_API_KEY", ""):
            with pytest.raises(RuntimeError, match="not configured"):
                await text_to_speech("Hello")

    @pytest.mark.asyncio
    async def test_tts_success(self):
        mock_response = MagicMock()
        mock_response.stream_to_file = MagicMock()

        mock_client = MagicMock()
        mock_client.audio.speech.create.return_value = mock_response

        with (
            patch("integrations.voice.OPENAI_API_KEY", "sk-test"),
            patch("integrations.voice.OpenAI", return_value=mock_client),
        ):
            result = await text_to_speech("Hello, I'm TARS.")

        assert str(result).endswith(".ogg")
        mock_client.audio.speech.create.assert_called_once_with(
            model="tts-1",
            voice="onyx",
            input="Hello, I'm TARS.",
            response_format="opus",
        )

        # Clean up temp file
        result.unlink(missing_ok=True)

    @pytest.mark.asyncio
    async def test_tts_custom_voice(self):
        mock_response = MagicMock()
        mock_response.stream_to_file = MagicMock()

        mock_client = MagicMock()
        mock_client.audio.speech.create.return_value = mock_response

        with (
            patch("integrations.voice.OPENAI_API_KEY", "sk-test"),
            patch("integrations.voice.OpenAI", return_value=mock_client),
        ):
            result = await text_to_speech("Hello", voice="nova")

        mock_client.audio.speech.create.assert_called_once_with(
            model="tts-1",
            voice="nova",
            input="Hello",
            response_format="opus",
        )

        result.unlink(missing_ok=True)
