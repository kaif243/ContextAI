"""Phase 5 H5 evaluation layer — deterministic, synthetic demonstration only.

SKILL: This module produces SYNTHETIC / DEMONSTRATION ONLY metrics using
existing H3 artifacts. Never describe 1.0 metrics as real-world accuracy.
"""
from __future__ import annotations

import hashlib
import json
import logging
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
)

logger = logging.getLogger(__name__)

# Paths relative to repo root (this file lives at src/backend/app/ml/evaluation/)
REPO_ROOT = Path(__file__).resolve().parents[5]
DEFAULT_DATASET = REPO_ROOT / "ml" / "datasets" / "file_classification" / "train.csv"
DEFAULT_MODEL = REPO_ROOT / "ml" / "models" / "file_classifier_v1" / "model.joblib"
DEFAULT_META = REPO_ROOT / "ml" / "models" / "file_classifier_v1" / "meta.json"

# Feature schema alignment with H2/H3
FEATURE_INPUT_ORDER = (
    "filename_length",
    "filename_has_numbers",
    "filename_special_char_count",
    "extension_category_idx",
    "file_type_category_idx",
    "content_kind_category_idx",
    "is_supported",
    "size_bytes_log",
    "size_category_idx",
    "days_since_modified",
    "days_since_accessed",
    "text_length",
    "text_line_count",
    "text_word_count",
    "text_avg_line_length",
    "classification_label_idx",
    "classification_confidence",
    "is_indexed",
    "extraction_status_idx",
    "extraction_attempts",
)

EXPECTED_MODEL_VERSION = "file-classifier-v1"
EXPECTED_FEATURE_VERSION = "1.0.0"
EXPECTED_FRAMEWORK = "scikit-learn"

SYNTHETIC_LABEL = "SYNTHETIC/DEMONSTRATION ONLY"


