"""Telegram message formatting helpers.

Telegram supports MarkdownV2 and HTML. We use HTML for reliability
(MarkdownV2 requires escaping many characters). These helpers format
agent responses for clean display in Telegram.
"""
from __future__ import annotations

import html


def escape(text: str) -> str:
    """Escape text for Telegram HTML mode."""
    return html.escape(text)


def bold(text: str) -> str:
    return f"<b>{escape(text)}</b>"


def italic(text: str) -> str:
    return f"<i>{escape(text)}</i>"


def code(text: str) -> str:
    return f"<code>{escape(text)}</code>"


def format_agent_response(text: str) -> str:
    """Format an agent response for Telegram.

    The agent returns plain text (possibly with markdown). For now,
    we pass it through as-is since Telegram handles plain text well.
    Later phases can add richer formatting for calendar events, emails, etc.
    """
    # Telegram has a 4096 char limit per message
    if len(text) > 4000:
        text = text[:4000] + "\n\n... (truncated)"
    return text
