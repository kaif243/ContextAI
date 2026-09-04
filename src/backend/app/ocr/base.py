"""OCR provider interface.

A clean abstraction over different OCR engines. The rest of the application
should depend on this interface, not on any specific engine.

Phase 2 ships:
  - ``MockOCRProvider``: a deterministic, dependency-free provider used for
    local development and tests. It returns the contents of a sidecar
    ``.txt`` file when one exists, or a generated stub otherwise.
  - ``TesseractOCRProvider``: production-ready wrapper around pytesseract
    (requires the Tesseract binary on the host). It is not used by default
    because pytesseract is an optional dependency.
  - ``PaddleOCRProvider``: placeholder for PaddleOCR. It is intentionally
    NOT implemented in Phase 2 because paddleocr / paddlepaddle have
    known Windows + Python 3.10 install issues; see ``docs/phase2-ocr.md``.

The selection is made at runtime via ``app.core.config.settings.ocr_provider``.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional


@dataclass
class OCRResult:
    """Result of an OCR pass over an image.

    Attributes:
        text: The extracted plain text.
        confidence: Overall confidence in [0.0, 1.0] when reported by the engine.
        word_count: Number of whitespace-separated tokens in ``text``.
        char_count: Number of characters in ``text``.
        engine: Name of the engine that produced the result (e.g. ``"mock"``).
        processing_ms: Wall-clock time the engine took, in milliseconds.
        regions: Optional structured list of text regions, when the engine
            reports bounding boxes. Each entry is engine-specific.
        metadata: Free-form engine-specific metadata (page numbers, languages, ...).
    """

    text: str
    confidence: Optional[float] = None
    word_count: int = 0
    char_count: int = 0
    engine: str = "unknown"
    processing_ms: int = 0
    regions: list[dict[str, Any]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to a JSON-serializable dict."""
        return {
            "text": self.text,
            "confidence": self.confidence,
            "word_count": self.word_count,
            "char_count": self.char_count,
            "engine": self.engine,
            "processing_ms": self.processing_ms,
            "regions": self.regions,
            "metadata": self.metadata,
        }


class OCRProvider(ABC):
    """Abstract OCR provider.

    Implementations MUST be safe to instantiate on a host where the
    underlying engine is missing — in that case ``is_available()`` returns
    ``False`` and ``recognize()`` raises a clear error.
    """

    name: str = "base"

    @abstractmethod
    def is_available(self) -> bool:
        """Return True if this provider can run on the current host."""
        ...

    @abstractmethod
    def recognize(self, image_path: str | Path) -> OCRResult:
        """Run OCR on the given image file and return the result.

        Args:
            image_path: Path to a readable image file.

        Raises:
            FileNotFoundError: If the file does not exist.
            RuntimeError: If the underlying engine is unavailable.
        """
        ...

    def get_info(self) -> dict[str, Any]:
        """Return diagnostic info about the provider."""
        return {
            "name": self.name,
            "available": self.is_available(),
        }
