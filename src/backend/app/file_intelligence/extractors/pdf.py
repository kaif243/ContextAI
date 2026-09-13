"""PDF extractor (self-contained)."""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from app.core.logging import get_logger
from app.file_intelligence.base import BaseFileExtractor, ExtractionResult, FileExtractionStatus
from app.file_intelligence.types import FILE_TYPE_PDF

logger = get_logger(__name__)

_UTF8 = "utf-8"
_LATIN1 = "latin-1"


def _truncate(text: str, max_chars: int) -> tuple[str, bool]:
    if max_chars <= 0:
        return "", False
    if len(text) <= max_chars:
        return text, False
    return text[:max_chars], True


def _ascii_preview(path: Path, max_chars: int) -> tuple[str, bool]:
    try:
        with path.open("rb") as f:
            chunk = f.read(min(max_chars * 4, 64 * 1024))
    except OSError:
        return "", False
    runs = re.findall(rb"[\x20-\x7e\r\n\t]{4,}", chunk)
    text = "\n".join(r.decode(_LATIN1, errors="replace") for r in runs)
    text, truncated = _truncate(text, max_chars)
    return text, truncated


class PdfExtractor(BaseFileExtractor):
    handles_file_type = FILE_TYPE_PDF
    version = "pdf-1"

    def is_available(self) -> bool:
        return True

    def extract(self, path: Path, *, max_chars: int = 8000) -> ExtractionResult:
        try:
            stat = path.stat()
        except OSError as e:
            return ExtractionResult(
                status=FileExtractionStatus.FAILED, error=f"stat failed: {e}"
            )
        try:
            return self._extract_with_pypdf(path, stat, max_chars=max_chars)
        except Exception as e:
            logger.info(f"PDF extraction with pypdf failed for {path.name}: {e}")
            return self._fallback(path, stat, max_chars=max_chars, error=str(e))

    def _extract_with_pypdf(
        self, path: Path, stat: Any, *, max_chars: int
    ) -> ExtractionResult:
        try:
            from pypdf import PdfReader
        except ImportError:
            return self._fallback(path, stat, max_chars=max_chars, error="pypdf_missing")
        try:
            reader = PdfReader(str(path))
        except Exception as e:
            return self._fallback(path, stat, max_chars=max_chars, error=str(e))
        try:
            page_count = len(reader.pages)
        except Exception:
            page_count = None
        chunks: list[str] = []
        total_chars = 0
        for page in reader.pages:
            try:
                page_text = page.extract_text() or ""
            except Exception:
                page_text = ""
            if not page_text:
                continue
            chunks.append(page_text)
            total_chars += len(page_text)
            if total_chars >= max_chars:
                break
        text = "\n".join(chunks)
        text, was_truncated = _truncate(text, max_chars)
        metadata: dict[str, Any] = {
            "size_bytes": stat.st_size,
            "page_count": page_count,
            "extractor": "pypdf",
        }
        warnings: list[str] = []
        if was_truncated:
            warnings.append("text_truncated")
        if not text:
            return ExtractionResult(
                status=FileExtractionStatus.SKIPPED,
                text="",
                metadata=metadata,
                warnings=warnings + ["no_text_layer"],
            )
        return ExtractionResult(
            status=FileExtractionStatus.OK,
            text=text,
            metadata=metadata,
            warnings=warnings,
        )

    def _fallback(
        self, path: Path, stat: Any, *, max_chars: int, error: str | None
    ) -> ExtractionResult:
        text, was_truncated = _ascii_preview(path, max_chars)
        metadata: dict[str, Any] = {
            "size_bytes": stat.st_size,
            "extractor": "ascii_fallback",
            "library_missing": error == "pypdf_missing",
        }
        warnings = ["text_truncated"] if was_truncated else []
        if not text:
            return ExtractionResult(
                status=FileExtractionStatus.SKIPPED,
                text="",
                metadata=metadata,
                warnings=warnings + ["no_extractable_text"],
            )
        return ExtractionResult(
            status=FileExtractionStatus.OK,
            text=text,
            metadata=metadata,
            warnings=warnings + ["fallback_preview"],
        )
