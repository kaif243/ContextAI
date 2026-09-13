"""File Intelligence subpackage (Phase 4).

This package is the local-first, deterministic counterpart to the
classifier / OCR / LLM modules. The public surface is:

  * :mod:`app.file_intelligence.types`        — file-type registry
  * :mod:`app.file_intelligence.base`         — abstract extractor + factory
  * :mod:`app.file_intelligence.classifier`   — baseline file classifier
  * :mod:`app.file_intelligence.validation`   — path / size / hash helpers
  * :mod:`app.file_intelligence.metadata`     — generic metadata extraction
  * :mod:`app.file_intelligence.service`      — orchestrator + search
  * :mod:`app.file_intelligence.extractors`   — per-format concrete extractors

Design notes
------------
* The default implementation is **NOT machine learning** — file
  classification is rule-based, content extraction is a thin wrapper
  over the appropriate stdlib (or third-party) parser. The interface
  in :mod:`app.file_intelligence.base` is the single point of truth
  so a real ML classifier can replace the baseline later without
  touching call sites.
* The subsystem is **privacy-first**: no file contents are sent
  off-device, no whole-disk scanning is performed, and the file
  path must be explicitly supplied by the user (via the Tauri file
  picker or an explicit API call).
* The subsystem is **deterministic and local**: no RAG, no
  embeddings, no vector DB. Phase 6 (RAG + Memory) is the right
  place to introduce those.
"""

from app.file_intelligence.base import (
    BaseFileExtractor,
    ExtractionResult,
    ExtractorFactory,
    FileExtractionStatus,
    get_file_extractor_factory,
)
from app.file_intelligence.classifier import (
    CLASSIFICATION_LABELS,
    FileClassification,
    classify_file,
)
from app.file_intelligence.metadata import build_metadata
from app.file_intelligence.service import (
    FileService,
    IndexResult,
    SearchHit,
    SearchResult,
    get_file_service,
)
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
    FILE_TYPE_OTHER,
    FILE_TYPE_PDF,
    FILE_TYPE_TXT,
    FILE_TYPE_UNSUPPORTED,
    FileTypeInfo,
    detect_file_type,
    supported_extensions,
)
from app.file_intelligence.validation import (
    FileStatInfo,
    FileValidationError,
    collect_stat_info,
    describe_file,
    hash_file,
    is_within_allowed_root,
    merge_allowed_extensions,
    parse_allowed_extensions,
    path_has_null_byte,
    validate_file_path,
)

__all__ = [
    # Base + factory
    "BaseFileExtractor",
    "ExtractionResult",
    "ExtractorFactory",
    "FileExtractionStatus",
    "get_file_extractor_factory",
    # Classifier
    "CLASSIFICATION_LABELS",
    "FileClassification",
    "classify_file",
    # Metadata
    "build_metadata",
    # Service
    "FileService",
    "IndexResult",
    "SearchHit",
    "SearchResult",
    "get_file_service",
    # Types / registry
    "CONTENT_KIND_BINARY",
    "CONTENT_KIND_CONFIG",
    "CONTENT_KIND_DOCUMENT",
    "CONTENT_KIND_MARKUP",
    "CONTENT_KIND_OTHER",
    "CONTENT_KIND_SOURCE_CODE",
    "CONTENT_KIND_STRUCTURED_DATA",
    "CONTENT_KIND_TEXT",
    "FILE_TYPE_CODE",
    "FILE_TYPE_CSV",
    "FILE_TYPE_DOCX",
    "FILE_TYPE_JSON",
    "FILE_TYPE_MARKDOWN",
    "FILE_TYPE_OTHER",
    "FILE_TYPE_PDF",
    "FILE_TYPE_TXT",
    "FILE_TYPE_UNSUPPORTED",
    "FileTypeInfo",
    "detect_file_type",
    "supported_extensions",
    # Validation
    "FileStatInfo",
    "FileValidationError",
    "collect_stat_info",
    "describe_file",
    "hash_file",
    "is_within_allowed_root",
    "merge_allowed_extensions",
    "parse_allowed_extensions",
    "path_has_null_byte",
    "validate_file_path",
]
