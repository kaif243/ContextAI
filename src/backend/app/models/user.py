"""User model for authentication and preferences."""

from sqlalchemy import String, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel


class User(BaseModel):
    """User model representing the application user."""

    __tablename__ = "users"

    username: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    email: Mapped[str | None] = mapped_column(String(255), unique=True, nullable=True)
    hashed_password: Mapped[str | None] = mapped_column(String(255), nullable=True)
    full_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_superuser: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Relationships
    settings: Mapped["Settings"] = relationship(
        "Settings", back_populates="user", uselist=False, cascade="all, delete-orphan"
    )
    clipboard_items: Mapped[list["ClipboardItem"]] = relationship(
        "ClipboardItem", back_populates="user", cascade="all, delete-orphan"
    )
    memories: Mapped[list["MemoryItem"]] = relationship(
        "MemoryItem", back_populates="user", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<User(id={self.id}, username={self.username})>"
