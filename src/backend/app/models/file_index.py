"""File index models for file intelligence feature."""

from datetime import datetime

from sqlalchemy import String, Integer, Boolean, Float, ForeignKey, Text, Index, JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel


class FileIndex(BaseModel):
    """File index model for storing indexed file metadata."""

    __tablename__ = "files"
    __table_args__ = (
        Index("ix_file_path", "path", unique=True),
        Index("ix_file_name", "name"),
        Index("ix_file_type", "file_type"),
        Index("ix_file_classification", "classification"),
        Index("ix_file_modified", "modified_at"),
    )

    # Basic file info
    path: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(500), nullable=False)
    file_type: Mapped[str] = mapped_column(String(50), nullable=False)
    extension: Mapped[str | None] = mapped_column(String(20), nullable=True)

    # Size and dates
    size_bytes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at_fs: Mapped[datetime | None] = mapped_column(nullable=True)
    modified_at: Mapped[datetime | None] = mapped_column(nullable=True)
    accessed_at: Mapped[datetime | None] = mapped_column(nullable=True)

    # Classification (ML-based)
    classification: Mapped[str | None] = mapped_column(String(50), nullable=True)
    classification_confidence: Mapped[float | None] = mapped_column(
        Float, nullable=True
    )

    # Content
    content_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    text_content: Mapped[str | None] = mapped_column(Text, nullable=True)
    extracted_text: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Metadata
    metadata_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    tags: Mapped[str] = mapped_column(String(1000), default="", nullable=False)

    # Status
    is_indexed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    last_checked: Mapped[datetime | None] = mapped_column(nullable=True)

    # Similarity (for duplicate detection)
    similar_files: Mapped[str | None] = mapped_column(
        String(2000), nullable=True
    )  # JSON array of similar file IDs

    def __repr__(self) -> str:
        return f"<FileIndex(id={self.id}, name={self.name}, type={self.file_type})>"

    def to_dict(self) -> dict:
        """Convert to dictionary for API response."""
        return {
            "id": self.id,
            "path": self.path,
            "name": self.name,
            "file_type": self.file_type,
            "extension": self.extension,
            "size_bytes": self.size_bytes,
            "modified_at": self.modified_at.isoformat() if self.modified_at else None,
            "classification": self.classification,
            "classification_confidence": self.classification_confidence,
            "is_indexed": self.is_indexed,
        }


class FileChunk(BaseModel):
    """File chunk model for storing text chunks with embeddings."""

    __tablename__ = "file_chunks"
    __table_args__ = (
        Index("ix_chunk_file_id", "file_id"),
        Index("ix_chunk_index", "file_id", "chunk_index"),
    )

    file_id: Mapped[int] = mapped_column(
        ForeignKey("files.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Chunk info
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    chunk_text: Mapped[str] = mapped_column(Text, nullable=False)
    char_start: Mapped[int] = mapped_column(Integer, nullable=False)
    char_end: Mapped[int] = mapped_column(Integer, nullable=False)

    # Embedding (stored as text for SQLite compatibility)
    embedding: Mapped[str | None] = mapped_column(Text, nullable=True)
    embedding_model: Mapped[str | None] = mapped_column(String(100), nullable=True)

    def __repr__(self) -> str:
        return f"<FileChunk(id={self.id}, file_id={self.file_id}, index={self.chunk_index})>"
