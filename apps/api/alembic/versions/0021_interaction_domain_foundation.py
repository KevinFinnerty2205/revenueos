"""Add the tenant-owned Interaction and source-neutral Evidence foundations.

Revision ID: 0021_interaction_domain_foundation
Revises: 0020_private_beta_readiness

Downgrade warning: downgrading permanently removes Interaction-only records,
Evidence envelopes, Capture Session metadata and Interaction audit history. Meeting,
Meeting Intelligence and Revenue Brain records are preserved, but Meeting-to-
Interaction links cannot be reconstructed without re-running the deterministic
upgrade backfill.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0021_interaction_domain_foundation"
down_revision: str | None = "0020_private_beta_readiness"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

BACKFILL_NAMESPACE = uuid.UUID("cf709ef5-e59d-4ce2-9c93-547a4a5e5990")
BACKFILL_BATCH_SIZE = 500
TENANT_TABLES = (
    "interactions",
    "capture_sessions",
    "evidence",
    "interaction_audit_events",
)
MEETING_TYPE_MAP = {
    "remote": "online_meeting",
    "phone": "phone_call",
    "in_person": "face_to_face_meeting",
    "other": "manual_interaction",
}
MEETING_STATUS_MAP = {
    "scheduled": "planned",
    "completed": "completed",
    "cancelled": "cancelled",
}


def _enable_tenant_rls() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return
    for table_name in TENANT_TABLES:
        op.execute(f"ALTER TABLE {table_name} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table_name} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"""CREATE POLICY {table_name}_tenant_isolation
            ON {table_name}
            USING (organisation_id = NULLIF(current_setting('app.organisation_id', true), '')::uuid)
            WITH CHECK (organisation_id = NULLIF(current_setting('app.organisation_id', true), '')::uuid)"""
        )


def _backfill_meeting_interactions() -> None:
    bind = op.get_bind()
    interactions = sa.table(
        "interactions",
        sa.column("id", sa.Uuid(as_uuid=True)),
        sa.column("organisation_id", sa.Uuid(as_uuid=True)),
        sa.column("company_id", sa.Uuid(as_uuid=True)),
        sa.column("opportunity_id", sa.Uuid(as_uuid=True)),
        sa.column("interaction_type", sa.String()),
        sa.column("lifecycle_status", sa.String()),
        sa.column("title", sa.String()),
        sa.column("scheduled_start_at", sa.DateTime(timezone=True)),
        sa.column("actual_start_at", sa.DateTime(timezone=True)),
        sa.column("actual_end_at", sa.DateTime(timezone=True)),
        sa.column("creation_origin", sa.String()),
        sa.column("created_by_user_id", sa.Uuid(as_uuid=True)),
        sa.column("created_at", sa.DateTime(timezone=True)),
        sa.column("updated_at", sa.DateTime(timezone=True)),
        sa.column("deleted_at", sa.DateTime(timezone=True)),
    )
    meetings = sa.table(
        "meetings",
        sa.column("id", sa.Uuid(as_uuid=True)),
        sa.column("organisation_id", sa.Uuid(as_uuid=True)),
        sa.column("interaction_id", sa.Uuid(as_uuid=True)),
        sa.column("company_id", sa.Uuid(as_uuid=True)),
        sa.column("opportunity_id", sa.Uuid(as_uuid=True)),
        sa.column("title", sa.String()),
        sa.column("meeting_date", sa.DateTime(timezone=True)),
        sa.column("meeting_type", sa.String()),
        sa.column("status", sa.String()),
        sa.column("created_by", sa.Uuid(as_uuid=True)),
        sa.column("created_at", sa.DateTime(timezone=True)),
        sa.column("updated_at", sa.DateTime(timezone=True)),
        sa.column("deleted_at", sa.DateTime(timezone=True)),
    )
    while True:
        rows = (
            bind.execute(
                sa.select(
                    meetings.c.id,
                    meetings.c.organisation_id,
                    meetings.c.company_id,
                    meetings.c.opportunity_id,
                    meetings.c.title,
                    meetings.c.meeting_date,
                    meetings.c.meeting_type,
                    meetings.c.status,
                    meetings.c.created_by,
                    meetings.c.created_at,
                    meetings.c.updated_at,
                    meetings.c.deleted_at,
                )
                .where(meetings.c.interaction_id.is_(None))
                .order_by(meetings.c.organisation_id, meetings.c.id)
                .limit(BACKFILL_BATCH_SIZE)
            )
            .mappings()
            .all()
        )
        if not rows:
            break
        interaction_rows: list[dict[str, object]] = []
        meeting_updates: list[dict[str, object]] = []
        for row in rows:
            organisation_id = uuid.UUID(str(row["organisation_id"]))
            meeting_id = uuid.UUID(str(row["id"]))
            interaction_id = uuid.uuid5(BACKFILL_NAMESPACE, f"{organisation_id}:{meeting_id}")
            is_completed = row["status"] == "completed"
            interaction_rows.append(
                {
                    "id": interaction_id,
                    "organisation_id": organisation_id,
                    "company_id": uuid.UUID(str(row["company_id"])) if row["company_id"] is not None else None,
                    "opportunity_id": (
                        uuid.UUID(str(row["opportunity_id"])) if row["opportunity_id"] is not None else None
                    ),
                    "interaction_type": MEETING_TYPE_MAP[str(row["meeting_type"])],
                    "lifecycle_status": MEETING_STATUS_MAP[str(row["status"])],
                    "title": row["title"],
                    "scheduled_start_at": row["meeting_date"],
                    "actual_start_at": row["meeting_date"] if is_completed else None,
                    "actual_end_at": row["meeting_date"] if is_completed else None,
                    "creation_origin": "meeting_compatibility",
                    "created_by_user_id": uuid.UUID(str(row["created_by"])),
                    "created_at": row["created_at"],
                    "updated_at": row["updated_at"],
                    "deleted_at": row["deleted_at"],
                }
            )
            meeting_updates.append({"meeting_id": meeting_id, "link_interaction_id": interaction_id})
        bind.execute(sa.insert(interactions), interaction_rows)
        bind.execute(
            sa.update(meetings)
            .where(meetings.c.id == sa.bindparam("meeting_id"))
            .values(interaction_id=sa.bindparam("link_interaction_id")),
            meeting_updates,
        )


def upgrade() -> None:
    uuid_type = sa.Uuid(as_uuid=True)
    op.create_table(
        "interactions",
        sa.Column("id", uuid_type, primary_key=True, nullable=False),
        sa.Column(
            "organisation_id",
            uuid_type,
            sa.ForeignKey("organisations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("company_id", uuid_type),
        sa.Column("opportunity_id", uuid_type),
        sa.Column("interaction_type", sa.String(length=40), server_default="manual_interaction", nullable=False),
        sa.Column("lifecycle_status", sa.String(length=20), server_default="planned", nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("scheduled_start_at", sa.DateTime(timezone=True)),
        sa.Column("scheduled_end_at", sa.DateTime(timezone=True)),
        sa.Column("actual_start_at", sa.DateTime(timezone=True)),
        sa.Column("actual_end_at", sa.DateTime(timezone=True)),
        sa.Column("timezone", sa.String(length=64)),
        sa.Column("creation_origin", sa.String(length=30), server_default="manual", nullable=False),
        sa.Column("created_by_user_id", uuid_type, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint("length(trim(title)) > 0", name="ck_interactions_title"),
        sa.CheckConstraint(
            "interaction_type IN ('online_meeting', 'face_to_face_meeting', 'presentation', 'workshop', "
            "'site_visit', 'executive_lunch', 'phone_call', 'conference_interaction', "
            "'trade_show_interaction', 'manual_interaction')",
            name="ck_interactions_type",
        ),
        sa.CheckConstraint(
            "lifecycle_status IN ('planned', 'in_progress', 'completed', 'cancelled')",
            name="ck_interactions_lifecycle_status",
        ),
        sa.CheckConstraint(
            "creation_origin IN ('manual', 'meeting_compatibility', 'imported_external')",
            name="ck_interactions_creation_origin",
        ),
        sa.CheckConstraint(
            "scheduled_end_at IS NULL OR scheduled_start_at IS NULL OR scheduled_end_at >= scheduled_start_at",
            name="ck_interactions_scheduled_range",
        ),
        sa.CheckConstraint(
            "actual_end_at IS NULL OR actual_start_at IS NULL OR actual_end_at >= actual_start_at",
            name="ck_interactions_actual_range",
        ),
        sa.ForeignKeyConstraint(
            ["organisation_id", "company_id"],
            ["companies.organisation_id", "companies.id"],
            name="fk_interactions_company_tenant",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organisation_id", "opportunity_id"],
            ["opportunities.organisation_id", "opportunities.id"],
            name="fk_interactions_opportunity_tenant",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organisation_id", "created_by_user_id"],
            ["organisation_memberships.organisation_id", "organisation_memberships.user_id"],
            name="fk_interactions_creator_membership",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint("organisation_id", "id", name="uq_interactions_organisation_id_id"),
    )
    op.create_index("ix_interactions_organisation_scheduled", "interactions", ["organisation_id", "scheduled_start_at"])
    op.create_index("ix_interactions_organisation_status", "interactions", ["organisation_id", "lifecycle_status"])
    op.create_index("ix_interactions_organisation_type", "interactions", ["organisation_id", "interaction_type"])
    op.create_index("ix_interactions_organisation_company", "interactions", ["organisation_id", "company_id"])
    op.create_index(
        "ix_interactions_organisation_opportunity",
        "interactions",
        ["organisation_id", "opportunity_id"],
    )
    op.create_index("ix_interactions_organisation_deleted", "interactions", ["organisation_id", "deleted_at"])

    op.create_table(
        "capture_sessions",
        sa.Column("id", uuid_type, primary_key=True, nullable=False),
        sa.Column(
            "organisation_id",
            uuid_type,
            sa.ForeignKey("organisations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("interaction_id", uuid_type, nullable=False),
        sa.Column("capture_type", sa.String(length=40), server_default="manual_notes", nullable=False),
        sa.Column("status", sa.String(length=20), server_default="created", nullable=False),
        sa.Column("started_by_user_id", uuid_type, nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint(
            "capture_type IN ('ai_debrief', 'voice_journal', 'live_recording', 'visual_capture', "
            "'uploaded_transcript', 'uploaded_recording', 'manual_notes')",
            name="ck_capture_sessions_type",
        ),
        sa.CheckConstraint(
            "status IN ('created', 'capturing', 'completed', 'abandoned', 'failed')",
            name="ck_capture_sessions_status",
        ),
        sa.CheckConstraint(
            "completed_at IS NULL OR started_at IS NULL OR completed_at >= started_at",
            name="ck_capture_sessions_time_range",
        ),
        sa.ForeignKeyConstraint(
            ["organisation_id", "interaction_id"],
            ["interactions.organisation_id", "interactions.id"],
            name="fk_capture_sessions_interaction_tenant",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["organisation_id", "started_by_user_id"],
            ["organisation_memberships.organisation_id", "organisation_memberships.user_id"],
            name="fk_capture_sessions_starter_membership",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint("organisation_id", "id", name="uq_capture_sessions_organisation_id_id"),
    )
    op.create_index(
        "ix_capture_sessions_organisation_interaction",
        "capture_sessions",
        ["organisation_id", "interaction_id"],
    )
    op.create_index("ix_capture_sessions_organisation_status", "capture_sessions", ["organisation_id", "status"])

    op.create_table(
        "evidence",
        sa.Column("id", uuid_type, primary_key=True, nullable=False),
        sa.Column(
            "organisation_id",
            uuid_type,
            sa.ForeignKey("organisations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("interaction_id", uuid_type, nullable=False),
        sa.Column("capture_session_id", uuid_type),
        sa.Column("evidence_type", sa.String(length=40), server_default="system_metadata", nullable=False),
        sa.Column("origin_class", sa.String(length=30), server_default="system_metadata", nullable=False),
        sa.Column("support_class", sa.String(length=20), server_default="direct", nullable=False),
        sa.Column("validation_state", sa.String(length=24), server_default="not_applicable", nullable=False),
        sa.Column("captured_by_user_id", uuid_type),
        sa.Column("captured_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("effective_start_at", sa.DateTime(timezone=True)),
        sa.Column("effective_end_at", sa.DateTime(timezone=True)),
        sa.Column("lifecycle_status", sa.String(length=20), server_default="received", nullable=False),
        sa.Column("retention_class", sa.String(length=20), server_default="inherited", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint(
            "evidence_type IN ('transcript', 'user_observation', 'recording', 'visual', "
            "'document', 'email', 'system_metadata')",
            name="ck_evidence_type",
        ),
        sa.CheckConstraint(
            "origin_class IN ('customer_direct', 'salesperson_reported', 'system_metadata', "
            "'imported_external', 'seller_prepared', 'ai_inferred')",
            name="ck_evidence_origin_class",
        ),
        sa.CheckConstraint(
            "support_class IN ('direct', 'reported', 'inferred', 'corroborated', "
            "'verified', 'disputed', 'stale', 'superseded')",
            name="ck_evidence_support_class",
        ),
        sa.CheckConstraint(
            "validation_state IN ('unreviewed', 'verified', 'disputed', 'rejected', 'not_applicable')",
            name="ck_evidence_validation_state",
        ),
        sa.CheckConstraint(
            "lifecycle_status IN ('received', 'available', 'excluded', 'superseded', 'deleted')",
            name="ck_evidence_lifecycle_status",
        ),
        sa.CheckConstraint(
            "retention_class IN ('inherited', 'short_lived', 'standard')",
            name="ck_evidence_retention_class",
        ),
        sa.CheckConstraint(
            "effective_end_at IS NULL OR effective_start_at IS NULL OR effective_end_at >= effective_start_at",
            name="ck_evidence_effective_range",
        ),
        sa.ForeignKeyConstraint(
            ["organisation_id", "interaction_id"],
            ["interactions.organisation_id", "interactions.id"],
            name="fk_evidence_interaction_tenant",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["organisation_id", "capture_session_id"],
            ["capture_sessions.organisation_id", "capture_sessions.id"],
            name="fk_evidence_capture_session_tenant",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organisation_id", "captured_by_user_id"],
            ["organisation_memberships.organisation_id", "organisation_memberships.user_id"],
            name="fk_evidence_captured_by_membership",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint("organisation_id", "id", name="uq_evidence_organisation_id_id"),
    )
    op.create_index("ix_evidence_organisation_interaction", "evidence", ["organisation_id", "interaction_id"])
    op.create_index(
        "ix_evidence_organisation_capture_session",
        "evidence",
        ["organisation_id", "capture_session_id"],
    )
    op.create_index("ix_evidence_organisation_status", "evidence", ["organisation_id", "lifecycle_status"])
    op.create_index("ix_evidence_organisation_type", "evidence", ["organisation_id", "evidence_type"])

    op.create_table(
        "interaction_audit_events",
        sa.Column("id", uuid_type, primary_key=True, nullable=False),
        sa.Column(
            "organisation_id",
            uuid_type,
            sa.ForeignKey("organisations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("interaction_id", uuid_type, nullable=False),
        sa.Column("actor_user_id", uuid_type, nullable=False),
        sa.Column("action", sa.String(length=20), nullable=False),
        sa.Column("changed_fields", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "action IN ('created', 'updated', 'completed', 'cancelled', 'deleted', 'meeting_linked')",
            name="ck_interaction_audit_events_action",
        ),
        sa.ForeignKeyConstraint(
            ["organisation_id", "interaction_id"],
            ["interactions.organisation_id", "interactions.id"],
            name="fk_interaction_audit_events_interaction_tenant",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["organisation_id", "actor_user_id"],
            ["organisation_memberships.organisation_id", "organisation_memberships.user_id"],
            name="fk_interaction_audit_events_actor_membership",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint(
            "organisation_id",
            "id",
            name="uq_interaction_audit_events_organisation_id_id",
        ),
    )
    op.create_index(
        "ix_interaction_audit_events_organisation_interaction_created",
        "interaction_audit_events",
        ["organisation_id", "interaction_id", "created_at"],
    )

    with op.batch_alter_table("meetings") as batch:
        batch.add_column(sa.Column("interaction_id", uuid_type, nullable=True))
    _backfill_meeting_interactions()
    with op.batch_alter_table("meetings") as batch:
        batch.alter_column("interaction_id", existing_type=uuid_type, nullable=False)
        batch.create_unique_constraint(
            "uq_meetings_organisation_interaction",
            ["organisation_id", "interaction_id"],
        )
        batch.create_foreign_key(
            "fk_meetings_interaction_tenant",
            "interactions",
            ["organisation_id", "interaction_id"],
            ["organisation_id", "id"],
            ondelete="RESTRICT",
        )
    _enable_tenant_rls()


def downgrade() -> None:
    with op.batch_alter_table("meetings") as batch:
        batch.drop_constraint("fk_meetings_interaction_tenant", type_="foreignkey")
        batch.drop_constraint("uq_meetings_organisation_interaction", type_="unique")
        batch.drop_column("interaction_id")
    op.drop_table("interaction_audit_events")
    op.drop_table("evidence")
    op.drop_table("capture_sessions")
    op.drop_table("interactions")
