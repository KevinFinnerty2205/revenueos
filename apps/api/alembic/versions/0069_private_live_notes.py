"""Persist private notes typed during a conversation.

Revision ID: 0069_private_live_notes
Revises: 0068_conversation_threads

Live notes remain user-private under the existing workspace owner policy. They
are deliberately separate from generated or edited post-conversation notes so
that a capture failure cannot replace what the user typed during the call.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0069_private_live_notes"
down_revision: str | None = "0068_conversation_threads"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("conversation_user_workspaces") as batch:
        batch.add_column(sa.Column("live_notes", sa.Text(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("conversation_user_workspaces") as batch:
        batch.drop_column("live_notes")
