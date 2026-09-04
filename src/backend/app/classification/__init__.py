"""Activity classifier package.

The default implementation is the deterministic, rule-based
``BaselineActivityClassifier`` — it is NOT a machine learning model.
The interface in ``app.classification.base.ActivityClassifier`` is
the single contract the rest of the system depends on, so a real ML
model can replace it later without touching call sites.
"""

from app.classification.base import (
    CLASSIFICATION_LABELS,
    ActivityClassifier,
    ClassificationInput,
    ClassificationResult,
)
from app.classification.baseline import BaselineActivityClassifier
from app.classification.factory import ClassifierFactory, get_activity_classifier

__all__ = [
    "CLASSIFICATION_LABELS",
    "ActivityClassifier",
    "ClassificationInput",
    "ClassificationResult",
    "BaselineActivityClassifier",
    "ClassifierFactory",
    "get_activity_classifier",
]
