"""Phase 4: File Intelligence schema extensions.

Revision ID: 005
Revises: 004
Create Date: 2026-09-05

The ``files`` table was originally created in the Phase 1 initial
schema (``001_initial_schema.py``). It already contains every column
Phase 4 needs (``extraction_status``, ``extraction_error``, ``tags``,
``is_indexed``, ``metadata_json``, etc.).

This migration only adds the *operational* columns Phase 4 needs for
the new indexer / search workflow:

  * ``extraction_status``  — string enum: ``pending`` / ``ok`` /
                             ``unsupported`` / ``failed`` / ``empty``
  * ``extraction_error``   — last extraction error message (nullable)
  * ``extraction_attempts`` — number of indexing attempts
  * ``indexed_at``         — timestamp the row was first persisted
  * ``text_truncated``     — boolean flag set when the extracted text
                             was truncated to ``file_max_text_chars``

It also adds two indexes that the search endpoint benefits from:

  * ``ix_file_status``     — on ``(is_indexed, is_deleted)``
  * ``ix_file_extraction_status`` — on ``extraction_status``

The model in ``app.models.file_index`` is updated in lock-step with
this migration.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "005"
down_revision: Union[str, None] = "004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Apply Phase 4 file-intelligence schema changes."""
    with op.batch_alter_table("files", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "extraction_status",
                sa.String(length=20),
                nullable=False,
                server_default="pending",
            )
        )
        batch_op.add_column(
            sa.Column("extraction_error", sa.Text(), nullable=True)
        )
        batch_op.add_column(
            sa.Column(
                "extraction_attempts",
                sa.Integer(),
                nullable=False,
                server_default="0",
            )
        )
        batch_op.add_column(
            sa.Column("indexed_at", sa.DateTime(timezone=True), nullable=True)
        )
        batch_op.add_column(
            sa.Column(
                "text_truncated",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            )
        )
        batch_op.create_index(
            "ix_file_status", ["is_indexed", "is_deleted"], unique=False
        )
        batch_op.create_index(
            "ix_file_extraction_status", ["extraction_status"], unique=False
        )


def downgrade() -> None:
    """Revert Phase 4 file-intelligence schema changes."""
    with op.batch_alter_table("files", schema=None) as batch_op:
        batch_op.drop_index("ix_file_extraction_status")
        batch_op.drop_index("ix_file_status")
        batch_op.drop_column("text_truncated")
        batch_op.drop_column("indexed_at")
        batch_op.drop_column("extraction_attempts")
        batch_op.drop_column("extraction_error")
        batch_op.drop_column("extraction_status")
