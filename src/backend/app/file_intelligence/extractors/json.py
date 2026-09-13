"""JSON extractor (self-contained)."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.file_intelligence.base import BaseFileExtractor, ExtractionResult, FileExtractionStatus
from app.file_intelligence.types import FILE_TYPE_JSON

_UTF8 = "utf-8"


def _truncate(text: str, max_chars: int) -> tuple[str, bool]:
    if max_chars <= 0:
        return "", False
    if len(text) <= max_chars:
        return text, False
    return text[:max_chars], True


def _count_lines(text: str) -> int:
    if not text:
        return 0
    return text.count("\n") + (0 if text.endswith("\n") else 1)


def _summarise_json(value: Any, *, depth: int = 0, max_depth: int = 6) -> Any:
    if depth >= max_depth:
        return "..."
    if isinstance(value, dict):
        return {
            str(k): _summarise_json(v, depth=depth + 1, max_depth=max_depth)
            for k, v in value.items()
        }
    if isinstance(value, list):
        if not value:
            return {"type": "array", "length": 0}
        first = _summarise_json(value[0], depth=depth + 1, max_depth=max_depth)
        return {"type": "array", "length": len(value), "first": first}
    if isinstance(value, str):
        return {"type": "string", "example": value[:64]}
    if isinstance(value, bool):
        return {"type": "boolean"}
    if isinstance(value, int):
        return {"type": "integer"}
    if isinstance(value, float):
        return {"type": "number"}
    if value is None:
        return {"type": "null"}
    return {"type": type(value).__name__}


class JsonExtractor(BaseFileExtractor):
    handles_file_type = FILE_TYPE_JSON
    version = "json-1"

    def extract(self, path: Path, *, max_chars: int = 8000) -> ExtractionResult:
        try:
            stat = path.stat()
        except OSError as e:
            return ExtractionResult(
                status=FileExtractionStatus.FAILED, error=f"stat failed: {e}"
            )
        try:
            raw = path.read_text(encoding=_UTF8, errors="replace")
        except OSError as e:
            return ExtractionResult(
                status=FileExtractionStatus.FAILED, error=f"read failed: {e}"
            )
        truncated_raw, was_truncated = _truncate(raw, max_chars * 2)
        try:
            data = json.loads(truncated_raw)
            parse_ok = True
        except (ValueError, TypeError) as e:
            return ExtractionResult(
                status=FileExtractionStatus.FAILED,
                text=truncated_raw,
                metadata={
                    "size_bytes": stat.st_size,
                    "parse_ok": False,
                    "parse_error": str(e),
                    "line_count": _count_lines(truncated_raw),
                },
                warnings=[
                    "text_truncated" if was_truncated else "json_parse_failed"
                ],
                error=str(e),
            )

        summary = _summarise_json(data)
        pretty = json.dumps(data, ensure_ascii=False, indent=2, default=str)
        text, text_truncated = _truncate(pretty, max_chars)
        warnings = []
        if was_truncated or text_truncated:
            warnings.append("text_truncated")
        return ExtractionResult(
            status=FileExtractionStatus.OK,
            text=text,
            metadata={
                "size_bytes": stat.st_size,
                "parse_ok": parse_ok,
                "line_count": _count_lines(pretty),
                "structure": summary,
            },
            warnings=warnings,
        )
