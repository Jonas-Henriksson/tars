"""Centralized LLM client — shared model configuration and call helper.

All LLM calls across the TARS system route through this module.
This ensures consistent model selection, logging, and easy override.

Model Strategy:
- All analytical/reasoning calls use Opus for maximum insight quality
- Agent chat uses Sonnet 4.6 as default (user can override in UI)
- TARS_MODEL_OVERRIDE env var forces all calls to a specific model
"""
from __future__ import annotations

import asyncio
import logging
import os
import time
from typing import Any

logger = logging.getLogger(__name__)

# -----------------------------------------------------------------------
# Model constants
# -----------------------------------------------------------------------

MODEL_OPUS = "claude-opus-4-6"
MODEL_SONNET = "claude-sonnet-4-6"
MODEL_HAIKU = "claude-haiku-4-5-20251001"

# Default model for all analytical calls
MODEL_DEFAULT = MODEL_OPUS

# Task-to-model mapping — all use Opus for maximum insight quality
MODEL_CONFIG: dict[str, str] = {
    "metadata_extraction": MODEL_OPUS,
    "task_title_rewrite": MODEL_OPUS,
    "topic_normalization": MODEL_OPUS,
    "knowledge_synthesis": MODEL_OPUS,
    "news_classification": MODEL_OPUS,
    "epic_generation": MODEL_OPUS,
    "people_enrichment": MODEL_OPUS,
    "context_synthesis": MODEL_OPUS,
    "context_relevance_check": MODEL_OPUS,
    "item_context_summary": MODEL_OPUS,
    "smart_steps": MODEL_OPUS,
}

# -----------------------------------------------------------------------
# Shared client
# -----------------------------------------------------------------------

_client = None


def _get_client():
    """Lazy-init shared Anthropic client."""
    global _client
    if _client is not None:
        return _client
    try:
        from config import ANTHROPIC_API_KEY
        if not ANTHROPIC_API_KEY:
            return None
        import anthropic
        _client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        return _client
    except Exception as e:
        logger.warning("Cannot initialize Anthropic client: %s", e)
        return None


def _resolve_model(task: str) -> str:
    """Resolve the model to use for a given task.

    Priority:
    1. TARS_MODEL_OVERRIDE env var (forces all calls)
    2. MODEL_CONFIG for the specific task
    3. MODEL_DEFAULT fallback
    """
    override = os.environ.get("TARS_MODEL_OVERRIDE", "")
    if override:
        return override
    return MODEL_CONFIG.get(task, MODEL_DEFAULT)


# -----------------------------------------------------------------------
# Main call helper
# -----------------------------------------------------------------------

async def llm_call(
    task: str,
    prompt: str,
    max_tokens: int = 1024,
    messages: list[dict[str, str]] | None = None,
) -> str | None:
    """Make an LLM call with automatic model selection and logging.

    Args:
        task: Task name (key in MODEL_CONFIG, used for model selection and logging)
        prompt: The prompt text (used as user message if messages not provided)
        max_tokens: Maximum tokens in the response
        messages: Optional custom messages list (overrides prompt)

    Returns:
        The text response, or None if LLM is unavailable/fails
    """
    client = _get_client()
    if client is None:
        logger.warning("LLM client unavailable for task '%s'", task)
        return None

    model = _resolve_model(task)
    msgs = messages or [{"role": "user", "content": prompt}]

    t0 = time.monotonic()
    try:
        response = await asyncio.to_thread(
            client.messages.create,
            model=model,
            max_tokens=max_tokens,
            messages=msgs,
        )
        elapsed_ms = int((time.monotonic() - t0) * 1000)
        text = response.content[0].text.strip()

        # Log usage
        usage = response.usage
        logger.info(
            "LLM [%s] model=%s tokens_in=%d tokens_out=%d latency=%dms",
            task, model,
            getattr(usage, "input_tokens", 0),
            getattr(usage, "output_tokens", 0),
            elapsed_ms,
        )

        # Strip markdown code fences if present
        if text.startswith("```"):
            text = text.split("\n", 1)[1].rsplit("```", 1)[0].strip()

        return text

    except Exception as e:
        elapsed_ms = int((time.monotonic() - t0) * 1000)
        logger.warning(
            "LLM [%s] model=%s FAILED after %dms: %s",
            task, model, elapsed_ms, e,
        )
        return None
