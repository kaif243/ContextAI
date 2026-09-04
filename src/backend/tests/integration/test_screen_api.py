"""Integration tests for the Phase 2 screen API endpoints."""

from __future__ import annotations

import base64
import struct
import zlib
from pathlib import Path

import pytest


def _make_minimal_png(width: int = 64, height: int = 64) -> bytes:
    def _chunk(tag: bytes, data: bytes) -> bytes:
        return (
            struct.pack(">I", len(data))
            + tag
            + data
            + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
        )

    signature = b"\x89PNG\r\n\x1a\n"
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    raw = (b"\x00" + b"\x00\x00\x00" * width) * height
    idat = zlib.compress(raw, 9)
    return signature + _chunk(b"IHDR", ihdr) + _chunk(b"IDAT", idat) + _chunk(b"IEND", b"")


def test_ocr_info_endpoint(client):
    response = client.get("/api/v1/screen/ocr/info")
    assert response.status_code == 200
    data = response.json()
    assert data["provider"] == "mock"
    assert data["available"] is True
    assert data["is_ml"] is False
    assert "note" in data


def test_classifier_info_endpoint(client):
    response = client.get("/api/v1/screen/classifier/info")
    assert response.status_code == 200
    data = response.json()
    assert data["is_ml"] is False
    assert data["version"].startswith("baseline")
    assert data["label_count"] >= 10


