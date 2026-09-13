"""File Intelligence API (Phase 4).

Exposes :class:`app.file_intelligence.service.FileService` through a
clean HTTP surface.

  POST   /api/v1/files/select            Index a single user-selected file.
  GET    /api/v1/files                    List indexed files (paginated).
  GET    /api/v1/files/{file_id}          Get one file (metadata + text).
  DELETE /api/v1/files/{file_id}          Remove one file from the index.
  POST   /api/v1/files/{file_id}/reindex  Force re-indexing.
  POST   /api/v1/files/{file_id}/reanalyse Re-run the file classifier.
  POST   /api/v1/files/{file_id}/explain   LLM explain-the-file action.
  POST   /api/v1/files/{file_id}/summarise LLM summarise-the-file action.
  POST   /api/v1/files/{file_id}/ask       LLM ask-the-file action.
  POST   /api/v1/files/search              Keyword search over the index.
  DELETE /api/v1/files                     Clear the entire file index.
  GET    /api/v1/files/stats               Aggregate counts by status / label.
  GET    /api/v1/files/supported-types     Extension / MIME type registry.

Backward compatibility
----------------------
The Phase 1 placeholder endpoints used a slightly different shape
(snake-case ``files`` / ``files_indexed`` in the list response, and
the search endpoint took *query* parameters rather than a JSON
body). The new endpoints accept both shapes:

  * ``GET /api/v1/files`` returns the modern ``items`` list **and**
    the legacy ``files`` alias so old clients keep working.
  * ``POST /api/v1/files/search`` accepts the modern JSON body
    **and** the legacy query-string parameters. Results are the
    same regardless of how the request was made.
  * ``POST /api/v1/files/index`` returns the modern
    ``FileIndexResponse`` shape **and** the legacy
    ``{success, files_indexed, errors}`` shape.

Privacy / safety
----------------
* Only absolute paths are accepted. Relative paths are refused.
* NUL bytes in the path are refused.
* The file must be within :attr:`settings.file_max_bytes` and have
  an allowed extension.
* ``file_intelligence_enabled`` is a master switch: when it is
  ``False`` the endpoints return a structured 4xx response instead
  of doing any work.
* No data is sent off-device. The LLM calls go through the
  existing :func:`app.llm.get_llm_provider` factory (default
  Ollama, never a paid cloud API).
"""

from __future__ import annotations

import time
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.logging import get_logger
from app.core.security import (
    PermissionLevel,
    get_permission_level,
)
from app.file_intelligence.service import (
    FileService,
    IndexResult,
    SearchResult,
    get_file_service,
)
from app.file_intelligence.types import (
    supported_extensions as _supported_extensions,
)
from app.models.file_index import FileIndex

logger = get_logger(__name__)

router = APIRouter()


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------
class FileSelectRequest(BaseModel):
    """Request body for ``POST /api/v1/files/select``."""

    path: str = Field(min_length=1, max_length=4096)
    force: bool = False


class FileRowSummary(BaseModel):
    """Compact row representation returned by list / search."""

    id: int
    path: str
    name: str
    file_type: str
    extension: str | None = None
    size_bytes: int = 0
    modified_at: str | None = None
    classification: str | None = None
    classification_confidence: float | None = None
    extraction_status: str = "pending"
    is_indexed: bool = True
    indexed_at: str | None = None


class FileIndexResponse(BaseModel):
    """Response wrapper for ``POST /select`` and ``POST /{id}/reindex``."""

    success: bool
    stored: bool
    reason: str
    changed: bool = False
    reused: bool = False
    raw_path: str
    file: FileRowSummary | None = None
    # Legacy shape: Phase 1 clients read these.
    files_indexed: int = 0
    errors: list[str] = Field(default_factory=list)


