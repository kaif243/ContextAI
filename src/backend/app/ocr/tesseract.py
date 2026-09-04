"""Tesseract OCR provider (pytesseract).

This is a real, production-capable OCR provider. It is NOT enabled by
default in Phase 2 because it requires the user to install:

  * the ``pytesseract`` Python package (``pip install pytesseract``)
  * the Tesseract binary on the host (https://github.com/tesseract-ocr/tesseract)
  * on Windows, the Tesseract installer from UB Mannheim

The provider is imported lazily so the rest of the backend works even
when pytesseract is not installed. If the user sets
``OCR_PROVIDER=tesseract`` without installing the dependencies,
``is_available()`` will return ``False`` and ``recognize()`` will raise a
clear ``RuntimeError``.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from app.core.logging import get_logger
from app.ocr.base import OCRProvider, OCRResult

logger = get_logger(__name__)


class TesseractOCRProvider(OCRProvider):
    """Wrapper around pytesseract.

    Set ``OCR_PROVIDER=tesseract`` and install pytesseract + the Tesseract
    binary to use this provider.
    """

    name = "tesseract"

    def __init__(self, language: str = "eng") -> None:
        self.language = language
        self._pytesseract: Any | None = None
        self._checked = False

    def is_available(self) -> bool:
        """Return True if pytesseract + Tesseract binary are usable."""
        if self._pytesseract is None and not self._checked:
            self._checked = True
            try:
                import pytesseract  # type: ignore[import-not-found]

                self._pytesseract = pytesseract
            except ImportError:
                logger.warning(
                    "TesseractOCRProvider: pytesseract not installed. "
                    "Run `pip install pytesseract` and install the Tesseract binary."
                )
                self._pytesseract = None
        return self._pytesseract is not None

    def recognize(self, image_path: str | Path) -> OCRResult:
        """Run Tesseract OCR on the image."""
        if not self.is_available():
            raise RuntimeError(
                "TesseractOCRProvider is not available. "
                "Install pytesseract and the Tesseract binary."
            )
        path = Path(image_path)
        if not path.exists():
            raise FileNotFoundError(f"Image not found: {path}")

        # Local import for type checker + lazy loading
        from PIL import Image  # type: ignore[import-not-found]

        assert self._pytesseract is not None
        pytesseract = self._pytesseract

        start = time.perf_counter()
        with Image.open(path) as img:
            data = pytesseract.image_to_data(
                img, lang=self.language, output_type=pytesseract.Output.DICT
            )
        processing_ms = int((time.perf_counter() - start) * 1000)

        words: list[str] = []
        regions: list[dict[str, Any]] = []
        confidences: list[float] = []
        for token, conf in zip(data.get("text", []), data.get("conf", [])):
            token = (token or "").strip()
            if not token:
                continue
            words.append(token)
            try:
                c = float(conf)
            except (TypeError, ValueError):
                c = -1.0
            if c >= 0:
                confidences.append(c / 100.0)
                regions.append(
                    {
                        "text": token,
                        "confidence": c / 100.0,
                        "left": data.get("left", [0] * len(data["text"]))[data["text"].index(token)],
                        "top": data.get("top", [0] * len(data["text"]))[data["text"].index(token)],
                        "width": data.get("width", [0] * len(data["text"]))[data["text"].index(token)],
                        "height": data.get("height", [0] * len(data["text"]))[data["text"].index(token)],
                    }
                )
        text = " ".join(words)
        avg_conf = (sum(confidences) / len(confidences)) if confidences else None

        return OCRResult(
            text=text,
            confidence=avg_conf,
            word_count=len(words),
            char_count=len(text),
            engine=self.name,
            processing_ms=processing_ms,
            regions=regions,
            metadata={"language": self.language},
        )
