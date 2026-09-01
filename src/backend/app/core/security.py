"""Permission system foundation for human-in-the-loop security."""

from enum import IntEnum
from typing import Optional


class PermissionLevel(IntEnum):
    """
    Three-tier permission system for ContextAI actions.

    GREEN: Safe operations that can run automatically
    YELLOW: Operations requiring user confirmation
    RED: Dangerous operations always requiring confirmation
    """

    GREEN = 1  # Auto-approve
    YELLOW = 2  # Require confirmation
    RED = 3  # Always require confirmation


class PermissionCategory:
    """Defines permission categories for different action types."""

    # GREEN - Safe, read-only operations
    READ_OPERATIONS = [
        "read_file",
        "search_files",
        "get_clipboard",
        "get_screen_content",
        "analyze_image",
        "classify_content",
        "semantic_search",
        "get_memory",
        "list_memory",
    ]

    # YELLOW - Operations that modify data but are generally safe
    MODIFY_OPERATIONS = [
        "save_to_memory",
        "copy_file",
        "move_file",
        "rename_file",
        "create_folder",
        "classify_file",
        "extract_entities",
        "summarize_content",
    ]

    # RED - Dangerous operations that require explicit confirmation
    DESTRUCTIVE_OPERATIONS = [
        "delete_file",
        "delete_memory",
        "execute_command",
        "modify_system",
        "send_message",
        "upload_file",
        "clear_clipboard",
        "clear_memory",
        "clear_all_data",
    ]


def get_permission_level(action: str) -> PermissionLevel:
    """
    Determine the permission level for an action.

    Args:
        action: The action name to check.

    Returns:
        The required permission level for the action.
    """
    action_lower = action.lower()

    if action_lower in PermissionCategory.READ_OPERATIONS:
        return PermissionLevel.GREEN
    elif action_lower in PermissionCategory.MODIFY_OPERATIONS:
        return PermissionLevel.YELLOW
    elif action_lower in PermissionCategory.DESTRUCTIVE_OPERATIONS:
        return PermissionLevel.RED

    # Default to YELLOW for unknown actions (assume requires confirmation)
    return PermissionLevel.YELLOW


def requires_confirmation(action: str) -> bool:
    """
    Check if an action requires user confirmation.

    Args:
        action: The action name to check.

    Returns:
        True if the action requires user confirmation.
    """
    return get_permission_level(action) != PermissionLevel.GREEN


def can_auto_approve(action: str) -> bool:
    """
    Check if an action can be automatically approved.

    Args:
        action: The action name to check.

    Returns:
        True if the action can proceed without confirmation.
    """
    return get_permission_level(action) == PermissionLevel.GREEN


class PermissionContext:
    """
    Context for permission evaluation.

    Allows tracking why a permission was granted or denied.
    """

    def __init__(
        self,
        action: str,
        level: PermissionLevel,
        reason: Optional[str] = None,
        metadata: Optional[dict] = None,
    ):
        self.action = action
        self.level = level
        self.reason = reason
        self.metadata = metadata or {}
        self.approved: Optional[bool] = None
        self.approved_by: Optional[str] = None
        self.approved_at: Optional[str] = None

    def to_dict(self) -> dict:
        """Convert context to dictionary."""
        return {
            "action": self.action,
            "level": self.level.name,
            "level_value": self.level.value,
            "reason": self.reason,
            "metadata": self.metadata,
            "requires_confirmation": requires_confirmation(self.action),
            "approved": self.approved,
            "approved_by": self.approved_by,
            "approved_at": self.approved_at,
        }

    def to_display_string(self) -> str:
        """Get a human-readable permission level string."""
        level_names = {
            PermissionLevel.GREEN: "🟢 Auto-approve",
            PermissionLevel.YELLOW: "🟡 Confirmation required",
            PermissionLevel.RED: "🔴 Always confirm",
        }
        return level_names.get(self.level, "Unknown")
