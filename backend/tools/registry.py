"""Unified tool registry — define once, emit Claude and OpenAI formats.

This eliminates the 35-vs-55 tool parity gap by maintaining a single source
of truth for all tool definitions. Each tool is registered with its schema
and handler, and can be exported in either format.
"""
from __future__ import annotations

import inspect
import json
import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Awaitable

logger = logging.getLogger(__name__)


@dataclass
class ToolDefinition:
    """A single tool definition with metadata and handler."""

    name: str
    description: str
    parameters: dict[str, Any]  # JSON Schema for parameters
    handler: Callable[..., Awaitable[dict[str, Any]]]
    category: str = "general"
    requires_auth: bool = False
    requires_confirmation: bool = False
    inject_chat_id: bool = False
    inject_user_id: bool = False

    def to_claude(self) -> dict[str, Any]:
        """Export as Claude API tool format."""
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.parameters,
        }

    def to_openai(self) -> dict[str, Any]:
        """Export as OpenAI function calling format."""
        return {
            "type": "function",
            "name": self.name,
            "description": self.description,
            "parameters": self.parameters,
        }


class ToolRegistry:
    """Central registry for all TARS tools.

    Handles registration, format conversion, and execution dispatch.
    Tools are grouped by category for organization.
    """

    def __init__(self) -> None:
        self._tools: dict[str, ToolDefinition] = {}
        self._categories: dict[str, list[str]] = {}

    def register(
        self,
        name: str,
        description: str,
        parameters: dict[str, Any],
        handler: Callable[..., Awaitable[dict[str, Any]]],
        *,
        category: str = "general",
        requires_auth: bool = False,
        requires_confirmation: bool = False,
        inject_chat_id: bool = False,
        inject_user_id: bool = False,
    ) -> None:
        """Register a tool. Idempotent — skips if already registered."""
        if name in self._tools:
            return

        tool = ToolDefinition(
            name=name,
            description=description,
            parameters=parameters,
            handler=handler,
            category=category,
            requires_auth=requires_auth,
            requires_confirmation=requires_confirmation,
            inject_chat_id=inject_chat_id,
            inject_user_id=inject_user_id,
        )
        self._tools[name] = tool
        self._categories.setdefault(category, []).append(name)
        logger.debug("Registered tool: %s [%s]", name, category)

    def get(self, name: str) -> ToolDefinition | None:
        """Get a tool definition by name."""
        return self._tools.get(name)

    @property
    def tool_names(self) -> list[str]:
        """All registered tool names."""
        return list(self._tools.keys())

    @property
    def categories(self) -> dict[str, list[str]]:
        """Tool names grouped by category."""
        return dict(self._categories)

    def to_claude_format(self, *, categories: list[str] | None = None) -> list[dict[str, Any]]:
        """Export all (or filtered) tools in Claude API format."""
        tools = self._filter_tools(categories)
        return [t.to_claude() for t in tools]

    def to_openai_format(self, *, categories: list[str] | None = None) -> list[dict[str, Any]]:
        """Export all (or filtered) tools in OpenAI format."""
        tools = self._filter_tools(categories)
        return [t.to_openai() for t in tools]

    async def execute(
        self,
        name: str,
        arguments: dict[str, Any],
        *,
        chat_id: int = 0,
        user_id: str = "",
        team_id: str = "",
    ) -> dict[str, Any]:
        """Execute a tool by name with the given arguments."""
        tool = self._tools.get(name)
        if tool is None:
            return {"error": f"Unknown tool: {name}"}

        try:
            # Inject context if needed
            if tool.inject_chat_id:
                arguments["_chat_id"] = chat_id
            if tool.inject_user_id:
                arguments["_user_id"] = user_id

            # Call handler
            if inspect.iscoroutinefunction(tool.handler):
                result = await tool.handler(arguments)
            else:
                result = tool.handler(arguments)

            return result

        except Exception as exc:
            logger.exception("Tool '%s' failed", name)
            return {"error": f"Tool '{name}' failed: {exc}"}

    def _filter_tools(self, categories: list[str] | None) -> list[ToolDefinition]:
        """Filter tools by category."""
        if categories is None:
            return list(self._tools.values())
        names = set()
        for cat in categories:
            names.update(self._categories.get(cat, []))
        return [self._tools[n] for n in names if n in self._tools]


# Global singleton registry
registry = ToolRegistry()
