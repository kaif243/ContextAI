"""Screen intelligence API (Phase 2).

Exposes the screen service through a clean HTTP surface:

  POST   /api/v1/screen/capture        Register a screenshot and run analysis.
  POST   /api/v1/screen/upload         Multipart upload of an image + analysis.
  GET    /api/v1/screen                List recent screenshots.
  GET    /api/v1/screen/{id}           Get one screenshot with full analysis.
  POST   /api/v1/screen/{id}/reanalyse Re-run OCR and classification.
  POST   /api/v1/screen/{id}/ask       Ask a free-form question (LLM Q&A).
  POST   /api/v1/screen/{id}/summarise Summarise the screen (LLM).
  PATCH  /api/v1/screen/{id}           Update notes / archived flag.
  DELETE /api/v1/screen/{id}           Delete a screenshot.
  GET    /api/v1/screen/{id}/analyses  List LLM analyses for the screenshot.
  GET    /api/v1/screen/ocr/info       Diagnose which OCR provider is active.
"""

from __future__ import annotations

import base64
import hashlib
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.classification import get_activity_classifier
from app.core.config import settings
from app.core.database import get_db
from app.core.logging import get_logger
from app.models.screenshot import ScreenAnalysis, Screenshot
from app.ocr import get_ocr_provider
from app.services.screen_service import ScreenService

logger = get_logger(__name__)
router = APIRouter()


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------
class ScreenRegion(BaseModel):
    x: int
    y: int
    width: int
    height: int


class ScreenCaptureRequest(BaseModel):
    image_base64: str | None = Field(
        default=None, description="PNG/JPEG bytes encoded as base64. Optional if image_path is provided."
    )
    image_path: str | None = Field(
        default=None, description="Absolute path to a pre-saved image. The Tauri layer writes here."
    )
    width: int = Field(ge=0, le=10000)
    height: int = Field(ge=0, le=10000)
    region: ScreenRegion | None = None
    monitor_index: int | None = None
    source_app: str | None = None
    window_title: str | None = None
    run_ocr: bool = True
    save_to_disk: bool = True
    file_name: str | None = None


class ScreenCaptureResponse(BaseModel):
    success: bool
    screenshot_id: int | None = None
    image_path: str
    width: int
    height: int
    file_size_bytes: int
    ocr_engine: str | None = None
    ocr_char_count: int = 0
    ocr_word_count: int = 0
    classification: str | None = None
    classification_confidence: float | None = None
    classifier_version: str | None = None
    extracted_entities: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None


class ScreenListResponse(BaseModel):
    items: list[dict[str, Any]]
    total: int
    limit: int
    offset: int


class ScreenUpdateRequest(BaseModel):
    notes: str | None = None
    is_archived: bool | None = None


class ScreenQuestionRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)


class ScreenAnalysisResponse(BaseModel):
    id: int
    screenshot_id: int
    analysis_type: str
    question: str | None = None
    answer: str
    model_used: str | None = None
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    processing_ms: int | None = None
    is_error: bool
    error_message: str | None = None
    created_at: str


class OCRInfoResponse(BaseModel):
    provider: str
    available: bool
    is_ml: bool
    note: str
    settings_provider: str


class ClassifierInfoResponse(BaseModel):
    name: str
    version: str
    is_ml: bool
    label_count: int
    note: str


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _decode_base64_image(data: str) -> bytes:
    if "," in data and data.lstrip().startswith("data:"):
        data = data.split(",", 1)[1]
    return base64.b64decode(data)


