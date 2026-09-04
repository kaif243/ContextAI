"""Phase 3: Clipboard Intelligence columns and indexes.

Revision ID: 003
Revises: 002
Create Date: 2026-09-04

Phase 3 extends ``clipboard_items`` with the new fields required by the
Clipboard Intelligence pipeline:

  * ``metadata_json``        — extracted entities + classifier signals
  * ``expires_at``           — retention timestamp (nullable for pinned/legacy)
  * ``is_sensitive``         — boolean flag for secret material
  * ``sensitive_reasons``    — comma-separated rule names that fired
  * ``redacted_content``     — safe preview stored alongside (or instead of) ``content``
  * ``source_app``           — extended to 200 chars to match the screen model
  * ``classification_confidence`` — heuristic score for the new content classifier
  * ``classifier_version``   — version tag of the classifier that labelled the row

The existing ``user_id`` foreign key is re-declared so that the column
keeps its ``ON DELETE CASCADE`` semantics after the model side stopped
declaring it inline. All operations use ``render_as_batch=True`` via
``env.py`` so SQLite ALTER TABLE is wrapped in a transaction.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Apply Phase 3 clipboard schema changes."""
    with op.batch_alter_table("clipboard_items", schema=None) as batch_op:
        # The user_id FK already exists in the Phase 1 schema with
        # ON DELETE CASCADE; do not try to re-add it here.
        batch_op.add_column(sa.Column("metadata_json", sa.JSON(), nullable=True))
        batch_op.add_column(
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True)
        )
        batch_op.add_column(
            sa.Column("is_sensitive", sa.Boolean(), nullable=False, server_default=sa.false())
        )
        batch_op.add_column(sa.Column("sensitive_reasons", sa.String(length=500), nullable=True))
        batch_op.add_column(sa.Column("redacted_content", sa.Text(), nullable=True))
        batch_op.alter_column(
            "source_app",
            existing_type=sa.String(length=100),
            type_=sa.String(length=200),
            existing_nullable=True,
        )
        batch_op.add_column(
            sa.Column("classification_confidence", sa.Float(), nullable=True)
        )
        batch_op.add_column(
            sa.Column("classifier_version", sa.String(length=50), nullable=True)
        )
        batch_op.create_index(
            "ix_clipboard_classification", ["classification"], unique=False
        )
        batch_op.create_index("ix_clipboard_sensitive", ["is_sensitive"], unique=False)
        batch_op.create_index("ix_clipboard_expires", ["expires_at"], unique=False)


def downgrade() -> None:
    """Revert Phase 3 clipboard schema changes."""
    with op.batch_alter_table("clipboard_items", schema=None) as batch_op:
        batch_op.drop_index("ix_clipboard_expires")
        batch_op.drop_index("ix_clipboard_sensitive")
        batch_op.drop_index("ix_clipboard_classification")
        batch_op.drop_column("classifier_version")
        batch_op.drop_column("classification_confidence")
        batch_op.alter_column(
            "source_app",
            existing_type=sa.String(length=200),
            type_=sa.String(length=100),
            existing_nullable=True,
        )
        batch_op.drop_column("redacted_content")
        batch_op.drop_column("sensitive_reasons")
        batch_op.drop_column("is_sensitive")
        batch_op.drop_column("expires_at")
        batch_op.drop_column("metadata_json")
