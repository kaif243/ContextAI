"""OCR provider package.

Exposes the abstract interface and the factory accessor.
"""

from app.ocr.base import OCRProvider, OCRResult
from app.ocr.factory import OCRFactory, get_ocr_provider

__all__ = [
    "OCRProvider",
    "OCRResult",
    "OCRFactory",
    "get_ocr_provider",
]