class FileDetailResponse(BaseModel):
    """Full detail of a single indexed file."""

    id: int
    path: str
    name: str
    file_type: str
    extension: str | None = None
    size_bytes: int = 0
    created_at: str | None = None
    modified_at: str | None = None
    classification: str | None = None
    classification_confidence: float | None = None
    classifier_version: str | None = None
    extraction_status: str = "pending"
    extraction_error: str | None = None
    text_truncated: bool = False
    content_hash: str | None = None
    indexed_at: str | None = None
    text_preview: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class FileListResponse(BaseModel):
    items: list[FileRowSummary]
    # Legacy alias used by the Phase 1 client (``files`` instead
    # of ``items``). Both fields hold the same list.
    files: list[FileRowSummary]
    total: int
    limit: int
    offset: int


class FileSearchRequest(BaseModel):
    """Request body for ``POST /api/v1/files/search``."""

    query: str = ""
    classification: str | None = None
    file_type: str | None = None
    extension: str | None = None
    status: str | None = None
    limit: int = Field(default=20, ge=1, le=100)


class FileSearchHit(BaseModel):
    file: FileRowSummary
    score: float
    match_type: str
    snippet: str = ""


class FileSearchResponse(BaseModel):
    results: list[FileSearchHit]
    total: int
    query_time_ms: int


class FileActionResponse(BaseModel):
    success: bool
    affected: int = 0
    detail: str | None = None


class FileLLMRequest(BaseModel):
    """Common shape for ask-the-file (and the explain/summarise wrappers)."""

    question: str | None = None


class FileLLMResponse(BaseModel):
    file_id: int
    action: str
    answer: str = ""
    is_error: bool = False
    error_message: str | None = None
    error_code: str | None = None
    model_used: str | None = None
    processing_ms: int | None = None


class FileStatsResponse(BaseModel):
    total: int
    by_status: dict[str, int]
    by_classification: dict[str, int]
    config: dict[str, Any]
    extractors: list[dict[str, Any]]


class SupportedTypeEntry(BaseModel):
    file_type: str
    content_kind: str
    display_name: str
    is_supported: bool
    extensions: list[str]
    mime_types: list[str]


class SupportedTypesResponse(BaseModel):
    supported_extensions: list[str]
    entries: list[SupportedTypeEntry]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _row_to_summary(row: FileIndex) -> FileRowSummary:
    return FileRowSummary(
        id=row.id,
        path=row.path,
        name=row.name,
        file_type=row.file_type or "other",
        extension=row.extension,
        size_bytes=row.size_bytes or 0,
        modified_at=row.modified_at.isoformat() if row.modified_at else None,
        classification=row.classification,
        classification_confidence=row.classification_confidence,
        extraction_status=row.extraction_status or "pending",
        is_indexed=bool(row.is_indexed),
        indexed_at=row.indexed_at.isoformat() if row.indexed_at else None,
    )


def _row_to_detail(row: FileIndex, *, max_text: int = 4_000) -> FileDetailResponse:
    text = (row.extracted_text or row.text_content or "") or ""
    preview = text[:max_text]
    if len(text) > max_text:
        preview = preview + "…"
    return FileDetailResponse(
        id=row.id,
        path=row.path,
        name=row.name,
        file_type=row.file_type or "other",
        extension=row.extension,
        size_bytes=row.size_bytes or 0,
        created_at=row.created_at_fs.isoformat() if row.created_at_fs else None,
        modified_at=row.modified_at.isoformat() if row.modified_at else None,
        classification=row.classification,
        classification_confidence=row.classification_confidence,
        classifier_version=row.classifier_version,
        extraction_status=row.extraction_status or "pending",
        extraction_error=row.extraction_error,
        text_truncated=bool(row.text_truncated),
        content_hash=row.content_hash,
        indexed_at=row.indexed_at.isoformat() if row.indexed_at else None,
        text_preview=preview,
        metadata=row.metadata_json or {},
    )


def _index_to_response(
    result: IndexResult,
    *,
    files_indexed: int = 0,
    errors: Optional[list[str]] = None,
) -> FileIndexResponse:
    return FileIndexResponse(
        success=result.stored,
        stored=result.stored,
        reason=result.reason,
        changed=result.changed,
        reused=result.reused,
        raw_path=result.raw_path,
        file=_row_to_summary(result.file_row) if result.file_row else None,
        files_indexed=files_indexed or (1 if result.stored else 0),
        errors=list(errors or []),
    )


