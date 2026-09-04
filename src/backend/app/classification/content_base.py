"""Content-type classifier abstraction for Phase 3 (Clipboard).

This is a sibling of ``app.classification.base``. It is intentionally
**separate** from the screen classifier because:

  * The input shape is different (a single piece of text vs. OCR text +
    image metadata).
  * The label set is different (``text / url / email / code / file_path /
    json / unknown`` vs. ``code / error / document / ...``).
  * A future ML model that classifies clipboard content will not want
    to be forced into the screen classifier's contract.

The interface in this module is the single point of truth — a real ML
classifier can replace the baseline implementation without touching
call sites. **NOT machine learning**: the baseline shipped here is a
deterministic, rule-based detector.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Optional


# Canonical labels for clipboard content. Keep this list stable; the
# analytics layer indexes by label string and the API contract exposes
# it as a Literal.
CLIPBOARD_CONTENT_LABELS: tuple[str, ...] = (
    "text",
    "url",
    "email",
    "code",
    "file_path",
    "json",
    "unknown",
)


@dataclass
class ContentInput:
    """Inputs to a content classifier.

    Attributes:
        text: The raw text the user copied. May be empty (which is a
            valid input that should be classified as ``unknown``).
        source_app: Optional name of the source application.
        metadata: Free-form additional context. The pipeline forwards
            extracted entities here.
    """

    text: str = ""
    source_app: Optional[str] = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ContentResult:
    """Output of a content classifier.

    Attributes:
        label: One of ``CLIPBOARD_CONTENT_LABELS``.
        confidence: Heuristic score in [0.0, 1.0]. **Not calibrated** for
            the baseline; treat it as a relative strength indicator.
        signals: Per-rule evidence used to make the decision, useful
            for debugging and the user-facing "Why?" question.
        version: Identifier of the classifier implementation that
            produced the result.
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


class ContentClassifier(ABC):
    """Abstract content-type classifier for clipboard text.

    Implementations label a piece of text as one of the values in
    ``CLIPBOARD_CONTENT_LABELS``. The interface is intentionally narrow
    so a future ML model can be dropped in without touching call sites.
    """

    version: str = "abstract"

    @abstractmethod
    def classify(self, data: ContentInput) -> ContentResult:
        """Classify the content and return a label + heuristic confidence."""
        ...

    def is_available(self) -> bool:
        """Return True if the classifier can run (always True by default)."""
        return True

    def get_info(self) -> dict[str, Any]:
        return {
            "name": type(self).__name__,
            "version": self.version,
            "available": self.is_available(),
            "is_ml": False,  # the baseline is not ML; future ML swaps in
                             # the same interface, but should set this
                             # to True.
            "labels": list(CLIPBOARD_CONTENT_LABELS),
        }
