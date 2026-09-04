"""PaddleOCR provider (placeholder).

NOT IMPLEMENTED in Phase 2.

PaddleOCR is a strong choice for production OCR, but its Python
distribution (paddleocr + paddlepaddle) has known install issues on
Windows + Python 3.10 (DLL load failures, large wheel, long CUDA
download). The team policy is to verify the environment first and
fall back to a clean OCR provider interface if installation is
problematic.

The interface here is a placeholder so that future integration has
a clear extension point. Selecting ``OCR_PROVIDER=paddle`` today
will raise a clear ``RuntimeError`` rather than silently producing
empty results.
"""

from __future__ import annotations

from pathlib import Path

from app.core.logging import get_logger
from app.ocr.base import OCRProvider, OCRResult

logger = get_logger(__name__)


class PaddleOCRProvider(OCRProvider):
    """Placeholder PaddleOCR provider — not yet implemented.

    To enable, install the real dependencies (see docs/phase2-ocr.md) and
    implement ``recognize()`` using ``PaddleOCR(use_angle_cls=True, lang='en')``.
    """

    name = "paddle"

    def is_available(self) -> bool:
        return False

    def recognize(self, image_path: str | Path) -> OCRResult:
        raise RuntimeError(
            "PaddleOCRProvider is not implemented in Phase 2. "
            "PaddlePaddle has known install issues on Windows + Python 3.10. "
            "Use OCR_PROVIDER=mock (default) or OCR_PROVIDER=tesseract instead. "
            "See docs/phase2-ocr.md for the production recommendation."
        )
