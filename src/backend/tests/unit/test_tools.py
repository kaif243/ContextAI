"""Test tool system."""

import pytest

from app.tools.base import Tool, ToolInput, ToolOutput
from app.tools.registry import ToolRegistry


class MockTool(Tool):
    """Mock tool for testing."""

    def __init__(self, name="mock_tool", permission="YELLOW"):
        super().__init__(
            name=name,
            description="A mock tool",
            permission_level=permission,
        )
        self.executed = False

    async def execute(self, tool_input: ToolInput) -> ToolOutput:
        self.executed = True
        return ToolOutput(success=True, result={"executed": True})


@pytest.mark.asyncio
async def test_tool_execution():
    """Test tool execution."""
    tool = MockTool()
    tool_input = ToolInput(action="test")

    result = await tool.execute(tool_input)

    assert result.success is True
    assert result.result == {"executed": True}
    assert tool.executed is True


def test_tool_info():
    """Test tool information."""
    tool = MockTool(name="my_tool", permission="RED")
    info = tool.get_info()

    assert info["name"] == "my_tool"
    assert info["description"] == "A mock tool"
    assert info["permission_level"] == "RED"


def test_registry_register():
    """Test tool registration."""
    registry = ToolRegistry()
    tool = MockTool(name="test_tool")

    registry.register(tool, category="file")

    assert registry.get("test_tool") is not None


def test_registry_unregister():
    """Test tool unregistration."""
    registry = ToolRegistry()
    tool = MockTool(name="test_tool")
    registry.register(tool, category="file")

    assert registry.unregister("test_tool") is True
    assert registry.get("test_tool") is None


def test_registry_unregister_not_found():
    """Test unregistering non-existent tool."""
    registry = ToolRegistry()

    assert registry.unregister("nonexistent") is False


def test_registry_list_by_category():
    """Test listing tools by category."""
    registry = ToolRegistry()
    tool1 = MockTool(name="tool1")
    tool2 = MockTool(name="tool2")

    registry.register(tool1, category="file")
    registry.register(tool2, category="file")

    tools = registry.list_by_category("file")
    assert len(tools) == 2


def test_registry_categories():
    """Test getting categories."""
    registry = ToolRegistry()

    categories = registry.get_categories()
    assert "file" in categories
    assert "screen" in categories
    assert "clipboard" in categories
