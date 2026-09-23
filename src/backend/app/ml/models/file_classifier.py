"""Concrete ML inference implementation for the Phase 5 H3 file-classifier-v1 artifact."""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import joblib
import numpy as np

from app.ml.inference import MLInference, MLResult
from app.ml.schemas.model_meta import FeatureSchema, SchemaVersion
from app.ml.features.file_features import FEATURE_NAMES, FEATURE_VERSION

logger = logging.getLogger(__name__)

MODEL_DIR_DEFAULT = Path(__file__).resolve().parents[5] / "ml" / "models" / "file_classifier_v1"
MODEL_PATH_DEFAULT = MODEL_DIR_DEFAULT / "model.joblib"
META_PATH_DEFAULT = MODEL_DIR_DEFAULT / "meta.json"

# Label mapping derived from H3 training artifact meta.json
LABEL_MAP_REV = {
    0: "document",
    1: "source_code",
    2: "data",
    3: "configuration",
    4: "notes",
    5: "unknown",
}
EXPECTED_MODEL_VERSION = "file-classifier-v1"
EXPECTED_FRAMEWORK = "scikit-learn"
EXPECTED_FEATURE_VERSION = str(FEATURE_VERSION)

# The model artifact was trained on 20 features (FEATURE_NAMES minus feature_version_str)
FEATURE_INPUT_ORDER = tuple(f for f in FEATURE_NAMES if f != "feature_version_str")


class FileClassifierInference(MLInference):
    """Concrete inference backend that loads the H3 file-classifier-v1 artifact."""

    version = "file-classifier-v1"

    def __init__(
        self,
        model_path: Path | None = None,
        meta_path: Path | None = None,
    ) -> None:
        super().__init__()
        self.model_path = Path(model_path) if model_path else MODEL_PATH_DEFAULT
        self.meta_path = Path(meta_path) if meta_path else META_PATH_DEFAULT
        self._model = None
        self._meta: dict[str, Any] | None = None
        self.load_model(self.model_path)

    def load_model(self, path: Path | None = None) -> bool:
        target = Path(path) if path else self.model_path
        meta_target = self.meta_path
        self._model = None
        self._meta = None

        if not target.exists():
            logger.info("FileClassifierInference.load_model: model file missing", extra={"path": str(target)})
            return False
        if not meta_target.exists():
            logger.info("FileClassifierInference.load_model: meta file missing", extra={"path": str(meta_target)})
            return False

        try:
            with open(meta_target, "r", encoding="utf-8") as f:
                meta_raw = json.load(f)
        except Exception as exc:
            logger.warning("FileClassifierInference.load_model: meta.json parse error: %s", exc)
            return False

        # Validate meta fields
        meta_version = meta_raw.get("model_version", "")
        meta_feature_version = meta_raw.get("feature_version", "")
        meta_framework = meta_raw.get("framework", "")

        if meta_version != EXPECTED_MODEL_VERSION:
            logger.warning(
                "FileClassifierInference.load_model: model version mismatch: expected %s, got %s",
                EXPECTED_MODEL_VERSION,
                meta_version,
            )
            return False
        if meta_feature_version != EXPECTED_FEATURE_VERSION:
            logger.warning(
                "FileClassifierInference.load_model: feature version mismatch: expected %s, got %s",
                EXPECTED_FEATURE_VERSION,
                meta_feature_version,
            )
            return False
        if meta_framework != EXPECTED_FRAMEWORK:
            logger.warning(
                "FileClassifierInference.load_model: framework mismatch: expected %s, got %s",
                EXPECTED_FRAMEWORK,
                meta_framework,
            )
            return False

        # Load joblib artifact
        try:
            loaded = joblib.load(str(target))
        except Exception as exc:
            logger.warning("FileClassifierInference.load_model: joblib load error: %s", exc)
            return False

        # Verify it is a scikit-learn classifier with the expected feature count
        if not hasattr(loaded, "predict"):
            logger.warning("FileClassifierInference.load_model: loaded object has no predict method")
            return False
        # Validate number of features matches our input order (20 features)
        expected_n_features = len(FEATURE_INPUT_ORDER)
        try:
            n_features_in = int(getattr(loaded, "n_features_in_", 0))
            if n_features_in != expected_n_features:
                logger.warning(
                    "FileClassifierInference.load_model: feature count mismatch: expected %d, got %d",
                    expected_n_features,
                    n_features_in,
                )
                return False
        except Exception as exc:
            logger.warning("FileClassifierInference.load_model: cannot verify feature count: %s", exc)
            return False

        self._meta = meta_raw
        self._model = loaded
        logger.info("FileClassifierInference.load_model: loaded successfully", extra={"model_version": meta_version})
        return True

    def predict(self, features: dict[str, Any]) -> MLResult:
        if self._model is None or not self.is_available():
            return MLResult(
                label="unknown",
                confidence=0.0,
                model_version="unavailable",
                signals={
                    "fallback_reason": "model_not_loaded",
                    "features_received": bool(features),
                },
            )
        try:
            # Build ordered array from H2 feature pipeline output
            ordered_features = []
            for feature_name in FEATURE_INPUT_ORDER:
                value = features.get(feature_name, 0)
                try:
                    ordered_features.append(float(value))
                except (TypeError, ValueError):
                    ordered_features.append(0.0)
            X = np.array([ordered_features], dtype=float)

            # Predict label
            pred_idx = int(self._model.predict(X)[0])
            label = LABEL_MAP_REV.get(pred_idx, "unknown")

            # Confidence via probability if available
            confidence = 0.0
            if hasattr(self._model, "predict_proba"):
                proba = self._model.predict_proba(X)[0]
                confidence = float(proba[pred_idx])

            signals = {
                "predicted_class_index": pred_idx,
                "label_map_version": EXPECTED_MODEL_VERSION,
                "feature_version_used": EXPECTED_FEATURE_VERSION,
                "input_feature_count": len(ordered_features),
                "confidence_from_proba": True,
            }
            return MLResult(
                label=label,
                confidence=round(confidence, 4),
                model_version=EXPECTED_MODEL_VERSION,
                signals=signals,
            )
        except Exception as exc:
            logger.exception("FileClassifierInference.predict: inference exception")
            return MLResult(
                label="unknown",
                confidence=0.0,
                model_version="fallback",
                signals={
                    "fallback_reason": "inference_exception",
                    "error": str(exc),
                    "features_received": bool(features),
                },
            )

    def is_available(self) -> bool:
        return self._model is not None

    def get_info(self) -> dict[str, Any]:
        meta_version = self._meta.get("model_version", "unknown") if self._meta else "unknown"
        meta_feature_version = self._meta.get("feature_version", "unknown") if self._meta else "unknown"
        return {
            "name": "FileClassifierML",
            "version": self.version,
            "available": self.is_available(),
            "is_ml": True,
            "model_version": meta_version,
            "feature_version": meta_feature_version,
            "framework": EXPECTED_FRAMEWORK,
            "expected_feature_version": EXPECTED_FEATURE_VERSION,
        }
