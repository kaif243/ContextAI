"""Clipboard Intelligence API (Phase 3).

Exposes the ClipboardService through a clean HTTP surface.

  POST   /api/v1/clipboard/capture        Submit a new clipboard change.
  GET    /api/v1/clipboard                List history (paginated).
  GET    /api/v1/clipboard/{id}           Get one item.
  DELETE /api/v1/clipboard/{id}           Delete one item.
  PATCH  /api/v1/clipboard/{id}/pin       Pin / unpin an item.
  DELETE /api/v1/clipboard                Clear all history.
  POST   /api/v1/clipboard/{id}/reanalyse Re-run the content classifier.
  POST   /api/v1/clipboard/{id}/explain   LLM explain-the-content action.
  POST   /api/v1/clipboard/{id}/summarise LLM summarise-the-content action.
  POST   /api/v1/clipboard/purge          Drop every expired row.

Sensitive items are returned with ``content`` cleared; the safe preview
is exposed via ``redacted_content`` and ``preview``. Callers cannot
opt-in to raw secret material through the API.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.logging import get_logger
from app.models.clipboard import ClipboardItem
from app.services.clipboard_service import CaptureResult, ClipboardService

logger = get_logger(__name__)
router = APIRouter()


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------
class ClipboardCaptureRequest(BaseModel):
    """Request body for ``POST /api/v1/clipboard/capture``."""

    content: str = Field(min_length=0, max_length=5_000_000)
    source_app: str | None = Field(default=None, max_length=200)
    content_type: str | None = Field(default=None, max_length=50)
    metadata: dict[str, Any] | None = None


class ClipboardCaptureResponse(BaseModel):
    """Response for ``POST /api/v1/clipboard/capture``."""

    success: bool
    stored: bool
    reason: str
    is_sensitive: bool = False
    redacted_content: str = ""
    item: ClipboardItemResponse | None = None


class ClipboardItemResponse(BaseModel):
    id: str
    content: str
    redacted_content: str = ""
    content_type: str
    classification: str | None = None
    classification_confidence: float | None = None
    classifier_version: str | None = None
    is_sensitive: bool = False
    sensitive_reasons: list[str] = []
    source_app: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    timestamp: str | None = None
    expires_at: str | None = None
    is_pinned: bool = False
    is_encrypted: bool = False
    char_count: int = 0
    word_count: int = 0
    preview: str = ""


class ClipboardListResponse(BaseModel):
    items: list[ClipboardItemResponse]
    total: int
    limit: int
    offset: int


class PinRequest(BaseModel):
    pinned: bool = True


class ClipboardActionResponse(BaseModel):
    """Standard wrapper for action endpoints (delete / clear / pin)."""

    success: bool
    affected: int = 0
    detail: str | None = None


class LLMAnalysisResponse(BaseModel):
    """Standard shape for explain / summarise."""

    item_id: int
    action: str
    answer: str
    is_error: bool
    error_message: str | None = None
    model_used: str | None = None
    processing_ms: int | None = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _to_response(item: ClipboardItem) -> ClipboardItemResponse:
    return ClipboardItemResponse(**item.to_dict(include_raw_content=False))


def _capture_to_response(result: CaptureResult) -> ClipboardCaptureResponse:
    return ClipboardCaptureResponse(
        success=True,
        stored=result.stored,
        reason=result.reason,
        is_sensitive=result.is_sensitive,
        redacted_content=result.redacted_content,
        item=_to_response(result.item) if result.item is not None else None,
    )


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@router.post("/capture", response_model=ClipboardCaptureResponse)
async def capture_clipboard(
    request: ClipboardCaptureRequest,
    db: Session = Depends(get_db),
) -> ClipboardCaptureResponse:
    """Submit a clipboard change to be classified + stored.

    The service applies the sensitive-data policy and the storage
    configuration. The response is always a structured record — even
    when nothing was stored (e.g. sensitive content dropped, item too
    large, exact duplicate).
    """
    if not settings.clipboard_monitoring:
        return _capture_to_response(
            CaptureResult(stored=False, reason="monitoring_disabled", item=None)
        )
    if not settings.clipboard_history_enabled:
        return _capture_to_response(
            CaptureResult(stored=False, reason="history_disabled", item=None)
        )
    if not request.content:
        return _capture_to_response(
            CaptureResult(stored=False, reason="empty_content", item=None)
        )

    service = ClipboardService(db)
    result = service.capture(
        request.content,
        source_app=request.source_app,
        content_type=request.content_type,
        metadata=request.metadata,
    )
    return _capture_to_response(result)


@router.get("", response_model=ClipboardListResponse)
async def list_clipboard(
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    content_type: str | None = None,
    classification: str | None = None,
    include_sensitive: bool = True,
    db: Session = Depends(get_db),
) -> ClipboardListResponse:
    """List clipboard history (most recent first)."""
    service = ClipboardService(db)
    items, total = service.list_history(
        limit=limit,
        offset=offset,
        content_type=content_type,
        classification=classification,
        include_sensitive=include_sensitive,
    )
    return ClipboardListResponse(
        items=[_to_response(item) for item in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/{item_id}", response_model=ClipboardItemResponse)
async def get_clipboard_item(
    item_id: int,
    db: Session = Depends(get_db),
) -> ClipboardItemResponse:
    """Get a single clipboard item by id."""
    service = ClipboardService(db)
    item = service.get(item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Clipboard item not found")
    return _to_response(item)


@router.delete("/{item_id}", response_model=ClipboardActionResponse)
async def delete_clipboard_item(
    item_id: int,
    db: Session = Depends(get_db),
) -> ClipboardActionResponse:
    """Delete a single clipboard item."""
    service = ClipboardService(db)
    if service.delete(item_id):
        return ClipboardActionResponse(success=True, affected=1, detail="deleted")
    raise HTTPException(status_code=404, detail="Clipboard item not found")


@router.patch("/{item_id}/pin", response_model=ClipboardItemResponse)
async def toggle_pin(
    item_id: int,
    request: PinRequest,
    db: Session = Depends(get_db),
) -> ClipboardItemResponse:
    """Pin or unpin a clipboard item."""
    service = ClipboardService(db)
    item = service.toggle_pin(item_id, request.pinned)
    if item is None:
        raise HTTPException(status_code=404, detail="Clipboard item not found")
    return _to_response(item)


@router.delete("", response_model=ClipboardActionResponse)
async def clear_history(
    keep_pinned: bool = Query(default=True),
    db: Session = Depends(get_db),
) -> ClipboardActionResponse:
    """Clear clipboard history. Pinned items are preserved by default."""
    service = ClipboardService(db)
    count = service.clear_history(keep_pinned=keep_pinned)
    return ClipboardActionResponse(
        success=True,
        affected=count,
        detail="kept_pinned" if keep_pinned else "deleted_all",
    )


@router.post("/{item_id}/reanalyse", response_model=ClipboardItemResponse)
async def reanalyse_item(
    item_id: int,
    db: Session = Depends(get_db),
) -> ClipboardItemResponse:
    """Re-run the content classifier against the stored text."""
    service = ClipboardService(db)
    item = service.reclassify(item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Clipboard item not found")
    return _to_response(item)


@router.post("/purge", response_model=ClipboardActionResponse)
async def purge_expired(
    db: Session = Depends(get_db),
) -> ClipboardActionResponse:
    """Drop every expired (non-pinned) row."""
    service = ClipboardService(db)
    count = service.purge_expired()
    return ClipboardActionResponse(success=True, affected=count, detail="purge_expired")


# ---------------------------------------------------------------------------
# LLM actions (Explain / Summarise)
# ---------------------------------------------------------------------------
async def _llm_action(
    db: Session, item_id: int, action: str
) -> LLMAnalysisResponse:
    """Common pipeline for explain / summarise.

    The service refuses to send raw secret material to the LLM.
    Sensitive items are summarised / explained on the redacted preview
    only.
    """
    import time

    service = ClipboardService(db)
    item = service.get(item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Clipboard item not found")

    # Choose the safe text: raw for non-sensitive, redacted for sensitive.
    if item.is_sensitive:
        text = item.redacted_content or ""
    else:
        text = item.content or ""
    if not text.strip():
        raise HTTPException(
            status_code=400,
            detail="Clipboard item has no usable text for LLM analysis",
        )

    # Build the prompt. Reuse the existing LLM factory; do not introduce
    # a new LLM client.
    from app.llm import get_llm_provider, Message  # local import: avoids top-level cycle

    if action == "explain":
        system = "You are ContextAI. Explain what the user copied. Be concise (1-3 sentences)."
        user = (
            "The user just copied the following clipboard content. "
            "Explain what it is and why it might be useful. "
            "If it looks like a code snippet, summarise its purpose.\n\n"
            f"Content type: {item.content_type}\n"
            f"Sensitive: {item.is_sensitive}\n"
            f"Content:\n---\n{text}\n---"
        )
    else:  # "summarise"
        system = "You are ContextAI. Summarise the user's clipboard content in 1-3 sentences."
        user = (
            f"Summarise the following {item.content_type} content the user just copied. "
            "If it is a URL, name the destination. If it is code, name the language and intent. "
            "If it is plain text, give a one-line gist.\n\n"
            f"Content:\n---\n{text}\n---"
        )

    start = time.perf_counter()
    try:
        provider = get_llm_provider()
        response = await provider.chat(
            [
                Message(role="system", content=system),
                Message(role="user", content=user),
            ]
        )
    except Exception as e:  # noqa: BLE001
        logger.exception(f"Clipboard LLM {action} failed")
        return LLMAnalysisResponse(
            item_id=item_id,
            action=action,
            answer=f"Error: {e}",
            is_error=True,
            error_message=str(e),
            model_used=None,
            processing_ms=int((time.perf_counter() - start) * 1000),
        )

    return LLMAnalysisResponse(
        item_id=item_id,
        action=action,
        answer=response.content,
        is_error=False,
        error_message=None,
        model_used=response.model,
        processing_ms=int((time.perf_counter() - start) * 1000),
    )


@router.post("/{item_id}/explain", response_model=LLMAnalysisResponse)
async def explain_clipboard_item(
    item_id: int,
    db: Session = Depends(get_db),
) -> LLMAnalysisResponse:
    """Ask the configured LLM to explain the clipboard item.

    If the item is sensitive, the LLM sees the redacted preview only.
    """
    return await _llm_action(db, item_id, "explain")


@router.post("/{item_id}/summarise", response_model=LLMAnalysisResponse)
async def summarise_clipboard_item(
    item_id: int,
    db: Session = Depends(get_db),
) -> LLMAnalysisResponse:
    """Ask the configured LLM to summarise the clipboard item."""
    return await _llm_action(db, item_id, "summarise")
