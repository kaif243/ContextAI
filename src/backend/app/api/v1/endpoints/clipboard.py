"""Clipboard endpoint for AI clipboard feature."""

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.logging import get_logger
from app.core.security import get_permission_level, PermissionLevel
from app.models.clipboard import ClipboardItem

logger = get_logger(__name__)

router = APIRouter()


# Pydantic models
class ClipboardItemResponse(BaseModel):
    """Clipboard item response model."""

    id: str
    content: str
    content_type: str
    classification: str | None = None
    timestamp: str
    is_pinned: bool
    char_count: int = 0
    word_count: int = 0


class ClipboardHistoryResponse(BaseModel):
    """Clipboard history response model."""

    items: list[ClipboardItemResponse]
    total: int


@router.get("/history", response_model=ClipboardHistoryResponse)
async def get_clipboard_history(
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    content_type: str | None = None,
    db: Session = Depends(get_db),
) -> ClipboardHistoryResponse:
    """
    Get clipboard history.

    Returns paginated clipboard history, most recent first.
    """
    # Check permission
    permission = get_permission_level("get_clipboard")
    logger.debug(f"Clipboard history requested (permission: {permission.name})")

    query = db.query(ClipboardItem).order_by(ClipboardItem.timestamp.desc())

    if content_type:
        query = query.filter(ClipboardItem.content_type == content_type)

    total = query.count()
    items = query.offset(offset).limit(limit).all()

    return ClipboardHistoryResponse(
        items=[
            ClipboardItemResponse(
                id=str(item.id),
                content=item.content,
                content_type=item.content_type,
                classification=item.classification,
                timestamp=item.timestamp.isoformat() if item.timestamp else "",
                is_pinned=item.is_pinned,
                char_count=item.char_count,
                word_count=item.word_count,
            )
            for item in items
        ],
        total=total,
    )


@router.post("/add")
async def add_clipboard_item(
    content: str,
    content_type: str = "text",
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """
    Add a new clipboard item.

    This would be called by clipboard monitoring.
    For Phase 1, this is a placeholder.
    """
    # Check permission
    permission = get_permission_level("save_to_memory")
    logger.info(f"Adding clipboard item (type: {content_type}, permission: {permission.name})")

    item = ClipboardItem(
        content=content,
        content_type=content_type,
        timestamp=datetime.now(timezone.utc),
        char_count=len(content),
        word_count=len(content.split()),
    )

    db.add(item)
    db.commit()
    db.refresh(item)

    return {"id": str(item.id), "success": True}


@router.delete("/{item_id}")
async def delete_clipboard_item(
    item_id: int,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """
    Delete a clipboard item.

    This is a RED permission action requiring confirmation.
    """
    # Check permission
    permission = get_permission_level("delete_memory")
    if permission == PermissionLevel.RED:
        logger.warning(f"Delete clipboard item {item_id} requires confirmation")

    item = db.query(ClipboardItem).filter(ClipboardItem.id == item_id).first()
    if item is None:
        raise HTTPException(status_code=404, detail="Clipboard item not found")

    db.delete(item)
    db.commit()

    return {"id": str(item_id), "success": True}


@router.patch("/{item_id}/pin")
async def toggle_pin_clipboard_item(
    item_id: int,
    pinned: bool = True,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """
    Toggle pin status of a clipboard item.
    """
    item = db.query(ClipboardItem).filter(ClipboardItem.id == item_id).first()
    if item is None:
        raise HTTPException(status_code=404, detail="Clipboard item not found")

    item.is_pinned = pinned
    db.commit()

    return {"id": str(item_id), "is_pinned": pinned, "success": True}


@router.delete("")
async def clear_clipboard_history(
    keep_pinned: bool = True,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """
    Clear clipboard history.

    This is a RED permission action requiring confirmation.
    """
    permission = get_permission_level("clear_clipboard")
    logger.warning(f"Clear clipboard history requested (permission: {permission.name})")

    query = db.query(ClipboardItem)
    if keep_pinned:
        query = query.filter(ClipboardItem.is_pinned == False)  # noqa: E712

    count = query.delete()
    db.commit()

    return {"deleted": count, "success": True}
