"""Clipboard service for managing clipboard items."""

from datetime import datetime, timezone
from typing import Sequence

from sqlalchemy.orm import Session

from app.models.clipboard import ClipboardItem
from app.core.logging import get_logger

logger = get_logger(__name__)


class ClipboardService:
    """Service for managing clipboard history."""

    def __init__(self, db: Session):
        """Initialize clipboard service."""
        self.db = db

    def add_item(self, content: str, content_type: str = "text") -> ClipboardItem:
        """
        Add a new clipboard item.

        Args:
            content: The clipboard content.
            content_type: Type of content (text, code, url, etc.).

        Returns:
            The created clipboard item.
        """
        item = ClipboardItem(
            content=content,
            content_type=content_type,
            timestamp=datetime.now(timezone.utc),
            char_count=len(content),
            word_count=len(content.split()),
        )
        self.db.add(item)
        self.db.commit()
        self.db.refresh(item)
        logger.info(f"Added clipboard item: {item.id}")
        return item

    def get_history(
        self,
        limit: int = 50,
        offset: int = 0,
        content_type: str | None = None,
    ) -> tuple[Sequence[ClipboardItem], int]:
        """
        Get clipboard history.

        Args:
            limit: Maximum number of items to return.
            offset: Number of items to skip.
            content_type: Optional content type filter.

        Returns:
            Tuple of (items, total_count).
        """
        query = self.db.query(ClipboardItem).order_by(ClipboardItem.timestamp.desc())

        if content_type:
            query = query.filter(ClipboardItem.content_type == content_type)

        total = query.count()
        items = query.offset(offset).limit(limit).all()

        return items, total

    def delete_item(self, item_id: int) -> bool:
        """
        Delete a clipboard item.

        Args:
            item_id: ID of the item to delete.

        Returns:
            True if deleted, False if not found.
        """
        item = self.db.query(ClipboardItem).filter(ClipboardItem.id == item_id).first()
        if item is None:
            return False

        self.db.delete(item)
        self.db.commit()
        logger.info(f"Deleted clipboard item: {item_id}")
        return True

    def toggle_pin(self, item_id: int, pinned: bool) -> ClipboardItem | None:
        """
        Toggle pin status of a clipboard item.

        Args:
            item_id: ID of the item to pin/unpin.
            pinned: Whether to pin (True) or unpin (False).

        Returns:
            Updated item or None if not found.
        """
        item = self.db.query(ClipboardItem).filter(ClipboardItem.id == item_id).first()
        if item is None:
            return None

        item.is_pinned = pinned
        self.db.commit()
        self.db.refresh(item)
        return item

    def clear_history(self, keep_pinned: bool = True) -> int:
        """
        Clear clipboard history.

        Args:
            keep_pinned: Whether to keep pinned items.

        Returns:
            Number of items deleted.
        """
        query = self.db.query(ClipboardItem)
        if keep_pinned:
            query = query.filter(ClipboardItem.is_pinned == False)  # noqa: E712

        count = query.delete()
        self.db.commit()
        logger.info(f"Cleared {count} clipboard items")
        return count
