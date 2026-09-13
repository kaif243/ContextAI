"""Source-code extractor (self-contained)."""
from __future__ import annotations

from pathlib import Path

from app.file_intelligence.base import BaseFileExtractor, ExtractionResult, FileExtractionStatus
from app.file_intelligence.types import FILE_TYPE_CODE

_UTF8 = "utf-8"
_LATIN1 = "latin-1"

_LANGUAGE_BY_EXT: dict[str, str] = {
    "py": "python", "pyi": "python", "pyw": "python",
    "js": "javascript", "mjs": "javascript", "cjs": "javascript",
    "ts": "typescript", "tsx": "tsx", "jsx": "jsx",
    "rs": "rust",
    "go": "go",
    "java": "java",
    "c": "c", "h": "c",
    "cpp": "cpp", "cc": "cpp", "cxx": "cpp", "hpp": "cpp", "hxx": "cpp",
    "rb": "ruby",
    "php": "php",
    "sh": "shell", "bash": "shell", "zsh": "shell",
    "ps1": "powershell",
    "yaml": "yaml", "yml": "yaml",
    "toml": "toml",
    "xml": "xml",
    "html": "html", "htm": "html",
    "css": "css", "scss": "scss", "less": "less",
    "sql": "sql",
}


def _read_text_safe(path: Path, max_bytes: int) -> str:
    with path.open("rb") as f:
        raw = f.read(max_bytes + 1)
    try:
        return raw[:max_bytes].decode(_UTF8, errors="replace")
    except UnicodeDecodeError:
        return raw[:max_bytes].decode(_LATIN1, errors="replace")


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


class CodeExtractor(BaseFileExtractor):
    handles_file_type = FILE_TYPE_CODE
    version = "code-1"

    def extract(self, path: Path, *, max_chars: int = 8000) -> ExtractionResult:
        try:
            stat = path.stat()
        except OSError as e:
            return ExtractionResult(
                status=FileExtractionStatus.FAILED, error=f"stat failed: {e}"
            )
        ext = path.suffix.lstrip(".").lower()
        language = _LANGUAGE_BY_EXT.get(ext, "unknown")
        if stat.st_size == 0:
            return ExtractionResult(
                status=FileExtractionStatus.EMPTY,
                text="",
                metadata={"size_bytes": 0, "language": language, "line_count": 0},
            )
        try:
            text = _read_text_safe(path, max_bytes=max_chars * 2)
        except OSError as e:
            return ExtractionResult(
                status=FileExtractionStatus.FAILED, error=f"read failed: {e}"
            )
        truncated, was_truncated = _truncate(text, max_chars)
        return ExtractionResult(
            status=FileExtractionStatus.OK,
            text=truncated,
            metadata={
                "size_bytes": stat.st_size,
                "language": language,
                "line_count": _count_lines(text),
                "encoding": _UTF8,
            },
            warnings=["text_truncated"] if was_truncated else [],
        )
