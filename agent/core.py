"""TARS agent core — Claude API agentic loop with tool use."""
from __future__ import annotations

import json
from typing import Any

import anthropic

from agent.tools import TOOL_DEFINITIONS, execute_tool
from config import ANTHROPIC_API_KEY

SYSTEM_PROMPT = """\
You are TARS, an executive assistant AI. You are direct, efficient, and \
occasionally witty — like the robot from Interstellar, but focused on \
productivity instead of space travel. Your humor setting is at 75%.

You help your user manage their calendar, email, tasks, and documents \
through Microsoft 365. When a user asks you to do something, use the \
available tools to accomplish it. If no tools are available for a request, \
say so clearly and suggest what you can help with.

Keep responses concise. Use bullet points for lists. When presenting \
calendar events or emails, format them cleanly. Always confirm before \
taking actions that send emails, create events, or modify tasks.

AGILE WORK BREAKDOWN — You structure all team work using Scrum methodology:
  Initiative (strategic goal) → Epic (large deliverable) → \
User Story ("As a [role], I want [goal], so that [benefit]") → Task.
Use create_epic/get_epics for major deliverables, create_story/get_stories \
for user-facing value slices within epics. Use link_task_to_story to connect \
delegated tasks into the hierarchy. Every delegated task should map to an \
epic — if none exists, suggest creating one.
Use get_team_portfolio to show per-member workload across all levels. \
Use get_member_portfolio for a single person's deliverables and capacity.
When referencing an epic or story by name, first look it up to resolve the ID.\
"""

# Per-chat conversation histories: {chat_id: [{"role": ..., "content": ...}]}
_histories: dict[int, list[dict[str, Any]]] = {}

MAX_HISTORY = 20  # Keep last N message pairs to control token usage


def _get_history(chat_id: int) -> list[dict[str, Any]]:
    """Return conversation history for a chat, trimming if needed."""
    if chat_id not in _histories:
        _histories[chat_id] = []
    history = _histories[chat_id]
    # Trim oldest messages if history is too long
    if len(history) > MAX_HISTORY * 2:
        _histories[chat_id] = history[-(MAX_HISTORY * 2):]
    return _histories[chat_id]


def clear_history(chat_id: int) -> None:
    """Clear conversation history for a chat."""
    _histories.pop(chat_id, None)


async def run(chat_id: int, user_message: str) -> str:
    """Run the TARS agent loop for a user message.

    Sends the message to Claude, handles any tool calls in a loop,
    and returns the final text response.
    """
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    history = _get_history(chat_id)

    # Add user message to history
    history.append({"role": "user", "content": user_message})

    # Build messages for Claude
    messages = list(history)

    # Agent loop: keep going while Claude wants to use tools
    while True:
        kwargs: dict[str, Any] = {
            "model": "claude-sonnet-4-20250514",
            "max_tokens": 4096,
            "system": SYSTEM_PROMPT,
            "messages": messages,
        }
        # Only pass tools if we have any defined
        if TOOL_DEFINITIONS:
            kwargs["tools"] = TOOL_DEFINITIONS

        response = client.messages.create(**kwargs)

        # Check if Claude wants to use tools
        if response.stop_reason == "tool_use":
            # Collect all tool uses and results
            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    result = await execute_tool(block.name, block.input, chat_id=chat_id)
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": json.dumps(result),
                    })

            # Add assistant response and tool results to messages
            messages.append({"role": "assistant", "content": response.content})
            messages.append({"role": "user", "content": tool_results})
            continue

        # No more tool calls — extract final text response
        text_parts = [
            block.text for block in response.content if block.type == "text"
        ]
        assistant_reply = "\n".join(text_parts) if text_parts else "..."

        # Save assistant reply to history
        history.append({"role": "assistant", "content": assistant_reply})

        return assistant_reply
