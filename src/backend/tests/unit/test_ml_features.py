"""Unit tests for Phase 5 H2 — feature engineering pipeline."""

import pytest
import math
from datetime import datetime

from app.ml.features.file_features import (
    extract_features,
    get_feature_schema,
    feature_version,
    FEATURE_VERSION,
    FEATURE_NAMES,
)
from app.file_intelligence.types import FileTypeInfo, FILE_TYPE_CODE, CONTENT_KIND_SOURCE_CODE


class TestFeatureSchema:
    def test_feature_names_stable(self):
        assert "filename_length" in FEATURE_NAMES
        assert "is_supported" in FEATURE_NAMES
        assert "feature_version_str" in FEATURE_NAMES
        # Must include all expected keys
        assert len(FEATURE_NAMES) >= 15

    def test_version_str_format(self):
        assert str(FEATURE_VERSION) == "1.0.0"

    def test_get_feature_schema(self):
        schema = get_feature_schema()
        assert schema.version == FEATURE_VERSION
        assert "filename_length" in schema.features
        assert schema.description.startswith("Phase 5 H2")


class TestDeterministicFeatures:
    def test_same_input_same_output(self):
        f1 = extract_features(
            filename="README.md",
            file_type_info=FileTypeInfo(
                file_type="markdown", content_kind="markup", is_supported=True
            ),
            size_bytes=1024,
            text_content="Hello world",
            classification="notes",
            classification_confidence=0.75,
        )
        f2 = extract_features(
            filename="README.md",
            file_type_info=FileTypeInfo(
                file_type="markdown", content_kind="markup", is_supported=True
            ),
            size_bytes=1024,
            text_content="Hello world",
            classification="notes",
            classification_confidence=0.75,
        )
        assert f1 == f2
        assert f1["feature_version_str"] == "1.0.0"


class TestValidInput:
    def test_full_features(self):
        result = extract_features(
            filename="data.csv",
            file_type_info=FileTypeInfo(
                file_type="csv", content_kind="structured_data", is_supported=True
            ),
            size_bytes=2048,
            extension="csv",
            modified_at=datetime(2026, 6, 1),
            accessed_at=datetime(2026, 6, 5),
            text_content="name,age\nAlice,30\n",
            classification="data",
            classification_confidence=0.9,
            is_indexed=True,
            extraction_status="success",
            extraction_attempts=1,
        )
        assert result["filename_length"] == len("data.csv")
        assert result["filename_has_numbers"] == 0
        assert result["is_supported"] == 1
        assert result["size_bytes_log"] > 0
        assert result["text_length"] > 0
        assert result["text_line_count"] == 2  # header + 1 data row
        assert result["classification_label_idx"] == 2  # data index
        assert result["classification_confidence"] == 0.9
        assert result["is_indexed"] == 1
        assert result["extraction_status_idx"] == 2  # success index

    def test_code_file(self):
        result = extract_features(
            filename="main.py",
            file_type_info=FileTypeInfo(
                file_type="code", content_kind="source_code", is_supported=True
            ),
            size_bytes=15000,
        )
        assert result["is_supported"] == 1
        assert result["file_type_category_idx"] >= 0
        assert result["content_kind_category_idx"] >= 0
        assert result["filename_special_char_count"] >= 0


class TestMissingFields:
    def test_all_none_defaults_safe(self):
        result = extract_features()
        # Must return dict with all feature names, using safe defaults
        assert isinstance(result, dict)
        assert "filename_length" in result
        assert result["filename_length"] == 0
        assert result["is_supported"] == 0  # no file info -> unsupported
        assert result["size_bytes_log"] == 0.0
        assert result["days_since_modified"] == 0.0
        assert result["days_since_accessed"] == 0.0
        assert result["text_length"] == 0
        assert result["text_word_count"] == 0
        assert result["classification_label_idx"] == -1
        assert result["classification_confidence"] == 0.0
        assert result["feature_version_str"] == "1.0.0"

    def test_none_filename(self):
        result = extract_features(filename=None)
        assert result["filename_length"] == 0

    def test_none_size_bytes(self):
        result = extract_features(filename="test.txt", size_bytes=None)
        assert result["size_bytes_log"] == 0.0

    def test_none_text_content(self):
        result = extract_features(filename="test.txt", text_content=None)
        assert result["text_length"] == 0
        assert result["text_line_count"] == 0

    def test_none_classification(self):
        result = extract_features(filename="test.txt", classification=None)
        assert result["classification_label_idx"] == -1
        assert result["classification_confidence"] == 0.0


class TestEdgeCases:
    def test_large_size(self):
        result = extract_features(filename="big.bin", size_bytes=10**9)
        assert result["size_bytes_log"] > 20
        assert result["size_category_idx"] == len([0, 1024, 10240, 102400, 1024000, 10240000]) - 1

    def test_empty_filename(self):
        result = extract_features(filename="")
        assert result["filename_length"] == 0

    def test_special_chars_only(self):
        result = extract_features(filename="!!!_@@.txt")
        assert result["filename_special_char_count"] > 0
        assert result["filename_has_numbers"] == 0

    def test_numbers_in_filename(self):
        result = extract_features(filename="file_2024_v2.pdf")
        assert result["filename_has_numbers"] == 1
        assert result["filename_length"] == len("file_2024_v2.pdf")


class TestInvalidInputHandling:
    def test_negative_size_bytes(self):
        result = extract_features(filename="x.txt", size_bytes=-500)
        assert result["size_bytes_log"] == round(math.log(1.0), 4)  # safe_size = 0
        assert result["size_category_idx"] == 0

    def test_invalid_modified_at(self):
        result = extract_features(filename="x.txt", modified_at="not-a-date")
        assert result["days_since_modified"] == 0.0

    def test_invalid_file_type_info_fallback(self):
        # Passing a non-standard info should still work due to string conversion
        class FakeInfo:
            file_type = "unknown"
            content_kind = "other"
            extension = ""
            mime_type = ""
            display_name = "Unknown"
            is_supported = False
        result = extract_features(filename="x.txt", file_type_info=FakeInfo())
        assert "feature_version_str" in result
        assert result["is_supported"] == 0


class TestSchemaConsistency:
    def test_all_features_present(self):
        result = extract_features(filename="test.md", size_bytes=100)
        for name in FEATURE_NAMES:
            assert name in result, f"Missing feature: {name}"

    def test_feature_version_string_in_result(self):
        result = extract_features()
        assert result["feature_version_str"] == "1.0.0"
