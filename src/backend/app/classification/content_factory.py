"""Content classifier factory.

Mirrors the Phase 2 ``ClassifierFactory`` pattern. The selection is
made by configuration (``settings.content_classifier``) and a future
real ML model can be added by branching here and registering the new
class in ``__init__.py``. The rest of the system always depends on the
abstract ``ContentClassifier`` from ``app.classification.content_base``.
"""

from __future__ import annotations

from typing import Optional

from app.classification.baseline_content import BaselineContentClassifier
from app.classification.content_base import ContentClassifier
from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class ContentClassifierFactory:
    """Builds and caches content classifier instances."""

    _instance: Optional[ContentClassifier] = None
    _current_kind: Optional[str] = None

    @classmethod
    def create_classifier(cls, kind: Optional[str] = None) -> ContentClassifier:
        kind = (kind or getattr(settings, "content_classifier", "baseline") or "baseline").lower()
        if kind == "baseline":
            return BaselineContentClassifier()
        logger.warning(f"Unknown content classifier '{kind}', falling back to baseline")
        return BaselineContentClassifier()

    @classmethod
    def get_default(cls) -> ContentClassifier:
        kind = getattr(settings, "content_classifier", "baseline")
        if cls._instance is None or cls._current_kind != kind:
            cls._instance = cls.create_classifier(kind)
            cls._current_kind = kind
            logger.info(
                f"Content classifier initialised: {cls._instance.get_info()}"
            )
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        cls._instance = None
        cls._current_kind = None


def get_content_classifier() -> ContentClassifier:
    """Convenience accessor used by the clipboard service."""
    return ContentClassifierFactory.get_default()
