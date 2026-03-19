"""TARS agent core — Claude API agentic loop with streaming and memory.

Improvements over the original agent/core.py:
- Async streaming for real-time token delivery
- Persistent conversation history in SQLite
- Model routing (Sonnet for conversation, Haiku for extraction)
- Unified tool registry integration
- User/team context awareness
"""
from __future__ import annotations

import json
import logging
from typing import Any, AsyncGenerator

import anthropic

from backend.database import get_db
from backend.database.queries import (
    generate_id, get_conversation_messages, insert_row, list_rows,
)
from backend.tools import registry
from backend.tools.handlers import register_all_tools
from config import ANTHROPIC_API_KEY

logger = logging.getLogger(__name__)

# Ensure tools are registered
register_all_tools()

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

AGILE WORK BREAKDOWN — You structure deliverables using Scrum methodology:
  Initiative → Epic (large deliverable) → User Story → Task.
Be pragmatic: use epics/stories for structured deliverables (features, \
projects, migrations) where team members need the bigger picture. \
Operational/admin work (hiring, vendor mgmt, ad-hoc asks) can stay as \
standalone tasks — don't over-structure what doesn't need it.

STRATEGIC LAYER — You have executive-grade strategic tools:
- Meeting prep: Before any meeting, use meeting_prep or next_meeting_brief.
- Decision register: Use log_decision, get_decisions for decision tracking.
- Initiatives & OKRs: Use create_initiative, get_initiatives for goals.
- Proactive alerts: Use get_alerts for risk scanning.

TEAM PORTFOLIO — get_team_portfolio for workload overview, \
get_member_portfolio for individual view.

When referencing an epic, story, initiative, or decision by name, \
first look it up to resolve the ID. Never ask the user for an ID directly.

When using tools, tell the user what you're doing. \
Always confirm before sending emails or creating events.\
"""

MAX_HISTORY_MESSAGES = 40  # Messages to load from DB for context


async def run_streaming(
    user_id: str,
    team_id: str,
    conversation_id: str,
    user_message: str,
) -> AsyncGenerator[dict[str, Any], None]:
    """Run the TARS agent loop with streaming token output.

    Yields events:
    - {"type": "token", "content": "..."}
    - {"type": "tool_call", "name": "...", "arguments": {...}}
    - {"type": "tool_result", "name": "...", "result": {...}}
    - {"type": "error", "detail": "..."}
    """
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    # Load conversation history from DB
    with get_db() as db:
        history = get_conversation_messages(
            db, conversation_id, limit=MAX_HISTORY_MESSAGES,
        )

    # Build messages for Claude
    messages: list[dict[str, Any]] = []
    for msg in history:
        role = msg["role"]
        if role in ("user", "assistant"):
            content = msg["content"]
            # Try to parse tool_calls/results from stored messages
            if msg.get("tool_calls"):
                try:
                    content = json.loads(msg["tool_calls"]) if isinstance(msg["tool_calls"], str) else msg["tool_calls"]
                except (json.JSONDecodeError, TypeError):
                    pass
            if msg.get("tool_results"):
                try:
                    content = json.loads(msg["tool_results"]) if isinstance(msg["tool_results"], str) else msg["tool_results"]
                except (json.JSONDecodeError, TypeError):
                    pass
            messages.append({"role": role, "content": content})

    # Add current user message
    messages.append({"role": "user", "content": user_message})

    # Get tool definitions
    tool_defs = registry.to_claude_format()

    # Agent loop
    while True:
        try:
            kwargs: dict[str, Any] = {
                "model": "claude-sonnet-4-20250514",
                "max_tokens": 4096,
                "system": SYSTEM_PROMPT,
                "messages": messages,
                "stream": True,
            }
            if tool_defs:
                kwargs["tools"] = tool_defs

            # Stream the response
            full_text = ""
            tool_uses = []

            with client.messages.stream(**kwargs) as stream:
                for event in stream:
                    if hasattr(event, 'type'):
                        if event.type == 'content_block_delta':
                            if hasattr(event.delta, 'text'):
                                full_text += event.delta.text
                                yield {"type": "token", "content": event.delta.text}

                response = stream.get_final_message()

        except Exception as exc:
            logger.exception("Claude API error")
            yield {"type": "error", "detail": str(exc)}
            return

        # Check for tool use
        if response.stop_reason == "tool_use":
            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    yield {
                        "type": "tool_call",
                        "name": block.name,
                        "arguments": block.input,
                    }

                    result = await registry.execute(
                        block.name, block.input,
                        user_id=user_id,
                        team_id=team_id,
                    )

                    yield {
                        "type": "tool_result",
                        "name": block.name,
                        "result": result,
                    }

                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": json.dumps(result),
                    })

            # Add to messages and continue loop
            messages.append({"role": "assistant", "content": response.content})
            messages.append({"role": "user", "content": tool_results})
            full_text = ""  # Reset for next response
            continue

        # Done — no more tool calls
        break


async def run(
    user_id: str,
    team_id: str,
    conversation_id: str,
    user_message: str,
) -> str:
    """Non-streaming version — runs the full agent loop and returns final text."""
    full_response = ""
    async for event in run_streaming(user_id, team_id, conversation_id, user_message):
        if event["type"] == "token":
            full_response += event["content"]
        elif event["type"] == "error":
            return f"Error: {event['detail']}"
    return full_response or "..."
