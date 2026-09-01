"""Files endpoint for file intelligence feature."""

import time
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.logging import get_logger
from app.core.security import get_permission_level, PermissionLevel
from app.models.file_index import FileIndex

logger = get_logger(__name__)

router = APIRouter()


# Pydantic models
class FileSearchResult(BaseModel):
    """File search result model."""

    path: str
    name: str
    size: int
    modified: str | None
    score: float
    match_type: str


class FileSearchResponse(BaseModel):
    """File search response model."""

    results: list[FileSearchResult]
    total: int
    query_time_ms: int


class FileIndexRequest(BaseModel):
    """File index request model."""

    folder_path: str
    recursive: bool = True
    include_patterns: list[str] | None = None
    exclude_patterns: list[str] | None = None


class FileIndexResponse(BaseModel):
    """File index response model."""

    success: bool
    files_indexed: int
    errors: list[str]


@router.post("/search", response_model=FileSearchResponse)
async def search_files(
    query: str,
    folder_path: str | None = None,
    file_types: list[str] | None = None,
    limit: int = Query(default=20, ge=1, le=100),
    semantic: bool = False,
    db: Session = Depends(get_db),
) -> FileSearchResponse:
    """
    Search indexed files.

    Supports both keyword search and semantic search.
    For Phase 1, only keyword search is implemented.
    """
    start_time = time.time()

    # Check permission
    permission = get_permission_level("search_files")
    logger.debug(f"File search requested: '{query}' (semantic: {semantic}, permission: {permission.name})")

    # Build query
    search_query = db.query(FileIndex).filter(FileIndex.is_deleted == False)  # noqa: E712

    # Keyword search in name and path
    if query:
        search_query = search_query.filter(
            (FileIndex.name.ilike(f"%{query}%")) |
            (FileIndex.path.ilike(f"%{query}%"))
        )

    # Filter by folder
    if folder_path:
        search_query = search_query.filter(FileIndex.path.startswith(folder_path))

    # Filter by file types
    if file_types:
        search_query = search_query.filter(FileIndex.extension.in_(file_types))

    # Get results
    files = search_query.limit(limit).all()

    results = [
        FileSearchResult(
            path=file.path,
            name=file.name,
            size=file.size_bytes,
            modified=file.modified_at.isoformat() if file.modified_at else None,
            score=0.8,  # Placeholder for similarity score
            match_type="keyword",
        )
        for file in files
    ]

    query_time = int((time.time() - start_time) * 1000)

    return FileSearchResponse(
        results=results,
        total=len(results),
        query_time_ms=query_time,
    )


@router.post("/index", response_model=FileIndexResponse)
async def index_folder(
    request: FileIndexRequest,
    db: Session = Depends(get_db),
) -> FileIndexResponse:
    """
    Index a folder for file search.

    This is a placeholder for Phase 1. Full implementation in Phase 4.
    """
    # Check permission
    permission = get_permission_level("search_files")
    logger.info(f"Folder indexing requested: {request.folder_path} (permission: {permission.name})")

    # Phase 1 placeholder - return mock response
    return FileIndexResponse(
        success=True,
        files_indexed=0,
        errors=[],
    )


@router.get("")
async def list_files(
    folder_path: str | None = None,
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    file_type: str | None = None,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """
    List indexed files.

    Returns paginated list of indexed files.
    """
    query = db.query(FileIndex).filter(FileIndex.is_deleted == False)  # noqa: E712

    if folder_path:
        query = query.filter(FileIndex.path.startswith(folder_path))

    if file_type:
        query = query.filter(FileIndex.file_type == file_type)

    total = query.count()
    files = query.offset(offset).limit(limit).all()

    return {
        "files": [
            {
                "id": file.id,
                "path": file.path,
                "name": file.name,
                "file_type": file.file_type,
                "size_bytes": file.size_bytes,
                "modified_at": file.modified_at.isoformat() if file.modified_at else None,
                "classification": file.classification,
                "is_indexed": file.is_indexed,
            }
            for file in files
        ],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.get("/{file_id}")
async def get_file(
    file_id: int,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Get details of an indexed file."""
    file = db.query(FileIndex).filter(FileIndex.id == file_id).first()
    if file is None:
        raise HTTPException(status_code=404, detail="File not found")

    return {
        "id": file.id,
        "path": file.path,
        "name": file.name,
        "file_type": file.file_type,
        "extension": file.extension,
        "size_bytes": file.size_bytes,
        "created_at_fs": file.created_at_fs.isoformat() if file.created_at_fs else None,
        "modified_at": file.modified_at.isoformat() if file.modified_at else None,
        "classification": file.classification,
        "classification_confidence": file.classification_confidence,
        "is_indexed": file.is_indexed,
        "metadata": file.metadata_json,
        "tags": file.tags.split(",") if file.tags else [],
    }
