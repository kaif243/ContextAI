"""File validation, hashing, and metadata helpers (Phase 4).

The functions here are deliberately stateless — they take a path,
do something useful, and return a structured result. The service
layer composes them; nothing in this module touches the database
or the network.
"""

from __future__ import annotations

import hashlib
import os
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable, Optional

from app.core.logging import get_logger
from app.file_intelligence.types import (
    detect_file_type,
    supported_extensions,
)

logger = get_logger(__name__)


# Conservative default; tests / callers can override.
_DEFAULT_MAX_BYTES = 25 * 1024 * 1024


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------
class FileValidationError(ValueError):
    """Raised when a user-supplied path fails validation.

    The error message is safe to surface to the API client; the
    service layer turns it into a 4xx response.
    """

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------
def parse_allowed_extensions(raw: str | None) -> set[str]:
    """Parse a comma-separated list of allowed extensions."""
    if not raw:
        return set()
    out: set[str] = set()
    for chunk in raw.split(","):
        ext = chunk.strip().lstrip(".").lower()
        if ext:
            out.add(ext)
    return out


def is_within_allowed_root(path: Path | str, allowed_roots: Iterable[Path | str]) -> bool:
    """Return True if ``path`` is inside one of ``allowed_roots``."""
    path_obj = Path(path) if isinstance(path, str) else path
    try:
        resolved = path_obj.resolve(strict=False)
    except (OSError, ValueError):
        return False
    for root in allowed_roots:
        root_obj = Path(root) if isinstance(root, str) else root
        try:
            root_resolved = root_obj.resolve(strict=False)
        except (OSError, ValueError):
            continue
        try:
            resolved.relative_to(root_resolved)
            return True
        except ValueError:
            continue
    return False


def validate_file_path(
    raw_path: str | os.PathLike[str],
    *,
    max_bytes: int = _DEFAULT_MAX_BYTES,
    allowed_extensions: Optional[set[str]] = None,
    allowed_roots: Optional[Iterable[Path]] = None,
    must_exist: bool = True,
) -> Path:
    """Validate a user-supplied file path.

    Checks:
      * path is a string / PathLike
      * path resolves to an absolute path
      * path is a regular file (not a directory, symlink loop, etc.)
      * file is readable
      * file size <= ``max_bytes``
      * extension is in ``allowed_extensions`` (if given)
      * path is within one of ``allowed_roots`` (if given)

    Returns the resolved :class:`Path` on success. Raises
    :class:`FileValidationError` with a stable ``code`` on
    failure.
    """
    if raw_path is None:
        raise FileValidationError("invalid_path", "Path is required")
    # NUL-byte check happens *before* we hand the path to pathlib
    # because on Windows the underlying resolver raises a bare
    # ``ValueError("embedded null character")`` for NUL bytes and
    # would otherwise escape our error-handling.
    raw_str = os.fspath(raw_path) if raw_path is not None else ""
    if _NULL_BYTE_RE.search(raw_str):
        raise FileValidationError("null_byte", "Path contains NUL byte")
    try:
        path = Path(raw_str).expanduser()
    except (TypeError, ValueError) as e:
        raise FileValidationError("invalid_path", f"Invalid path: {e}") from e
    if not str(path):
        raise FileValidationError("invalid_path", "Empty path")
    if path.is_absolute() is False:
        # ``is_absolute()`` is the cheapest test for "this is a
        # path the user explicitly picked" — relative paths are
        # not allowed, they would make the indexer crawl
        # arbitrary working directories.
        raise FileValidationError(
            "invalid_path", "Path must be absolute"
        )

    if must_exist:
        try:
            resolved = path.resolve(strict=True)
        except (OSError, RuntimeError) as e:
            raise FileValidationError(
                "not_found", f"File does not exist: {e}"
            ) from e
        if not resolved.is_file():
            raise FileValidationError(
                "not_a_file", f"Not a regular file: {resolved}"
            )
        # Refuse symlinks pointing outside the allowed roots
        # (we still want to allow symlinks *inside* the roots,
        # e.g. a "latest" symlink to a dated file in Documents).
        if resolved.is_symlink():
            try:
                target = resolved.readlink()
            except OSError:
                target = None
            if target is not None and not str(target).startswith(str(resolved.parent)):
                if not is_within_allowed_root(resolved, allowed_roots or []):
                    raise FileValidationError(
                        "unsafe_symlink",
                        f"Symlink target is outside allowed roots: {resolved}",
                    )
        try:
            os.access(resolved, os.R_OK)
        except OSError as e:
            raise FileValidationError("not_readable", str(e)) from e
        try:
            size = resolved.stat().st_size
        except OSError as e:
            raise FileValidationError("stat_failed", str(e)) from e
        if size < 0:
            raise FileValidationError("invalid_size", "Negative file size")
        if size > max_bytes:
            raise FileValidationError(
                "too_large",
                f"File is {size} bytes; max allowed is {max_bytes}",
            )
        if allowed_extensions is not None:
            ext = resolved.suffix.lstrip(".").lower()
            if ext not in allowed_extensions:
                raise FileValidationError(
                    "unsupported_extension",
                    f"Extension '{ext or '(none)'}' is not in the allowed list",
                )
        if allowed_roots and not is_within_allowed_root(resolved, allowed_roots):
            raise FileValidationError(
                "outside_allowed_roots",
                f"Path is outside the allowed roots: {resolved}",
            )
        return resolved

    # must_exist=False: just normalise the path.
    try:
        return path.resolve(strict=False)
    except (OSError, RuntimeError) as e:
        raise FileValidationError("invalid_path", str(e)) from e


# ---------------------------------------------------------------------------
# Hashing
# ---------------------------------------------------------------------------
_SHA256 = "sha256"


