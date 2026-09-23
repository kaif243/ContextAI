"""Focused tests for Phase 5 H5 — ML Evaluation (SYNTHETIC / DEMONSTRATION ONLY)."""

import json
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from app.ml.evaluation.evaluate import (
    SYNTHETIC_LABEL,
    DEFAULT_DATASET,
    DEFAULT_MODEL,
    DEFAULT_META,
    evaluate_model_artifact,
    validate_inputs,
)


class TestSyntheticLabeling:
    def test_result_has_synthetic_label(self):
        result = evaluate_model_artifact()
        assert result.get("synthetic_label") == SYNTHETIC_LABEL
        assert SYNTHETIC_LABEL in result.get("status", "")
        assert "SYNTHETIC" in result.get("note", "")
        assert "DEMONSTRATION ONLY" in result.get("note", "")

    def test_note_warns_against_real_world_interpretation(self):
        result = evaluate_model_artifact()
        note = result.get("note", "")
        assert "must not be interpreted as real-world" in note


class TestMetricCompleteness:
    def test_accuracy_present(self):
        result = evaluate_model_artifact()
        assert "metrics" in result
        assert "accuracy" in result["metrics"]
        assert 0.0 <= result["metrics"]["accuracy"] <= 1.0

    def test_macro_metrics_present(self):
        result = evaluate_model_artifact()
        metrics = result["metrics"]
        assert "precision_macro" in metrics
        assert "recall_macro" in metrics
        assert "f1_macro" in metrics

    def test_per_class_has_all_classes(self):
        result = evaluate_model_artifact()
        per_class = result["metrics"]["per_class"]
        expected = result.get("labels_ordered", [])
        for label in expected:
            assert label in per_class
            assert "precision" in per_class[label]
            assert "recall" in per_class[label]
            assert "f1" in per_class[label]
            assert "support" in per_class[label]
            assert isinstance(per_class[label]["support"], int)

    def test_confusion_matrix_shape(self):
        result = evaluate_model_artifact()
        cm = result["metrics"]["confusion_matrix"]
        labels = result.get("labels_ordered", [])
        assert len(cm) == len(labels)
        for row in cm:
            assert len(row) == len(labels)
            assert all(isinstance(x, int) for x in row)

    def test_row_count_and_hashes(self):
        result = evaluate_model_artifact()
        assert result["dataset_rows"] == 72
        assert result.get("dataset_hash") == "dataset_v1_72_rows_seed42"
        assert result.get("dataset_file_hash") is not None
        assert len(result.get("dataset_file_hash", "")) >= 4

    def test_model_version_and_feature_version_propagated(self):
        result = evaluate_model_artifact()
        assert result["model_version"] == "file-classifier-v1"
        assert result["feature_version"] == "1.0.0"
        assert result.get("algorithm") is not None


class TestValidation:
    def test_missing_dataset_raises(self, tmp_path):
        fake_model = DEFAULT_MODEL
        fake_meta = DEFAULT_META
        fake_dataset = tmp_path / "missing.csv"
        with pytest.raises(ValueError) as exc_info:
            validate_inputs(fake_dataset, fake_model, fake_meta)
        assert "Dataset missing" in str(exc_info.value)

    def test_missing_model_raises(self, tmp_path):
        fake_dataset = DEFAULT_DATASET
        fake_model = tmp_path / "missing_model.joblib"
        fake_meta = DEFAULT_META
        with pytest.raises(ValueError) as exc_info:
            validate_inputs(fake_dataset, fake_model, fake_meta)
        assert "Model artifact missing" in str(exc_info.value)

    def test_missing_metadata_raises(self, tmp_path):
        fake_dataset = DEFAULT_DATASET
        fake_model = DEFAULT_MODEL
        fake_meta = tmp_path / "missing_meta.json"
        with pytest.raises(ValueError) as exc_info:
            validate_inputs(fake_dataset, fake_model, fake_meta)
        assert "Metadata missing" in str(exc_info.value)

    def test_incompatible_feature_version_raises(self, tmp_path):
        # Create a dataset with wrong feature_version_str
        df = pd.read_csv(DEFAULT_DATASET)
        df["feature_version_str"] = "99.99.99"
        bad_dataset = tmp_path / "bad_version.csv"
        df.to_csv(bad_dataset, index=False)
        with pytest.raises(ValueError) as exc_info:
            validate_inputs(bad_dataset, DEFAULT_MODEL, DEFAULT_META)
        assert "Feature version incompatibility" in str(exc_info.value)

    def test_invalid_metadata_raises(self, tmp_path):
        bad_meta = tmp_path / "bad_meta.json"
        bad_meta.write_text("not json")
        with pytest.raises(ValueError) as exc_info:
            validate_inputs(DEFAULT_DATASET, DEFAULT_MODEL, bad_meta)
        assert "Invalid/malformed metadata" in str(exc_info.value)

    def test_incompatible_model_version_raises(self, tmp_path):
        bad_meta = tmp_path / "bad_version_meta.json"
        bad_meta.write_text(json.dumps({
            "model_version": "wrong",
            "feature_version": "1.0.0",
            "framework": "scikit-learn",
            "labels": ["document", "source_code", "data", "configuration", "notes", "unknown"],
            "dataset_hash": "test",
        }))
        with pytest.raises(ValueError) as exc_info:
            validate_inputs(DEFAULT_DATASET, DEFAULT_MODEL, bad_meta)
        assert "Model version mismatch" in str(exc_info.value)


class TestDeterminism:
    def test_repeated_evaluations_are_identical(self):
        r1 = evaluate_model_artifact()
        r2 = evaluate_model_artifact()
        assert r1["metrics"]["accuracy"] == r2["metrics"]["accuracy"]
        assert r1["metrics"]["f1_macro"] == r2["metrics"]["f1_macro"]
        assert r1["metrics"]["confusion_matrix"] == r2["metrics"]["confusion_matrix"]
        assert r1["dataset_file_hash"] == r2["dataset_file_hash"]
        assert r1["dataset_hash"] == r2["dataset_hash"]