def _dataset_hash(dataset_path: Path) -> str:
    """Compute a stable SHA-256 hash over dataset file contents."""
    hasher = hashlib.sha256()
    with open(dataset_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            hasher.update(chunk)
    return hasher.hexdigest()[:16]


def validate_inputs(dataset_path: Path, model_path: Path, meta_path: Path) -> None:
    """Validate that required artifacts exist and schema aligns.

    Raises ValueError with clear message for any missing/incompatible artifact.
    """
    errors: list[str] = []

    if not dataset_path.exists():
        errors.append(f"Dataset missing: {dataset_path}")
    if not model_path.exists():
        errors.append(f"Model artifact missing: {model_path}")
    if not meta_path.exists():
        errors.append(f"Metadata missing: {meta_path}")

    # Read meta for version checks
    meta_raw: dict[str, Any] = {}
    if meta_path.exists():
        try:
            with open(meta_path, "r", encoding="utf-8") as f:
                meta_raw = json.load(f)
        except Exception as exc:
            errors.append(f"Invalid/malformed metadata (JSON parse error): {exc}")

    if meta_raw:
        if meta_raw.get("model_version") != EXPECTED_MODEL_VERSION:
            errors.append(
                f"Model version mismatch: expected '{EXPECTED_MODEL_VERSION}', "
                f"got '{meta_raw.get('model_version', 'missing')}'"
            )
        if meta_raw.get("feature_version") != EXPECTED_FEATURE_VERSION:
            errors.append(
                f"Feature version mismatch: expected '{EXPECTED_FEATURE_VERSION}', "
                f"got '{meta_raw.get('feature_version', 'missing')}'"
            )
        if meta_raw.get("framework") != EXPECTED_FRAMEWORK:
            errors.append(
                f"Framework mismatch: expected '{EXPECTED_FRAMEWORK}', "
                f"got '{meta_raw.get('framework', 'missing')}'"
            )

    # Dataset schema check
    if dataset_path.exists():
        try:
            df = pd.read_csv(dataset_path)
        except Exception as exc:
            errors.append(f"Dataset unreadable: {exc}")
            df = pd.DataFrame()
        else:
            missing_cols = [f for f in FEATURE_INPUT_ORDER if f not in df.columns]
            if missing_cols:
                errors.append(f"Missing feature columns in dataset: {missing_cols}")
            if "label" not in df.columns:
                errors.append("Dataset missing required 'label' column")
            else:
                # Check feature_version_str compatibility
                if "feature_version_str" in df.columns:
                    unique_versions = df["feature_version_str"].dropna().unique()
                    if len(unique_versions) > 0 and not any(
                        str(EXPECTED_FEATURE_VERSION) == str(v) for v in unique_versions
                    ):
                        errors.append(
                            f"Feature version incompatibility: dataset feature_version_str={list(unique_versions)}, "
                            f"expected '{EXPECTED_FEATURE_VERSION}'"
                        )

    if errors:
        raise ValueError("; ".join(errors))


def evaluate_model_artifact(
    model_path: Path | str = DEFAULT_MODEL,
    meta_path: Path | str = DEFAULT_META,
    dataset_path: Path | str = DEFAULT_DATASET,
) -> dict[str, Any]:
    """Compute deterministic evaluation metrics against existing H3 artifacts.

    Returns a dict with all required metrics, clearly marked SYNTHETIC.
    """
    model_path_obj = Path(model_path)
    meta_path_obj = Path(meta_path)
    dataset_path_obj = Path(dataset_path)

    validate_inputs(dataset_path_obj, model_path_obj, meta_path_obj)

    # Load dataset
    df = pd.read_csv(dataset_path_obj)

    # Load meta
    with open(meta_path_obj, "r", encoding="utf-8") as f:
        meta = json.load(f)

    # Load model
    model = joblib.load(str(model_path_obj))

    # Build feature matrix (20 input features, exclude feature_version_str)
    feature_cols = [col for col in FEATURE_INPUT_ORDER if col != "feature_version_str"]
    X = df[feature_cols]
    # Preserve feature names for scikit-learn compatibility (model fitted with named DataFrame)
    # Import label mapping here to avoid circular imports and match model behavior
    from app.ml.features.file_features import CLASSIFICATION_LABEL_ORDER

    label_map_rev = {i: label for i, label in enumerate(CLASSIFICATION_LABEL_ORDER)}
    # The dataset label column uses the same string labels.
    # Convert dataset string labels to integer indices for comparison with model predictions.
    label_to_idx = {label: idx for idx, label in enumerate(CLASSIFICATION_LABEL_ORDER)}
    y_true_idx = np.array([label_to_idx.get(str(label), -1) for label in df["label"].values])
    # Predictions from model are integer indices
    y_pred_idx = model.predict(X)

    # For reporting with string labels, map predictions back
    y_pred_labels = np.array([label_map_rev.get(int(p), "unknown") for p in y_pred_idx])
    y_true_labels = np.array([label_map_rev.get(int(t), "unknown") if t >= 0 else "unknown" for t in y_true_idx])

    labels_sorted = sorted(meta.get("labels", list(CLASSIFICATION_LABEL_ORDER)))

    # Compute metrics using integer label indices (model native)
    accuracy = float(accuracy_score(y_true_idx, y_pred_idx))
    precision_macro = float(precision_score(y_true_idx, y_pred_idx, average="macro", labels=list(range(len(labels_sorted))), zero_division=0))
    recall_macro = float(recall_score(y_true_idx, y_pred_idx, average="macro", labels=list(range(len(labels_sorted))), zero_division=0))
    f1_macro = float(f1_score(y_true_idx, y_pred_idx, average="macro", labels=list(range(len(labels_sorted))), zero_division=0))

    # Per-class metrics and support (using integer label indices aligned with labels_sorted)
    cm = confusion_matrix(y_true_idx, y_pred_idx, labels=list(range(len(labels_sorted))))
    per_class: dict[str, Any] = {}
    for idx, label in enumerate(labels_sorted):
        tp = int(cm[idx, idx])
        fn = int(cm[idx, :].sum()) - tp
        fp = int(cm[:, idx].sum()) - tp
        support = int(cm[idx, :].sum())
        prec = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        rec = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1_cls = (2 * prec * rec) / (prec + rec) if (prec + rec) > 0 else 0.0
        per_class[label] = {
            "precision": round(float(prec), 6),
            "recall": round(float(rec), 6),
            "f1": round(float(f1_cls), 6),
            "support": support,
        }

    # Confusion matrix as nested list of ints
    confusion_matrix_list = cm.tolist()

    result = {
        "status": SYNTHETIC_LABEL,
        "note": "These metrics are SYNTHETIC / DEMONSTRATION ONLY and derived solely from the existing H3 dataset/model artifact for demonstration. They must not be interpreted as real-world accuracy.",
        "dataset_path": str(dataset_path_obj),
        "dataset_hash": meta.get("dataset_hash", ""),
        "dataset_rows": int(len(df)),
        "dataset_file_hash": _dataset_hash(dataset_path_obj),
        "model_path": str(model_path_obj),
        "model_version": meta.get("model_version", "unknown"),
        "feature_version": meta.get("feature_version", "unknown"),
        "algorithm": meta.get("algorithm", meta.get("framework", "unknown")),
        "framework": meta.get("framework", "unknown"),
        "metrics": {
            "accuracy": round(accuracy, 6),
            "precision_macro": round(precision_macro, 6),
            "recall_macro": round(recall_macro, 6),
            "f1_macro": round(f1_macro, 6),
            "per_class": per_class,
            "confusion_matrix": confusion_matrix_list,
        },
        "labels_ordered": labels_sorted,
        "synthetic_label": SYNTHETIC_LABEL,
    }
    return result