def hash_file(path: Path | str, *, algo: str = _SHA256, max_bytes: int | None = None) -> str:
    """Compute a content hash for ``path``.

    Reads the file in 64KB chunks. ``max_bytes`` caps the number
    of bytes hashed so we don't accidentally slurp a 1GB log
    file — the resulting hash still uniquely identifies the
    "head" of the file plus its size, which is what we use to
    detect changes cheaply.

    Returns the lowercase hex digest. Returns ``""`` if the
    file is empty and the caller asked for the empty-string
    sentinel.
    """
    path_obj = Path(path) if isinstance(path, str) else path
    hasher = hashlib.new(algo)
    try:
        size = path_obj.stat().st_size
    except OSError as e:
        raise FileValidationError("stat_failed", str(e)) from e
    if size == 0:
        return hashlib.new(algo, b"").hexdigest()
    read_total = 0
    chunk_size = 64 * 1024
    try:
        with path_obj.open("rb") as f:
            while True:
                chunk = f.read(chunk_size)
                if not chunk:
                    break
                if max_bytes is not None and read_total + len(chunk) > max_bytes:
                    hasher.update(chunk[: max_bytes - read_total])
                    read_total = max_bytes
                    break
                hasher.update(chunk)
                read_total += len(chunk)
    except OSError as e:
        raise FileValidationError("read_failed", str(e)) from e
    return hasher.hexdigest()


# ---------------------------------------------------------------------------
# File-stat metadata
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class FileStatInfo:
    """Structured file-stat metadata."""

    size_bytes: int
    created_at: Optional[datetime]
    modified_at: Optional[datetime]
    accessed_at: Optional[datetime]
    extension: str
    filename: str

    def to_dict(self) -> dict[str, object]:
        return {
            "size_bytes": self.size_bytes,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "modified_at": self.modified_at.isoformat() if self.modified_at else None,
            "accessed_at": self.accessed_at.isoformat() if self.accessed_at else None,
            "extension": self.extension,
            "filename": self.filename,
        }


def collect_stat_info(path: Path | str) -> FileStatInfo:
    """Collect filesystem metadata for ``path``."""
    path_obj = Path(path) if isinstance(path, str) else path
    st = path_obj.stat()
    return FileStatInfo(
        size_bytes=st.st_size,
        created_at=_to_utc(st.st_ctime),
        modified_at=_to_utc(st.st_mtime),
        accessed_at=_to_utc(st.st_atime),
        extension=path_obj.suffix.lstrip(".").lower(),
        filename=path_obj.name,
    )


def _to_utc(ts: float) -> Optional[datetime]:
    try:
        return datetime.utcfromtimestamp(ts)
    except (OverflowError, OSError, ValueError):
        return None


# ---------------------------------------------------------------------------
# Combined "describe" helper
# ---------------------------------------------------------------------------
def describe_file(
    path: Path,
    *,
    max_bytes: int = _DEFAULT_MAX_BYTES,
    allowed_extensions: Optional[set[str]] = None,
    allowed_roots: Optional[Iterable[Path]] = None,
    algo: str = _SHA256,
) -> dict[str, object]:
    """Return a dict with everything the service needs to build a row.

    Convenience wrapper that combines validation, stat collection,
    content hashing, and type detection.
    """
    resolved = validate_file_path(
        path,
        max_bytes=max_bytes,
        allowed_extensions=allowed_extensions,
        allowed_roots=allowed_roots,
        must_exist=True,
    )
    stat = collect_stat_info(resolved)
    content_hash = hash_file(resolved, algo=algo, max_bytes=max_bytes)
    type_info = detect_file_type(
        extension=stat.extension, mime_type=_guess_mime(resolved)
    )
    return {
        "path": str(resolved),
        "stat": stat,
        "content_hash": content_hash,
        "type_info": type_info,
    }


# ---------------------------------------------------------------------------
# Mime-type fallback (no external dependency)
# ---------------------------------------------------------------------------
_MIME_BY_EXT: dict[str, str] = {
    "txt": "text/plain",
    "md": "text/markdown",
    "markdown": "text/markdown",
    "json": "application/json",
    "csv": "text/csv",
    "tsv": "text/tab-separated-values",
    "yml": "application/yaml",
    "yaml": "application/yaml",
    "toml": "text/x-toml",
    "xml": "application/xml",
    "html": "text/html",
    "css": "text/css",
    "js": "application/javascript",
    "ts": "text/typescript",
    "py": "text/x-python",
    "rs": "text/x-rust",
    "go": "text/x-go",
    "java": "text/x-java-source",
    "sh": "application/x-shellscript",
    "ps1": "text/x-powershell",
    "pdf": "application/pdf",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}


def _guess_mime(path: Path) -> str:
    ext = path.suffix.lstrip(".").lower()
    return _MIME_BY_EXT.get(ext, "")


def merge_allowed_extensions(
    configured: str | None,
    registry_extensions: Iterable[str] | None = None,
) -> set[str]:
    """Combine the configured allow-list with the registry defaults.

    If ``configured`` is empty, falls back to the registry's full
    extension list. Used by the service to keep "I forgot to
    configure it" safe.
    """
    parsed = parse_allowed_extensions(configured)
    if parsed:
        return parsed
    return set(registry_extensions or supported_extensions())


# ---------------------------------------------------------------------------
# Path-safety helpers (defence-in-depth)
# ---------------------------------------------------------------------------
_NULL_BYTE_RE = re.compile(r"\x00")


def path_has_null_byte(raw: str) -> bool:
    """Return True if the raw path contains a NUL byte (a classic
    path-traversal / smuggling attempt)."""
    return bool(_NULL_BYTE_RE.search(raw or ""))
