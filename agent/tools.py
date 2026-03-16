"""Tool definitions and executor for the TARS agent.

Tools are registered here as Claude API tool schemas. The execute_tool
function dispatches tool calls to the appropriate integration module.
"""
from __future__ import annotations

from typing import Any

# Tool definitions in Claude API format.
# Each entry is a dict with "name", "description", and "input_schema".
# Add tools here as integrations are built.
TOOL_DEFINITIONS: list[dict[str, Any]] = []

# Maps tool names to async handler functions.
# Handlers receive the tool input dict and return a result dict.
_TOOL_HANDLERS: dict[str, Any] = {}


def register_tool(name: str, description: str, input_schema: dict, handler) -> None:
    """Register a tool for the agent to use.

    Args:
        name: Tool name (e.g. "get_calendar_events").
        description: What the tool does (shown to Claude).
        input_schema: JSON Schema for the tool's input parameters.
        handler: Async function that executes the tool. Receives input dict, returns result dict.
    """
    TOOL_DEFINITIONS.append({
        "name": name,
        "description": description,
        "input_schema": input_schema,
    })
    _TOOL_HANDLERS[name] = handler


async def execute_tool(name: str, tool_input: dict) -> dict:
    """Execute a registered tool by name.

    Returns:
        Result dict to send back to Claude.
    """
    handler = _TOOL_HANDLERS.get(name)
    if handler is None:
        return {"error": f"Unknown tool: {name}"}
    try:
        return await handler(tool_input)
    except RuntimeError as exc:
        return {"error": str(exc)}
    except Exception as exc:
        return {"error": f"Tool '{name}' failed: {exc}"}


# ---------------------------------------------------------------------------
# Register calendar tools
# ---------------------------------------------------------------------------

def _register_calendar_tools() -> None:
    """Register Microsoft 365 calendar tools."""
    from integrations.calendar import create_event, get_events
    from integrations.ms_auth import is_configured

    if not is_configured():
        return

    async def _handle_get_events(tool_input: dict) -> dict:
        return await get_events(
            days=tool_input.get("days", 7),
            max_results=tool_input.get("max_results", 20),
        )

    register_tool(
        name="get_calendar_events",
        description=(
            "Get the user's upcoming Microsoft 365 calendar events. "
            "Returns a list of events with subject, start/end times, location, and organizer."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "days": {
                    "type": "integer",
                    "description": "Number of days ahead to look. Default 7.",
                },
                "max_results": {
                    "type": "integer",
                    "description": "Maximum number of events to return. Default 20.",
                },
            },
        },
        handler=_handle_get_events,
    )

    async def _handle_create_event(tool_input: dict) -> dict:
        return await create_event(
            subject=tool_input["subject"],
            start_time=tool_input["start_time"],
            end_time=tool_input["end_time"],
            timezone_str=tool_input.get("timezone", "UTC"),
            location=tool_input.get("location", ""),
            body=tool_input.get("body", ""),
            attendees=tool_input.get("attendees"),
        )

    register_tool(
        name="create_calendar_event",
        description=(
            "Create a new event on the user's Microsoft 365 calendar. "
            "Always confirm the details with the user before calling this tool."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "subject": {
                    "type": "string",
                    "description": "Event title.",
                },
                "start_time": {
                    "type": "string",
                    "description": "Start time in ISO 8601 format (e.g. '2025-01-15T10:00:00').",
                },
                "end_time": {
                    "type": "string",
                    "description": "End time in ISO 8601 format.",
                },
                "timezone": {
                    "type": "string",
                    "description": "IANA timezone (e.g. 'Europe/Stockholm'). Default 'UTC'.",
                },
                "location": {
                    "type": "string",
                    "description": "Optional event location.",
                },
                "body": {
                    "type": "string",
                    "description": "Optional event description.",
                },
                "attendees": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Optional list of attendee email addresses.",
                },
            },
            "required": ["subject", "start_time", "end_time"],
        },
        handler=_handle_create_event,
    )


# Auto-register tools on import
_register_calendar_tools()
