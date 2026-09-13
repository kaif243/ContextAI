"""File Intelligence service (Phase 4).

Owns the end-to-end pipeline for indexing a user-selected file:

    raw path
        ↓
    validate (size, extension, allowed root, NUL-byte check)
        ↓
    stat + content hash
        ↓
    detect file type (extension + MIME)
        ↓
    run the appropriate extractor
        ↓
    classify (rule-based)
        ↓
    build metadata blob
        ↓
    upsert FileIndex row
        ↓
    return IndexResult

The service also handles reads (list, get, search), mutations
(reindex, delete, clear), and the LLM-driven actions
(explain, summarise, ask) — those last three are implemented as
thin wrappers that call into the existing
:func:`app.llm.get_llm_provider`.

The service is **stateless beyond its DB session and
collaborators**. Collaborators (the extractor factory) are
singletons via their own factory.
"""

from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Optional

from sqlalchemy import or_, and_
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.logging import get_logger
from app.file_intelligence.base import (
    ExtractionResult,
    FileExtractionStatus,
    get_file_extractor_factory,
)
from app.file_intelligence.classifier import classify_file
from app.file_intelligence.metadata import build_metadata
from app.file_intelligence.types import (
    FILE_TYPE_UNSUPPORTED,
    detect_file_type,
    supported_extensions,
)
from app.file_intelligence.validation import (
    FileStatInfo,
    FileValidationError,
    collect_stat_info,
    hash_file,
    merge_allowed_extensions,
    parse_allowed_extensions,
    path_has_null_byte,
    validate_file_path,
)
from app.models.file_index import FileIndex

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------
@dataclass
class IndexResult:
    """Outcome of a single ``index_file`` call.

    Always safe to serialise. ``file_row`` is the persisted
    :class:`FileIndex` (or the existing row if the file was
    already indexed and unchanged).
    """

    stored: bool
    reason: str
    file_row: Optional[FileIndex] = None
    changed: bool = False
    reused: bool = False
    raw_path: str = ""

    def to_dict(self) -> dict[str, Any]:
        row = self.file_row
        return {
            "stored": self.stored,
            "reason": self.reason,
            "changed": self.changed,
            "reused": self.reused,
            "file": row.to_dict() if row else None,
            "raw_path": self.raw_path,
        }


@dataclass
class SearchHit:
    """A single search hit."""

    file: FileIndex
    score: float
    match_type: str
    snippet: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "file": self.file.to_dict(),
            "score": self.score,
            "match_type": self.match_type,
            "snippet": self.snippet,
        }


