"""Baseline file classifier (Phase 4).

NOT a machine learning model.

This is a deterministic, transparent classifier that decides the
*logical family* of a file based on:

  1. The canonical ``file_type`` from :mod:`app.file_intelligence.types`.
  2. The filename (e.g. ``"readme.md"`` → ``notes``).
  3. Heuristic content signals (e.g. "looks like notes" if the
     first 1KB contains lots of bullet points).

The label set is the spec's list:

  * ``document``   — PDFs, DOCX, long-form text
  * ``source_code`` — anything in the code family
  * ``data``        — JSON / CSV / structured data
  * ``configuration`` — YAML / TOML / XML / env / shell scripts
  * ``notes``       — markdown files that look like notes (not docs)
  * ``unknown``     — fallback when nothing matches

The interface in :func:`classify_file` is the single point of
truth — a future ML model can replace this implementation
without touching call sites.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from app.core.logging import get_logger
from app.file_intelligence.types import (
    CONTENT_KIND_BINARY,
    CONTENT_KIND_CONFIG,
    CONTENT_KIND_DOCUMENT,
    CONTENT_KIND_MARKUP,
    CONTENT_KIND_OTHER,
    CONTENT_KIND_SOURCE_CODE,
    CONTENT_KIND_STRUCTURED_DATA,
    CONTENT_KIND_TEXT,
    FILE_TYPE_CODE,
    FILE_TYPE_CSV,
    FILE_TYPE_DOCX,
    FILE_TYPE_JSON,
    FILE_TYPE_MARKDOWN,
    FILE_TYPE_PDF,
    FILE_TYPE_TXT,
    FileTypeInfo,
)

logger = get_logger(__name__)


# Canonical labels (stable, see spec 4.5).
CLASSIFICATION_LABELS: tuple[str, ...] = (
    "document",
    "source_code",
    "data",
    "configuration",
    "notes",
    "unknown",
)


# Filename patterns that push a file toward ``notes``. Intentionally
# conservative — only obvious note file names.
_NOTES_FILENAME_RE = re.compile(
    r"^(readme|notes|todo|todo\.md|scratch|journal|changelog|diary)",
    re.IGNORECASE,
)
_CONFIG_FILENAME_RE = re.compile(
    r"^(\.|_)?(env|env\..*|config|cfg|settings|setup|package|tsconfig|pyproject|"
    r"cargo\.toml|\.prettier|\.eslint|\.editorconfig|.*rc)$",
    re.IGNORECASE,
)
_CONFIG_EXTENSIONS = {".toml", ".yaml", ".yml", ".ini", ".cfg", ".env"}
_CODE_EXTENSIONS = {".sh", ".ps1", ".bat", ".cmd"}

# "Notes vs document" content signal: lots of bullet lines and
# short paragraphs.
_BULLET_RE = re.compile(r"^\s*[-*+]\s+\S", re.MULTILINE)
_NUMBERED_RE = re.compile(r"^\s*\d+\.\s+\S", re.MULTILINE)


@dataclass(frozen=True)
class FileClassification:
    """Outcome of a single :func:`classify_file` call."""

    label: str
    confidence: float
    signals: dict[str, Any]
    version: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "label": self.label,
            "confidence": self.confidence,
            "signals": self.signals,
            "version": self.version,
        }


# Mapping from ``content_kind`` → default label. The file-type
# override in :func:`classify_file` is the primary signal; this
# is the fallback.
_KIND_TO_DEFAULT_LABEL: dict[str, str] = {
    CONTENT_KIND_TEXT: "document",
    CONTENT_KIND_MARKUP: "notes",
    CONTENT_KIND_STRUCTURED_DATA: "data",
    CONTENT_KIND_SOURCE_CODE: "source_code",
    CONTENT_KIND_CONFIG: "configuration",
    CONTENT_KIND_DOCUMENT: "document",
    CONTENT_KIND_BINARY: "unknown",
    CONTENT_KIND_OTHER: "unknown",
}


_VERSION = "baseline-file-1"


def classify_file(
    *,
    filename: str,
    type_info: FileTypeInfo,
    content_preview: str = "",
) -> FileClassification:
    """Return a deterministic label + heuristic confidence for a file.

    Args:
        filename: The file's name (basename). Used for filename-based
            hints like "README" or ".env".
        type_info: The :class:`FileTypeInfo` from the registry.
        content_preview: First ~2KB of extracted text. Used for
            ``notes`` vs ``document`` disambiguation. Empty string
            is acceptable.
    """
    name = (filename or "").strip()
    signals: dict[str, Any] = {
        "filename": name,
        "file_type": type_info.file_type,
        "content_kind": type_info.content_kind,
        "is_supported": type_info.is_supported,
    }

    # Hard overrides by filename. These are the most reliable
    # signals the spec asks us to honour.
    if _NOTES_FILENAME_RE.match(name):
        signals["hint"] = "notes_filename"
        return FileClassification(
            label="notes", confidence=0.85, signals=signals, version=_VERSION
        )
    if _CONFIG_FILENAME_RE.match(name):
        signals["hint"] = "config_filename"
        return FileClassification(
            label="configuration", confidence=0.9, signals=signals, version=_VERSION
        )

    # File-type driven labels.
    label, base_confidence = _label_for_type(type_info, signals)

    # Shell / batch / powershell are configuration, not source
    # code (a .ps1 script is "shell", not "Python").
    suffix = "." + name.rsplit(".", 1)[-1].lower() if "." in name else ""
    if suffix in _CODE_EXTENSIONS:
        label = "configuration"
        base_confidence = max(base_confidence, 0.8)
        signals["hint"] = "shell_extension"
    if suffix in _CONFIG_EXTENSIONS:
        label = "configuration"
        base_confidence = max(base_confidence, 0.85)
        signals["hint"] = "config_extension"

    # Content disambiguation: markdown files that look like notes
    # vs. markdown files that look like long-form docs.
    if label == "notes" and content_preview:
        bullets = len(_BULLET_RE.findall(content_preview))
        numbered = len(_NUMBERED_RE.findall(content_preview))
        if bullets + numbered < 3 and len(content_preview) > 2_000:
            # Long markdown with few bullets → treat as a document.
            label = "document"
            base_confidence = 0.65
            signals["hint"] = "long_markdown_no_bullets"

    if not type_info.is_supported:
        label = "unknown"
        base_confidence = 0.5
        signals["hint"] = "unsupported_type"

    return FileClassification(
        label=label, confidence=round(base_confidence, 3), signals=signals, version=_VERSION
    )


def _label_for_type(
    type_info: FileTypeInfo, signals: dict[str, Any]
) -> tuple[str, float]:
    if type_info.file_type == FILE_TYPE_TXT:
        return "document", 0.7
    if type_info.file_type == FILE_TYPE_MARKDOWN:
        return "notes", 0.7
    if type_info.file_type in (FILE_TYPE_JSON, FILE_TYPE_CSV):
        return "data", 0.9
    if type_info.file_type == FILE_TYPE_CODE:
        return "source_code", 0.9
    if type_info.file_type == FILE_TYPE_PDF:
        return "document", 0.9
    if type_info.file_type == FILE_TYPE_DOCX:
        return "document", 0.9
    # Fall back to the content-kind mapping.
    return _KIND_TO_DEFAULT_LABEL.get(type_info.content_kind, "unknown"), 0.5
