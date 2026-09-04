"""Clipboard item model for AI clipboard feature.

Phase 3 extends the Phase 1 columns with:

  * ``metadata_json`` — extracted entities + classifier signals.
  * ``expires_at``    — retention timestamp computed at write time.
  * ``is_sensitive``  — true when the local secret detector fired.
  * ``redacted_content`` — a display-safe preview that never reveals
    secret material; ``content`` itself may be empty when a sensitive
    item is stored without its raw text.
  * ``source_app``    — name of the application that produced the
    clipboard payload (best-effort; not all Tauri platforms supply it).
  * ``classifier_version`` — version of the content classifier that
    labelled the row, so future reclassification can skip rows it
    already covered.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel


class ClipboardItem(BaseModel):
    """Clipboard item model for storing clipboard history."""

    __tablename__ = "clipboard_items"
    __table_args__ = (
        Index("ix_clipboard_user_content_type", "user_id", "content_type"),
        Index("ix_clipboard_timestamp", "timestamp"),
        Index("ix_clipboard_classification", "classification"),
        Index("ix_clipboard_sensitive", "is_sensitive"),
        Index("ix_clipboard_expires", "expires_at"),
    )

    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=True,
    )

    # ------------------------------------------------------------------
    # Core content
    # ------------------------------------------------------------------
    content: Mapped[str] = mapped_column(Text, nullable=False, default="")
    # When ``is_sensitive`` is True and the policy is "redact", ``content``
    # is stored as the empty string and only ``redacted_content`` holds a
    # non-secret preview. Callers must check ``is_sensitive`` before
    # displaying ``content`` to the user.
    redacted_content: Mapped[str | None] = mapped_column(Text, nullable=True)
    content_type: Mapped[str] = mapped_column(
        String(50), default="text", nullable=False
    )  # text, code, url, email, file_path, json, unknown

    # ------------------------------------------------------------------
    # Classification + privacy
    # ------------------------------------------------------------------
    classification: Mapped[str | None] = mapped_column(String(50), nullable=True)
    classification_confidence: Mapped[float | None] = mapped_column(nullable=True)
    classifier_version: Mapped[str | None] = mapped_column(String(50), nullable=True)
    is_sensitive: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False, index=True
    )
    sensitive_reasons: Mapped[str | None] = mapped_column(
        String(500), nullable=True
    )  # comma-separated rule names (api_key, bearer_token, ...)

    # ------------------------------------------------------------------
    # Metadata
    # ------------------------------------------------------------------
    source_app: Mapped[str | None] = mapped_column(String(200), nullable=True)
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    char_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    word_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # ------------------------------------------------------------------
    # Timestamps for sorting + retention
    # ------------------------------------------------------------------
    timestamp: Mapped[datetime] = mapped_column(nullable=False, index=True)
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )

    # ------------------------------------------------------------------
    # User actions / flags
    # ------------------------------------------------------------------
    is_pinned: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_encrypted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # ------------------------------------------------------------------
    # Relationships
    # ------------------------------------------------------------------
    user: Mapped["User | None"] = relationship("User", back_populates="clipboard_items")

    def __repr__(self) -> str:
        preview_source = self.redacted_content or self.content
        preview = preview_source[:50] + "..." if len(preview_source) > 50 else preview_source
        return (
            f"<ClipboardItem(id={self.id}, type={self.content_type}, "
            f"sensitive={self.is_sensitive}, preview={preview!r})>"
        )

    @property
    def preview(self) -> str:
        """Return a UI-safe preview. Sensitive items never show ``content``."""
        if self.is_sensitive:
            source = self.redacted_content or ""
        else:
            source = self.content
        if len(source) <= 100:
            return source
        return source[:100] + "..."

    # ------------------------------------------------------------------
    # Serialisation
    # ------------------------------------------------------------------
    def to_dict(self, *, include_raw_content: bool | None = None) -> dict:
        """Serialise the row for the API.

        ``include_raw_content`` controls whether the raw ``content`` is
        returned for sensitive items. Defaults to a policy-aware value
        that returns the raw content only for non-sensitive rows.
        """
        if include_raw_content is None:
            include_raw_content = not self.is_sensitive

        return {
            "id": str(self.id),
            # For sensitive items the API must not leak raw secrets; the
            # redacted preview is the only safe surface.
            "content": self.content if include_raw_content else "",
            "redacted_content": self.redacted_content or "",
            "content_type": self.content_type,
            "classification": self.classification,
            "classification_confidence": self.classification_confidence,
            "classifier_version": self.classifier_version,
            "is_sensitive": self.is_sensitive,
            "sensitive_reasons": self._split_reasons(),
            "source_app": self.source_app,
            "metadata": self.metadata_json or {},
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "is_pinned": self.is_pinned,
            "is_encrypted": self.is_encrypted,
            "char_count": self.char_count,
            "word_count": self.word_count,
            "preview": self.preview,
        }

    def _split_reasons(self) -> list[str]:
        if not self.sensitive_reasons:
            return []
        return [r for r in self.sensitive_reasons.split(",") if r]
