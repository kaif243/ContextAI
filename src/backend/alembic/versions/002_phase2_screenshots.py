"""Phase 2: Screen intelligence tables.

Revision ID: 002
Revises: 001
Create Date: 2026-09-03
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create screenshot and screen analysis tables."""
    op.create_table(
        "screenshots",
        sa.Column("id", sa.Integer(), autoincrement=True, primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=True),
        sa.Column("file_path", sa.String(length=1000), nullable=False),
        sa.Column("file_name", sa.String(length=500), nullable=False),
        sa.Column("width", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("height", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("file_size_bytes", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("content_hash", sa.String(length=64), nullable=True),
        sa.Column("region_x", sa.Integer(), nullable=True),
        sa.Column("region_y", sa.Integer(), nullable=True),
        sa.Column("region_width", sa.Integer(), nullable=True),
        sa.Column("region_height", sa.Integer(), nullable=True),
        sa.Column("monitor_index", sa.Integer(), nullable=True),
        sa.Column("ocr_text", sa.Text(), nullable=True),
        sa.Column("ocr_engine", sa.String(length=50), nullable=True),
        sa.Column("ocr_confidence", sa.Float(), nullable=True),
        sa.Column("ocr_word_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("ocr_char_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("ocr_processing_ms", sa.Integer(), nullable=True),
        sa.Column("classification", sa.String(length=50), nullable=True),
        sa.Column("classification_confidence", sa.Float(), nullable=True),
        sa.Column("classification_signals", sa.JSON(), nullable=True),
        sa.Column("classifier_version", sa.String(length=50), nullable=True),
        sa.Column("extracted_entities", sa.JSON(), nullable=True),
        sa.Column("source_app", sa.String(length=200), nullable=True),
        sa.Column("window_title", sa.String(length=500), nullable=True),
        sa.Column("is_saved", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("is_archived", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("user_notes", sa.Text(), nullable=True),
    )
    op.create_index("ix_screenshot_user_created", "screenshots", ["user_id", "created_at"])
    op.create_index("ix_screenshot_classification", "screenshots", ["classification"])

    op.create_table(
        "screen_analyses",
        sa.Column("id", sa.Integer(), autoincrement=True, primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column(
            "screenshot_id",
            sa.Integer(),
            sa.ForeignKey("screenshots.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("analysis_type", sa.String(length=50), nullable=False),
        sa.Column("question", sa.Text(), nullable=True),
        sa.Column("answer", sa.Text(), nullable=False),
        sa.Column("model_used", sa.String(length=100), nullable=True),
        sa.Column("prompt_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("completion_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("processing_ms", sa.Integer(), nullable=True),
        sa.Column("is_error", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("error_message", sa.Text(), nullable=True),
    )
    op.create_index("ix_screen_analysis_screenshot", "screen_analyses", ["screenshot_id"])
    op.create_index("ix_screen_analysis_type", "screen_analyses", ["analysis_type"])


def downgrade() -> None:
    """Drop screen analysis tables."""
    op.drop_index("ix_screen_analysis_type", table_name="screen_analyses")
    op.drop_index("ix_screen_analysis_screenshot", table_name="screen_analyses")
    op.drop_table("screen_analyses")

    op.drop_index("ix_screenshot_classification", table_name="screenshots")
    op.drop_index("ix_screenshot_user_created", table_name="screenshots")
    op.drop_table("screenshots")