def _persist_upload(
    raw: bytes, file_name: str | None, save_to_disk: bool
) -> tuple[Path, bool]:
    """Write raw bytes to the screenshots directory and return the path.

    Returns the path and a flag indicating whether the file was newly
    written (True) or pre-existed on disk (False).
    """
    if not save_to_disk:
        # Caller wants the file to be ephemerally held in memory. We still
        # write to a temp file because the OCR pipeline expects a path.
        import tempfile

        tmp_dir = settings.temp_dir
        tmp_dir.mkdir(parents=True, exist_ok=True)
        suffix = os.path.splitext(file_name or "")[1] or ".png"
        path = Path(tempfile.mkstemp(suffix=suffix, dir=str(tmp_dir))[1])
        path.write_bytes(raw)
        return path, True

    settings.screenshots_dir.mkdir(parents=True, exist_ok=True)
    suffix = os.path.splitext(file_name or "")[1] or ".png"
    safe_suffix = suffix if suffix.startswith(".") else f".{suffix}"
    final_name = f"{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}{safe_suffix}"
    final_path = settings.screenshots_dir / final_name
    final_path.write_bytes(raw)
    return final_path, True


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@router.post("/capture", response_model=ScreenCaptureResponse)
async def capture_screen(
    request: ScreenCaptureRequest,
    db: Session = Depends(get_db),
) -> ScreenCaptureResponse:
    """Register a captured screenshot and run the analysis pipeline.

    The Tauri side performs the actual screen capture (native Windows
    API) and either sends the bytes inline (base64) or writes them to
    a known path and references them via ``image_path``.
    """
    try:
        # 1. Resolve the on-disk image path.
        if request.image_path:
            path = Path(request.image_path)
            if not path.exists():
                raise HTTPException(status_code=400, detail=f"image_path not found: {request.image_path}")
            raw = path.read_bytes()
            newly_written = False
        elif request.image_base64:
            raw = _decode_base64_image(request.image_base64)
            if not raw:
                raise HTTPException(status_code=400, detail="image_base64 is empty")
            path, newly_written = _persist_upload(raw, request.file_name, request.save_to_disk)
        else:
            raise HTTPException(status_code=400, detail="Either image_path or image_base64 is required")

        if len(raw) > settings.max_screenshot_bytes:
            # Clean up only if we wrote the file ourselves.
            if newly_written and path.exists():
                try:
                    path.unlink()
                except OSError:
                    pass
            raise HTTPException(
                status_code=413,
                detail=f"image exceeds max_screenshot_bytes={settings.max_screenshot_bytes}",
            )

        # 2. Persist and analyse via the service.
        service = ScreenService(db)
        screenshot = service.register_capture(
            image_path=str(path),
            width=request.width,
            height=request.height,
            region=request.region.model_dump() if request.region else None,
            monitor_index=request.monitor_index,
            source_app=request.source_app,
            window_title=request.window_title,
            run_ocr=request.run_ocr and settings.ocr_enabled,
        )

        return ScreenCaptureResponse(
            success=True,
            screenshot_id=screenshot.id,
            image_path=screenshot.file_path,
            width=screenshot.width,
            height=screenshot.height,
            file_size_bytes=screenshot.file_size_bytes,
            ocr_engine=screenshot.ocr_engine,
            ocr_char_count=screenshot.ocr_char_count,
            ocr_word_count=screenshot.ocr_word_count,
            classification=screenshot.classification,
            classification_confidence=screenshot.classification_confidence,
            classifier_version=screenshot.classifier_version,
            extracted_entities=screenshot.extracted_entities or {},
        )

    except HTTPException:
        raise
    except FileNotFoundError as e:
        logger.warning(f"Capture failed (file not found): {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except ValueError as e:
        logger.warning(f"Capture failed (bad request): {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:  # noqa: BLE001
        logger.exception("Screen capture failed")
        return ScreenCaptureResponse(
            success=False,
            image_path=request.image_path or "",
            width=request.width,
            height=request.height,
            file_size_bytes=0,
            error=str(e),
        )


@router.post("/upload", response_model=ScreenCaptureResponse)
async def upload_screenshot(
    file: UploadFile = File(...),
    width: int = Form(0),
    height: int = Form(0),
    source_app: str | None = Form(default=None),
    window_title: str | None = Form(default=None),
    run_ocr: bool = Form(default=True),
    db: Session = Depends(get_db),
) -> ScreenCaptureResponse:
    """Upload a screenshot file via multipart form data."""
    raw = await file.read()
    if not raw:
        raise HTTPException(status_code=400, detail="Empty upload")

    try:
        path, _ = _persist_upload(raw, file.filename or "upload.png", save_to_disk=True)
        service = ScreenService(db)
        screenshot = service.register_capture(
            image_path=str(path),
            width=width,
            height=height,
            source_app=source_app,
            window_title=window_title,
            run_ocr=run_ocr and settings.ocr_enabled,
        )
        return ScreenCaptureResponse(
            success=True,
            screenshot_id=screenshot.id,
            image_path=screenshot.file_path,
            width=screenshot.width,
            height=screenshot.height,
            file_size_bytes=screenshot.file_size_bytes,
            ocr_engine=screenshot.ocr_engine,
            ocr_char_count=screenshot.ocr_char_count,
            ocr_word_count=screenshot.ocr_word_count,
            classification=screenshot.classification,
            classification_confidence=screenshot.classification_confidence,
            classifier_version=screenshot.classifier_version,
            extracted_entities=screenshot.extracted_entities or {},
        )
    except HTTPException:
        raise
    except Exception as e:  # noqa: BLE001
        logger.exception("Screenshot upload failed")
        return ScreenCaptureResponse(
            success=False,
            image_path=file.filename or "",
            width=width,
            height=height,
            file_size_bytes=len(raw),
            error=str(e),
        )


@router.get("", response_model=ScreenListResponse)
async def list_screenshots(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    classification: str | None = None,
    include_archived: bool = False,
    db: Session = Depends(get_db),
) -> ScreenListResponse:
    """List recent screenshots with their analysis results."""
    service = ScreenService(db)
    items, total = service.list_recent(
        limit=limit, offset=offset, classification=classification, include_archived=include_archived
    )
    return ScreenListResponse(
        items=[item.to_dict() for item in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/ocr/info", response_model=OCRInfoResponse)
async def ocr_info() -> OCRInfoResponse:
    """Diagnostic information about the active OCR provider."""
    provider = get_ocr_provider()
    info = provider.get_info()
    note_map = {
        "mock": (
            "Mock OCR is active. It returns sidecar .txt/.ocr.json files next to the image, "
            "or a deterministic stub. Suitable for development and tests only."
        ),
        "tesseract": (
            "Tesseract OCR is active (pytesseract + Tesseract binary). Production-ready on Windows."
        ),
        "paddle": (
            "PaddleOCR placeholder is active. It is NOT implemented in Phase 2 — see docs/phase2-ocr.md."
        ),
    }
    return OCRInfoResponse(
        provider=info["name"],
        available=info["available"],
        is_ml=False,
        note=note_map.get(info["name"], "Unknown OCR provider."),
        settings_provider=settings.ocr_provider,
    )


@router.get("/classifier/info", response_model=ClassifierInfoResponse)
async def classifier_info() -> ClassifierInfoResponse:
    """Diagnostic information about the active activity classifier."""
    from app.classification.base import CLASSIFICATION_LABELS

    classifier = get_activity_classifier()
    info = classifier.get_info()
    return ClassifierInfoResponse(
        name=info["name"],
        version=info["version"],
        is_ml=info["is_ml"],
        label_count=len(CLASSIFICATION_LABELS),
        note=(
            "This is a deterministic, rule-based baseline classifier. "
            "It is NOT a machine-learning model. Replace via the "
            "ActivityClassifier interface when a real model is available."
        ),
    )


@router.get("/{screenshot_id}")
async def get_screenshot(
    screenshot_id: int,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Fetch a single screenshot with its full analysis."""
    service = ScreenService(db)
    screenshot = service.get(screenshot_id)
    if screenshot is None:
        raise HTTPException(status_code=404, detail="Screenshot not found")
    return screenshot.to_dict()


@router.post("/{screenshot_id}/reanalyse", response_model=ScreenCaptureResponse)
async def reanalyse_screenshot(
    screenshot_id: int,
    db: Session = Depends(get_db),
) -> ScreenCaptureResponse:
    """Re-run OCR + classification for an existing screenshot."""
    service = ScreenService(db)
    try:
        screenshot = service.re_analyse(screenshot_id)
    except LookupError:
        raise HTTPException(status_code=404, detail="Screenshot not found")
    except FileNotFoundError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return ScreenCaptureResponse(
        success=True,
        screenshot_id=screenshot.id,
        image_path=screenshot.file_path,
        width=screenshot.width,
        height=screenshot.height,
        file_size_bytes=screenshot.file_size_bytes,
        ocr_engine=screenshot.ocr_engine,
        ocr_char_count=screenshot.ocr_char_count,
        ocr_word_count=screenshot.ocr_word_count,
        classification=screenshot.classification,
        classification_confidence=screenshot.classification_confidence,
        classifier_version=screenshot.classifier_version,
        extracted_entities=screenshot.extracted_entities or {},
    )


@router.post("/{screenshot_id}/ask", response_model=ScreenAnalysisResponse)
async def ask_screenshot(
    screenshot_id: int,
    request: ScreenQuestionRequest,
    db: Session = Depends(get_db),
) -> ScreenAnalysisResponse:
    """Ask a free-form question about the screenshot (LLM Q&A)."""
    service = ScreenService(db)
    try:
        analysis = await service.ask_question(screenshot_id, request.question)
    except LookupError:
        raise HTTPException(status_code=404, detail="Screenshot not found")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return ScreenAnalysisResponse(**_analysis_to_dict(analysis))


@router.post("/{screenshot_id}/summarise", response_model=ScreenAnalysisResponse)
async def summarise_screenshot(
    screenshot_id: int,
    db: Session = Depends(get_db),
) -> ScreenAnalysisResponse:
    """Run the LLM summarisation flow on a screenshot."""
    service = ScreenService(db)
    try:
        analysis = await service.summarise(screenshot_id)
    except LookupError:
        raise HTTPException(status_code=404, detail="Screenshot not found")
    return ScreenAnalysisResponse(**_analysis_to_dict(analysis))


@router.get("/{screenshot_id}/analyses", response_model=list[ScreenAnalysisResponse])
async def list_analyses(
    screenshot_id: int,
    db: Session = Depends(get_db),
) -> list[ScreenAnalysisResponse]:
    """List all LLM analyses for a screenshot."""
    service = ScreenService(db)
    if service.get(screenshot_id) is None:
        raise HTTPException(status_code=404, detail="Screenshot not found")
    analyses = service.list_analyses(screenshot_id)
    return [ScreenAnalysisResponse(**_analysis_to_dict(a)) for a in analyses]


@router.patch("/{screenshot_id}")
async def update_screenshot(
    screenshot_id: int,
    request: ScreenUpdateRequest,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Update notes or archived flag for a screenshot."""
    service = ScreenService(db)
    if request.notes is not None:
        screenshot = service.set_notes(screenshot_id, request.notes)
        if screenshot is None:
            raise HTTPException(status_code=404, detail="Screenshot not found")
    if request.is_archived is not None:
        screenshot = service.set_archived(screenshot_id, request.is_archived)
        if screenshot is None:
            raise HTTPException(status_code=404, detail="Screenshot not found")
    screenshot = service.get(screenshot_id)
    if screenshot is None:
        raise HTTPException(status_code=404, detail="Screenshot not found")
    return screenshot.to_dict()


@router.delete("/{screenshot_id}")
async def delete_screenshot(
    screenshot_id: int,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Delete a screenshot (and its analyses via cascade)."""
    service = ScreenService(db)
    deleted = service.delete(screenshot_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Screenshot not found")
    return {"id": str(screenshot_id), "success": True}


def _analysis_to_dict(analysis: ScreenAnalysis) -> dict[str, Any]:
    return {
        "id": analysis.id,
        "screenshot_id": analysis.screenshot_id,
        "analysis_type": analysis.analysis_type,
        "question": analysis.question,
        "answer": analysis.answer,
        "model_used": analysis.model_used,
        "prompt_tokens": analysis.prompt_tokens,
        "completion_tokens": analysis.completion_tokens,
        "total_tokens": analysis.total_tokens,
        "processing_ms": analysis.processing_ms,
        "is_error": analysis.is_error,
        "error_message": analysis.error_message,
        "created_at": analysis.created_at.isoformat() if analysis.created_at else "",
    }
