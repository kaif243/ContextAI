"""Settings model for user preferences."""

from sqlalchemy import String, Boolean, Integer, ForeignKey, Float
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel


class Settings(BaseModel):
    """Application settings model for storing user preferences."""

    __tablename__ = "settings"

    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=True,
        unique=True,
    )

    # Hotkey settings
    hotkey: Mapped[str] = mapped_column(String(50), default="Ctrl+Space", nullable=False)

    # Behavior settings
    auto_start: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    minimize_to_tray: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    privacy_mode: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Monitoring settings
    clipboard_monitoring: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False
    )
    screen_monitoring: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )
    file_indexing_enabled: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )

    # LLM settings
    llm_provider: Mapped[str] = mapped_column(
        String(50), default="ollama", nullable=False
    )
    llm_model: Mapped[str] = mapped_column(
        String(100), default="llama3.1:8b", nullable=False
    )

    # Logging
    log_level: Mapped[str] = mapped_column(
        String(20), default="INFO", nullable=False
    )

    # Indexing settings
    indexed_folders: Mapped[str] = mapped_column(
        String(2000), default="", nullable=False
    )  # JSON array of folders
    exclude_patterns: Mapped[str] = mapped_column(
        String(2000),
        default="node_modules,.git,__pycache__,dist,build,.venv",
        nullable=False,
    )

    # Privacy settings
    retain_clipboard_days: Mapped[int] = mapped_column(
        Integer, default=30, nullable=False
    )
    retain_memories_days: Mapped[int] = mapped_column(
        Integer, default=365, nullable=False
    )

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="settings")

    def __repr__(self) -> str:
        return f"<Settings(id={self.id}, user_id={self.user_id})>"

    def to_dict(self) -> dict:
        """Convert settings to dictionary for API response."""
        return {
            "hotkey": self.hotkey,
            "auto_start": self.auto_start,
            "minimize_to_tray": self.minimize_to_tray,
            "privacy_mode": self.privacy_mode,
            "clipboard_monitoring": self.clipboard_monitoring,
            "screen_monitoring": self.screen_monitoring,
            "file_indexing_enabled": self.file_indexing_enabled,
            "llm_provider": self.llm_provider,
            "llm_model": self.llm_model,
            "log_level": self.log_level,
        }