def test_capture_with_image_path(client, tmp_path, monkeypatch):
    from app.core.config import settings as cfg
    monkeypatch.setattr(cfg, "screenshots_dir", tmp_path / "shots")
    cfg.screenshots_dir.mkdir(parents=True, exist_ok=True)

    image = tmp_path / "code.png"
    image.write_bytes(_make_minimal_png())
    # Sidecar so the mock OCR returns real text
    image.with_suffix(image.suffix + ".txt").write_text("import os\ndef hi():\n    pass\n", encoding="utf-8")

    response = client.post(
        "/api/v1/screen/capture",
        json={
            "image_path": str(image),
            "width": 64,
            "height": 64,
            "source_app": "code.exe",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["screenshot_id"] is not None
    assert data["classification"] == "code"
    assert data["ocr_engine"] == "mock"
    assert data["classifier_version"].startswith("baseline")
    assert "extracted_entities" in data


def test_capture_with_base64_image(client, tmp_path, monkeypatch):
    from app.core.config import settings as cfg
    monkeypatch.setattr(cfg, "screenshots_dir", tmp_path / "shots")
    cfg.screenshots_dir.mkdir(parents=True, exist_ok=True)

    raw = _make_minimal_png()
    response = client.post(
        "/api/v1/screen/capture",
        json={
            "image_base64": base64.b64encode(raw).decode("ascii"),
            "width": 64,
            "height": 64,
            "save_to_disk": True,
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["screenshot_id"] is not None


def test_capture_rejects_missing_path(client):
    response = client.post(
        "/api/v1/screen/capture",
        json={"image_path": "/no/such/file.png", "width": 64, "height": 64},
    )
    assert response.status_code == 400


def test_capture_rejects_missing_both(client):
    response = client.post(
        "/api/v1/screen/capture",
        json={"width": 64, "height": 64},
    )
    assert response.status_code == 400


def test_capture_rejects_oversize(client, tmp_path, monkeypatch):
    from app.core.config import settings as cfg
    monkeypatch.setattr(cfg, "max_screenshot_bytes", 16)
    raw = _make_minimal_png(width=256, height=256)
    response = client.post(
        "/api/v1/screen/capture",
        json={
            "image_base64": base64.b64encode(raw).decode("ascii"),
            "width": 256,
            "height": 256,
        },
    )
    assert response.status_code == 413


def test_list_and_get_screenshot(client, tmp_path, monkeypatch):
    from app.core.config import settings as cfg
    monkeypatch.setattr(cfg, "screenshots_dir", tmp_path / "shots")
    cfg.screenshots_dir.mkdir(parents=True, exist_ok=True)

    image = tmp_path / "x.png"
    image.write_bytes(_make_minimal_png())
    image.with_suffix(image.suffix + ".txt").write_text("Receipt $5.00 Total $5.00", encoding="utf-8")

    cap = client.post(
        "/api/v1/screen/capture",
        json={"image_path": str(image), "width": 64, "height": 64},
    )
    screenshot_id = cap.json()["screenshot_id"]

    response = client.get("/api/v1/screen")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] >= 1
    assert any(item["id"] == str(screenshot_id) for item in data["items"])

    detail = client.get(f"/api/v1/screen/{screenshot_id}")
    assert detail.status_code == 200
    detail_data = detail.json()
    assert detail_data["id"] == str(screenshot_id)
    assert "ocr" in detail_data
    assert "classification" in detail_data


def test_get_unknown_screenshot_returns_404(client):
    response = client.get("/api/v1/screen/9999")
    assert response.status_code == 404


def test_update_screenshot_notes_and_archive(client, tmp_path, monkeypatch):
    from app.core.config import settings as cfg
    monkeypatch.setattr(cfg, "screenshots_dir", tmp_path / "shots")
    cfg.screenshots_dir.mkdir(parents=True, exist_ok=True)
    image = tmp_path / "x.png"
    image.write_bytes(_make_minimal_png())
    image.with_suffix(image.suffix + ".txt").write_text("hello", encoding="utf-8")

    cap = client.post(
        "/api/v1/screen/capture",
        json={"image_path": str(image), "width": 64, "height": 64},
    )
    sid = cap.json()["screenshot_id"]

    response = client.patch(
        f"/api/v1/screen/{sid}",
        json={"notes": "Important reference", "is_archived": True},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["user_notes"] == "Important reference"
    assert data["is_archived"] is True


def test_reanalyse_endpoint(client, tmp_path, monkeypatch):
    from app.core.config import settings as cfg
    monkeypatch.setattr(cfg, "screenshots_dir", tmp_path / "shots")
    cfg.screenshots_dir.mkdir(parents=True, exist_ok=True)
    image = tmp_path / "x.png"
    image.write_bytes(_make_minimal_png())
    image.with_suffix(image.suffix + ".txt").write_text("def f():\n    pass\n", encoding="utf-8")

    cap = client.post(
        "/api/v1/screen/capture",
        json={"image_path": str(image), "width": 64, "height": 64},
    )
    sid = cap.json()["screenshot_id"]

    # Change the sidecar and re-analyse.
    image.with_suffix(image.suffix + ".txt").write_text("Receipt $9.99 Total $9.99", encoding="utf-8")
    response = client.post(f"/api/v1/screen/{sid}/reanalyse")
    assert response.status_code == 200
    assert response.json()["classification"] == "receipt"


def test_ask_question_records_error_when_no_llm(client, tmp_path, monkeypatch):
    """The Q&A endpoint should always return a row, with is_error=True when
    the LLM is not available in the test environment."""
    from app.core.config import settings as cfg
    monkeypatch.setattr(cfg, "screenshots_dir", tmp_path / "shots")
    cfg.screenshots_dir.mkdir(parents=True, exist_ok=True)
    image = tmp_path / "x.png"
    image.write_bytes(_make_minimal_png())
    image.with_suffix(image.suffix + ".txt").write_text("error: file not found", encoding="utf-8")

    cap = client.post(
        "/api/v1/screen/capture",
        json={"image_path": str(image), "width": 64, "height": 64},
    )
    sid = cap.json()["screenshot_id"]

    response = client.post(
        f"/api/v1/screen/{sid}/ask",
        json={"question": "What is wrong?"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["screenshot_id"] == sid
    assert data["analysis_type"] == "qa"
    assert data["question"] == "What is wrong?"
    # No LLM in the test env → is_error should be True and answer should mention the failure.
    assert data["is_error"] is True
    assert data["error_message"]


def test_ask_question_rejects_empty(client, tmp_path, monkeypatch):
    from app.core.config import settings as cfg
    monkeypatch.setattr(cfg, "screenshots_dir", tmp_path / "shots")
    cfg.screenshots_dir.mkdir(parents=True, exist_ok=True)
    image = tmp_path / "x.png"
    image.write_bytes(_make_minimal_png())
    image.with_suffix(image.suffix + ".txt").write_text("hi", encoding="utf-8")

    cap = client.post(
        "/api/v1/screen/capture",
        json={"image_path": str(image), "width": 64, "height": 64},
    )
    sid = cap.json()["screenshot_id"]

    response = client.post(
        f"/api/v1/screen/{sid}/ask",
        json={"question": "   "},
    )
    assert response.status_code == 400


def test_summarise_endpoint(client, tmp_path, monkeypatch):
    from app.core.config import settings as cfg
    monkeypatch.setattr(cfg, "screenshots_dir", tmp_path / "shots")
    cfg.screenshots_dir.mkdir(parents=True, exist_ok=True)
    image = tmp_path / "x.png"
    image.write_bytes(_make_minimal_png())
    image.with_suffix(image.suffix + ".txt").write_text("Lecture on transformers at 10:00 AM", encoding="utf-8")

    cap = client.post(
        "/api/v1/screen/capture",
        json={"image_path": str(image), "width": 64, "height": 64},
    )
    sid = cap.json()["screenshot_id"]

    response = client.post(f"/api/v1/screen/{sid}/summarise")
    assert response.status_code == 200
    data = response.json()
    assert data["analysis_type"] == "summary"
    # No LLM in the test env → is_error should be True.
    assert data["is_error"] is True


def test_ask_unknown_screenshot_returns_404(client):
    response = client.post("/api/v1/screen/9999/ask", json={"question": "why?"})
    assert response.status_code == 404


def test_list_analyses_endpoint(client, tmp_path, monkeypatch):
    from app.core.config import settings as cfg
    monkeypatch.setattr(cfg, "screenshots_dir", tmp_path / "shots")
    cfg.screenshots_dir.mkdir(parents=True, exist_ok=True)
    image = tmp_path / "x.png"
    image.write_bytes(_make_minimal_png())
    image.with_suffix(image.suffix + ".txt").write_text("hello", encoding="utf-8")

    cap = client.post(
        "/api/v1/screen/capture",
        json={"image_path": str(image), "width": 64, "height": 64},
    )
    sid = cap.json()["screenshot_id"]

    # Trigger a recorded analysis
    client.post(f"/api/v1/screen/{sid}/ask", json={"question": "why?"})

    response = client.get(f"/api/v1/screen/{sid}/analyses")
    assert response.status_code == 200
    items = response.json()
    assert len(items) >= 1
    assert items[0]["analysis_type"] == "qa"


def test_delete_screenshot(client, tmp_path, monkeypatch):
    from app.core.config import settings as cfg
    monkeypatch.setattr(cfg, "screenshots_dir", tmp_path / "shots")
    cfg.screenshots_dir.mkdir(parents=True, exist_ok=True)
    image = tmp_path / "x.png"
    image.write_bytes(_make_minimal_png())
    image.with_suffix(image.suffix + ".txt").write_text("hello", encoding="utf-8")

    cap = client.post(
        "/api/v1/screen/capture",
        json={"image_path": str(image), "width": 64, "height": 64},
    )
    sid = cap.json()["screenshot_id"]

    response = client.delete(f"/api/v1/screen/{sid}")
    assert response.status_code == 200
    assert response.json()["success"] is True

    detail = client.get(f"/api/v1/screen/{sid}")
    assert detail.status_code == 404


def test_health_reports_ocr_and_classifier(client):
    """Phase 2 should make the health check report OCR + classifier status."""
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    services = data["services"]
    assert services["ocr"] is True  # mock is always available
    assert services["activity_classifier"] is True  # baseline is always available
