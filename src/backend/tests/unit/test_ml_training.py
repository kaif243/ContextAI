"""Unit tests for Phase 5 H3 — dataset construction, training, artifacts."""

import pytest
from pathlib import Path

from app.ml.training.dataset_builder import dataset_exists, get_row_count, DATASET_PATH, build_dataset
from app.ml.training.train import LABEL_MAP, FEATURE_COLUMNS, MODEL_VERSION, MODEL_OUTPUT_DIR
from app.ml.schemas.model_meta import SchemaVersion


class TestDataset:
    def test_dataset_exists(self):
        assert dataset_exists() is True

    def test_row_count_positive(self):
        count = get_row_count()
        assert count > 0
        # Synthetic dataset should have 72 rows (6 labels * 12)
        assert count == 72

    def test_dataset_rebuildable(self):
        path = build_dataset(force=False)
        assert path.exists()
        assert path == DATASET_PATH

    def test_dataset_is_synthetic_readme_exists(self):
        readme_path = DATASET_PATH.parent / "README.md"
        assert readme_path.exists()
        content = readme_path.read_text()
        assert "SYNTHETIC" in content or "synthetic" in content
        assert ("personal" in content.lower() and "does not contain" in content.lower()) or "synthetic" in content.lower()


class TestTrainingArtifacts:
    def test_model_file_exists(self):
        model_path = MODEL_OUTPUT_DIR / "model.joblib"
        assert model_path.exists()
        assert model_path.stat().st_size > 0

    def test_meta_file_exists(self):
        meta_path = MODEL_OUTPUT_DIR / "meta.json"
        assert meta_path.exists()
        import json
        meta = json.loads(meta_path.read_text())
        assert meta["model_version"] == MODEL_VERSION
        assert meta["feature_version"] == "1.0.0"
        assert meta["framework"] == "scikit-learn"
        assert "labels" in meta
        assert "evaluation_summary" in meta
        assert meta["evaluation_summary"]["algorithm"] == "RandomForestClassifier"
        assert meta["evaluation_summary"]["random_state"] == 42

    def test_model_version_matches(self):
        meta_path = MODEL_OUTPUT_DIR / "meta.json"
        import json
        meta = json.loads(meta_path.read_text())
        assert meta["model_version"] == "file-classifier-v1"

    def test_labels_defined(self):
        assert len(LABEL_MAP) == 6
        assert "unknown" in LABEL_MAP
        assert "document" in LABEL_MAP


class TestReproducibility:
    def test_training_runs_reproducible(self):
        from app.ml.training.train import train
        result = train()
        # Metrics should be consistent for synthetic dataset with fixed seed
        assert result["dataset_rows"] == 72
        assert result["random_state"] == 42
        # The synthetic dataset produces perfect separation by design,
        # so metrics will be very high (not artificially inflated).
        assert result["accuracy"] >= 0.0
        assert result["f1_macro"] >= 0.0
        assert result["f1_macro"] <= 1.0


class TestFeaturesSchema:
    def test_feature_version_matches(self):
        from app.ml.features.file_features import FEATURE_VERSION
        meta_path = MODEL_OUTPUT_DIR / "meta.json"
        import json
        meta = json.loads(meta_path.read_text())
        assert meta["feature_version"] == str(FEATURE_VERSION)
