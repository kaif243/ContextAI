"""Generic, lightweight metadata extraction (Phase 4).

This module produces the structured ``metadata_json`` blob stored
on each :class:`app.models.file_index.FileIndex` row. It is
intentionally format-agnostic and combines:

  * file-system metadata (size, dates, extension) from
    :mod:`app.file_intelligence.validation`
  * extractor output (line count, language, structure, …) from
    :mod:`app.file_intelligence.base`
  * classification signals from
    :mod:`app.file_intelligence.classifier`

Nothing here is machine learning; it's all metadata we already
computed elsewhere, combined into one payload that the API
returns and the UI displays.
"""

from __future__ import annotations

from typing import Any

from app.file_intelligence.classifier import FileClassification
from app.file_intelligence.types import FileTypeInfo
from app.file_intelligence.validation import FileStatInfo


def build_metadata(
    *,
    stat: FileStatInfo,
    type_info: FileTypeInfo,
    classification: FileClassification,
    extractor_metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build the metadata blob stored on the file row.

    The shape is intentionally small and stable: top-level keys
    are the categories the UI cares about, nested values are
    extractor-specific.
    """
    extractor_metadata = dict(extractor_metadata or {})
    meta: dict[str, Any] = {
        "filename": stat.filename,
        "extension": stat.extension,
        "size_bytes": stat.size_bytes,
        "created_at": stat.created_at.isoformat() if stat.created_at else None,
        "modified_at": stat.modified_at.isoformat() if stat.modified_at else None,
        "accessed_at": stat.accessed_at.isoformat() if stat.accessed_at else None,
        "type": {
            "file_type": type_info.file_type,
            "content_kind": type_info.content_kind,
            "display_name": type_info.display_name,
            "is_supported": type_info.is_supported,
        },
        "classification": {
            "label": classification.label,
            "confidence": classification.confidence,
            "version": classification.version,
        },
        "extractor": extractor_metadata,
    }
    # Surface a couple of common keys at the top level for
    # convenience (line_count, word_count, page_count). Keeps the
    # UI from digging into ``extractor`` for the obvious fields.
    for key in ("line_count", "word_count", "language", "page_count", "row_count", "column_count"):
        if key in extractor_metadata:
            meta[key] = extractor_metadata[key]
    return meta
