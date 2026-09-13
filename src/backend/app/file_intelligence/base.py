"""File extractor abstraction.

The extractor contract is intentionally narrow so the rest of the
codebase never has to know *how* a PDF or DOCX was parsed:

    BaseFileExtractor
        ↓
    TextExtractor / MarkdownExtractor / JsonExtractor / ...

Each extractor declares which ``file_type`` it handles via
:attr:`handles_file_type` and exposes a single
:meth:`extract` method that returns an :class:`ExtractionResult`.

The factory in :mod:`app.file_intelligence.factory` (a sibling
module) maps a file type to the right extractor. The rest of the
system only ever depends on the abstract base.

Design notes
------------
* The default implementations are **not** machine learning — they
  are thin wrappers over the appropriate stdlib / third-party
  parser. Where a third-party library would be required (e.g.
  ``pypdf`` for PDFs, ``python-docx`` for Word documents), the
  Phase 4 contract is to return a "library_missing" result
  instead of crashing. The actual file metadata is still
  available, so the file can still appear in search results.
* Extractors **must not** modify the file. They are read-only.
* Extractors **must not** send data off-device.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Optional

from app.core.logging import get_logger

logger = get_logger(__name__)


class FileExtractionStatus(str, Enum):
    """Outcome of a single :meth:`BaseFileExtractor.extract` call.

    Members:
        OK: Extraction succeeded; ``text`` and ``metadata`` are usable.
        UNSUPPORTED: This extractor does not handle the file type.
            The service should mark the row as
            ``extraction_status='unsupported'`` and return early.
        EMPTY: The file is empty (zero-byte file, or text that
            decodes to nothing).
        FAILED: Extraction failed (corrupted file, encoding
            error, etc.). ``error`` carries a human-readable
            message. The service should mark the row as
            ``extraction_status='failed'``.
        SKIPPED: The extractor intentionally chose not to extract
            this file (e.g. the size cap is hit and the file is
            not text-like). The row is still recorded as
            ``extraction_status='ok'`` with empty ``text`` (we
            want the metadata, just not the content).
    """

    OK = "ok"
    UNSUPPORTED = "unsupported"
    EMPTY = "empty"
    FAILED = "failed"
    SKIPPED = "skipped"

    def __str__(self) -> str:  # pragma: no cover - trivial
        return self.value


@dataclass
class ExtractionResult:
    """Outcome of an :meth:`BaseFileExtractor.extract` call.

    Attributes:
        status: What happened. See :class:`FileExtractionStatus`.
        text: Best-effort extracted text. Empty string for
            non-text formats or when extraction was skipped.
        metadata: Free-form per-extractor metadata (line count,
            JSON structure, page count, ...).
        warnings: Non-fatal issues the caller should know about
            (e.g. "text was truncated").
        error: Human-readable error message when ``status`` is
            ``FAILED``. ``None`` otherwise.
    """

    status: FileExtractionStatus = FileExtractionStatus.OK
    text: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    error: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status.value,
            "text": self.text,
            "metadata": dict(self.metadata),
            "warnings": list(self.warnings),
            "error": self.error,
        }

    @property
    def ok(self) -> bool:
        return self.status == FileExtractionStatus.OK

    @property
    def char_count(self) -> int:
        return len(self.text or "")


class BaseFileExtractor(ABC):
    """Abstract base for file extractors.

    Subclasses must declare which ``file_type`` they handle and
    implement :meth:`extract`. They should **not** raise — they
    should return a :class:`ExtractionResult` with the appropriate
    status.
    """

    #: The ``file_type`` this extractor handles. Must be a
    #: canonical label from ``app.file_intelligence.types``.
    handles_file_type: str = ""

    #: Implementation version, surfaced for diagnostics.
    version: str = "abstract"

    @abstractmethod
    def extract(self, path: Path, *, max_chars: int) -> ExtractionResult:
        """Extract content from ``path``.

        Args:
            path: Absolute path to the file on disk. The extractor
                must open it read-only.
            max_chars: Hard cap on the number of characters kept
                in the returned ``text``. Extractors that produce
                a long output (PDFs, large code files) must
                truncate here and add a warning.

        Returns:
            A :class:`ExtractionResult`. Never raises.
        """
        ...

    def is_available(self) -> bool:
        """Return True if this extractor can run.

        The default is True. Subclasses that depend on a missing
        optional library should override and return False — the
        factory will then skip them and the service will record
        a "library_missing" status.
        """
        return True

    def get_info(self) -> dict[str, Any]:
        return {
            "name": type(self).__name__,
            "version": self.version,
            "handles_file_type": self.handles_file_type,
            "available": self.is_available(),
        }


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------
class ExtractorFactory:
    """Builds and caches file extractors.

    The factory keeps a mapping ``file_type -> extractor``. The
    service layer calls :meth:`get` with the file's canonical
    type; the factory returns a working extractor or the
    ``NullExtractor`` sentinel.
    """

    def __init__(self) -> None:
        self._extractors: dict[str, BaseFileExtractor] = {}
        self._loaded = False

    def _register(self, extractor: BaseFileExtractor) -> None:
        ft = getattr(extractor, "handles_file_type", "") or ""
        if not ft:
            return
        if not extractor.is_available():
            logger.info(
                f"Extractor {extractor.get_info()['name']} is not available; "
                f"file_type={ft} will fall back to the null extractor"
            )
            return
        self._extractors[ft] = extractor

    def _ensure_loaded(self) -> None:
        if self._loaded:
            return
        # Imported here to avoid a top-level import cycle (the
        # concrete extractors import from this module's types).
        from app.file_intelligence.extractors import (  # noqa: PLC0415
            CsvExtractor,
            CodeExtractor,
            DocxExtractor,
            JsonExtractor,
            MarkdownExtractor,
            NullExtractor,
            PdfExtractor,
            TextExtractor,
        )

        for cls in (
            TextExtractor,
            MarkdownExtractor,
            JsonExtractor,
            CsvExtractor,
            CodeExtractor,
            PdfExtractor,
            DocxExtractor,
        ):
            self._register(cls())
        # Always register the null extractor as a last-ditch fallback.
        self._null = NullExtractor()
        self._loaded = True

    def get(self, file_type: str) -> BaseFileExtractor:
        """Return the extractor for ``file_type`` (or the null one)."""
        self._ensure_loaded()
        return self._extractors.get(file_type, self._null)

    def get_for_path(self, path: Path | str) -> BaseFileExtractor:
        """Return extractor based on file path extension."""
        self._ensure_loaded()
        path_obj = Path(path) if isinstance(path, str) else path
        from app.file_intelligence.types import detect_file_type
        info = detect_file_type(filename=str(path_obj))
        return self.get(info.file_type if info.file_type else "unsupported")

    def list_supported(self) -> list[dict[str, Any]]:
        """Return info about every registered extractor."""
        self._ensure_loaded()
        out: list[dict[str, Any]] = []
        for ft, ex in sorted(self._extractors.items()):
            info = ex.get_info()
            info["file_type"] = ft
            out.append(info)
        return out

    def reset(self) -> None:
        """Clear the registry. Useful for tests."""
        self._extractors.clear()
        self._loaded = False
        self._null = None  # type: ignore[assignment]


# Module-level singleton + convenience accessor.
_factory: ExtractorFactory | None = None


def get_file_extractor_factory() -> ExtractorFactory:
    """Return the module-level extractor factory."""
    global _factory
    if _factory is None:
        _factory = ExtractorFactory()
    return _factory
