"""Test security/permission system."""

import pytest

from app.core.security import (
    PermissionLevel,
    get_permission_level,
    requires_confirmation,
    can_auto_approve,
    PermissionCategory,
    PermissionContext,
)


def test_green_actions_dont_need_confirmation():
    """Test that GREEN permission actions don't need confirmation."""
    for action in PermissionCategory.READ_OPERATIONS:
        assert requires_confirmation(action) is False
        assert can_auto_approve(action) is True
        assert get_permission_level(action) == PermissionLevel.GREEN


def test_yellow_actions_need_confirmation():
    """Test that YELLOW permission actions need confirmation."""
    for action in PermissionCategory.MODIFY_OPERATIONS:
        assert requires_confirmation(action) is True
        assert can_auto_approve(action) is False
        assert get_permission_level(action) == PermissionLevel.YELLOW


def test_red_actions_always_need_confirmation():
    """Test that RED permission actions always need confirmation."""
    for action in PermissionCategory.DESTRUCTIVE_OPERATIONS:
        assert requires_confirmation(action) is True
        assert can_auto_approve(action) is False
        assert get_permission_level(action) == PermissionLevel.RED


def test_unknown_action_defaults_to_yellow():
    """Test that unknown actions default to YELLOW permission."""
    assert get_permission_level("unknown_action") == PermissionLevel.YELLOW
    assert requires_confirmation("unknown_action") is True


def test_permission_context_to_dict():
    """Test PermissionContext serialization."""
    ctx = PermissionContext(
        action="delete_file",
        level=PermissionLevel.RED,
        reason="User request",
        metadata={"file_path": "/test.txt"},
    )
    data = ctx.to_dict()

    assert data["action"] == "delete_file"
    assert data["level"] == "RED"
    assert data["level_value"] == 3
    assert data["reason"] == "User request"
    assert data["requires_confirmation"] is True
    assert data["approved"] is None


def test_permission_context_display():
    """Test PermissionContext display string."""
    green_ctx = PermissionContext("read_file", PermissionLevel.GREEN)
    yellow_ctx = PermissionContext("move_file", PermissionLevel.YELLOW)
    red_ctx = PermissionContext("delete_file", PermissionLevel.RED)

    assert "Auto-approve" in green_ctx.to_display_string()
    assert "Confirmation required" in yellow_ctx.to_display_string()
    assert "Always confirm" in red_ctx.to_display_string()
