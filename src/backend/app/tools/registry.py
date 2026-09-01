"""Tool registry for managing available tools."""

from typing import Any

from app.core.logging import get_logger
from app.tools.base import Tool

logger = get_logger(__name__)


class ToolRegistry:
    """
    Registry for managing available tools.

    Provides tool lookup, registration, and categorization.
    """

    def __init__(self):
        """Initialize tool registry."""
        self._tools: dict[str, Tool] = {}
        self._categories: dict[str, list[str]] = {
            "file": [],
            "screen": [],
            "clipboard": [],
            "search": [],
            "browser": [],
            "developer": [],
        }

    def register(self, tool: Tool, category: str | None = None) -> None:
        """
        Register a tool.

        Args:
            tool: Tool instance to register.
            category: Optional category for the tool.
        """
        if tool.name in self._tools:
            logger.warning(f"Tool {tool.name} already registered, overwriting")

        self._tools[tool.name] = tool

        if category and category in self._categories:
            if tool.name not in self._categories[category]:
                self._categories[category].append(tool.name)

        logger.info(f"Registered tool: {tool.name}")

    def unregister(self, name: str) -> bool:
        """
        Unregister a tool.

        Args:
            name: Tool name to unregister.

        Returns:
            True if removed, False if not found.
        """
        if name not in self._tools:
            return False

        del self._tools[name]

        # Remove from categories
        for category_tools in self._categories.values():
            if name in category_tools:
                category_tools.remove(name)

        logger.info(f"Unregistered tool: {name}")
        return True

    def get(self, name: str) -> Tool | None:
        """Get a tool by name."""
        return self._tools.get(name)

    def list_all(self) -> list[dict[str, Any]]:
        """List all registered tools."""
        return [tool.get_info() for tool in self._tools.values()]

    def list_by_category(self, category: str) -> list[dict[str, Any]]:
        """List tools in a specific category."""
        tool_names = self._categories.get(category, [])
        return [
            self._tools[name].get_info()
            for name in tool_names
            if name in self._tools
        ]

    def get_categories(self) -> list[str]:
        """Get list of tool categories."""
        return list(self._categories.keys())


# Global tool registry instance
_registry = ToolRegistry()


def get_tool_registry() -> ToolRegistry:
    """Get the global tool registry."""
    return _registry
