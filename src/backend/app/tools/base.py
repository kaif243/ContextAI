"""Tool system base classes."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class ToolInput:
    """Input schema for a tool."""

    action: str
    parameters: dict[str, Any] = field(default_factory=dict)
    context: dict[str, Any] = field(default_factory=dict)


@dataclass
class ToolOutput:
    """Output schema for a tool."""

    success: bool
    result: Any = None
    error: Optional[str] = None
    metadata: dict[str, Any] = field(default_factory=dict)


class Tool(ABC):
    """
    Base class for all tools.

    Tools are modular functions with strict input/output schemas.
    """

    def __init__(
        self,
        name: str,
        description: str,
        permission_level: str = "YELLOW",  # GREEN, YELLOW, RED
        input_schema: Optional[dict[str, Any]] = None,
        output_schema: Optional[dict[str, Any]] = None,
    ):
        """
        Initialize a tool.

        Args:
            name: Tool name (e.g., "read_file").
            description: Human-readable description.
            permission_level: Required permission level.
            input_schema: JSON Schema for input.
            output_schema: JSON Schema for output.
        """
        self.name = name
        self.description = description
        self.permission_level = permission_level
        self.input_schema = input_schema or {}
        self.output_schema = output_schema or {}

    @abstractmethod
    async def execute(self, tool_input: ToolInput) -> ToolOutput:
        """
        Execute the tool.

        Args:
            tool_input: Input data for the tool.

        Returns:
            ToolOutput with results.
        """
        pass

    def get_info(self) -> dict[str, Any]:
        """Get tool information."""
        return {
            "name": self.name,
            "description": self.description,
            "permission_level": self.permission_level,
            "input_schema": self.input_schema,
            "output_schema": self.output_schema,
        }