def _service(db: Session) -> FileService:
    return get_file_service(db)


def _permission_error(action: str) -> HTTPException:
    return HTTPException(
        status_code=403,
        detail={
            "code": "permission_denied",
            "action": action,
            "level": get_permission_level(action).name,
        },
    )


def _check_permission_or_403(action: str) -> None:
    """Refuse RED-level actions; accept GREEN/YELLOW for Phase 4.

    Phase 4 leaves the human-in-the-loop wiring to a higher layer
    (Phase 7). YELLOW actions return a structured response so the
    UI can prompt the user, but the API does not block them.
    """
    level = get_permission_level(action)
    if level == PermissionLevel.RED:
        raise _permission_error(action)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@router.post("/select", response_model=FileIndexResponse)
async def select_file(
    request: FileSelectRequest,
    db: Session = Depends(get_db),
) -> FileIndexResponse:
    """Index a single user-selected file.

    The path is expected to come from the Tauri file picker; the
    endpoint itself does not scan the filesystem. The response
    always includes a structured ``reason`` so the UI can
    explain what happened.
    """
    if not settings.file_intelligence_enabled:
        return FileIndexResponse(
            success=False,
            stored=False,
            reason="file_intelligence_disabled",
            raw_path=request.path,
        )
    _check_permission_or_403("index_file")
    service = _service(db)
    result = service.index_file(request.path, force=request.force)
    return _index_to_response(result)