@dataclass
class SearchResult:
    """Outcome of a ``search`` call."""

    hits: list[SearchHit] = field(default_factory=list)
    total: int = 0
    query_time_ms: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "results": [h.to_dict() for h in self.hits],
            "total": self.total,
            "query_time_ms": self.query_time_ms,
        }


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------
class FileService:
    """High-level file intelligence orchestration.

    The service is constructed per-request (it owns a database
    session) and is intentionally stateless beyond its
    collaborators. The extractor factory is a singleton via
    :func:`get_file_extractor_factory`.
    """

    #: Maximum text length sent to the LLM for
    #: summarise / explain. Larger texts are truncated by the
    #: service before the call.
    LLM_TEXT_LIMIT = 8_000

    def __init__(self, db: Session) -> None:
        from app.core.config import settings as _s
        self.db = db
        self._factory = get_file_extractor_factory()
        # Capture settings at construction time to avoid race with test patches.
        self._file_intelligence_enabled = bool(getattr(_s, "file_intelligence_enabled", False))
        self._max_bytes = max(0, int(getattr(_s, "file_max_bytes", 25 * 1024 * 1024)))
        self._allowed_extensions_config = getattr(_s, "file_allowed_extensions", None)
        self._allowed_roots_config = getattr(_s, "file_allowed_roots", None)
        self._max_text_chars = max(0, int(getattr(_s, "file_max_text_chars", 200_000)))
        self._llm_text_limit = max(0, int(getattr(_s, "file_llm_text_chars", 8_000)))
        self._retention_days = max(0, int(getattr(_s, "file_retention_days", 0)))

    # ------------------------------------------------------------------
    # Configuration helpers
    # ------------------------------------------------------------------
    @property
    def max_bytes(self) -> int:
        return self._max_bytes

    @property
    def allowed_extensions(self) -> set[str]:
        return merge_allowed_extensions(
            self._allowed_extensions_config,
            supported_extensions(),
        )

    @property
    def allowed_roots(self) -> list[str]:
        """Return the configured allowed roots, defaulting to empty list."""
        roots = self._allowed_roots_config
        if not roots:
            return []
        return list(roots) if isinstance(roots, list) else [roots]

    @property
    def max_text_chars(self) -> int:
        return self._max_text_chars

    @property
    def llm_text_limit(self) -> int:
        return self._llm_text_limit

    @property
    def file_intelligence_enabled(self) -> bool:
        return self._file_intelligence_enabled

    @property
    def retention_days(self) -> int:
        return self._retention_days

    # ------------------------------------------------------------------
    # Validation helper
    # ------------------------------------------------------------------
    def validate_user_path(self, raw_path: str | Path) -> Path:
        """Validate a user-supplied file path.

        Raises :class:`FileValidationError` on failure.
        """
        if isinstance(raw_path, str) and path_has_null_byte(raw_path):
            raise FileValidationError("invalid_path", "Path contains NUL byte")
        return validate_file_path(
            raw_path,
            max_bytes=self.max_bytes,
            allowed_extensions=self.allowed_extensions,
            allowed_roots=self.allowed_roots,
            must_exist=True,
        )

    # ------------------------------------------------------------------
    # Indexing
    # ------------------------------------------------------------------
    def index_file(
        self,
        raw_path: str | Path,
        *,
        force: bool = False,
    ) -> IndexResult:
        """Index (or re-index) a single file.

        The pipeline:

          1. Validate the user-supplied path.
          2. Collect filesystem metadata + content hash.
          3. Detect the file type.
          4. Run the appropriate extractor.
          5. Classify (rule-based).
          6. Build the metadata blob.
          7. Upsert the ``FileIndex`` row.
          8. Return a structured :class:`IndexResult`.

        Args:
            raw_path: Absolute path to the file. Must be one the
                user explicitly selected (e.g. via the Tauri
                file picker).
            force: If ``True``, re-extract even if the file's
                content hash hasn't changed since the last
                indexing run. Useful for ``POST /files/{id}/reindex``.

        Errors are converted to ``IndexResult(stored=False, reason=...)``
        rather than raised so the API can return them as
        structured responses.
        """
        if not self.file_intelligence_enabled:
            return IndexResult(stored=False, reason="file_intelligence_disabled", raw_path=str(raw_path))

        try:
            resolved = self.validate_user_path(raw_path)
        except FileValidationError as e:
            return IndexResult(
                stored=False,
                reason=e.code,
                raw_path=str(raw_path),
            )
        except Exception as e:  # noqa: BLE001
            logger.exception("index_file: unexpected validation failure")
            return IndexResult(stored=False, reason="validation_error", raw_path=str(raw_path))

        stat = collect_stat_info(resolved)
        try:
            content_hash = hash_file(resolved, max_bytes=self.max_bytes)
        except FileValidationError as e:
            return IndexResult(stored=False, reason=e.code, raw_path=str(resolved))
        type_info = detect_file_type(extension=stat.extension, mime_type="")

        existing = (
            self.db.query(FileIndex)
            .filter(FileIndex.path == str(resolved))
            .one_or_none()
        )

        if (
            existing is not None
            and not force
            and existing.content_hash == content_hash
            and existing.is_deleted is False
        ):
            existing.last_checked = datetime.now(timezone.utc)
            self.db.commit()
            self.db.refresh(existing)
            return IndexResult(
                stored=True,
                reason="unchanged",
                file_row=existing,
                changed=False,
                reused=True,
                raw_path=str(resolved),
            )

        # Extract content. The extractor itself never raises.
        extractor = self._factory.get(type_info.file_type)
        result = extractor.extract(resolved, max_chars=self.max_text_chars)
        classification = classify_file(
            filename=stat.filename,
            type_info=type_info,
            content_preview=(result.text or "")[:2048],
        )
        meta_blob = build_metadata(
            stat=stat,
            type_info=type_info,
            classification=classification,
            extractor_metadata=result.metadata,
        )

        # Map extractor status → row extraction_status.
        row_status = self._map_status(result.status, type_info.is_supported)

        # Build the upsert payload.
        payload = self._build_row_payload(
            resolved=resolved,
            stat=stat,
            type_info=type_info,
            result=result,
            classification=classification,
            meta_blob=meta_blob,
            content_hash=content_hash,
            row_status=row_status,
        )
        if existing is None:
            row = FileIndex(**payload)
            self.db.add(row)
        else:
            for key, value in payload.items():
                setattr(existing, key, value)
            existing.is_indexed = True
            existing.is_deleted = False
            existing.indexed_at = datetime.now(timezone.utc)
            existing.last_checked = datetime.now(timezone.utc)
            existing.extraction_attempts = (existing.extraction_attempts or 0) + 1
            row = existing

        try:
            self.db.commit()
            self.db.refresh(row)
        except Exception as e:  # noqa: BLE001
            logger.exception("index_file: DB commit failed")
            self.db.rollback()
            return IndexResult(
                stored=False,
                reason="db_error",
                raw_path=str(resolved),
            )

        return IndexResult(
            stored=True,
            reason="indexed" if result.ok else row_status,
            file_row=row,
            changed=True,
            reused=False,
            raw_path=str(resolved),
        )

    @staticmethod
    def _map_status(
        result_status: FileExtractionStatus, is_supported: bool
    ) -> str:
        if result_status == FileExtractionStatus.UNSUPPORTED or not is_supported:
            return "unsupported"
        if result_status == FileExtractionStatus.FAILED:
            return "failed"
        if result_status == FileExtractionStatus.EMPTY:
            return "empty"
        # OK or SKIPPED both result in a stored, indexed row.
        return "ok"

    @staticmethod
    def _build_row_payload(
        *,
        resolved: Path,
        stat: FileStatInfo,
        type_info,
        result: ExtractionResult,
        classification,
        meta_blob: dict[str, Any],
        content_hash: str,
        row_status: str,
    ) -> dict[str, Any]:
        now = datetime.now(timezone.utc)
        return {
            "path": str(resolved),
            "name": stat.filename,
            "file_type": type_info.file_type or FILE_TYPE_UNSUPPORTED,
            "extension": stat.extension or None,
            "size_bytes": stat.size_bytes,
            "created_at_fs": stat.created_at,
            "modified_at": stat.modified_at,
            "accessed_at": stat.accessed_at,
            "classification": classification.label,
            "classification_confidence": classification.confidence,
            "classifier_version": classification.version,
            "content_hash": content_hash,
            "text_content": result.text or None,
            "extracted_text": result.text or None,
            "text_truncated": "text_truncated" in (result.warnings or []),
            "metadata_json": meta_blob,
            "tags": "",
            "extraction_status": row_status,
            "extraction_error": result.error,
            "extraction_attempts": 1,
            "indexed_at": now,
            "is_indexed": True,
            "is_deleted": False,
            "last_checked": now,
        }

    # ------------------------------------------------------------------
    # Reads
    # ------------------------------------------------------------------
    def get(self, file_id: int) -> Optional[FileIndex]:
        return self.db.get(FileIndex, file_id)

    def list_files(
        self,
        *,
        classification: Optional[str] = None,
        file_type: Optional[str] = None,
        extension: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
        include_deleted: bool = False,
    ) -> tuple[list[FileIndex], int]:
        query = self.db.query(FileIndex)
        if not include_deleted:
            query = query.filter(FileIndex.is_deleted == False)  # noqa: E712
        if classification:
            query = query.filter(FileIndex.classification == classification)
        if file_type:
            query = query.filter(FileIndex.file_type == file_type)
        if extension:
            ext = extension.lstrip(".").lower()
            query = query.filter(FileIndex.extension == ext)
        query = query.order_by(FileIndex.indexed_at.desc(), FileIndex.id.desc())
        total = query.count()
        items = query.offset(offset).limit(limit).all()
        return items, total

    def get_by_path(self, path: str) -> Optional[FileIndex]:
        return (
            self.db.query(FileIndex)
            .filter(FileIndex.path == str(path))
            .one_or_none()
        )

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------
    def search(
        self,
        query: str = "",
        *,
        classification: Optional[str] = None,
        file_type: Optional[str] = None,
        extension: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 20,
    ) -> SearchResult:
        start = time.perf_counter()
        q = self.db.query(FileIndex).filter(FileIndex.is_deleted == False)  # noqa: E712
        if classification:
            q = q.filter(FileIndex.classification == classification)
        if file_type:
            q = q.filter(FileIndex.file_type == file_type)
        if extension:
            ext = extension.lstrip(".").lower()
            q = q.filter(FileIndex.extension == ext)
        if status:
            q = q.filter(FileIndex.extraction_status == status)

        if query:
            needle = f"%{query}%"
            q = q.filter(
                or_(
                    FileIndex.name.ilike(needle),
                    FileIndex.path.ilike(needle),
                    FileIndex.classification.ilike(needle),
                    FileIndex.file_type.ilike(needle),
                    FileIndex.extracted_text.ilike(needle),
                    FileIndex.tags.ilike(needle),
                )
            )

        rows = q.order_by(FileIndex.indexed_at.desc(), FileIndex.id.desc()).limit(limit).all()
        hits: list[SearchHit] = []
        for row in rows:
            snippet = self._snippet_for(row, query)
            match_type = self._match_type_for(row, query)
            hits.append(SearchHit(file=row, score=0.8, match_type=match_type, snippet=snippet))
        elapsed = int((time.perf_counter() - start) * 1000)
        return SearchResult(hits=hits, total=len(hits), query_time_ms=elapsed)

    @staticmethod
    def _match_type_for(row: FileIndex, query: str) -> str:
        if not query:
            return "list"
        q = query.lower()
        if q in (row.name or "").lower() or q in (row.path or "").lower():
            return "filename"
        if row.classification and q in row.classification.lower():
            return "classification"
        if row.extracted_text and q in row.extracted_text.lower():
            return "content"
        return "keyword"

    @staticmethod
    def _snippet_for(row: FileIndex, query: str, *, max_chars: int = 240) -> str:
        if not query:
            return ""
        # Prefer the extracted text — it has the most signal.
        text = row.extracted_text or row.text_content or ""
        if not text:
            return ""
        q = query.lower()
        lower = text.lower()
        idx = lower.find(q)
        if idx < 0:
            return text[:max_chars].strip()
        # Show ~half a window on each side of the match.
        half = max_chars // 2
        start = max(0, idx - half)
        end = min(len(text), idx + len(query) + half)
        snippet = text[start:end].strip()
        if start > 0:
            snippet = "…" + snippet
        if end < len(text):
            snippet = snippet + "…"
        return snippet

    # ------------------------------------------------------------------
    # Writes
    # ------------------------------------------------------------------
    def delete(self, file_id: int) -> bool:
        row = self.db.get(FileIndex, file_id)
        if row is None:
            return False
        self.db.delete(row)
        self.db.commit()
        return True

    def soft_delete(self, file_id: int) -> bool:
        row = self.db.get(FileIndex, file_id)
        if row is None:
            return False
        row.is_deleted = True
        self.db.commit()
        return True

    def clear_index(self) -> int:
        count = self.db.query(FileIndex).delete()
        self.db.commit()
        return count

    def reindex(self, file_id: int) -> IndexResult:
        row = self.db.get(FileIndex, file_id)
        if row is None:
            return IndexResult(stored=False, reason="not_found")
        return self.index_file(row.path, force=True)

    def reanalyse(self, file_id: int) -> Optional[FileIndex]:
        """Re-run classification on an already-indexed file."""
        row = self.db.get(FileIndex, file_id)
        if row is None:
            return None
        path = Path(row.path)
        try:
            stat = collect_stat_info(path)
        except OSError:
            stat = FileStatInfo(
                size_bytes=row.size_bytes,
                created_at=row.created_at_fs,
                modified_at=row.modified_at,
                accessed_at=row.accessed_at,
                extension=row.extension or "",
                filename=row.name,
            )
        # Reuse the stored preview for the notes/document signal.
        preview = (row.extracted_text or "")[:2048]
        type_info = detect_file_type(extension=stat.extension, mime_type="")
        classification = classify_file(
            filename=stat.filename, type_info=type_info, content_preview=preview
        )
        row.classification = classification.label
        row.classification_confidence = classification.confidence
        row.classifier_version = classification.version
        # Refresh metadata_json's classification block in place.
        meta = dict(row.metadata_json or {})
        meta["classification"] = classification.to_dict()
        row.metadata_json = meta
        self.db.commit()
        self.db.refresh(row)
        return row

    # ------------------------------------------------------------------
    # Stats
    # ------------------------------------------------------------------
    def stats(self) -> dict[str, Any]:
        total = self.db.query(FileIndex).filter(FileIndex.is_deleted == False).count()  # noqa: E712
        by_status: dict[str, int] = {}
        for label in ("ok", "unsupported", "failed", "empty", "pending"):
            by_status[label] = (
                self.db.query(FileIndex)
                .filter(FileIndex.is_deleted == False)  # noqa: E712
                .filter(FileIndex.extraction_status == label)
                .count()
            )
        by_classification: dict[str, int] = {}
        for label in ("document", "source_code", "data", "configuration", "notes", "unknown"):
            by_classification[label] = (
                self.db.query(FileIndex)
                .filter(FileIndex.is_deleted == False)  # noqa: E712
                .filter(FileIndex.classification == label)
                .count()
            )
        return {
            "total": total,
            "by_status": by_status,
            "by_classification": by_classification,
            "config": {
                "file_intelligence_enabled": self.file_intelligence_enabled,
                "max_bytes": self.max_bytes,
                "max_text_chars": self.max_text_chars,
                "allowed_extensions": sorted(self.allowed_extensions),
            },
            "extractors": self._factory.list_supported(),
        }

    # ------------------------------------------------------------------
    # LLM-driven actions (explain / summarise / ask)
    # ------------------------------------------------------------------
    def _safe_text_for_llm(self, file_id: int) -> tuple[Optional[FileIndex], str]:
        row = self.db.get(FileIndex, file_id)
        if row is None:
            return None, ""
        text = (row.extracted_text or row.text_content or "").strip()
        limit = self.llm_text_limit
        if limit and len(text) > limit:
            text = text[:limit] + "\n[truncated]"
        return row, text

    async def explain_file(self, file_id: int) -> dict[str, Any]:
        row, text = self._safe_text_for_llm(file_id)
        if row is None:
            return self._llm_error(file_id, "explain", "not_found")
        if not text:
            return self._llm_error(
                file_id,
                "explain",
                "no_extractable_text",
                detail="The file has no extracted text yet.",
            )
        return await self._llm_action(
            file_id=file_id,
            action="explain",
            row=row,
            text=text,
        )

    async def summarise_file(self, file_id: int) -> dict[str, Any]:
        row, text = self._safe_text_for_llm(file_id)
        if row is None:
            return self._llm_error(file_id, "summarise", "not_found")
        if not text:
            return self._llm_error(
                file_id,
                "summarise",
                "no_extractable_text",
                detail="The file has no extracted text yet.",
            )
        return await self._llm_action(
            file_id=file_id,
            action="summarise",
            row=row,
            text=text,
        )

    async def ask_question(self, file_id: int, question: str) -> dict[str, Any]:
        row, text = self._safe_text_for_llm(file_id)
        if row is None:
            return self._llm_error(file_id, "ask", "not_found")
        if not text:
            return self._llm_error(
                file_id,
                "ask",
                "no_extractable_text",
                detail="The file has no extracted text yet.",
            )
        question = (question or "").strip()
        if not question:
            return self._llm_error(file_id, "ask", "empty_question")
        return await self._llm_action(
            file_id=file_id,
            action="ask",
            row=row,
            text=text,
            question=question,
        )

    async def _llm_action(
        self,
        *,
        file_id: int,
        action: str,
        row: FileIndex,
        text: str,
        question: Optional[str] = None,
    ) -> dict[str, Any]:
        from app.llm import Message, get_llm_provider  # local import: avoid cycle

        if action == "explain":
            system = (
                "You are ContextAI. Explain what the file contains. "
                "Be concise (1-3 sentences)."
            )
            user = (
                "The user indexed the following file. Explain what it is "
                "and what it appears to contain. If the content is a code "
                "snippet, summarise its purpose.\n\n"
                f"File: {row.name}\n"
                f"Type: {row.file_type}\n"
                f"Classification: {row.classification or 'unknown'}\n"
                f"Content:\n---\n{text}\n---"
            )
        elif action == "summarise":
            system = "You are ContextAI. Summarise the file in 3-5 sentences."
            user = (
                f"Summarise the following {row.file_type} file. "
                "Call out key topics, numbers, and any notable entities.\n\n"
                f"File: {row.name}\n"
                f"Content:\n---\n{text}\n---"
            )
        else:  # ask
            system = (
                "You are ContextAI. Answer the user's question about the "
                "file based on the extracted content. If the content is "
                "insufficient, say so honestly."
            )
            user = (
                f"File: {row.name}\n"
                f"Type: {row.file_type}\n"
                f"Content:\n---\n{text}\n---\n\n"
                f"User question: {question}"
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
            logger.exception("File LLM %s failed", action)
            return self._llm_error(
                file_id,
                action,
                "llm_error",
                detail=str(e),
                processing_ms=int((time.perf_counter() - start) * 1000),
            )

        return {
            "file_id": file_id,
            "action": action,
            "answer": response.content,
            "is_error": False,
            "error_message": None,
            "model_used": response.model,
            "processing_ms": int((time.perf_counter() - start) * 1000),
        }

    @staticmethod
    def _llm_error(
        file_id: int,
        action: str,
        code: str,
        *,
        detail: str | None = None,
        processing_ms: int | None = None,
    ) -> dict[str, Any]:
        return {
            "file_id": file_id,
            "action": action,
            "answer": "",
            "is_error": True,
            "error_message": detail or code,
            "model_used": None,
            "processing_ms": processing_ms,
            "error_code": code,
        }


# ---------------------------------------------------------------------------
# Convenience accessor
# ---------------------------------------------------------------------------
def get_file_service(db: Session) -> FileService:
    """Return a fresh :class:`FileService` for the given session."""
    return FileService(db)
