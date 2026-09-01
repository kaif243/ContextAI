"""Memory model for user-controlled memory system."""

from sqlalchemy import String, Boolean, Text, Index, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel


class MemoryItem(BaseModel):
    """Memory item model for user-controlled memory."""

    __tablename__ = "memories"
    __table_args__ = (
        Index("ix_memory_user_type", "user_id", "memory_type"),
        Index("ix_memory_pinned", "is_pinned"),
    )

    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=True,
    )

    # Content
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)

    # Classification
    memory_type: Mapped[str] = mapped_column(
        String(50), default="note", nullable=False
    )  # note, document, snippet, task, date, other
    tags: Mapped[str] = mapped_column(String(1000), default="", nullable=False)

    # Status
    is_pinned: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Source tracking
    source_type: Mapped[str | None] = mapped_column(
        String(50), nullable=True
    )  # clipboard, file, screenshot, manual
    source_id: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # Importance
    importance: Mapped[str] = mapped_column(
        String(20), default="normal", nullable=False
    )  # high, normal, low

    # Relationships
    user: Mapped["User | None"] = relationship("User", back_populates="memories")

    def __repr__(self) -> str:
        return f"<MemoryItem(id={self.id}, title={self.title}, type={self.memory_type})>"

    def to_dict(self) -> dict:
        """Convert to dictionary for API response."""
        return {
            "id": str(self.id),
            "title": self.title,
            "content": self.content,
            "memory_type": self.memory_type,
            "tags": self.tags.split(",") if self.tags else [],
            "is_pinned": self.is_pinned,
            "is_archived": self.is_archived,
            "importance": self.importance,
            "source_type": self.source_type,
            "source_id": self.source_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
