"""Tests for the Phase 2 Screenshot and ScreenAnalysis models."""

from __future__ import annotations

import json
import struct
import zlib
from pathlib import Path

import pytest

from app.classification import get_activity_classifier
from app.ocr import get_ocr_provider
from app.services.screen_service import ScreenService


def _make_minimal_png(path: Path, width: int = 64, height: int = 64) -> None:
    def _chunk(tag: bytes, data: bytes) -> bytes:
        return (
            struct.pack(">I", len(data))
            + tag
            + data
            + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
        )

    signature = b"\x89PNG\r\n\x1a\n"
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    raw = b"\x00" + b"\x00\x00\x00" * width
    raw = raw * height
    idat = zlib.compress(raw, 9)
    path.write_bytes(signature + _chunk(b"IHDR", ihdr) + _chunk(b"IDAT", idat) + _chunk(b"IEND", b""))


def _sidecar(path: Path, text: str) -> None:
    path.with_suffix(path.suffix + ".txt").write_text(text, encoding="utf-8")


def test_register_capture_persists_screenshot(db_session, tmp_path):
    image = tmp_path / "shot.png"
    _make_minimal_png(image)
    _sidecar(image, "def hello():\n    return 42\n")

    service = ScreenService(
        db_session,
        ocr_provider=get_ocr_provider(),
        classifier=get_activity_classifier(),
    )
    screenshot = service.register_capture(
        image_path=str(image),
        width=64,
        height=64,
        source_app="code.exe",
    )

    assert screenshot.id is not None
    assert screenshot.content_hash is not None
    assert screenshot.file_size_bytes > 0
    assert screenshot.ocr_text is not None
    assert "hello" in screenshot.ocr_text
    assert screenshot.classification == "code"
    assert screenshot.classifier_version is not None
    assert screenshot.classifier_version.startswith("baseline")
    assert screenshot.extracted_entities is not None
    assert "extra" in screenshot.extracted_entities
    assert "word_count" in screenshot.extracted_entities["extra"]


def test_register_capture_rejects_missing_file(db_session, tmp_path):
    service = ScreenService(
        db_session,
        ocr_provider=get_ocr_provider(),
        classifier=get_activity_classifier(),
    )
    with pytest.raises(FileNotFoundError):
        service.register_capture(
            image_path=str(tmp_path / "missing.png"),
            width=64,
            height=64,
        )


def test_register_capture_rejects_oversize(db_session, tmp_path, monkeypatch):
    image = tmp_path / "shot.png"
    _make_minimal_png(image, width=2000, height=2000)
    # Lower the limit to force rejection
    from app.core.config import settings as cfg
    monkeypatch.setattr(cfg, "max_screenshot_bytes", 10)
    service = ScreenService(
        db_session,
        ocr_provider=get_ocr_provider(),
        classifier=get_activity_classifier(),
    )
    with pytest.raises(ValueError):
        service.register_capture(
            image_path=str(image),
            width=2000,
            height=2000,
        )


def test_register_capture_with_ocr_disabled(db_session, tmp_path, monkeypatch):
    from app.core.config import settings as cfg
    monkeypatch.setattr(cfg, "ocr_enabled", False)
    image = tmp_path / "shot.png"
    _make_minimal_png(image)
    _sidecar(image, "should not be read")

    service = ScreenService(
        db_session,
        ocr_provider=get_ocr_provider(),
        classifier=get_activity_classifier(),
    )
    screenshot = service.register_capture(
        image_path=str(image),
        width=64,
        height=64,
    )
    assert screenshot.ocr_text is None
    assert screenshot.classification is None


def test_register_capture_with_region(db_session, tmp_path):
    image = tmp_path / "shot.png"
    _make_minimal_png(image, width=400, height=200)
    _sidecar(image, "Receipt $5.00")

    service = ScreenService(
        db_session,
        ocr_provider=get_ocr_provider(),
        classifier=get_activity_classifier(),
    )
    screenshot = service.register_capture(
        image_path=str(image),
        width=400,
        height=200,
        region={"x": 10, "y": 20, "width": 300, "height": 150},
        monitor_index=1,
    )
    assert screenshot.region_x == 10
    assert screenshot.region_y == 20
    assert screenshot.region_width == 300
    assert screenshot.region_height == 150
    assert screenshot.monitor_index == 1


def test_list_recent_filters_by_classification(db_session, tmp_path):
    service = ScreenService(
        db_session,
        ocr_provider=get_ocr_provider(),
        classifier=get_activity_classifier(),
    )
    code_img = tmp_path / "code.png"
    _make_minimal_png(code_img)
    _sidecar(code_img, "def f():\n    pass\n")
    service.register_capture(image_path=str(code_img), width=64, height=64)

    receipt_img = tmp_path / "receipt.png"
    _make_minimal_png(receipt_img)
    _sidecar(receipt_img, "Receipt $5.00 Total $5.00")
    service.register_capture(image_path=str(receipt_img), width=64, height=64)

    code_items, total = service.list_recent(classification="code")
    assert total == 1
    assert code_items[0].classification == "code"


def test_re_analyse_updates_fields(db_session, tmp_path):
    image = tmp_path / "shot.png"
    _make_minimal_png(image)
    _sidecar(image, "def f():\n    pass\n")
    service = ScreenService(
        db_session,
        ocr_provider=get_ocr_provider(),
        classifier=get_activity_classifier(),
    )
    s = service.register_capture(image_path=str(image), width=64, height=64)
    assert s.classification == "code"

    # Replace the sidecar with receipt text and re-analyse
    image.with_suffix(image.suffix + ".txt").write_text("Receipt $9.99 Total $9.99", encoding="utf-8")
    s2 = service.re_analyse(s.id)
    assert s2.classification == "receipt"


def test_delete_screenshot(db_session, tmp_path):
    image = tmp_path / "shot.png"
    _make_minimal_png(image)
    _sidecar(image, "hello")
    service = ScreenService(
        db_session,
        ocr_provider=get_ocr_provider(),
        classifier=get_activity_classifier(),
    )
    s = service.register_capture(image_path=str(image), width=64, height=64)
    assert service.delete(s.id) is True
    assert service.get(s.id) is None


def test_archive_screenshot(db_session, tmp_path):
    image = tmp_path / "shot.png"
    _make_minimal_png(image)
    _sidecar(image, "hello")
    service = ScreenService(
        db_session,
        ocr_provider=get_ocr_provider(),
        classifier=get_activity_classifier(),
    )
    s = service.register_capture(image_path=str(image), width=64, height=64)
    updated = service.set_archived(s.id, True)
    assert updated.is_archived is True


def test_screenshot_to_dict_round_trip(db_session, tmp_path):
    image = tmp_path / "shot.png"
    _make_minimal_png(image)
    _sidecar(image, "def f():\n    return 'x'\n")
    service = ScreenService(
        db_session,
        ocr_provider=get_ocr_provider(),
        classifier=get_activity_classifier(),
    )
    s = service.register_capture(image_path=str(image), width=64, height=64)
    d = s.to_dict()
    # Round-trip the dict through JSON to ensure it's serialisable.
    blob = json.dumps(d)
    again = json.loads(blob)
    assert again["id"] == str(s.id)
    assert again["classification"]["label"] == "code"
    assert again["ocr"]["text"]
