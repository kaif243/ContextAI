"""DOCX extractor (self-contained)."""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from app.core.logging import get_logger
from app.file_intelligence.base import BaseFileExtractor, ExtractionResult, FileExtractionStatus
from app.file_intelligence.types import FILE_TYPE_DOCX

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


class DocxExtractor(BaseFileExtractor):
    handles_file_type = FILE_TYPE_DOCX
    version = "docx-1"

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
            return self._extract_with_docx(path, stat, max_chars=max_chars)
        except Exception as e:
            logger.info(f"DOCX extraction with python-docx failed for {path.name}: {e}")
            return self._fallback(path, stat, max_chars=max_chars, error=str(e))

    def _extract_with_docx(
        self, path: Path, stat: Any, *, max_chars: int
    ) -> ExtractionResult:
        try:
            import docx
        except ImportError:
            return self._fallback(path, stat, max_chars=max_chars, error="docx_missing")
        try:
            document = docx.Document(str(path))
        except Exception as e:
            return self._fallback(path, stat, max_chars=max_chars, error=str(e))
        paragraphs: list[str] = []
        for para in document.paragraphs:
            text = (para.text or "").strip()
            if text:
                paragraphs.append(text)
            if sum(len(p) for p in paragraphs) >= max_chars:
                break
        text = "\n".join(paragraphs)
        text, was_truncated = _truncate(text, max_chars)
        metadata: dict[str, Any] = {
            "size_bytes": stat.st_size,
            "paragraph_count": len(paragraphs),
            "extractor": "python-docx",
        }
        warnings: list[str] = []
        if was_truncated:
            warnings.append("text_truncated")
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
            warnings=warnings,
        )

    def _fallback(
        self, path: Path, stat: Any, *, max_chars: int, error: str | None
    ) -> ExtractionResult:
        text, was_truncated = _ascii_preview(path, max_chars)
        metadata: dict[str, Any] = {
            "size_bytes": stat.st_size,
            "extractor": "ascii_fallback",
            "library_missing": error == "docx_missing",
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
