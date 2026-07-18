"""Extend meeting audit events for AI domain services.

Revision ID: 0005_ai_domain_services
Revises: 0004_ai_database_foundation
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005_ai_domain_services"
down_revision: str | None = "0004_ai_database_foundation"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


AI_AUDIT_ACTIONS = (
    "intelligence_requested",
    "ai_job_created",
    "ai_job_status_changed",
    "ai_artifact_created",
)


def upgrade() -> None:
    with op.batch_alter_table("meeting_audit_events") as batch_op:
        batch_op.drop_constraint("ck_meeting_audit_events_action", type_="check")
        batch_op.drop_constraint("ck_meeting_audit_events_entity_type", type_="check")
        batch_op.alter_column(
            "action",
            existing_type=sa.String(length=20),
            type_=sa.String(length=40),
            existing_nullable=False,
        )
        batch_op.add_column(
            sa.Column(
                "metadata_json",
                sa.JSON(none_as_null=True),
                server_default=sa.text("'{}'"),
                nullable=False,
            )
        )
        batch_op.create_check_constraint(
            "ck_meeting_audit_events_action",
            "action IN ("
            "'created', 'updated', 'deleted', 'restored', "
            "'intelligence_requested', 'ai_job_created', "
            "'ai_job_status_changed', 'ai_artifact_created'"
            ")",
        )
        batch_op.create_check_constraint(
            "ck_meeting_audit_events_entity_type",
            "entity_type IN ('meeting', 'participant', 'transcript', 'ai_job', 'ai_artifact')",
        )


def downgrade() -> None:
    actions = ", ".join(f"'{action}'" for action in AI_AUDIT_ACTIONS)
    op.execute(f"DELETE FROM meeting_audit_events WHERE action IN ({actions})")
    with op.batch_alter_table("meeting_audit_events") as batch_op:
        batch_op.drop_constraint("ck_meeting_audit_events_action", type_="check")
        batch_op.drop_constraint("ck_meeting_audit_events_entity_type", type_="check")
        batch_op.drop_column("metadata_json")
        batch_op.alter_column(
            "action",
            existing_type=sa.String(length=40),
            type_=sa.String(length=20),
            existing_nullable=False,
        )
        batch_op.create_check_constraint(
            "ck_meeting_audit_events_action",
            "action IN ('created', 'updated', 'deleted', 'restored')",
        )
        batch_op.create_check_constraint(
            "ck_meeting_audit_events_entity_type",
            "entity_type IN ('meeting', 'participant', 'transcript')",
        )
