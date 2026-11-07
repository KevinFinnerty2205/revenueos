"""Bind live-intelligence sessions to their authorised provider.

Revision ID: 0070_live_provider_binding
Revises: 0069_private_live_notes

The provider choice and external-processing acknowledgement are immutable facts
of a live session. Persisting them prevents a local session from beginning to
send transcript windows externally after a configuration change or restart.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0070_live_provider_binding"
down_revision: str | None = "0069_private_live_notes"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("live_interaction_sessions") as batch:
        batch.add_column(
            sa.Column(
                "provider_name",
                sa.String(length=50),
                server_default="mock",
                nullable=False,
            )
        )
        batch.add_column(
            sa.Column(
                "provider_uses_external_processing",
                sa.Boolean(),
                server_default=sa.false(),
                nullable=False,
            )
        )
        batch.add_column(
            sa.Column(
                "external_processing_acknowledged_at",
                sa.DateTime(timezone=True),
                nullable=True,
            )
        )
        batch.create_check_constraint(
            "ck_live_sessions_provider_name",
            "length(trim(provider_name)) BETWEEN 1 AND 50",
        )
        batch.create_check_constraint(
            "ck_live_sessions_external_ack",
            "(provider_uses_external_processing = false AND "
            "external_processing_acknowledged_at IS NULL) OR "
            "(provider_uses_external_processing = true AND "
            "external_processing_acknowledged_at IS NOT NULL)",
        )


def downgrade() -> None:
    with op.batch_alter_table("live_interaction_sessions") as batch:
        batch.drop_constraint("ck_live_sessions_external_ack", type_="check")
        batch.drop_constraint("ck_live_sessions_provider_name", type_="check")
        batch.drop_column("external_processing_acknowledged_at")
        batch.drop_column("provider_uses_external_processing")
        batch.drop_column("provider_name")
