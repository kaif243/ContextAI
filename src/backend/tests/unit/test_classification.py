"""Tests for the baseline (rule-based) screen activity classifier.

These tests are intentionally written to make the "NOT ML" promise
explicit: every assertion can be traced back to a rule in
``app.classification.baseline``. If a test ever asserts something
``baseline`` cannot produce, the implementation is wrong (or the
classifier is no longer a pure baseline).
"""

from __future__ import annotations

import pytest

from app.classification import (
    BaselineActivityClassifier,
    ClassificationInput,
    get_activity_classifier,
)
from app.classification.base import CLASSIFICATION_LABELS


# --- helpers ----------------------------------------------------------------
def _classify(text: str, source_app: str | None = None, window_title: str | None = None) -> dict:
    clf = BaselineActivityClassifier()
    res = clf.classify(
        ClassificationInput(
            ocr_text=text,
            image_width=1920,
            image_height=1080,
            source_app=source_app,
            window_title=window_title,
        )
    )
    return res.to_dict()


# --- metadata ---------------------------------------------------------------
def test_classifier_metadata_marks_baseline_as_not_ml():
    clf = get_activity_classifier()
    info = clf.get_info()
    assert info["is_ml"] is False
    assert info["version"].startswith("baseline")


def test_classifier_default_is_baseline():
    clf = get_activity_classifier()
    assert isinstance(clf, BaselineActivityClassifier)


def test_classification_labels_are_stable():
    # Downstream analytics / dashboards index by label string. Any change
    # here is a breaking change and must be intentional.
    assert "code" in CLASSIFICATION_LABELS
    assert "error" in CLASSIFICATION_LABELS
    assert "document" in CLASSIFICATION_LABELS
    assert "receipt" in CLASSIFICATION_LABELS
    assert "timetable" in CLASSIFICATION_LABELS
    assert "table" in CLASSIFICATION_LABELS
    assert "form" in CLASSIFICATION_LABELS
    assert "webpage" in CLASSIFICATION_LABELS
    assert "image" in CLASSIFICATION_LABELS
    assert "general_ui" in CLASSIFICATION_LABELS
    assert "unknown" in CLASSIFICATION_LABELS


# --- rule behaviour ---------------------------------------------------------
def test_python_traceback_classified_as_error():
    text = (
        "Traceback (most recent call last):\n"
        "  File 'app.py', line 12\n"
        "ModuleNotFoundError: No module named 'pandas'\n"
    )
    result = _classify(text)
    assert result["label"] == "error"
    assert result["confidence"] > 0
    assert "rule_hits" in result["signals"]


def test_python_code_classified_as_code():
    text = (
        "import os\n"
        "from typing import List\n"
        "def hello(name: str) -> str:\n"
        "    return f'hi {name}'\n"
    )
    result = _classify(text)
    assert result["label"] == "code"


def test_receipt_classified_as_receipt():
    text = (
        "Receipt\n"
        "Subtotal: $10.00\n"
        "Tax: $1.00\n"
        "Total: $11.00\n"
        "Visa **** 1234\n"
    )
    result = _classify(text)
    assert result["label"] == "receipt"


def test_timetable_classified_as_timetable():
    text = (
        "CS101 Lecture - Monday 9:00 AM\n"
        "ML Lab - Tuesday 10:00 AM\n"
        "Spring Semester\n"
    )
    result = _classify(text)
    assert result["label"] == "timetable"


def test_login_form_classified_as_form():
    text = (
        "Sign in\n"
        "Please enter your email and password\n"
        "Required field\n"
        "[Submit]\n"
    )
    result = _classify(text)
    assert result["label"] == "form"


def test_webpage_classified_as_webpage():
    text = (
        "https://example.com/article\n"
        "Home / About / Blog\n"
        "Main navigation\n"
    )
    result = _classify(text)
    assert result["label"] == "webpage"


def test_document_with_chapter_classified_as_document():
    text = (
        "Chapter 1. Introduction\n"
        "This paper describes...\n"
        "References\n"
        "Bibliography\n"
        "Page 1 of 12\n"
    )
    result = _classify(text)
    assert result["label"] == "document"


def test_empty_text_returns_unknown():
    result = _classify("")
    assert result["label"] == "unknown"
    assert result["confidence"] == 0.0


def test_irrelevant_text_returns_unknown():
    # Use a small image so the low-text-density rule does NOT push the
    # decision toward "image".
    from app.classification import ClassificationInput, BaselineActivityClassifier

    res = BaselineActivityClassifier().classify(
        ClassificationInput(
            ocr_text="hello world foo bar",
            image_width=64,
            image_height=64,
        )
    )
    assert res.label in ("unknown", "general_ui")


def test_app_hint_used_when_ocr_weak():
    # OCR yields almost nothing, but the source app is VS Code.
    result = _classify("", source_app="Code.exe")
    assert result["label"] == "code"
    assert result["signals"].get("app_hint") == "code"


def test_window_title_can_drive_classification():
    result = _classify("ok", window_title="Microsoft Excel - Book1.xlsx")
    assert result["label"] == "table"


def test_low_text_density_pushes_image_label():
    text = "small"  # 5 chars / (1920*1080) ≈ 2.4e-6, very low
    # Build a ClassificationInput directly so we can use a large image.
    from app.classification import ClassificationInput, BaselineActivityClassifier

    res = BaselineActivityClassifier().classify(
        ClassificationInput(
            ocr_text=text,
            image_width=1920,
            image_height=1080,
        )
    )
    scores = res.signals.get("scores", {})
    assert scores.get("image", 0.0) >= 1.0


def test_classifier_is_deterministic():
    text = "import os\ndef f():\n    pass\n"
    a = _classify(text)
    b = _classify(text)
    assert a == b


def test_confidence_is_bounded():
    long_code = "import os\n" * 500 + "def f():\n    pass\n" * 200
    result = _classify(long_code)
    assert 0.0 <= result["confidence"] <= 1.0
