"""Enhanced permission system with caching and validation."""

from enum import IntEnum
from typing import Optional, Dict, Set
from datetime import datetime, timezone

from sqlalchemy import Column, String, Integer, Boolean, ForeignKey, Text, Index
from sqlalchemy.orm import relationship

from app.models.base import BaseModel
from app.core.security import PermissionLevel, PermissionCategory, get_permission_level, can_auto_approve


class ActionPermission(BaseModel):
    """Tracks permission assignments and approvals for actions."""

    __tablename__ = "action_permissions"
    __table_args__ = (
        Index("ix_permission_user_action", "user_id", "action"),
        Index("ix_permission_entity", "entity_type", "entity_id"),
    )

    id: Column[int] = Column(Integer, primary_key=True, autoincrement=True)
    user_id: Column[int | None] = Column(ForeignKey("users.id", ondelete="CASCADE"), nullable=True)

    # Action details
    action: Column[str] = Column(String(100), nullable=False, index=True)
    action_category: Column[str] = Column(String(50), nullable=False)  # read, write, delete, admin

    # Target entity
    entity_type: Column[str | None] = Column(String(50), nullable=True)
    entity_id: Column[str | None] = Column(String(100), nullable=True)

    # Permission level
    required_level: Column[PermissionLevel] = Column(Integer, nullable=False)
    granted_level: Column[PermissionLevel | None] = Column(Integer, nullable=True)
    is_active: Column[bool] = Column(Boolean, default=True, nullable=False)

    # Context
    reason: Column[str | None] = Column(Text, nullable=True)
    conditions: Column[dict | None] = Column(String(500), nullable=True)  # JSON

    # Timestamps
    granted_at: Column[datetime] = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    expires_at: Column[datetime | None] = Column(DateTime(timezone=True), nullable=True)

    # Approval tracking
    approved_by: Column[str | None] = Column(String(100), nullable=True)
    approved_at: Column[datetime | None] = Column(DateTime(timezone=True), nullable=True)
    approval_notes: Column[str | None] = Column(Text, nullable=True)

    # Relationships
    user: Column["User | None"] = relationship("User", back_populates="action_permissions")

    def __repr__(self) -> str:
        return f"<ActionPermission(id={self.id}, action={self.action}, level={self.required_level.name})>"

    def to_dict(self) -> dict:
        """Convert to dictionary for API response."""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "action": self.action,
            "action_category": self.action_category,
            "entity_type": self.entity_type,
            "entity_id": self.entity_id,
            "required_level": self.required_level.name,
            "granted_level": self.granted_level.name if self.granted_level else None,
            "is_active": self.is_active,
            "reason": self.reason,
            "granted_at": self.granted_at.isoformat() if self.granted_at else None,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "approved_by": self.approved_by,
            "approved_at": self.approved_at.isoformat() if self.approved_at else None,
        }

    def is_valid(self) -> bool:
        """Check if permission is still valid."""
        if not self.is_active:
            return False
        if self.expires_at and datetime.now(timezone.utc) > self.expires_at:
            return False
        return True

    def can_approve(self, approver_level: PermissionLevel) -> bool:
        """Check if a permission level can approve this action."""
        return approver_level.value >= self.required_level.value

    def can_execute(self, executor_level: PermissionLevel) -> bool:
        """Check if a permission level can execute this action."""
        if not self.is_valid():
            return False
        if self.granted_level and executor_level.value < self.granted_level.value:
            return False
        return executor_level.value >= self.required_level.value


class PermissionCache:
    """Cache for permission checks to improve performance."""

    def __init__(self):
        self._cache: Dict[str, dict] = {}
        self._user_cache: Dict[int, dict] = {}

    def get_permission(self, user_id: Optional[int], action: str, entity_type: Optional[str] = None, entity_id: Optional[str] = None) -> dict:
        """Get permission for a user/action combination."""
        cache_key = f"{user_id}:{action}:{entity_type}:{entity_id}"

        if cache_key in self._cache:
            return self._cache[cache_key]

        # Default to GREEN for read operations
        if can_auto_approve(action):
            result = {
                "level": PermissionLevel.GREEN.value,
                "can_auto_approve": True,
                "requires_confirmation": False,
                "is_valid": True,
            }
        else:
            result = {
                "level": get_permission_level(action).value,
                "can_auto_approve": False,
                "requires_confirmation": True,
                "is_valid": True,
            }

        # Cache the result
        self._cache[cache_key] = result
        return result

    def clear_user_cache(self, user_id: int) -> None:
        """Clear cache for a specific user."""
        keys_to_remove = [k for k in self._cache.keys() if k.startswith(f"{user_id}:")]
        for key in keys_to_remove:
            del self._cache[key]

    def clear_all(self) -> None:
        """Clear all caches."""
        self._cache.clear()
        self._user_cache.clear()


# Global permission cache instance
_permission_cache = PermissionCache()


def get_permission_cache() -> PermissionCache:
    """Get the global permission cache."""
    return _permission_cache


def check_permission(user_id: Optional[int], action: str, entity_type: Optional[str] = None, entity_id: Optional[str] = None) -> dict:
    """Check if a user has permission to perform an action."""
    return _permission_cache.get_permission(user_id, action, entity_type, entity_id)


def validate_permission_level(user_level: int, action: str, required_level: int) -> bool:
    """Validate that a user permission level meets requirements."""
    return user_level >= required_level


def get_action_categories() -> Dict[str, Set[str]]:
    """Get all available action categories."""
    categories: Dict[str, Set[str]] = {
        "read": set(PermissionCategory.READ_OPERATIONS),
        "write": set(PermissionCategory.MODIFY_OPERATIONS),
        "delete": set(PermissionCategory.DESTRUCTIVE_OPERATIONS),
        "admin": set(),
    }
    return categories