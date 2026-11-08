"""Separate briefing source observation from operational row updates.

Revision ID: 0076_briefing_source_observation
Revises: 0075_automatic_draft_job_origin

Worker claims, retries and receipts advance the ordinary ``updated_at`` value.
Briefing discovery instead needs a durable cursor that changes only after the
delivery envelope has been recomputed from its source records.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0076_briefing_source_observation"
down_revision: str | None = "0075_automatic_draft_job_origin"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "conversation_briefing_outbox",
        sa.Column("source_observed_at", sa.DateTime(timezone=True), nullable=True),
    )
    # ``created_at`` is the last safe lower bound for legacy materialisation.
    # In particular, do not copy ``updated_at``: a later worker retry may have
    # occurred without re-rendering the stored subject or body.
    op.execute(
        "UPDATE conversation_briefing_outbox SET source_observed_at = created_at WHERE source_observed_at IS NULL"
    )
    with op.batch_alter_table("conversation_briefing_outbox") as batch:
        batch.alter_column(
            "source_observed_at",
            existing_type=sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        )


def downgrade() -> None:
    with op.batch_alter_table("conversation_briefing_outbox") as batch:
        batch.drop_column("source_observed_at")
