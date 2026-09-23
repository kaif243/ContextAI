"""ML inference abstraction — clean interface for loading a model,
prediction/inference, model metadata/version, confidence scores,
and graceful fallback when a model is unavailable.

This module coexists with deterministic classifiers (Phase 1-4) and
does NOT modify any existing application flow in H1.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any, Optional
from pathlib import Path

from app.ml.schemas.model_meta import ModelMeta, SchemaVersion, FeatureSchema
from app.core.logging import get_logger

logger = get_logger(__name__)


class MLResult:
    """Result of an ML inference call."""

    def __init__(
        self,
        label: str,
        confidence: float,
        model_version: str,
        signals: Optional[dict[str, Any]] = None,
    ) -> None:
        self.label = label
        self.confidence = float(confidence)
        self.model_version = model_version
        self.signals = signals or {}

    def to_dict(self) -> dict[str, Any]:
        return {
            "label": self.label,
            "confidence": self.confidence,
            "model_version": self.model_version,
            "signals": self.signals,
        }

    def is_fallback(self) -> bool:
        return self.model_version in ("unavailable", "fallback")


class MLInference(ABC):
    """Abstract ML inference interface.

    Implementations must provide: load_model (optional), predict,
    get_info, and is_available. The interface is intentionally narrow
    so a real scikit-learn model can replace it later without
    changing call sites.
    """

    version: str = "abstract"

    @abstractmethod
    def predict(self, features: dict[str, Any]) -> MLResult:
        """Run inference on the given feature dictionary and return MLResult."""
        ...

    @abstractmethod
    def is_available(self) -> bool:
        """Return True if the inference backend can run."""
        ...

    @abstractmethod
    def get_info(self) -> dict[str, Any]:
        """Return metadata about the inference backend."""
        ...

    def load_model(self, path: Path) -> bool:
        """Load a model artifact from disk.

        Returns True if loaded successfully, False otherwise.
        Subclasses may override; the default is a safe no-op that
        reports failure without raising.
        """
        logger.info(
            "load_model called",
            extra={"path": str(path), "class": type(self).__name__},
        )
        return False


class UnavailableMLInference(MLInference):
    """Graceful fallback implementation when no ML model is available.

    This ensures the rest of the application never crashes because
    a model file is missing, corrupt, or unloaded. It always reports
    a safe "unknown" label with zero confidence and a clear fallback
    version identifier.
    """

    version = "fallback-1"

    def __init__(self) -> None:
        pass

    def predict(self, features: dict[str, Any]) -> MLResult:
        return MLResult(
            label="unknown",
            confidence=0.0,
            model_version="unavailable",
            signals={"fallback_reason": "no_model_loaded", "features_received": bool(features)},
        )

    def is_available(self) -> bool:
        return False

    def get_info(self) -> dict[str, Any]:
        return {
            "name": type(self).__name__,
            "version": self.version,
            "available": False,
            "is_ml": False,
            "fallback": True,
        }

    def load_model(self, path: Path) -> bool:
        logger.info(
            "UnavailableMLInference.load_model: ignoring load request",
            extra={"path": str(path), "reason": "fallback"},
        )
        return False
