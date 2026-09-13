"""File-format detection and type registry.

This module is the single source of truth for *what* a file is. It
maps file extensions and MIME types to:

  * a stable ``file_type`` string stored in the database
  * a logical ``content_kind`` used by the baseline classifier
  * the human-readable display name used by the UI

The registry is intentionally a hand-written constant. The Phase 1
spec says we must not install heavyweight magic-byte libraries
(``python-magic`` requires a system ``libmagic`` binary, which is
fragile to install on Windows). Extension + MIME-type detection
covers all the formats we explicitly support and keeps the
"unsupported" path deterministic.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

# ---------------------------------------------------------------------------
# Canonical labels
# ---------------------------------------------------------------------------
# Keep this list stable; downstream services and the API contract
# index ML dashboards and analytics by ``file_type`` string.

FILE_TYPE_TXT = "text"
FILE_TYPE_MARKDOWN = "markdown"
FILE_TYPE_JSON = "json"
FILE_TYPE_CSV = "csv"
FILE_TYPE_CODE = "code"
FILE_TYPE_PDF = "pdf"
FILE_TYPE_DOCX = "docx"
FILE_TYPE_OTHER = "other"
FILE_TYPE_UNSUPPORTED = "unsupported"

# ``content_kind`` is the *logical* family the baseline classifier
# cares about. The classifier groups ``code``/``python``/``javascript``
# under one ``source_code`` family, ``json``/``csv`` under ``data``,
# etc.
CONTENT_KIND_TEXT = "text"
CONTENT_KIND_MARKUP = "markup"  # markdown / html
CONTENT_KIND_STRUCTURED_DATA = "structured_data"  # json / csv
CONTENT_KIND_SOURCE_CODE = "source_code"
CONTENT_KIND_CONFIG = "config"
CONTENT_KIND_DOCUMENT = "document"  # pdf / docx
CONTENT_KIND_BINARY = "binary"
CONTENT_KIND_OTHER = "other"


@dataclass(frozen=True)
class _Entry:
    """Internal entry in the file-type registry."""

    file_type: str
    content_kind: str
    extensions: tuple[str, ...]
    mime_types: tuple[str, ...]
    display_name: str
    is_supported: bool


# Hand-written extension / MIME registry. Order does not matter for
# resolution; ``detect_file_type`` does an exact match.
_REGISTRY: tuple[_Entry, ...] = (
    # --- text / markdown ---
    _Entry(
        file_type=FILE_TYPE_TXT,
        content_kind=CONTENT_KIND_TEXT,
        extensions=("txt", "log", "env"),
        mime_types=("text/plain",),
        display_name="Plain Text",
        is_supported=True,
    ),
    _Entry(
        file_type=FILE_TYPE_MARKDOWN,
        content_kind=CONTENT_KIND_MARKUP,
        extensions=("md", "markdown", "mdx"),
        mime_types=("text/markdown",),
        display_name="Markdown",
        is_supported=True,
    ),
    # --- structured data ---
    _Entry(
        file_type=FILE_TYPE_JSON,
        content_kind=CONTENT_KIND_STRUCTURED_DATA,
        extensions=("json",),
        mime_types=("application/json",),
        display_name="JSON",
        is_supported=True,
    ),
    _Entry(
        file_type=FILE_TYPE_CSV,
        content_kind=CONTENT_KIND_STRUCTURED_DATA,
        extensions=("csv", "tsv"),
        mime_types=("text/csv", "text/tab-separated-values"),
        display_name="CSV",
        is_supported=True,
    ),
    # --- source code ---
    _Entry(
        file_type=FILE_TYPE_CODE,
        content_kind=CONTENT_KIND_SOURCE_CODE,
        extensions=(
            "py", "pyi", "pyw",
            "js", "mjs", "cjs",
            "ts", "tsx", "jsx",
            "rs",
            "go",
            "java",
            "c", "h",
            "cpp", "cc", "cxx", "hpp", "hxx",
            "rb",
            "php",
            "sh", "bash", "zsh",
            "ps1",
            "yaml", "yml",
            "toml",
            "xml",
            "html", "htm", "css", "scss", "less",
            "sql",
        ),
        mime_types=(
            "text/x-python",
            "application/javascript",
            "text/typescript",
            "text/x-rust",
            "text/x-go",
            "text/x-java-source",
            "text/x-c",
            "text/x-c++",
            "text/x-shellscript",
            "application/x-shellscript",
            "text/x-yaml",
            "application/yaml",
            "text/x-toml",
            "application/xml",
            "text/html",
            "text/css",
            "text/x-sql",
        ),
        display_name="Source Code",
        is_supported=True,
    ),
    # --- documents (Phase 4: best-effort extraction) ---
    _Entry(
        file_type=FILE_TYPE_PDF,
        content_kind=CONTENT_KIND_DOCUMENT,
        extensions=("pdf",),
        mime_types=("application/pdf",),
        display_name="PDF",
        is_supported=True,
    ),
    _Entry(
        file_type=FILE_TYPE_DOCX,
        content_kind=CONTENT_KIND_DOCUMENT,
        extensions=("docx",),
        mime_types=(
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ),
        display_name="Word Document",
        is_supported=True,
    ),
)


# Indexes for O(1) lookup.
_BY_EXT: dict[str, _Entry] = {}
_BY_MIME: dict[str, _Entry] = {}
for _e in _REGISTRY:
    for _ext in _e.extensions:
        _BY_EXT[_ext.lower()] = _e
    for _mime in _e.mime_types:
        _BY_MIME[_mime.lower()] = _e


def _norm_ext(ext: str | None) -> str:
    if not ext:
        return ""
    return ext.lstrip(".").lower().strip()


def _norm_mime(mime: str | None) -> str:
    if not mime:
        return ""
    return mime.split(";", 1)[0].strip().lower()


@dataclass(frozen=True)
class FileTypeInfo:
    """Result of :func:`detect_file_type`.

    Attributes:
        file_type: The canonical ``file_type`` string (e.g. ``"pdf"``).
        content_kind: The logical family (e.g. ``"document"``).
        extension: The extension used for the lookup (lower-cased,
            without leading dot). ``""`` if the file has no extension.
        mime_type: The MIME type used for the lookup (lower-cased,
            without parameters). ``""`` if not provided.
        display_name: Human-readable name.
        is_supported: ``True`` if Phase 4 has a working extractor for
            this file type. ``False`` means we *can* store metadata
            but cannot extract content.
    """

    file_type: str
    content_kind: str
    extension: str = ""
    mime_type: str = ""
    display_name: str = "Other"
    is_supported: bool = False

    def to_dict(self) -> dict[str, str | bool]:
        return {
            "file_type": self.file_type,
            "content_kind": self.content_kind,
            "extension": self.extension,
            "mime_type": self.mime_type,
            "display_name": self.display_name,
            "is_supported": self.is_supported,
        }


# Default sentinel for files we cannot classify.
UNKNOWN = FileTypeInfo(
    file_type=FILE_TYPE_UNSUPPORTED,
    content_kind=CONTENT_KIND_OTHER,
    extension="",
    mime_type="",
    display_name="Other",
    is_supported=False,
)


def detect_file_type(
    filename: str | None = None,
    *,
    extension: str | None = None,
    mime_type: str | None = None,
) -> FileTypeInfo:
    """Detect the canonical file type for a file.

    Lookup is extension-first (more specific) then MIME. If neither
    yields a result, returns :data:`UNKNOWN`.
    """
    ext = _norm_ext(extension)
    if filename and not extension:
        ext = _norm_ext(Path(filename).suffix) if "." in filename else ""
        if not ext:
            ext = _norm_ext(filename.split(".")[-1] if "." in filename else "")
    mime = _norm_mime(mime_type)

    if ext and ext in _BY_EXT:
        entry = _BY_EXT[ext]
        return FileTypeInfo(
            file_type=entry.file_type,
            content_kind=entry.content_kind,
            extension=ext,
            mime_type=mime,
            display_name=entry.display_name,
            is_supported=entry.is_supported,
        )
    if mime and mime in _BY_MIME:
        entry = _BY_MIME[mime]
        return FileTypeInfo(
            file_type=entry.file_type,
            content_kind=entry.content_kind,
            extension=ext,
            mime_type=mime,
            display_name=entry.display_name,
            is_supported=entry.is_supported,
        )
    return FileTypeInfo(
        file_type=FILE_TYPE_UNSUPPORTED,
        content_kind=CONTENT_KIND_OTHER,
        extension=ext,
        mime_type=mime,
        display_name="Other",
        is_supported=False,
    )


def supported_extensions() -> tuple[str, ...]:
    """Return every extension the registry knows about."""
    return tuple(sorted(_BY_EXT.keys()))


def iter_entries() -> Iterable[_Entry]:
    """Iterate the raw registry (for tests / debugging)."""
    return tuple(_REGISTRY)
