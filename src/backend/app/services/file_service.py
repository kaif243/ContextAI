"""File service for managing file indexing and search."""

import time
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from app.models.file_index import FileIndex
from app.core.logging import get_logger

logger = get_logger(__name__)


class FileService:
    """Service for file indexing and search."""

    def __init__(self, db: Session):
        """Initialize file service."""
        self.db = db

    def search_files(
        self,
        query: str,
        folder_path: str | None = None,
        file_types: list[str] | None = None,
        limit: int = 20,
        semantic: bool = False,
    ) -> dict[str, Any]:
        """
        Search indexed files.

        Args:
            query: Search query.
            folder_path: Optional folder path filter.
            file_types: Optional file type filters.
            limit: Maximum results to return.
            semantic: Whether to use semantic search.

        Returns:
            Search results with metadata.
        """
        start_time = time.time()

        search_query = self.db.query(FileIndex).filter(FileIndex.is_deleted == False)  # noqa: E712

        # Keyword search
        if query:
            search_query = search_query.filter(
                (FileIndex.name.ilike(f"%{query}%")) |
                (FileIndex.path.ilike(f"%{query}%"))
            )

        if folder_path:
            search_query = search_query.filter(FileIndex.path.startswith(folder_path))

        if file_types:
            search_query = search_query.filter(FileIndex.extension.in_(file_types))

        files = search_query.limit(limit).all()

        results = [
            {
                "path": file.path,
                "name": file.name,
                "size": file.size_bytes,
                "modified": file.modified_at.isoformat() if file.modified_at else None,
                "score": 0.8,  # Placeholder
                "match_type": "keyword" if not semantic else "semantic",
            }
            for file in files
        ]

        query_time = int((time.time() - start_time) * 1000)

        return {
            "results": results,
            "total": len(results),
            "query_time_ms": query_time,
        }

    def index_folder(
        self,
        folder_path: str,
        recursive: bool = True,
        exclude_patterns: list[str] | None = None,
    ) -> dict[str, Any]:
        """
        Index files in a folder.

        Args:
            folder_path: Path to the folder to index.
            recursive: Whether to index subdirectories.
            exclude_patterns: Patterns to exclude from indexing.

        Returns:
            Indexing results.
        """
        # Phase 1 placeholder - full implementation in Phase 4
        logger.info(f"Folder indexing requested: {folder_path}")

        return {
            "success": True,
            "files_indexed": 0,
            "errors": [],
        }

    def get_file(self, file_id: int) -> FileIndex | None:
        """Get a file by ID."""
        return self.db.query(FileIndex).filter(FileIndex.id == file_id).first()

    def list_files(
        self,
        folder_path: str | None = None,
        file_type: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[dict[str, Any]], int]:
        """
        List indexed files.

        Returns:
            Tuple of (files, total_count).
        """
        query = self.db.query(FileIndex).filter(FileIndex.is_deleted == False)  # noqa: E712

        if folder_path:
            query = query.filter(FileIndex.path.startswith(folder_path))

        if file_type:
            query = query.filter(FileIndex.file_type == file_type)

        total = query.count()
        files = query.offset(offset).limit(limit).all()

        return [
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
        ], total
