"""Plain-text extractor (self-contained)."""
from __future__ import annotations

from pathlib import Path

from app.core.logging import get_logger
from app.file_intelligence.base import BaseFileExtractor, ExtractionResult, FileExtractionStatus
from app.file_intelligence.types import FILE_TYPE_TXT

logger = get_logger(__name__)

_UTF8 = "utf-8"
_LATIN1 = "latin-1"


def _read_text_safe(path: Path, max_bytes: int) -> str:
    with path.open("rb") as f:
        raw = f.read(max_bytes + 1)
    try:
        return raw[:max_bytes].decode(_UTF8, errors="replace")
    except UnicodeDecodeError:
        return raw[:max_bytes].decode(_LATIN1, errors="replace")


def _truncate(text: str, max_chars: int) -> tuple[str, bool]:
    if max_chars <= 0:
        return "", False
    if len(text) <= max_chars:
        return text, False
    return text[:max_chars], True


def _count_lines(text: str) -> int:
    if not text:
        return 0
    return text.count("\n") + (0 if text.endswith("\n") else 1)


class TextExtractor(BaseFileExtractor):
    handles_file_type = FILE_TYPE_TXT
    version = "text-1"

    def extract(self, path: Path, *, max_chars: int = 8000) -> ExtractionResult:
        try:
            stat = path.stat()
        except OSError as e:
            return ExtractionResult(
                status=FileExtractionStatus.FAILED, error=f"stat failed: {e}"
            )
        if stat.st_size == 0:
            return ExtractionResult(
                status=FileExtractionStatus.EMPTY,
                text="",
                metadata={"size_bytes": 0, "encoding": _UTF8},
            )
        try:
            text = _read_text_safe(path, max_bytes=max_chars * 2)
        except OSError as e:
            return ExtractionResult(
                status=FileExtractionStatus.FAILED, error=f"read failed: {e}"
            )
        truncated, was_truncated = _truncate(text, max_chars)
        return ExtractionResult(
            status=FileExtractionStatus.OK,
            text=truncated,
            metadata={
                "size_bytes": stat.st_size,
                "encoding": _UTF8,
                "line_count": _count_lines(text),
                "word_count": len(text.split()),
            },
            warnings=["text_truncated"] if was_truncated else [],
        )
