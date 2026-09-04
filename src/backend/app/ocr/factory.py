"""OCR provider factory.

Selects the OCR provider implementation based on configuration. The rest
of the application should depend on the abstract ``OCRProvider`` rather
than concrete implementations, so this factory is the single point of
truth for which engine runs.
"""

from __future__ import annotations

from typing import Optional

from app.core.config import settings
from app.core.logging import get_logger
from app.ocr.base import OCRProvider
from app.ocr.mock import MockOCRProvider

logger = get_logger(__name__)


class OCRFactory:
    """Builds and caches OCR provider instances."""

    _instance: Optional[OCRProvider] = None
    _current_name: Optional[str] = None

    @classmethod
    def create_provider(cls, name: Optional[str] = None) -> OCRProvider:
        """Create an OCR provider by name.

        Defaults to ``settings.ocr_provider``. Unknown names fall back to
        the mock provider with a warning — fail-soft behaviour is safer
        than a hard crash during local development.
        """
        name = (name or settings.ocr_provider or "mock").lower()
        if name == "mock":
            return MockOCRProvider()
        if name == "tesseract":
            # Local import to keep pytesseract optional.
            from app.ocr.tesseract import TesseractOCRProvider

            return TesseractOCRProvider()
        if name == "paddle":
            from app.ocr.paddle import PaddleOCRProvider

            return PaddleOCRProvider()
        logger.warning(f"Unknown OCR provider '{name}', falling back to mock")
        return MockOCRProvider()

    @classmethod
    def get_default(cls) -> OCRProvider:
        """Return a cached provider, rebuilding it if the config changed."""
        name = settings.ocr_provider
        if cls._instance is None or cls._current_name != name:
            cls._instance = cls.create_provider(name)
            cls._current_name = name
            logger.info(f"OCR provider initialised: {cls._instance.name}")
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        """Clear the cached provider (used in tests)."""
        cls._instance = None
        cls._current_name = None


def get_ocr_provider() -> OCRProvider:
    """Convenience accessor used by the screen service."""
    return OCRFactory.get_default()
