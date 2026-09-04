"""Screen activity classifier.

This package classifies the activity that produced a screenshot based on
OCR text and image metadata. The classification is consumed by the screen
Q&A service to decide what kind of answer to generate.

IMPORTANT
=========
The default implementation in ``app.classification.baseline`` is a
**deterministic, rule-based baseline**. It is **NOT machine learning**:
no model is trained, no probabilities are learned from data, and there
is no calibrated confidence. The reported "confidence" is a heuristic
indicator of how strongly the rules fired.

The interface here is the only contract the rest of the system depends on,
so a real ML model can replace the baseline without changing call sites.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Optional


# Canonical labels the system can produce. Keep this list stable; downstream
# services index ML dashboards and analytics by label string.
CLASSIFICATION_LABELS: tuple[str, ...] = (
    "code",
    "error",
    "document",
    "receipt",
    "timetable",
    "table",
    "form",
    "webpage",
    "image",
    "general_ui",
    "unknown",
)


@dataclass
class ClassificationInput:
    """Inputs to a classifier call.

    Attributes:
        ocr_text: The OCR-extracted text for the screenshot, or empty if
            OCR was skipped.
        ocr_engine: Name of the engine that produced ``ocr_text``.
        image_width: Width of the screenshot in pixels.
        image_height: Height of the screenshot in pixels.
        source_app: Optional identifier of the application that produced
            the screenshot (e.g. ``"code.exe"``).
        window_title: Optional title of the active window.
        metadata: Free-form additional context.
    """

    ocr_text: str = ""
    ocr_engine: Optional[str] = None
    image_width: int = 0
    image_height: int = 0
    source_app: Optional[str] = None
    window_title: Optional[str] = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ClassificationResult:
    """Output of a classifier call.

    Attributes:
        label: One of ``CLASSIFICATION_LABELS``.
        confidence: Heuristic score in [0.0, 1.0]. **Not calibrated** for
            the baseline implementation.
        signals: Per-label signal strengths and rule hits, useful for
            debugging and explanation.
        version: Identifier of the classifier implementation that produced
            the result (e.g. ``"baseline-1"``).
    """

    label: str = "unknown"
    confidence: float = 0.0
    signals: dict[str, Any] = field(default_factory=dict)
    version: str = "unknown"

    def to_dict(self) -> dict[str, Any]:
        return {
            "label": self.label,
            "confidence": self.confidence,
            "signals": self.signals,
            "version": self.version,
        }


class ActivityClassifier(ABC):
    """Abstract screen activity classifier.

    Implementations classify the activity shown on the screen based on
    OCR text + image metadata. The interface is intentionally narrow so
    a future ML model can be dropped in without touching call sites.
    """

    version: str = "abstract"

    @abstractmethod
    def classify(self, data: ClassificationInput) -> ClassificationResult:
        """Classify the activity and return a label + heuristic confidence."""
        ...

    def is_available(self) -> bool:
        """Return True if the classifier can run (always True by default)."""
        return True

    def get_info(self) -> dict[str, Any]:
        return {
            "name": type(self).__name__,
            "version": self.version,
            "available": self.is_available(),
            "is_ml": False,  # always False in Phase 2; the interface contract
                             # is what guarantees a future ML model can swap in.
        }
