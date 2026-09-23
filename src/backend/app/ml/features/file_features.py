"""Feature extraction pipeline for Phase 5 H2."""
from __future__ import annotations
import math
from datetime import datetime
from typing import Any
from app.file_intelligence.types import FileTypeInfo, detect_file_type
from app.ml.schemas.model_meta import FeatureSchema, SchemaVersion

FEATURE_VERSION = SchemaVersion(major=1, minor=0, patch=0)
FEATURE_NAMES = (
    "filename_length", "filename_has_numbers", "filename_special_char_count",
    "extension_category_idx", "file_type_category_idx", "content_kind_category_idx",
    "is_supported", "size_bytes_log", "size_category_idx",
    "days_since_modified", "days_since_accessed",
    "text_length", "text_line_count", "text_word_count", "text_avg_line_length",
    "classification_label_idx", "classification_confidence",
    "is_indexed", "extraction_status_idx", "extraction_attempts",
    "feature_version_str",
)
FILE_TYPE_ORDER = ("text", "markdown", "json", "csv", "code", "pdf", "docx", "unsupported", "other")
CONTENT_KIND_ORDER = ("text", "markup", "structured_data", "source_code", "config", "document", "binary", "other")
EXTENSION_ORDER = tuple(sorted({
    "txt", "md", "markdown", "json", "csv", "py", "pyi", "pyw", "js", "mjs", "cjs", "ts", "tsx", "jsx", "rs", "go", "java", "c", "h", "cpp", "cc", "cxx", "hpp", "hxx", "rb", "php", "sh", "bash", "zsh", "ps1", "yaml", "yml", "toml", "xml", "html", "htm", "css", "scss", "less", "sql", "pdf", "docx",
}))
SIZE_BUCKETS = [0, 1024, 10240, 102400, 1024000, 10240000]
EXTRACTION_STATUS_ORDER = ("pending", "running", "success", "failed", "skipped")
CLASSIFICATION_LABEL_ORDER = ("document", "source_code", "data", "configuration", "notes", "unknown")

def _filename_features(name: str) -> dict[str, Any]:
    basename = (name or "").strip()
    return {
        "filename_length": len(basename),
        "filename_has_numbers": 1 if any(ch.isdigit() for ch in basename) else 0,
        "filename_special_char_count": sum(1 for ch in basename if not ch.isalnum() and ch != "."),
    }

def _extension_category(ext: str | None) -> int:
    ext_norm = (ext or "").lstrip(".").lower().strip()
    try:
        return EXTENSION_ORDER.index(ext_norm)
    except ValueError:
        return len(EXTENSION_ORDER) - 1

def _file_type_category(file_type: str) -> int:
    try:
        return FILE_TYPE_ORDER.index(file_type)
    except ValueError:
        return len(FILE_TYPE_ORDER) - 1

def _content_kind_category(content_kind: str) -> int:
    try:
        return CONTENT_KIND_ORDER.index(content_kind)
    except ValueError:
        return len(CONTENT_KIND_ORDER) - 1

def _size_features(size_bytes: int | None) -> dict[str, Any]:
    safe_size = max(0, int(size_bytes) if size_bytes is not None else 0)
    log_val = math.log(safe_size + 1.0)
    bucket_idx = max([i for i, t in enumerate(SIZE_BUCKETS) if safe_size >= t] or [0])
    return {"size_bytes_log": round(log_val, 4), "size_category_idx": bucket_idx}

def _date_features(modified_at, accessed_at) -> dict[str, Any]:
    reference = datetime(2026, 1, 1)
    def _days(date_val) -> float:
        if date_val is None:
            return 0.0
        try:
            if isinstance(date_val, datetime):
                dt = date_val
            else:
                dt = datetime.fromisoformat(str(date_val).replace("Z", "+00:00"))
            return float((dt - reference).total_seconds() / 86400.0)
        except Exception:
            return 0.0
    return {"days_since_modified": round(_days(modified_at), 4), "days_since_accessed": round(_days(accessed_at), 4)}

def _text_statistics(text_content: str | None) -> dict[str, Any]:
    text = text_content or ""
    length = len(text)
    lines = text.splitlines()
    line_count = len(lines) if lines else 0
    word_count = len(text.split()) if text.strip() else 0
    avg_line_length = (length / max(line_count, 1)) if line_count > 0 else 0.0
    return {
        "text_length": length,
        "text_line_count": line_count,
        "text_word_count": word_count,
        "text_avg_line_length": round(avg_line_length, 4),
    }

def _classification_features(classification: str | None, confidence: float | None) -> dict[str, Any]:
    label_idx = -1
    if classification:
        try:
            label_idx = CLASSIFICATION_LABEL_ORDER.index(str(classification))
        except ValueError:
            label_idx = len(CLASSIFICATION_LABEL_ORDER) - 1
    return {
        "classification_label_idx": label_idx,
        "classification_confidence": round(float(confidence) if confidence is not None else 0.0, 4),
    }

def _status_features(is_indexed: bool, extraction_status: str | None, attempts: int | None) -> dict[str, Any]:
    status_idx = 0
    try:
        status_idx = EXTRACTION_STATUS_ORDER.index(str(extraction_status)) if extraction_status else 0
    except ValueError:
        status_idx = len(EXTRACTION_STATUS_ORDER) - 1
    return {
        "is_indexed": 1 if is_indexed else 0,
        "extraction_status_idx": status_idx,
        "extraction_attempts": int(attempts) if attempts is not None else 0,
    }

def extract_features(
    filename: str | None = None,
    file_type_info=None,
    size_bytes: int | None = None,
    extension: str | None = None,
    modified_at=None,
    accessed_at=None,
    text_content: str | None = None,
    classification: str | None = None,
    classification_confidence: float | None = None,
    is_indexed: bool = False,
    extraction_status: str | None = None,
    extraction_attempts: int | None = None,
) -> dict[str, Any]:
    if file_type_info is None:
        file_type_info = detect_file_type(filename=filename, extension=extension)
    else:
        file_type_info = FileTypeInfo(
            file_type=str(file_type_info.file_type or ""),
            content_kind=str(file_type_info.content_kind or ""),
            extension=str(file_type_info.extension or ""),
            mime_type=str(file_type_info.mime_type or ""),
            display_name=str(file_type_info.display_name or ""),
            is_supported=bool(file_type_info.is_supported),
        )
    basename = (filename or "").split("/")[-1].split("\\")[-1]
    ext_for_lookup = extension or file_type_info.extension or (basename.split(".")[-1] if "." in basename else "")
    result = {}
    result.update(_filename_features(basename))
    result["extension_category_idx"] = _extension_category(ext_for_lookup)
    result["file_type_category_idx"] = _file_type_category(file_type_info.file_type or "other")
    result["content_kind_category_idx"] = _content_kind_category(file_type_info.content_kind or "other")
    result["is_supported"] = 1 if file_type_info.is_supported else 0
    result.update(_size_features(size_bytes))
    result.update(_date_features(modified_at, accessed_at))
    result.update(_text_statistics(text_content))
    result.update(_classification_features(classification, classification_confidence))
    result.update(_status_features(is_indexed, extraction_status, extraction_attempts))
    result["feature_version_str"] = str(FEATURE_VERSION)
    return result

def get_feature_schema() -> FeatureSchema:
    return FeatureSchema(
        version=FEATURE_VERSION,
        features=FEATURE_NAMES,
        description="Phase 5 H2 file-classification feature schema — safe, deterministic, reproducible, no personal data",
    )

def feature_version():
    return FEATURE_VERSION
