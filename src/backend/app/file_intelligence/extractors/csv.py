"""CSV extractor (self-contained)."""
from __future__ import annotations

import csv
import io
from pathlib import Path
from typing import Any

from app.file_intelligence.base import BaseFileExtractor, ExtractionResult, FileExtractionStatus
from app.file_intelligence.types import FILE_TYPE_CSV

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


def _format_as_table(rows: list[list[Any]], max_chars: int) -> str:
    if not rows:
        return ""
    str_rows = [[("" if c is None else str(c)) for c in r] for r in rows]
    width = max(max(len(c) for c in r) for r in str_rows) if str_rows else 0
    width = min(width, 40)
    lines: list[str] = []
    for i, r in enumerate(str_rows):
        line = " | ".join(c.ljust(width)[:width] for c in r)
        lines.append(line)
        if i == 0 and len(str_rows) > 1:
            lines.append("-+-".join("-" * width for _ in r))
    text = "\n".join(lines)
    if len(text) > max_chars:
        return text[:max_chars]
    return text


class CsvExtractor(BaseFileExtractor):
    handles_file_type = FILE_TYPE_CSV
    version = "csv-1"

    _DIALECTS: dict[str, type[csv.Dialect]] = {
        "csv": csv.excel,
        "tsv": csv.excel_tab,
    }

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
        if not raw.strip():
            return ExtractionResult(
                status=FileExtractionStatus.EMPTY,
                text="",
                metadata={"size_bytes": stat.st_size, "row_count": 0, "column_count": 0},
            )

        dialect = self._sniff_dialect(raw)
        reader = csv.reader(io.StringIO(raw), dialect=dialect)
        try:
            rows = list(reader)
        except csv.Error as e:
            return ExtractionResult(
                status=FileExtractionStatus.FAILED,
                text=raw[:max_chars],
                metadata={"size_bytes": stat.st_size, "parse_ok": False, "parse_error": str(e)},
                warnings=["csv_parse_failed"],
                error=str(e),
            )

        if not rows:
            return ExtractionResult(
                status=FileExtractionStatus.EMPTY,
                text="",
                metadata={"size_bytes": stat.st_size, "row_count": 0, "column_count": 0},
            )

        header = [str(c) for c in rows[0]] if rows else []
        body = rows[1:] if len(rows) > 1 else []
        columns: list[dict[str, Any]] = []
        for idx, col in enumerate(header):
            sample = ""
            for row in body:
                if idx < len(row) and str(row[idx]).strip():
                    sample = str(row[idx])[:64]
                    break
            columns.append({"index": idx, "name": col, "sample": sample})

        max_rows = 50
        preview_rows = rows[: max_rows + 1]
        try:
            text_preview = _format_as_table(preview_rows, max_chars)
        except Exception:
            text_preview = "\n".join(",".join(map(str, r)) for r in preview_rows)
        text, was_truncated = _truncate(text_preview, max_chars)

        return ExtractionResult(
            status=FileExtractionStatus.OK,
            text=text,
            metadata={
                "size_bytes": stat.st_size,
                "dialect": dialect.__class__.__name__,
                "row_count": len(body),
                "column_count": len(header),
                "columns": columns,
                "line_count": _count_lines(raw),
            },
            warnings=["text_truncated"] if was_truncated else [],
        )

    def _sniff_dialect(self, sample: str) -> type[csv.Dialect]:
        head = sample[:4096]
        lowered = head.lstrip()
        if lowered.startswith("{") and lowered.endswith("}"):
            return csv.excel
        try:
            return csv.Sniffer().sniff(head, delimiters=",\t;|")
        except csv.Error:
            if "\t" in head.splitlines()[0] and "," not in head.splitlines()[0]:
                return csv.excel_tab
            return csv.excel
