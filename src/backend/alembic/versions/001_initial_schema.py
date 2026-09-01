"""Initial schema with all Phase 1 tables.

Revision ID: 001
Revises:
Create Date: 2026-08-31
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create initial database schema."""
    # Users table
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), autoincrement=True, primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("username", sa.String(100), unique=True, nullable=False),
        sa.Column("email", sa.String(255), unique=True, nullable=True),
        sa.Column("hashed_password", sa.String(255), nullable=True),
        sa.Column("full_name", sa.String(255), nullable=True),
        sa.Column("is_active", sa.Boolean(), default=True, nullable=False),
        sa.Column("is_superuser", sa.Boolean(), default=False, nullable=False),
    )

    # Settings table
    op.create_table(
        "settings",
        sa.Column("id", sa.Integer(), autoincrement=True, primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=True, unique=True),
        sa.Column("hotkey", sa.String(50), default="Ctrl+Space", nullable=False),
        sa.Column("auto_start", sa.Boolean(), default=False, nullable=False),
        sa.Column("minimize_to_tray", sa.Boolean(), default=True, nullable=False),
        sa.Column("privacy_mode", sa.Boolean(), default=False, nullable=False),
        sa.Column("clipboard_monitoring", sa.Boolean(), default=True, nullable=False),
        sa.Column("screen_monitoring", sa.Boolean(), default=False, nullable=False),
        sa.Column("file_indexing_enabled", sa.Boolean(), default=False, nullable=False),
        sa.Column("llm_provider", sa.String(50), default="ollama", nullable=False),
        sa.Column("llm_model", sa.String(100), default="llama3.1:8b", nullable=False),
        sa.Column("log_level", sa.String(20), default="INFO", nullable=False),
        sa.Column("indexed_folders", sa.String(2000), default="", nullable=False),
        sa.Column("exclude_patterns", sa.String(2000), default="node_modules,.git,__pycache__,dist,build,.venv", nullable=False),
        sa.Column("retain_clipboard_days", sa.Integer(), default=30, nullable=False),
        sa.Column("retain_memories_days", sa.Integer(), default=365, nullable=False),
    )

    # Clipboard items table
    op.create_table(
        "clipboard_items",
        sa.Column("id", sa.Integer(), autoincrement=True, primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=True),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("content_type", sa.String(50), default="text", nullable=False),
        sa.Column("classification", sa.String(50), nullable=True),
        sa.Column("importance", sa.String(20), nullable=True),
        sa.Column("source_app", sa.String(100), nullable=True),
        sa.Column("char_count", sa.Integer(), default=0, nullable=False),
        sa.Column("word_count", sa.Integer(), default=0, nullable=False),
        sa.Column("timestamp", sa.DateTime(), nullable=False),
        sa.Column("is_pinned", sa.Boolean(), default=False, nullable=False),
        sa.Column("is_encrypted", sa.Boolean(), default=False, nullable=False),
    )
    op.create_index("ix_clipboard_user_content_type", "clipboard_items", ["user_id", "content_type"])
    op.create_index("ix_clipboard_timestamp", "clipboard_items", ["timestamp"])

    # Files (file_index) table
    op.create_table(
        "files",
        sa.Column("id", sa.Integer(), autoincrement=True, primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("path", sa.Text(), nullable=False, unique=True),
        sa.Column("name", sa.String(500), nullable=False),
        sa.Column("file_type", sa.String(50), nullable=False),
        sa.Column("extension", sa.String(20), nullable=True),
        sa.Column("size_bytes", sa.Integer(), default=0, nullable=False),
        sa.Column("created_at_fs", sa.DateTime(), nullable=True),
        sa.Column("modified_at", sa.DateTime(), nullable=True),
        sa.Column("accessed_at", sa.DateTime(), nullable=True),
        sa.Column("classification", sa.String(50), nullable=True),
        sa.Column("classification_confidence", sa.Float(), nullable=True),
        sa.Column("content_hash", sa.String(64), nullable=True),
        sa.Column("text_content", sa.Text(), nullable=True),
        sa.Column("extracted_text", sa.Text(), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column("tags", sa.String(1000), default="", nullable=False),
        sa.Column("is_indexed", sa.Boolean(), default=False, nullable=False),
        sa.Column("is_deleted", sa.Boolean(), default=False, nullable=False),
        sa.Column("last_checked", sa.DateTime(), nullable=True),
        sa.Column("similar_files", sa.String(2000), nullable=True),
    )
    op.create_index("ix_file_path", "files", ["path"], unique=True)
    op.create_index("ix_file_name", "files", ["name"])
    op.create_index("ix_file_type", "files", ["file_type"])
    op.create_index("ix_file_classification", "files", ["classification"])
    op.create_index("ix_file_modified", "files", ["modified_at"])

    # File chunks table
    op.create_table(
        "file_chunks",
        sa.Column("id", sa.Integer(), autoincrement=True, primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("file_id", sa.Integer(), sa.ForeignKey("files.id", ondelete="CASCADE"), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("chunk_text", sa.Text(), nullable=False),
        sa.Column("char_start", sa.Integer(), nullable=False),
        sa.Column("char_end", sa.Integer(), nullable=False),
        sa.Column("embedding", sa.Text(), nullable=True),
        sa.Column("embedding_model", sa.String(100), nullable=True),
    )
    op.create_index("ix_chunk_file_id", "file_chunks", ["file_id"])
    op.create_index("ix_chunk_index", "file_chunks", ["file_id", "chunk_index"])

    # Memories table
    op.create_table(
        "memories",
        sa.Column("id", sa.Integer(), autoincrement=True, primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=True),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("memory_type", sa.String(50), default="note", nullable=False),
        sa.Column("tags", sa.String(1000), default="", nullable=False),
        sa.Column("is_pinned", sa.Boolean(), default=False, nullable=False),
        sa.Column("is_archived", sa.Boolean(), default=False, nullable=False),
        sa.Column("source_type", sa.String(50), nullable=True),
        sa.Column("source_id", sa.String(100), nullable=True),
        sa.Column("importance", sa.String(20), default="normal", nullable=False),
    )
    op.create_index("ix_memory_user_type", "memories", ["user_id", "memory_type"])
    op.create_index("ix_memory_pinned", "memories", ["is_pinned"])

    # Agent tasks table
    op.create_table(
        "agent_tasks",
        sa.Column("id", sa.Integer(), autoincrement=True, primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=True),
        sa.Column("request", sa.Text(), nullable=False),
        sa.Column("plan", sa.Text(), nullable=True),
        sa.Column("status", sa.String(50), default="pending", nullable=False),
        sa.Column("result", sa.Text(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("total_steps", sa.Integer(), default=0, nullable=False),
        sa.Column("completed_steps", sa.Integer(), default=0, nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("approval_required", sa.Boolean(), default=False, nullable=False),
        sa.Column("approval_status", sa.String(50), nullable=True),
        sa.Column("approved_by", sa.String(100), nullable=True),
        sa.Column("approved_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_task_status", "agent_tasks", ["status"])
    op.create_index("ix_task_created", "agent_tasks", ["created_at"])

    # Agent steps table
    op.create_table(
        "agent_steps",
        sa.Column("id", sa.Integer(), autoincrement=True, primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("task_id", sa.Integer(), sa.ForeignKey("agent_tasks.id", ondelete="CASCADE"), nullable=False),
        sa.Column("step_number", sa.Integer(), nullable=False),
        sa.Column("action", sa.String(100), nullable=False),
        sa.Column("tool", sa.String(100), nullable=True),
        sa.Column("status", sa.String(50), default="pending", nullable=False),
        sa.Column("input_data", sa.JSON(), nullable=True),
        sa.Column("output_data", sa.JSON(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("retry_count", sa.Integer(), default=0, nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("requires_approval", sa.Boolean(), default=False, nullable=False),
        sa.Column("approval_status", sa.String(50), nullable=True),
    )


def downgrade() -> None:
    """Drop all tables."""
    op.drop_table("agent_steps")
    op.drop_table("agent_tasks")
    op.drop_table("memories")
    op.drop_table("file_chunks")
    op.drop_table("files")
    op.drop_table("clipboard_items")
    op.drop_table("settings")
    op.drop_table("users")
