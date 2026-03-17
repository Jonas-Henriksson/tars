"""Voice transcription via OpenAI Whisper API."""
from __future__ import annotations

import logging
import tempfile
from pathlib import Path
from typing import Any

from openai import OpenAI

from config import OPENAI_API_KEY

logger = logging.getLogger(__name__)


def is_configured() -> bool:
    """Return True if OpenAI API key is set."""
    return bool(OPENAI_API_KEY)


async def transcribe(audio_path: str | Path) -> dict[str, Any]:
    """Transcribe an audio file using OpenAI Whisper API.

    Args:
        audio_path: Path to the audio file (ogg, mp3, wav, etc.).

    Returns:
        Dict with "text" (transcription) and "language".
    """
    if not is_configured():
        raise RuntimeError(
            "Voice transcription is not configured. "
            "Set OPENAI_API_KEY in your .env file."
        )

    client = OpenAI(api_key=OPENAI_API_KEY)

    with open(audio_path, "rb") as audio_file:
        result = client.audio.transcriptions.create(
            model="whisper-1",
            file=audio_file,
            response_format="verbose_json",
        )

    return {
        "text": result.text,
        "language": getattr(result, "language", "unknown"),
    }
