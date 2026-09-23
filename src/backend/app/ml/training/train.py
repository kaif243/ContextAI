"""Reproducible local model training pipeline for Phase 5 H3."""
from __future__ import annotations

import joblib
from pathlib import Path
from typing import Any

import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score, confusion_matrix
from sklearn.model_selection import train_test_split

from app.ml.schemas.model_meta import ModelMeta, SchemaVersion, FeatureSchema
from app.ml.features.file_features import FEATURE_NAMES, FEATURE_VERSION, get_feature_schema
from app.ml.training.dataset_builder import DATASET_PATH, build_dataset, dataset_exists

MODEL_VERSION = "file-classifier-v1"
import os
_REPO_ROOT = Path(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))))))
MODEL_OUTPUT_DIR = _REPO_ROOT / "ml/models/file_classifier_v1"
LABEL_MAP = {
    "document": 0, "source_code": 1, "data": 2,
    "configuration": 3, "notes": 4, "unknown": 5,
}
REVERSE_LABEL_MAP = {v: k for k, v in LABEL_MAP.items()}
FEATURE_COLUMNS = [f for f in FEATURE_NAMES if f != "feature_version_str"]


def train(
    dataset_path: Path | None = None,
    test_size: float = 0.25,
    random_state: int = 42,
) -> dict[str, Any]:
    """Train the file-classifier model locally and save artifacts.

    Args:
        dataset_path: Path to synthetic CSV dataset. Uses default if None.
        test_size: Fraction for validation/test split.
        random_state: Fixed seed for reproducibility.

    Returns:
        Dictionary with training summary, metrics, and artifact paths.
    """
    dataset_path = dataset_path or DATASET_PATH
    build_dataset()

    df = pd.read_csv(dataset_path)
    # Separate label
    y_raw = df["label"].astype(str)
    y = y_raw.map(LABEL_MAP).fillna(LABEL_MAP["unknown"]).astype(int)
    X = df[FEATURE_COLUMNS].copy()

    # Train/test split
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=test_size, random_state=random_state, stratify=y
    )

    # Train model
    model = RandomForestClassifier(
        n_estimators=50,
        max_depth=10,
        random_state=random_state,
        n_jobs=-1,
    )
    model.fit(X_train, y_train)

    # Predictions and metrics
    y_pred = model.predict(X_test)
    metrics = {
        "accuracy": float(accuracy_score(y_test, y_pred)),
        "precision_macro": float(precision_score(y_test, y_pred, average="macro", zero_division=0)),
        "recall_macro": float(recall_score(y_test, y_pred, average="macro", zero_division=0)),
        "f1_macro": float(f1_score(y_test, y_pred, average="macro", zero_division=0)),
        "confusion_matrix": confusion_matrix(y_test, y_pred, labels=list(LABEL_MAP.values())).tolist(),
        "dataset_rows": int(len(df)),
        "train_rows": int(len(X_train)),
        "test_rows": int(len(X_test)),
        "model_version": MODEL_VERSION,
        "feature_version": str(FEATURE_VERSION),
        "algorithm": "RandomForestClassifier",
        "random_state": random_state,
    }

    # Save artifact
    MODEL_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    model_path = MODEL_OUTPUT_DIR / "model.joblib"
    joblib.dump(model, model_path)

    meta = ModelMeta(
        model_version=MODEL_VERSION,
        feature_version=FEATURE_VERSION,
        framework="scikit-learn",
        labels=tuple(LABEL_MAP.keys()),
        dataset_hash=f"dataset_v1_{len(df)}_rows_seed{random_state}",
        evaluation_summary=metrics,
    )
    meta_path = MODEL_OUTPUT_DIR / "meta.json"
    import json
    with open(meta_path, "w") as f:
        f.write(json.dumps(meta.to_dict(), indent=2))

    metrics["artifact_path"] = str(model_path)
    metrics["meta_path"] = str(meta_path)
    return metrics
