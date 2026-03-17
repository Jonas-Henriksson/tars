"""TARS agent core — Claude API agentic loop with tool use."""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import anthropic

from agent.tools import TOOL_DEFINITIONS, execute_tool
from config import ANTHROPIC_API_KEY

log = logging.getLogger(__name__)

_BASE_SYSTEM_PROMPT = """\
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
Use create_epic/get_epics for major deliverables, create_story/get_stories \
for value slices. Use link_task_to_story to connect tasks to stories.
Use get_team_portfolio for per-member workload, get_member_portfolio for \
one person's full plate. Unlinked tasks are fine for operational work.
When referencing an epic or story by name, first look it up to resolve the ID.\
"""

_MEMORY_INSTRUCTIONS = """

## Memory Instructions
When the user tells you their name, role, timezone, or other personal facts — \
call remember_fact() immediately, without asking.
When the user states a preference about how TARS should respond (style, \
format, language, brevity) — call remember_preference() immediately.
When the user mentions something important to remember across sessions \
(dates, personal context, ongoing situations) — call add_memory_note() immediately.
Do all of this proactively and silently — don't announce that you're saving."""


def _build_system_prompt() -> str:
    """Build the system prompt, injecting user memory and current work context."""
    parts = [_BASE_SYSTEM_PROMPT]

    # Inject user memory if any exists
    try:
        from integrations.memory import get_memory
        mem = get_memory()
        if mem.get("facts") or mem.get("preferences") or mem.get("notes"):
            lines = ["\n## About the User (remembered across sessions)"]
            if mem.get("facts"):
                lines.append("Facts: " + ", ".join(f"{k}: {v}" for k, v in mem["facts"].items()))
            if mem.get("preferences"):
                lines.append("Preferences: " + "; ".join(f"{k} → {v}" for k, v in mem["preferences"].items()))
            if mem.get("notes"):
                # Show most recent 5 notes
                recent = [n["text"] for n in mem["notes"][-5:]]
                lines.append("Notes: " + " | ".join(recent))
            parts.append("\n".join(lines))
    except Exception:
        pass

    # Inject brief current work context from existing intel data (read-only, no scan)
    try:
        from integrations.intel import get_intel_summary
        summary = get_intel_summary()
        if summary:
            parts.append(f"\n## Current Work Context\n{summary}")
    except Exception:
        pass

    # Inject business context from knowledge repository
    try:
        from integrations.knowledge import get_knowledge, get_company_summary
        kb = get_knowledge()
        for company_key in kb.get("companies", {}):
            summary = get_company_summary(company_key)
            if summary:
                parts.append(f"\n{summary}")
    except Exception:
        pass

    parts.append(_MEMORY_INSTRUCTIONS)
    return "\n".join(parts)


# ---- Conversation history ----

# Per-chat conversation histories: {chat_id: [{"role": ..., "content": ...}]}
_histories: dict[int, list[dict[str, Any]]] = {}

MAX_HISTORY = 20  # Keep last N message pairs to control token usage

_HISTORY_FILE = Path(__file__).parent.parent / "conversation_history.json"


def _load_histories() -> None:
    """Load persisted conversation histories from disk into memory."""
    global _histories
    if not _HISTORY_FILE.exists():
        return
    try:
        raw: dict[str, list[dict]] = json.loads(_HISTORY_FILE.read_text())
        # Only load plain text role/content pairs — skip any tool-use dicts
        for chat_id_str, messages in raw.items():
            clean = [
                m for m in messages
                if isinstance(m, dict)
                and m.get("role") in ("user", "assistant")
                and isinstance(m.get("content"), str)
            ]
            if clean:
                _histories[int(chat_id_str)] = clean
    except (json.JSONDecodeError, OSError, ValueError):
        log.warning("Could not load conversation_history.json — starting fresh.")


def _save_histories() -> None:
    """Persist current in-memory histories to disk."""
    try:
        serializable = {str(k): v for k, v in _histories.items()}
        _HISTORY_FILE.write_text(json.dumps(serializable, indent=2, ensure_ascii=False))
    except OSError as e:
        log.warning("Could not save conversation history: %s", e)


# Load persisted histories on module import
_load_histories()


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
    _save_histories()


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
            "system": _build_system_prompt(),
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

        # Save assistant reply to history (plain text only) and persist to disk
        history.append({"role": "assistant", "content": assistant_reply})
        _save_histories()

        return assistant_reply
