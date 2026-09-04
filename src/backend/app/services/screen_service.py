"""Screen intelligence service (Phase 2).

Owns the end-to-end pipeline for a screenshot:

  capture metadata -> persist image -> OCR -> baseline classification ->
  entity extraction -> persist analysis -> (optional) LLM Q&A

The pipeline is intentionally split so each stage can be replaced or
swapped in isolation. The OCR stage depends on ``app.ocr`` (clean
provider interface with a mock for local dev), the classification stage
depends on ``app.classification`` (rule-based baseline, replaceable
with a real ML model later), and the LLM stage depends on the
existing ``app.llm`` factory.
"""

from __future__ import annotations

import hashlib
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.classification.base import ActivityClassifier, ClassificationInput
from app.core.config import settings
from app.core.logging import get_logger
from app.models.screenshot import ScreenAnalysis, Screenshot
from app.ocr.base import OCRProvider, OCRResult
from app.services.entity_extractor import extract_entities

logger = get_logger(__name__)


# Maximum length of OCR text sent to the LLM. Larger OCR passes are
# truncated; the truncation is reported back to the caller so the UI
# can show "text was truncated".
_LLM_OCR_CONTEXT_CHARS = 8000


class ScreenService:
    """High-level screen intelligence orchestration.

    The service is constructed per-request (it owns a database session)
    and is intentionally stateless beyond its collaborators (classifier,
    OCR provider) — the collaborators are themselves singletons via
    their factories.
    """

    def __init__(
        self,
        db: Session,
        *,
        ocr_provider: Optional[OCRProvider] = None,
        classifier: Optional[ActivityClassifier] = None,
    ) -> None:
        # Lazy imports to avoid a circular dependency on app factory.
        from app.classification import get_activity_classifier
        from app.ocr import get_ocr_provider

        self.db = db
        self.ocr = ocr_provider or get_ocr_provider()
        self.classifier = classifier or get_activity_classifier()

    # ------------------------------------------------------------------
    # Capture & persistence
    # ------------------------------------------------------------------
    def register_capture(
        self,
        *,
        image_path: str,
        width: int,
        height: int,
        region: Optional[dict[str, int]] = None,
        monitor_index: Optional[int] = None,
        source_app: Optional[str] = None,
        window_title: Optional[str] = None,
        run_ocr: bool = True,
    ) -> Screenshot:
        """Persist a new screenshot and run OCR + classification on it.

        Args:
            image_path: Absolute path to the saved image file. The file
                must already exist on disk; the service reads it for OCR
                and computes its hash and size.
            width: Pixel width of the capture.
            height: Pixel height of the capture.
            region: Optional dict with x/y/width/height describing the
                captured region (None for full-screen captures).
            monitor_index: Optional 0-based monitor index.
            source_app: Optional source-app identifier.
            window_title: Optional window title.
            run_ocr: If ``True`` (default), run OCR and classification
                inline. Set to ``False`` when the caller wants to defer
                analysis (e.g. bulk imports).

        Returns:
            The persisted ``Screenshot`` instance, refreshed from the DB.
        """
        path = Path(image_path)
        if not path.exists():
            raise FileNotFoundError(f"Screenshot file not found: {image_path}")
        if path.stat().st_size > settings.max_screenshot_bytes:
            raise ValueError(
                f"Screenshot is {path.stat().st_size} bytes, "
                f"exceeding max_screenshot_bytes={settings.max_screenshot_bytes}"
            )

        with path.open("rb") as f:
            data = f.read()
        content_hash = hashlib.sha256(data).hexdigest()
        file_size = len(data)

        screenshot = Screenshot(
            file_path=str(path),
            file_name=path.name,
            width=width,
            height=height,
            file_size_bytes=file_size,
            content_hash=content_hash,
            region_x=region.get("x") if region else None,
            region_y=region.get("y") if region else None,
            region_width=region.get("width") if region else None,
            region_height=region.get("height") if region else None,
            monitor_index=monitor_index,
            source_app=source_app,
            window_title=window_title,
            is_saved=True,
        )
        self.db.add(screenshot)
        self.db.flush()  # populate screenshot.id

        if run_ocr and settings.ocr_enabled:
            self._run_ocr_and_classify(screenshot, path)

        self.db.commit()
        self.db.refresh(screenshot)
        logger.info(f"Screenshot registered: id={screenshot.id} file={path.name}")
        return screenshot

    # ------------------------------------------------------------------
    # OCR + classification
    # ------------------------------------------------------------------
    def _run_ocr_and_classify(self, screenshot: Screenshot, path: Path) -> OCRResult:
        """Run OCR, classification, and entity extraction for a screenshot."""
        ocr_result = self.ocr.recognize(path)
        screenshot.ocr_text = ocr_result.text
        screenshot.ocr_engine = ocr_result.engine
        screenshot.ocr_confidence = ocr_result.confidence
        screenshot.ocr_word_count = ocr_result.word_count
        screenshot.ocr_char_count = ocr_result.char_count
        screenshot.ocr_processing_ms = ocr_result.processing_ms

        clf_input = ClassificationInput(
            ocr_text=ocr_result.text,
            ocr_engine=ocr_result.engine,
            image_width=screenshot.width,
            image_height=screenshot.height,
            source_app=screenshot.source_app,
            window_title=screenshot.window_title,
        )
        clf_result = self.classifier.classify(clf_input)
        screenshot.classification = clf_result.label
        screenshot.classification_confidence = clf_result.confidence
        screenshot.classification_signals = clf_result.signals
        screenshot.classifier_version = clf_result.version

        entities = extract_entities(ocr_result.text)
        screenshot.extracted_entities = entities.to_dict()

        logger.info(
            f"Screenshot {screenshot.id}: ocr_chars={ocr_result.char_count} "
            f"class={clf_result.label} confidence={clf_result.confidence}"
        )
        return ocr_result

    def re_analyse(self, screenshot_id: int) -> Screenshot:
        """Re-run OCR and classification for an existing screenshot."""
        screenshot = self.db.get(Screenshot, screenshot_id)
        if screenshot is None:
            raise LookupError(f"Screenshot {screenshot_id} not found")
        path = Path(screenshot.file_path)
        if not path.exists():
            raise FileNotFoundError(
                f"Screenshot file is missing on disk: {screenshot.file_path}"
            )
        self._run_ocr_and_classify(screenshot, path)
        self.db.commit()
        self.db.refresh(screenshot)
        return screenshot

    # ------------------------------------------------------------------
    # Reads
    # ------------------------------------------------------------------
    def get(self, screenshot_id: int) -> Optional[Screenshot]:
        return self.db.get(Screenshot, screenshot_id)

    def list_recent(
        self,
        limit: int = 50,
        offset: int = 0,
        classification: Optional[str] = None,
        include_archived: bool = False,
    ) -> tuple[list[Screenshot], int]:
        query = self.db.query(Screenshot)
        if not include_archived:
            query = query.filter(Screenshot.is_archived == False)  # noqa: E712
        if classification:
            query = query.filter(Screenshot.classification == classification)
        query = query.order_by(Screenshot.created_at.desc())
        total = query.count()
        items = query.offset(offset).limit(limit).all()
        return items, total

    def delete(self, screenshot_id: int) -> bool:
        screenshot = self.db.get(Screenshot, screenshot_id)
        if screenshot is None:
            return False
        self.db.delete(screenshot)
        self.db.commit()
        return True

    def set_archived(self, screenshot_id: int, archived: bool) -> Optional[Screenshot]:
        screenshot = self.db.get(Screenshot, screenshot_id)
        if screenshot is None:
            return None
        screenshot.is_archived = archived
        self.db.commit()
        self.db.refresh(screenshot)
        return screenshot

    def set_notes(self, screenshot_id: int, notes: str) -> Optional[Screenshot]:
        screenshot = self.db.get(Screenshot, screenshot_id)
        if screenshot is None:
            return None
        screenshot.user_notes = notes
        self.db.commit()
        self.db.refresh(screenshot)
        return screenshot

    # ------------------------------------------------------------------
    # LLM-driven Q&A
    # ------------------------------------------------------------------
    async def ask_question(self, screenshot_id: int, question: str) -> ScreenAnalysis:
        """Ask a free-form question about a screenshot.

        The OCR text, classification, and extracted entities are sent to
        the configured LLM provider as context. The full transcript is
        persisted as a ``ScreenAnalysis`` row.
        """
        screenshot = self.db.get(Screenshot, screenshot_id)
        if screenshot is None:
            raise LookupError(f"Screenshot {screenshot_id} not found")

        question = (question or "").strip()
        if not question:
            raise ValueError("Question must not be empty")

        analysis = ScreenAnalysis(
            screenshot_id=screenshot.id,
            analysis_type="qa",
            question=question,
            answer="",
            is_error=False,
        )
        self.db.add(analysis)
        self.db.flush()

        start = time.perf_counter()
        try:
            answer, model_used, prompt_tokens, completion_tokens = await self._ask_llm(
                screenshot, question
            )
        except Exception as e:  # noqa: BLE001
            logger.exception("LLM Q&A failed")
            analysis.is_error = True
            analysis.error_message = str(e)
            analysis.answer = f"Error: {e}"
            analysis.processing_ms = int((time.perf_counter() - start) * 1000)
            self.db.commit()
            self.db.refresh(analysis)
            return analysis

        analysis.answer = answer
        analysis.model_used = model_used
        analysis.prompt_tokens = prompt_tokens
        analysis.completion_tokens = completion_tokens
        analysis.total_tokens = prompt_tokens + completion_tokens
        analysis.processing_ms = int((time.perf_counter() - start) * 1000)
        self.db.commit()
        self.db.refresh(analysis)
        return analysis

    async def summarise(self, screenshot_id: int) -> ScreenAnalysis:
        """Run a generic "summarise the screen" LLM call.

        Same plumbing as ``ask_question`` but uses the canonical
        summarise prompt. Persisted as ``analysis_type='summary'``.
        """
        screenshot = self.db.get(Screenshot, screenshot_id)
        if screenshot is None:
            raise LookupError(f"Screenshot {screenshot_id} not found")

        analysis = ScreenAnalysis(
            screenshot_id=screenshot.id,
            analysis_type="summary",
            question=None,
            answer="",
        )
        self.db.add(analysis)
        self.db.flush()

        start = time.perf_counter()
        try:
            answer, model_used, prompt_tokens, completion_tokens = await self._summarise_llm(screenshot)
        except Exception as e:  # noqa: BLE001
            logger.exception("LLM summarise failed")
            analysis.is_error = True
            analysis.error_message = str(e)
            analysis.answer = f"Error: {e}"
            analysis.processing_ms = int((time.perf_counter() - start) * 1000)
            self.db.commit()
            self.db.refresh(analysis)
            return analysis

        analysis.answer = answer
        analysis.model_used = model_used
        analysis.prompt_tokens = prompt_tokens
        analysis.completion_tokens = completion_tokens
        analysis.total_tokens = prompt_tokens + completion_tokens
        analysis.processing_ms = int((time.perf_counter() - start) * 1000)
        self.db.commit()
        self.db.refresh(analysis)
        return analysis

    async def _ask_llm(
        self, screenshot: Screenshot, question: str
    ) -> tuple[str, Optional[str], int, int]:
        from app.llm import Message  # local import: avoids top-level cycle

        context = self._build_context(screenshot)
        prompt = (
            "You are ContextAI, a desktop intelligence assistant. The user has "
            "captured a screenshot of their screen. You are given the OCR-extracted "
            "text, a heuristic activity label (NOT a machine-learning prediction), "
            "and a few simple regex-extracted entities. Use them to answer the "
            "user's question accurately. If the OCR text is empty or insufficient, "
            "say so honestly.\n\n"
            f"Activity label (heuristic): {screenshot.classification or 'unknown'}\n"
            f"Source app: {screenshot.source_app or 'unknown'}\n"
            f"Window title: {screenshot.window_title or 'unknown'}\n"
            f"Extracted entities (regex): {screenshot.extracted_entities or {}}\n\n"
            f"OCR text (truncated to {_LLM_OCR_CONTEXT_CHARS} chars):\n"
            f"---\n{context}\n---\n\n"
            f"User question: {question}"
        )
        response = await self._dispatch_chat(
            [
                Message(role="system", content="You answer questions about screen contents."),
                Message(role="user", content=prompt),
            ]
        )
        return response.content, response.model, response.prompt_tokens, response.completion_tokens

    async def _summarise_llm(self, screenshot: Screenshot) -> tuple[str, Optional[str], int, int]:
        from app.llm import Message

        context = self._build_context(screenshot)
        prompt = (
            "You are ContextAI. Summarise the screen content captured in the OCR "
            "text below. Be concise (3-6 sentences) and call out dates, names, "
            "amounts, or other notable entities when present. If the OCR text is "
            "empty, say so honestly.\n\n"
            f"Activity label (heuristic): {screenshot.classification or 'unknown'}\n"
            f"OCR text (truncated to {_LLM_OCR_CONTEXT_CHARS} chars):\n"
            f"---\n{context}\n---\n"
        )
        response = await self._dispatch_chat(
            [
                Message(role="system", content="You summarise screen content concisely."),
                Message(role="user", content=prompt),
            ]
        )
        return response.content, response.model, response.prompt_tokens, response.completion_tokens

    @staticmethod
    async def _dispatch_chat(messages: list[Any]) -> Any:
        """Call the configured LLM provider through the existing factory."""
        from app.llm import get_llm_provider

        provider = get_llm_provider()
        return await provider.chat(messages)

    @staticmethod
    def _build_context(screenshot: Screenshot) -> str:
        text = (screenshot.ocr_text or "").strip()
        if len(text) > _LLM_OCR_CONTEXT_CHARS:
            return text[:_LLM_OCR_CONTEXT_CHARS] + "\n[truncated]"
        return text or "(no OCR text available)"

    # ------------------------------------------------------------------
    # List analyses
    # ------------------------------------------------------------------
    def list_analyses(self, screenshot_id: int) -> list[ScreenAnalysis]:
        return (
            self.db.query(ScreenAnalysis)
            .filter(ScreenAnalysis.screenshot_id == screenshot_id)
            .order_by(ScreenAnalysis.created_at.asc())
            .all()
        )
