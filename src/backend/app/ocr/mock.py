"""Mock OCR provider for local development and tests.

This provider does NOT do real OCR. It exists so the rest of the system
(screenshots, classification, Q&A) can be developed end-to-end on machines
where the user has not installed Tesseract or PaddleOCR.

Behaviour:
  1. If a sidecar ``<image>.txt`` file exists next to the image, its contents
     are returned verbatim. This lets developers annotate real screenshots
     for deterministic testing.
  2. If a JSON sidecar ``<image>.ocr.json`` exists, its structured data
     is used to populate ``confidence`` and ``regions``.
  3. Otherwise a synthetic stub is returned. The stub encodes image
     dimensions and a checksum so downstream tests can still assert on
     determinism without depending on a real OCR engine.
"""

from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path

from app.core.logging import get_logger
from app.ocr.base import OCRProvider, OCRResult

logger = get_logger(__name__)


class MockOCRProvider(OCRProvider):
    """Deterministic, dependency-free OCR provider for development."""

    name = "mock"

    def is_available(self) -> bool:
        """Always available — no external dependencies."""
        return True

    def recognize(self, image_path: str | Path) -> OCRResult:
        """Return OCR text from a sidecar file or generate a deterministic stub.

        Args:
            image_path: Path to the image to "OCR".

        Returns:
            An ``OCRResult`` with engine="mock".

        Raises:
            FileNotFoundError: If ``image_path`` does not exist.
        """
        path = Path(image_path)
        if not path.exists():
            raise FileNotFoundError(f"Image not found: {path}")

        start = time.perf_counter()
        text: str
        confidence: float | None
        regions: list[dict] = []

        sidecar_txt = path.with_suffix(path.suffix + ".txt")
        sidecar_json = path.with_suffix(path.suffix + ".ocr.json")

        if sidecar_txt.exists():
            text = sidecar_txt.read_text(encoding="utf-8", errors="replace")
            confidence = 1.0
            logger.debug(f"Mock OCR: read sidecar {sidecar_txt}")
        elif sidecar_json.exists():
            try:
                data = json.loads(sidecar_json.read_text(encoding="utf-8"))
                text = str(data.get("text", ""))
                confidence = data.get("confidence")
                regions = list(data.get("regions", []))
            except json.JSONDecodeError as e:
                logger.warning(f"Mock OCR: bad sidecar JSON: {e}; using stub")
                text, confidence = self._make_stub(path)
        else:
            text, confidence = self._make_stub(path)

        processing_ms = int((time.perf_counter() - start) * 1000)
        word_count = len(text.split()) if text else 0
        char_count = len(text) if text else 0

        return OCRResult(
            text=text,
            confidence=confidence,
            word_count=word_count,
            char_count=char_count,
            engine=self.name,
            processing_ms=processing_ms,
            regions=regions,
            metadata={"source": str(path), "is_stub": not sidecar_txt.exists() and not sidecar_json.exists()},
        )

    @staticmethod
    def _make_stub(path: Path) -> tuple[str, float]:
        """Generate a deterministic stub OCR result from image properties."""
        digest = hashlib.sha256(path.read_bytes()).hexdigest()[:12]
        try:
            with path.open("rb") as f:
                f.seek(16)
                w_bytes = f.read(4)
                h_bytes = f.read(4)
            width = int.from_bytes(w_bytes, "big") if len(w_bytes) == 4 else 0
            height = int.from_bytes(h_bytes, "big") if len(h_bytes) == 4 else 0
        except Exception:
            width, height = 0, 0

        stub = (
            f"[mock-ocr] {path.name} ({width}x{height}) sha={digest}\n"
            "This is a stub OCR result. Provide a sidecar .txt file next to the "
            "image with the ground-truth text to exercise the real pipeline."
        )
        return stub, 0.5
