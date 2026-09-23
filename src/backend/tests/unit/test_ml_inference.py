"""Unit tests for Phase 5 H1 — ML inference abstraction and graceful fallback."""

import pytest
from pathlib import Path

from app.ml.inference import MLInference, MLResult, UnavailableMLInference
from app.ml.schemas.model_meta import ModelMeta, SchemaVersion, FeatureSchema


class TestMLResult:
    def test_to_dict(self):
        r = MLResult(label="test", confidence=0.85, model_version="v1")
        d = r.to_dict()
        assert d["label"] == "test"
        assert d["confidence"] == 0.85
        assert d["model_version"] == "v1"
        assert d["signals"] == {}

    def test_is_fallback_true(self):
        r = MLResult(label="unknown", confidence=0.0, model_version="unavailable")
        assert r.is_fallback() is True

    def test_is_fallback_false(self):
        r = MLResult(label="document", confidence=0.92, model_version="ml-v1")
        assert r.is_fallback() is False

    def test_signals_custom(self):
        r = MLResult(label="x", confidence=0.1, model_version="v1", signals={"a": 1})
        assert r.signals == {"a": 1}


class TestUnavailableMLInference:
    def test_is_available_false(self):
        inf = UnavailableMLInference()
        assert inf.is_available() is False

    def test_predict_fallback(self):
        inf = UnavailableMLInference()
        result = inf.predict({"filename": "test.pdf"})
        assert result.label == "unknown"
        assert result.confidence == 0.0
        assert result.is_fallback() is True
        assert result.model_version == "unavailable"
        assert "fallback_reason" in result.signals

    def test_predict_empty_features(self):
        inf = UnavailableMLInference()
        result = inf.predict({})
        assert result.label == "unknown"
        assert result.confidence == 0.0

    def test_get_info(self):
        inf = UnavailableMLInference()
        info = inf.get_info()
        assert info["name"] == "UnavailableMLInference"
        assert info["available"] is False
        assert info["is_ml"] is False
        assert info["fallback"] is True
        assert info["version"] == "fallback-1"

    def test_load_model_returns_false(self):
        inf = UnavailableMLInference()
        assert inf.load_model(Path("/fake/model.pkl")) is False


class TestModelMeta:
    def test_default_version(self):
        meta = ModelMeta(model_version="v1")
        assert meta.framework == "scikit-learn"
        assert meta.created_at != ""
        assert meta.feature_version == SchemaVersion()

    def test_to_dict(self):
        meta = ModelMeta(
            model_version="file-v1",
            feature_version=SchemaVersion(major=1, minor=2),
            framework="scikit-learn",
            labels=("document", "code"),
            dataset_hash="abc123",
            evaluation_summary={"f1": 0.95},
        )
        d = meta.to_dict()
        assert d["model_version"] == "file-v1"
        assert d["feature_version"] == "1.2.0"
        assert d["labels"] == ["document", "code"]
        assert d["dataset_hash"] == "abc123"


class TestSchemaVersion:
    def test_str(self):
        sv = SchemaVersion(major=2, minor=1, patch=0)
        assert str(sv) == "2.1.0"

    def test_default(self):
        sv = SchemaVersion()
        assert str(sv) == "1.0.0"
