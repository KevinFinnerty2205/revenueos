"""Add the review-only Action Layer.

Revision ID: 0031_action_layer
Revises: 0030_live_interaction_intel

Downgrade warning: Action proposals, immutable revisions and metadata-only
review history are permanently removed. No external actions are affected
because this migration introduces no executor.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0031_action_layer"
down_revision: str | None = "0030_live_interaction_intel"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TENANT_TABLES = (
    "action_proposals",
    "action_proposal_versions",
    "action_audit_events",
)


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


def _create_immutability_guards() -> None:
    dialect = op.get_bind().dialect.name
    if dialect == "postgresql":
        op.execute(
            """
            CREATE FUNCTION protect_wo021_immutable_rows()
            RETURNS trigger
            LANGUAGE plpgsql
            AS $$
            BEGIN
                RAISE EXCEPTION 'Action revisions and audit events are immutable';
            END;
            $$
            """
        )
        for table_name in ("action_proposal_versions", "action_audit_events"):
            op.execute(
                f"""CREATE TRIGGER {table_name}_immutable
                BEFORE UPDATE ON {table_name}
                FOR EACH ROW EXECUTE FUNCTION protect_wo021_immutable_rows()"""
            )
    elif dialect == "sqlite":
        for table_name in ("action_proposal_versions", "action_audit_events"):
            op.execute(
                f"""CREATE TRIGGER {table_name}_immutable
                BEFORE UPDATE ON {table_name}
                FOR EACH ROW
                BEGIN
                    SELECT RAISE(ABORT, 'Action revisions and audit events are immutable');
                END"""
            )


def _drop_immutability_guards() -> None:
    dialect = op.get_bind().dialect.name
    if dialect == "postgresql":
        for table_name in ("action_proposal_versions", "action_audit_events"):
            op.execute(f"DROP TRIGGER {table_name}_immutable ON {table_name}")
        op.execute("DROP FUNCTION protect_wo021_immutable_rows()")
    elif dialect == "sqlite":
        for table_name in ("action_proposal_versions", "action_audit_events"):
            op.execute(f"DROP TRIGGER {table_name}_immutable")


def upgrade() -> None:
    op.create_table(
        "action_proposals",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organisation_id", sa.Uuid(), nullable=False),
        sa.Column("opportunity_id", sa.Uuid(), nullable=False),
        sa.Column("interaction_id", sa.Uuid(), nullable=True),
        sa.Column("action_type", sa.String(length=40), server_default="other", nullable=False),
        sa.Column("status", sa.String(length=24), server_default="proposed", nullable=False),
        sa.Column("priority", sa.String(length=12), server_default="normal", nullable=False),
        sa.Column("audience", sa.String(length=20), server_default="internal", nullable=False),
        sa.Column(
            "risk_class",
            sa.String(length=32),
            server_default="internal_low_risk",
            nullable=False,
        ),
        sa.Column("current_version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("approved_version", sa.Integer(), nullable=True),
        sa.Column("source_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("semantic_key", sa.String(length=64), nullable=False),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("reviewed_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rejected_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rejection_reason_code", sa.String(length=24), nullable=True),
        sa.Column("supersedes_action_id", sa.Uuid(), nullable=True),
        sa.Column("completed_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "action_type IN ('follow_up_email', 'send_requested_material', 'create_task', "
            "'follow_up_stakeholder', 'schedule_interaction', 'update_opportunity', "
            "'update_contact', 'update_stakeholder', 'add_decision', 'add_commitment', "
            "'add_risk', 'update_timeline', 'update_procurement', 'update_security_legal', "
            "'create_reminder', 'notify_internal', 'prepare_next_interaction', "
            "'resolve_open_question', 'review_conflict', 'other')",
            name="ck_action_proposals_type",
        ),
        sa.CheckConstraint(
            "status IN ('proposed', 'edited', 'approved', 'rejected', 'superseded', 'completed_manually')",
            name="ck_action_proposals_status",
        ),
        sa.CheckConstraint("priority IN ('high', 'normal', 'low')", name="ck_action_proposals_priority"),
        sa.CheckConstraint("audience IN ('internal', 'customer_facing')", name="ck_action_proposals_audience"),
        sa.CheckConstraint(
            "risk_class IN ('internal_low_risk', 'external_customer_facing', 'data_mutation')",
            name="ck_action_proposals_risk",
        ),
        sa.CheckConstraint("current_version > 0", name="ck_action_proposals_current_version"),
        sa.CheckConstraint(
            "approved_version IS NULL OR approved_version BETWEEN 1 AND current_version",
            name="ck_action_proposals_approved_version",
        ),
        sa.CheckConstraint("length(source_fingerprint) = 64", name="ck_action_proposals_fingerprint"),
        sa.CheckConstraint("length(semantic_key) = 64", name="ck_action_proposals_semantic_key"),
        sa.CheckConstraint(
            "rejection_reason_code IS NULL OR rejection_reason_code IN "
            "('already_done', 'incorrect', 'not_relevant', 'unsupported', 'duplicate', 'not_now', 'other')",
            name="ck_action_proposals_rejection_reason",
        ),
        sa.ForeignKeyConstraint(["organisation_id"], ["organisations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["organisation_id", "opportunity_id"],
            ["opportunities.organisation_id", "opportunities.id"],
            name="fk_action_proposals_opportunity_tenant",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["organisation_id", "interaction_id"],
            ["interactions.organisation_id", "interactions.id"],
            name="fk_action_proposals_interaction_tenant",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["organisation_id", "created_by_user_id"],
            ["organisation_memberships.organisation_id", "organisation_memberships.user_id"],
            name="fk_action_proposals_creator_tenant",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organisation_id", "reviewed_by_user_id"],
            ["organisation_memberships.organisation_id", "organisation_memberships.user_id"],
            name="fk_action_proposals_reviewer_tenant",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organisation_id", "completed_by_user_id"],
            ["organisation_memberships.organisation_id", "organisation_memberships.user_id"],
            name="fk_action_proposals_completer_tenant",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organisation_id", "supersedes_action_id"],
            ["action_proposals.organisation_id", "action_proposals.id"],
            name="fk_action_proposals_supersedes_tenant",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organisation_id", "id", name="uq_action_proposals_org_id"),
        sa.UniqueConstraint(
            "organisation_id",
            "opportunity_id",
            "source_fingerprint",
            name="uq_action_proposals_source_fingerprint",
        ),
    )
    op.create_index(
        "ix_action_proposals_org_opportunity_status",
        "action_proposals",
        ["organisation_id", "opportunity_id", "status"],
    )
    op.create_index(
        "ix_action_proposals_org_created",
        "action_proposals",
        ["organisation_id", "generated_at"],
    )
    op.create_index(
        "ix_action_proposals_org_semantic",
        "action_proposals",
        ["organisation_id", "opportunity_id", "semantic_key"],
    )

    op.create_table(
        "action_proposal_versions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organisation_id", sa.Uuid(), nullable=False),
        sa.Column("action_id", sa.Uuid(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=240), nullable=False),
        sa.Column("description", sa.String(length=2000), nullable=False),
        sa.Column("proposed_due_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("target_entity_type", sa.String(length=24), nullable=True),
        sa.Column("target_entity_id", sa.Uuid(), nullable=True),
        sa.Column("payload_json", sa.JSON(), nullable=False),
        sa.Column("source_refs_json", sa.JSON(), nullable=False),
        sa.Column("provenance_summary", sa.String(length=2000), nullable=False),
        sa.Column("content_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("version > 0", name="ck_action_versions_version"),
        sa.CheckConstraint("length(trim(title)) BETWEEN 1 AND 240", name="ck_action_versions_title"),
        sa.CheckConstraint(
            "length(trim(description)) BETWEEN 1 AND 2000",
            name="ck_action_versions_description",
        ),
        sa.CheckConstraint(
            "target_entity_type IS NULL OR target_entity_type IN "
            "('opportunity', 'contact', 'stakeholder', 'interaction', 'task', 'internal_user')",
            name="ck_action_versions_target_type",
        ),
        sa.CheckConstraint(
            "(target_entity_type IS NULL AND target_entity_id IS NULL) OR target_entity_type IS NOT NULL",
            name="ck_action_versions_target_pair",
        ),
        sa.CheckConstraint(
            "length(trim(provenance_summary)) BETWEEN 1 AND 2000",
            name="ck_action_versions_provenance",
        ),
        sa.CheckConstraint("length(content_fingerprint) = 64", name="ck_action_versions_fingerprint"),
        sa.ForeignKeyConstraint(["organisation_id"], ["organisations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["organisation_id", "action_id"],
            ["action_proposals.organisation_id", "action_proposals.id"],
            name="fk_action_versions_action_tenant",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["organisation_id", "created_by_user_id"],
            ["organisation_memberships.organisation_id", "organisation_memberships.user_id"],
            name="fk_action_versions_creator_tenant",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organisation_id", "id", name="uq_action_versions_org_id"),
        sa.UniqueConstraint("organisation_id", "action_id", "version", name="uq_action_versions_action_version"),
    )
    op.create_index(
        "ix_action_versions_org_action",
        "action_proposal_versions",
        ["organisation_id", "action_id", "version"],
    )

    op.create_table(
        "action_audit_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organisation_id", sa.Uuid(), nullable=False),
        sa.Column("action_id", sa.Uuid(), nullable=False),
        sa.Column("actor_user_id", sa.Uuid(), nullable=False),
        sa.Column("event_type", sa.String(length=24), nullable=False),
        sa.Column("proposal_version", sa.Integer(), nullable=False),
        sa.Column("metadata_json", sa.JSON(), server_default=sa.text("'{}'"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "event_type IN ('proposed', 'edited', 'approved', 'rejected', 'superseded', 'completed_manually')",
            name="ck_action_audit_events_type",
        ),
        sa.CheckConstraint("proposal_version > 0", name="ck_action_audit_events_version"),
        sa.ForeignKeyConstraint(["organisation_id"], ["organisations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["organisation_id", "action_id"],
            ["action_proposals.organisation_id", "action_proposals.id"],
            name="fk_action_audit_events_action_tenant",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["organisation_id", "actor_user_id"],
            ["organisation_memberships.organisation_id", "organisation_memberships.user_id"],
            name="fk_action_audit_events_actor_tenant",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organisation_id", "id", name="uq_action_audit_events_org_id"),
    )
    op.create_index(
        "ix_action_audit_events_org_action_created",
        "action_audit_events",
        ["organisation_id", "action_id", "created_at"],
    )
    _enable_tenant_rls()
    _create_immutability_guards()


def downgrade() -> None:
    _drop_immutability_guards()
    op.drop_table("action_audit_events")
    op.drop_table("action_proposal_versions")
    op.drop_table("action_proposals")
