"""Markdown extractor (self-contained)."""
from __future__ import annotations

from pathlib import Path

from app.file_intelligence.base import BaseFileExtractor, ExtractionResult, FileExtractionStatus
from app.file_intelligence.extractors.text import TextExtractor, _count_lines, _truncate
from app.file_intelligence.types import FILE_TYPE_MARKDOWN


class MarkdownExtractor(TextExtractor):
    handles_file_type = FILE_TYPE_MARKDOWN
    version = "markdown-1"

    def extract(self, path: Path, *, max_chars: int = 8000) -> ExtractionResult:
        result = super().extract(path, max_chars=max_chars)
        result.metadata["format"] = "markdown"
        if result.ok or result.status == FileExtractionStatus.EMPTY:
            heading_count = sum(
                1 for line in (result.text or "").splitlines() if line.lstrip().startswith("#")
            )
            result.metadata["heading_count"] = heading_count
        return result
