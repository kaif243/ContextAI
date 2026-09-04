"""Activity + content classifier package.

The default implementation in every sub-module is the deterministic,
rule-based baseline — it is **NOT** a machine learning model. The
abstract interfaces in ``base`` (screen) and ``content_base`` (clipboard
content) are the only contracts the rest of the system depends on, so a
real ML model can replace the baseline later without touching call
sites.
"""

from app.classification.base import (
    CLASSIFICATION_LABELS,
    ActivityClassifier,
    ClassificationInput,
    ClassificationResult,
)
from app.classification.baseline import BaselineActivityClassifier
from app.classification.factory import ClassifierFactory, get_activity_classifier
from app.classification.baseline_content import BaselineContentClassifier
from app.classification.content_base import (
    CLIPBOARD_CONTENT_LABELS,
    ContentClassifier,
    ContentInput,
    ContentResult,
)
from app.classification.content_factory import (
    ContentClassifierFactory,
    get_content_classifier,
)

__all__ = [
    # Screen (Phase 2)
    "CLASSIFICATION_LABELS",
    "ActivityClassifier",
    "ClassificationInput",
    "ClassificationResult",
    "BaselineActivityClassifier",
    "ClassifierFactory",
    "get_activity_classifier",
    # Clipboard content (Phase 3)
    "CLIPBOARD_CONTENT_LABELS",
    "ContentClassifier",
    "ContentInput",
    "ContentResult",
    "BaselineContentClassifier",
    "ContentClassifierFactory",
    "get_content_classifier",
]