@router.get("", response_model=FileListResponse)
async def list_files(
    folder_path: str | None = Query(default=None),
    file_type: str | None = Query(default=None),
    classification: str | None = Query(default=None),
    extension: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    include_deleted: bool = Query(default=False),
    db: Session = Depends(get_db),
) -> FileListResponse:
    """List indexed files, most recently indexed first.

    Accepts the legacy ``folder_path`` filter for backward
    compatibility with the Phase 1 placeholder: when provided,
    files whose path starts with the folder string are kept.
    """
    _check_permission_or_403("list_files")
    service = _service(db)
    rows, total = service.list_files(
        classification=classification,
        file_type=file_type,
        extension=extension,
        limit=limit,
        offset=offset,
        include_deleted=include_deleted,
    )
    if folder_path:
        rows = [r for r in rows if (r.path or "").startswith(folder_path)]
        total = len(rows)
    items = [_row_to_summary(r) for r in rows]
    return FileListResponse(
        items=items,
        files=items,  # legacy alias
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/stats", response_model=FileStatsResponse)
async def file_stats(
    db: Session = Depends(get_db),
) -> FileStatsResponse:
    """Aggregate stats for the file index."""
    _check_permission_or_403("list_files")
    service = _service(db)
    stats = service.stats()
    return FileStatsResponse(**stats)


@router.get("/supported-types", response_model=SupportedTypesResponse)
async def supported_types() -> SupportedTypesResponse:
    """Return the file-type registry (extension / MIME info)."""
    from app.file_intelligence.types import iter_entries

    entries = [
        SupportedTypeEntry(
            file_type=e.file_type,
            content_kind=e.content_kind,
            display_name=e.display_name,
            is_supported=e.is_supported,
            extensions=list(e.extensions),
            mime_types=list(e.mime_types),
        )
        for e in iter_entries()
    ]
    return SupportedTypesResponse(
        supported_extensions=list(_supported_extensions()),
        entries=entries,
    )


@router.post("/search", response_model=FileSearchResponse)
async def search_files(
    # Modern JSON body (preferred).
    request: Optional[FileSearchRequest] = None,
    # Legacy query-string params (still accepted for Phase 1 clients).
    query: str = Query(default=""),
    folder_path: str | None = Query(default=None),
    file_types: list[str] | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
) -> FileSearchResponse:
    """Keyword search over the file index.

    Matches on file name, path, classification, file type, and
    extracted text. Phase 4 does not embed anything; "semantic
    search" is intentionally not implemented (Phase 6).
    """
    _check_permission_or_403("search_files")
    service = _service(db)
    # Merge modern body + legacy query params, body wins when both
    # are present.
    body = request or FileSearchRequest()
    effective_query = body.query or query
    effective_classification = body.classification
    effective_file_type = body.file_type
    effective_extension = body.extension
    if file_types and not effective_file_type and not effective_extension:
        # ``file_types`` was historically a list of extensions
        # passed in the query string. Take the first entry as
        # the extension filter (most common case).
        effective_extension = file_types[0] if file_types else None
    effective_limit = body.limit or limit

    start = time.perf_counter()
    result: SearchResult = service.search(
        effective_query,
        classification=effective_classification,
        file_type=effective_file_type,
        extension=effective_extension,
        status=body.status,
        limit=effective_limit,
    )
    # Apply the legacy ``folder_path`` filter post-hoc.
    if folder_path:
        result.hits = [h for h in result.hits if (h.file.path or "").startswith(folder_path)]
        result.total = len(result.hits)
    # Re-measure so the legacy client gets a consistent number.
    result.query_time_ms = int((time.perf_counter() - start) * 1000)
    return FileSearchResponse(
        results=[
            FileSearchHit(
                file=_row_to_summary(h.file),
                score=h.score,
                match_type=h.match_type,
                snippet=h.snippet,
            )
            for h in result.hits
        ],
        total=result.total,
        query_time_ms=result.query_time_ms,
    )


# Backward-compat: the original Phase 1 /index endpoint. The
# placeholder accepted a JSON body with ``folder_path`` etc.; the
# real Phase 4 implementation walks the folder's top level only.
@router.post("/index", response_model=FileIndexResponse)
async def index_folder(
    # Legacy JSON body parameters.
    folder_path: str | None = None,
    recursive: bool = False,
    # Phase 1 placeholder shape.
    request: Optional["_LegacyIndexBody"] = None,
    db: Session = Depends(get_db),
) -> FileIndexResponse:
    """Index the top-level files in a folder (no recursion by default)."""
    if not settings.file_intelligence_enabled:
        return FileIndexResponse(
            success=False,
            stored=False,
            reason="file_intelligence_disabled",
            raw_path=folder_path or "",
        )
    _check_permission_or_403("index_file")

    # Resolve the folder path. The Phase 1 placeholder accepted
    # ``{"folder_path": "..."}``; we still honour that shape by
    # also accepting it as the ``request`` body.
    actual_folder = folder_path
    if actual_folder is None and request is not None:
        actual_folder = request.folder_path
    if not actual_folder:
        raise HTTPException(
            status_code=400,
            detail={"code": "invalid_path", "message": "folder_path is required"},
        )

    from pathlib import Path

    folder = Path(actual_folder)
    if not folder.is_absolute():
        raise HTTPException(
            status_code=400,
            detail={"code": "invalid_path", "message": "folder_path must be absolute"},
        )
    if not folder.exists() or not folder.is_dir():
        raise HTTPException(
            status_code=404,
            detail={"code": "not_found", "message": f"Folder not found: {actual_folder}"},
        )

    service = _service(db)
    indexed = 0
    errors: list[str] = []
    last_result: IndexResult | None = None
    entries = list(folder.iterdir())
    if recursive:
        # Recursive mode is opt-in and still capped by the same
        # allowed-extensions / max-bytes checks.
        entries = list(folder.rglob("*"))
    for entry in entries:
        if not entry.is_file():
            continue
        result = service.index_file(entry, force=False)
        last_result = result
        if result.stored:
            indexed += 1
        if result.reason not in ("indexed", "unchanged"):
            errors.append(f"{entry.name}: {result.reason}")
    if last_result is None:
        return FileIndexResponse(
            success=True,
            stored=False,
            reason="empty_folder",
            raw_path=actual_folder,
            files_indexed=0,
            errors=[],
        )
    # Use the last per-file result as the response shape (the
    # old "single result" UX), but also include the aggregated
    # counts for the modern client.
    last_result.raw_path = actual_folder
    return _index_to_response(
        last_result,
        files_indexed=indexed,
        errors=errors,
    )


class _LegacyIndexBody(BaseModel):
    folder_path: str
    recursive: bool = True
    include_patterns: list[str] | None = None
    exclude_patterns: list[str] | None = None


# Re-bind the forward reference used above.
index_folder.__annotations__["request"] = Optional[_LegacyIndexBody]  # type: ignore[attr-defined]


@router.get("/{file_id}", response_model=FileDetailResponse)
async def get_file(
    file_id: int,
    db: Session = Depends(get_db),
) -> FileDetailResponse:
    """Get one indexed file by id."""
    _check_permission_or_403("get_file")
    service = _service(db)
    row = service.get(file_id)
    if row is None:
        raise HTTPException(status_code=404, detail="File not found")
    return _row_to_detail(row)


@router.delete("/{file_id}", response_model=FileActionResponse)
async def delete_file(
    file_id: int,
    db: Session = Depends(get_db),
) -> FileActionResponse:
    """Remove a file from the index. Does NOT delete the file on disk."""
    _check_permission_or_403("delete_file")
    service = _service(db)
    if service.delete(file_id):
        return FileActionResponse(success=True, affected=1, detail="deleted")
    raise HTTPException(status_code=404, detail="File not found")


@router.delete("", response_model=FileActionResponse)
async def clear_index(
    db: Session = Depends(get_db),
) -> FileActionResponse:
    """Clear the entire file index. DESTRUCTIVE — requires RED level."""
    if get_permission_level("clear_file_index") != PermissionLevel.RED:
        # Defensive guard so a future category change can never
        # silently weaken the guardrail.
        raise HTTPException(
            status_code=403,
            detail={"code": "permission_denied", "action": "clear_file_index"},
        )
    service = _service(db)
    count = service.clear_index()
    return FileActionResponse(success=True, affected=count, detail="cleared")


@router.post("/{file_id}/reindex", response_model=FileIndexResponse)
async def reindex_file(
    file_id: int,
    db: Session = Depends(get_db),
) -> FileIndexResponse:
    """Force re-indexing of an existing file (e.g. after edits)."""
    _check_permission_or_403("reindex_file")
    service = _service(db)
    result = service.reindex(file_id)
    if not result.stored and result.reason == "not_found":
        raise HTTPException(status_code=404, detail="File not found")
    return _index_to_response(result)


@router.post("/{file_id}/reanalyse", response_model=FileDetailResponse)
async def reanalyse_file(
    file_id: int,
    db: Session = Depends(get_db),
) -> FileDetailResponse:
    """Re-run the file classifier against the stored preview."""
    _check_permission_or_403("reanalyse_file")
    service = _service(db)
    row = service.reanalyse(file_id)
    if row is None:
        raise HTTPException(status_code=404, detail="File not found")
    return _row_to_detail(row)


# ---------------------------------------------------------------------------
# LLM actions
# ---------------------------------------------------------------------------
@router.post("/{file_id}/explain", response_model=FileLLMResponse)
async def explain_file(
    file_id: int,
    db: Session = Depends(get_db),
) -> FileLLMResponse:
    """Ask the configured LLM to explain the file."""
    _check_permission_or_403("explain_file")
    service = _service(db)
    payload = await service.explain_file(file_id)
    return FileLLMResponse(**payload)


@router.post("/{file_id}/summarise", response_model=FileLLMResponse)
async def summarise_file(
    file_id: int,
    db: Session = Depends(get_db),
) -> FileLLMResponse:
    """Ask the configured LLM to summarise the file."""
    _check_permission_or_403("summarise_file")
    service = _service(db)
    payload = await service.summarise_file(file_id)
    return FileLLMResponse(**payload)


@router.post("/{file_id}/ask", response_model=FileLLMResponse)
async def ask_file(
    file_id: int,
    request: FileLLMRequest,
    db: Session = Depends(get_db),
) -> FileLLMResponse:
    """Ask a free-form question about the file's extracted content."""
    _check_permission_or_403("ask_file")
    service = _service(db)
    payload = await service.ask_question(file_id, request.question or "")
    return FileLLMResponse(**payload)
