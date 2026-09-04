"""Screenshot model for screen intelligence feature (Phase 2)."""

from datetime import datetime

from sqlalchemy import String, Integer, Boolean, Float, ForeignKey, Text, Index, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel


class Screenshot(BaseModel):
    """Screenshot model for storing captured screen images and analysis results.

    Phase 2 stores metadata about the capture (path, dimensions, hash), the
    extracted text, and the baseline (rule-based) classification label so the
    data is reusable in later ML training without re-capturing.
    """

    __tablename__ = "screenshots"
    __table_args__ = (
        Index("ix_screenshot_user_created", "user_id", "created_at"),
        Index("ix_screenshot_classification", "classification"),
    )

    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=True,
    )

    # Capture metadata
    file_path: Mapped[str] = mapped_column(String(1000), nullable=False)
    file_name: Mapped[str] = mapped_column(String(500), nullable=False)
    width: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    height: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    file_size_bytes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    content_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)

    # Region capture info (None means full screen)
    region_x: Mapped[int | None] = mapped_column(Integer, nullable=True)
    region_y: Mapped[int | None] = mapped_column(Integer, nullable=True)
    region_width: Mapped[int | None] = mapped_column(Integer, nullable=True)
    region_height: Mapped[int | None] = mapped_column(Integer, nullable=True)
    monitor_index: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # OCR results
    ocr_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    ocr_engine: Mapped[str | None] = mapped_column(String(50), nullable=True)
    ocr_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    ocr_word_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    ocr_char_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    ocr_processing_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Baseline (rule-based) classification. NOT ML — replaceable via the
    # ActivityClassifier interface in app.classification.
    classification: Mapped[str | None] = mapped_column(String(50), nullable=True)
    classification_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    classification_signals: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    classifier_version: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # Extracted entities from OCR text (regex-based, simple, deterministic)
    extracted_entities: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # Source / context
    source_app: Mapped[str | None] = mapped_column(String(200), nullable=True)
    window_title: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # User actions
    is_saved: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    user_notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationships
    analyses: Mapped[list["ScreenAnalysis"]] = relationship(
        "ScreenAnalysis",
        back_populates="screenshot",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<Screenshot(id={self.id}, file={self.file_name}, class={self.classification})>"

    def to_dict(self) -> dict:
        """Convert to dictionary for API response."""
        return {
            "id": str(self.id),
            "file_path": self.file_path,
            "file_name": self.file_name,
            "width": self.width,
            "height": self.height,
            "file_size_bytes": self.file_size_bytes,
            "content_hash": self.content_hash,
            "region": (
                {
                    "x": self.region_x,
                    "y": self.region_y,
                    "width": self.region_width,
                    "height": self.region_height,
                }
                if self.region_x is not None
                else None
            ),
            "monitor_index": self.monitor_index,
            "ocr": {
                "text": self.ocr_text or "",
                "engine": self.ocr_engine,
                "confidence": self.ocr_confidence,
                "word_count": self.ocr_word_count,
                "char_count": self.ocr_char_count,
                "processing_ms": self.ocr_processing_ms,
            },
            "classification": {
                "label": self.classification,
                "confidence": self.classification_confidence,
                "signals": self.classification_signals or {},
                "version": self.classifier_version,
            },
            "extracted_entities": self.extracted_entities or {},
            "source_app": self.source_app,
            "window_title": self.window_title,
            "is_saved": self.is_saved,
            "is_archived": self.is_archived,
            "user_notes": self.user_notes,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class ScreenAnalysis(BaseModel):
    """Screen analysis model for storing LLM Q&A and analysis sessions.

    Each analysis is tied to a screenshot. Multiple analyses can be performed
    on the same screenshot (e.g., user asks several questions).
    """

    __tablename__ = "screen_analyses"
    __table_args__ = (
        Index("ix_screen_analysis_screenshot", "screenshot_id"),
        Index("ix_screen_analysis_type", "analysis_type"),
    )

    screenshot_id: Mapped[int] = mapped_column(
        ForeignKey("screenshots.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Analysis details
    analysis_type: Mapped[str] = mapped_column(String(50), nullable=False)
    # "qa", "explain", "summary", "extract"

    question: Mapped[str | None] = mapped_column(Text, nullable=True)
    answer: Mapped[str] = mapped_column(Text, nullable=False)
    model_used: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # Performance
    prompt_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    completion_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    processing_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Status
    is_error: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationships
    screenshot: Mapped["Screenshot"] = relationship("Screenshot", back_populates="analyses")

    def __repr__(self) -> str:
        return f"<ScreenAnalysis(id={self.id}, type={self.analysis_type})>"

    def to_dict(self) -> dict:
        """Convert to dictionary for API response."""
        return {
            "id": str(self.id),
            "screenshot_id": str(self.screenshot_id),
            "analysis_type": self.analysis_type,
            "question": self.question,
            "answer": self.answer,
            "model_used": self.model_used,
            "tokens": {
                "prompt": self.prompt_tokens,
                "completion": self.completion_tokens,
                "total": self.total_tokens,
            },
            "processing_ms": self.processing_ms,
            "is_error": self.is_error,
            "error_message": self.error_message,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
