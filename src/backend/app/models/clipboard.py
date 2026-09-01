"""Clipboard item model for AI clipboard feature."""

from datetime import datetime

from sqlalchemy import String, Boolean, Integer, Text, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel


class ClipboardItem(BaseModel):
    """Clipboard item model for storing clipboard history."""

    __tablename__ = "clipboard_items"
    __table_args__ = (
        Index("ix_clipboard_user_content_type", "user_id", "content_type"),
        Index("ix_clipboard_timestamp", "timestamp"),
    )

    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=True,
    )

    # Content
    content: Mapped[str] = mapped_column(Text, nullable=False)
    content_type: Mapped[str] = mapped_column(
        String(50), default="text", nullable=False
    )  # text, code, url, email, etc.

    # Classification
    classification: Mapped[str | None] = mapped_column(String(50), nullable=True)
    importance: Mapped[str | None] = mapped_column(
        String(20), nullable=True
    )  # high, normal, low

    # Metadata
    source_app: Mapped[str | None] = mapped_column(String(100), nullable=True)
    char_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    word_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Timestamps for sorting
    timestamp: Mapped[datetime] = mapped_column(nullable=False, index=True)

    # Pinning
    is_pinned: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Privacy
    is_encrypted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Relationships
    user: Mapped["User | None"] = relationship("User", back_populates="clipboard_items")

    def __repr__(self) -> str:
        preview = self.content[:50] + "..." if len(self.content) > 50 else self.content
        return f"<ClipboardItem(id={self.id}, type={self.content_type}, preview={preview})>"

    @property
    def preview(self) -> str:
        """Get a preview of the content."""
        if len(self.content) <= 100:
            return self.content
        return self.content[:100] + "..."

    def to_dict(self) -> dict:
        """Convert to dictionary for API response."""
        return {
            "id": str(self.id),
            "content": self.content,
            "content_type": self.content_type,
            "classification": self.classification,
            "importance": self.importance,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "is_pinned": self.is_pinned,
            "char_count": self.char_count,
            "word_count": self.word_count,
            "source_app": self.source_app,
        }
