"""Keep conversation assignment versions monotonic after unassignment.

Revision ID: 0071_assignment_tombstones
Revises: 0070_live_provider_binding

An unassigned interaction keeps its assignment state row with a null thread so
the optimistic lock version cannot reset to zero or one during an ABA
remove/recreate cycle.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0071_assignment_tombstones"
down_revision: str | None = "0070_live_provider_binding"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("conversation_thread_assignments") as batch:
        batch.alter_column(
            "thread_id",
            existing_type=sa.Uuid(as_uuid=True),
            nullable=True,
        )


def downgrade() -> None:
    # Tombstones cannot be represented by the old schema. They contain no
    # active grouping, so remove only those rows before restoring NOT NULL.
    op.execute(sa.text("DELETE FROM conversation_thread_assignments WHERE thread_id IS NULL"))
    with op.batch_alter_table("conversation_thread_assignments") as batch:
        batch.alter_column(
            "thread_id",
            existing_type=sa.Uuid(as_uuid=True),
            nullable=False,
        )
