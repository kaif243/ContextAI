"""Phase 3: Clipboard Intelligence settings columns.

Revision ID: 004
Revises: 003
Create Date: 2026-09-04

Adds the user-facing clipboard configuration columns to the
``settings`` table. Defaults are aligned with the
``AppSettings`` defaults in ``app.core.config`` so a fresh install
behaves the same whether settings are read from env vars or the DB.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "004"
down_revision: Union[str, None] = "003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("settings", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "clipboard_history_enabled",
                sa.Boolean(),
                nullable=False,
                server_default=sa.true(),
            )
        )
        batch_op.add_column(
            sa.Column(
                "clipboard_max_bytes",
                sa.Integer(),
                nullable=False,
                server_default="200000",
            )
        )
        batch_op.add_column(
            sa.Column(
                "clipboard_store_sensitive",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            )
        )
        batch_op.add_column(
            sa.Column(
                "clipboard_keep_raw_when_sensitive",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            )
        )


def downgrade() -> None:
    with op.batch_alter_table("settings", schema=None) as batch_op:
        batch_op.drop_column("clipboard_keep_raw_when_sensitive")
        batch_op.drop_column("clipboard_store_sensitive")
        batch_op.drop_column("clipboard_max_bytes")
        batch_op.drop_column("clipboard_history_enabled")
