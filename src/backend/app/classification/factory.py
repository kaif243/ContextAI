"""Activity classifier factory.

Phase 2 ships a single ``BaselineActivityClassifier``. The factory
exists so the selection can be made by configuration
(``settings.activity_classifier``) and so a future real ML model can be
swapped in by adding a new branch here and registering it in
``__init__.py``. The rest of the system always depends on the abstract
``ActivityClassifier`` from ``app.classification.base``.
"""

from __future__ import annotations

from typing import Optional

from app.classification.base import ActivityClassifier
from app.classification.baseline import BaselineActivityClassifier
from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class ClassifierFactory:
    """Builds and caches activity classifier instances."""

    _instance: Optional[ActivityClassifier] = None
    _current_kind: Optional[str] = None

    @classmethod
    def create_classifier(cls, kind: Optional[str] = None) -> ActivityClassifier:
        kind = (kind or settings.activity_classifier or "baseline").lower()
        if kind == "baseline":
            return BaselineActivityClassifier()
        logger.warning(f"Unknown classifier '{kind}', falling back to baseline")
        return BaselineActivityClassifier()

    @classmethod
    def get_default(cls) -> ActivityClassifier:
        kind = settings.activity_classifier
        if cls._instance is None or cls._current_kind != kind:
            cls._instance = cls.create_classifier(kind)
            cls._current_kind = kind
            logger.info(
                f"Activity classifier initialised: {cls._instance.get_info()}"
            )
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        cls._instance = None
        cls._current_kind = None


def get_activity_classifier() -> ActivityClassifier:
    """Convenience accessor used by the screen service."""
    return ClassifierFactory.get_default()
