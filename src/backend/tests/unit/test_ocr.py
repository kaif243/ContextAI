"""Tests for the OCR provider interface and its default implementation."""

from __future__ import annotations

import base64
import io
import json
import struct
import zlib
from pathlib import Path

import pytest

from app.ocr import OCRFactory, get_ocr_provider
from app.ocr.base import OCRProvider
from app.ocr.mock import MockOCRProvider
from app.ocr.paddle import PaddleOCRProvider
from app.ocr.tesseract import TesseractOCRProvider


# --- helpers ----------------------------------------------------------------
def _make_minimal_png(path: Path, width: int = 32, height: int = 32) -> None:
    """Write a minimal valid PNG to ``path`` (no external libs required)."""
    def _chunk(tag: bytes, data: bytes) -> bytes:
        return (
            struct.pack(">I", len(data))
            + tag
            + data
            + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
        )

    signature = b"\x89PNG\r\n\x1a\n"
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    raw = b""
    for _ in range(height):
        raw += b"\x00"  # filter byte
        raw += b"\x00\x00\x00" * width  # RGB black
    idat = zlib.compress(raw, 9)
    path.write_bytes(signature + _chunk(b"IHDR", ihdr) + _chunk(b"IDAT", idat) + _chunk(b"IEND", b""))


# --- factory ----------------------------------------------------------------
def test_factory_default_returns_mock():
    provider = OCRFactory.get_default()
    assert isinstance(provider, MockOCRProvider)
    assert provider.is_available() is True


def test_factory_create_mock():
    provider = OCRFactory.create_provider("mock")
    assert isinstance(provider, MockOCRProvider)


def test_factory_create_tesseract_class():
    provider = OCRFactory.create_provider("tesseract")
    assert isinstance(provider, TesseractOCRProvider)
    # Without pytesseract installed, is_available should be False
    # (or True if the host happens to have it). Either is acceptable;
    # what matters is the contract.


def test_factory_create_paddle_placeholder():
    provider = OCRFactory.create_provider("paddle")
    assert isinstance(provider, PaddleOCRProvider)
    assert provider.is_available() is False


def test_factory_unknown_falls_back_to_mock():
    provider = OCRFactory.create_provider("does-not-exist")
    assert isinstance(provider, MockOCRProvider)


# --- mock provider ----------------------------------------------------------
def test_mock_ocr_returns_sidecar_text(tmp_path: Path):
    image = tmp_path / "shot.png"
    _make_minimal_png(image)
    sidecar = image.with_suffix(image.suffix + ".txt")
    sidecar.write_text("Hello sidecar", encoding="utf-8")

    result = MockOCRProvider().recognize(image)
    assert result.text == "Hello sidecar"
    assert result.engine == "mock"
    assert result.confidence == 1.0
    assert result.word_count == 2
    assert result.char_count == len("Hello sidecar")


def test_mock_ocr_returns_structured_sidecar(tmp_path: Path):
    image = tmp_path / "shot.png"
    _make_minimal_png(image)
    payload = {
        "text": "alpha beta",
        "confidence": 0.91,
        "regions": [{"text": "alpha", "left": 0, "top": 0, "width": 1, "height": 1}],
    }
    (image.with_suffix(image.suffix + ".ocr.json")).write_text(
        json.dumps(payload), encoding="utf-8"
    )
    result = MockOCRProvider().recognize(image)
    assert result.text == "alpha beta"
    assert result.confidence == 0.91
    assert len(result.regions) == 1


def test_mock_ocr_generates_stub_when_no_sidecar(tmp_path: Path):
    image = tmp_path / "shot.png"
    _make_minimal_png(image, width=64, height=32)

    result = MockOCRProvider().recognize(image)
    assert "[mock-ocr]" in result.text
    assert "stub" in result.text.lower() or "sidecar" in result.text.lower()
    assert result.engine == "mock"


def test_mock_ocr_raises_for_missing_file(tmp_path: Path):
    with pytest.raises(FileNotFoundError):
        MockOCRProvider().recognize(tmp_path / "missing.png")


def test_mock_ocr_stub_is_deterministic(tmp_path: Path):
    image = tmp_path / "shot.png"
    _make_minimal_png(image, width=128, height=128)

    a = MockOCRProvider().recognize(image)
    b = MockOCRProvider().recognize(image)
    # Stub text embeds the image bytes hash; identical bytes → identical text
    assert a.text == b.text


# --- tesseract provider (interface only) ------------------------------------
def test_tesseract_provider_is_abstract_subclass():
    assert issubclass(TesseractOCRProvider, OCRProvider)


def test_tesseract_provider_recognize_without_binary_raises(tmp_path: Path):
    image = tmp_path / "shot.png"
    _make_minimal_png(image)
    provider = TesseractOCRProvider()
    if provider.is_available():
        pytest.skip("Tesseract is installed on this host; skipping negative test")
    with pytest.raises(RuntimeError):
        provider.recognize(image)


# --- paddle provider --------------------------------------------------------
def test_paddle_provider_recognize_always_raises(tmp_path: Path):
    image = tmp_path / "shot.png"
    _make_minimal_png(image)
    with pytest.raises(RuntimeError):
        PaddleOCRProvider().recognize(image)


def test_paddle_provider_is_not_available():
    assert PaddleOCRProvider().is_available() is False


# --- get_ocr_provider accessor ----------------------------------------------
def test_get_ocr_provider_returns_provider():
    provider = get_ocr_provider()
    assert isinstance(provider, OCRProvider)
