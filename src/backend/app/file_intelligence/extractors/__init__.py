"""Per-format file extractors - public exports only."""
from __future__ import annotations

from pathlib import Path

from app.file_intelligence.extractors.code import CodeExtractor
from app.file_intelligence.extractors.csv import CsvExtractor
from app.file_intelligence.extractors.docx import DocxExtractor
from app.file_intelligence.extractors.json import JsonExtractor
from app.file_intelligence.extractors.markdown import MarkdownExtractor
from app.file_intelligence.extractors.pdf import PdfExtractor
from app.file_intelligence.extractors.text import TextExtractor
from app.file_intelligence.base import (
    BaseFileExtractor,
    ExtractionResult,
    FileExtractionStatus,
)

__all__ = [
    "BaseFileExtractor",
    "ExtractionResult",
    "FileExtractionStatus",
    "TextExtractor",
    "MarkdownExtractor",
    "JsonExtractor",
    "CsvExtractor",
    "CodeExtractor",
    "PdfExtractor",
    "DocxExtractor",
    "NullExtractor",
]


class NullExtractor(BaseFileExtractor):
    """Fallback used when no specific extractor is registered."""

    handles_file_type = ""
    version = "null-1"

    def extract(self, path: Path, *, max_chars: int = 8000) -> ExtractionResult:
        return ExtractionResult(
            status=FileExtractionStatus.UNSUPPORTED,
            text="",
            metadata={"reason": "no_extractor"},
            warnings=["no_extractor_available"],
        )
