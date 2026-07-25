"""Add tenant-owned private beta controls and operational records.

Revision ID: 0020_private_beta_readiness
Revises: 0019_revenue_brain_reasoning

Downgrade warning: downgrading permanently removes beta consent, settings,
onboarding, usage, feedback, request and safe-event metadata, user/membership
status, and organisation external-auth mappings. Historical manager roles
mapped to member cannot be reconstructed.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0020_private_beta_readiness"
down_revision: str | None = "0019_revenue_brain_reasoning"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TENANT_TABLES = (
    "organisation_beta_settings",
    "data_notice_acknowledgements",
    "onboarding_progress",
    "ai_usage_counters",
    "beta_feedback",
    "beta_data_requests",
    "beta_system_events",
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


def _allow_approved_brain_deletion() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return
    op.execute(
        """
        CREATE OR REPLACE FUNCTION prevent_revenue_brain_snapshot_mutation()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
            IF TG_OP = 'DELETE'
               AND current_setting('app.beta_maintenance', true) = 'approved'
               AND OLD.organisation_id = NULLIF(current_setting('app.organisation_id', true), '')::uuid THEN
                RETURN OLD;
            END IF;
            RAISE EXCEPTION 'Revenue Brain snapshots are append only';
        END;
        $$
        """
    )
    op.execute(
        """
        CREATE OR REPLACE FUNCTION prevent_revenue_brain_insight_mutation()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
            IF TG_OP = 'DELETE'
               AND current_setting('app.beta_maintenance', true) = 'approved'
               AND OLD.organisation_id = NULLIF(current_setting('app.organisation_id', true), '')::uuid THEN
                RETURN OLD;
            END IF;
            RAISE EXCEPTION 'Revenue Brain insights are append only';
        END;
        $$
        """
    )


def _restore_brain_immutability() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return
    op.execute(
        """
        CREATE OR REPLACE FUNCTION prevent_revenue_brain_snapshot_mutation()
        RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION 'Revenue Brain snapshots are append only';
        END;
        $$
        """
    )
    op.execute(
        """
        CREATE OR REPLACE FUNCTION prevent_revenue_brain_insight_mutation()
        RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION 'Revenue Brain insights are append only';
        END;
        $$
        """
    )


def upgrade() -> None:
    uuid_type = sa.Uuid(as_uuid=True)
    with op.batch_alter_table("organisations") as batch:
        batch.add_column(sa.Column("external_auth_id", sa.String(length=255), nullable=True))
        batch.create_unique_constraint("uq_organisations_external_auth_id", ["external_auth_id"])
    with op.batch_alter_table("users") as batch:
        batch.add_column(sa.Column("status", sa.String(length=20), server_default="active", nullable=False))
        batch.create_check_constraint("ck_users_status", "status IN ('active', 'disabled')")
    op.execute("UPDATE organisation_memberships SET role = 'member' WHERE role = 'manager'")
    with op.batch_alter_table("organisation_memberships") as batch:
        batch.drop_constraint("ck_memberships_role", type_="check")
        batch.create_check_constraint("ck_memberships_role", "role IN ('admin', 'member')")
        batch.add_column(sa.Column("status", sa.String(length=20), server_default="active", nullable=False))
        batch.add_column(
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                nullable=False,
            )
        )
        batch.create_check_constraint("ck_memberships_status", "status IN ('active', 'disabled')")

    op.create_table(
        "organisation_beta_settings",
        sa.Column("organisation_id", uuid_type, nullable=False),
        sa.Column("retention_days", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "retention_days IS NULL OR retention_days IN (30, 90, 180)",
            name="ck_organisation_beta_settings_retention",
        ),
        sa.ForeignKeyConstraint(
            ["organisation_id"],
            ["organisations.id"],
            name="fk_organisation_beta_settings_organisation",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("organisation_id"),
    )
    op.create_table(
        "data_notice_acknowledgements",
        sa.Column("id", uuid_type, nullable=False),
        sa.Column("organisation_id", uuid_type, nullable=False),
        sa.Column("user_id", uuid_type, nullable=False),
        sa.Column("notice_version", sa.Integer(), nullable=False),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("notice_version > 0", name="ck_data_notice_acknowledgements_version"),
        sa.ForeignKeyConstraint(
            ["organisation_id"],
            ["organisations.id"],
            name="fk_data_notice_acknowledgements_organisation",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["organisation_id", "user_id"],
            ["organisation_memberships.organisation_id", "organisation_memberships.user_id"],
            name="fk_data_notice_acknowledgements_membership",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organisation_id",
            "user_id",
            "notice_version",
            name="uq_data_notice_acknowledgements_version",
        ),
    )
    op.create_index(
        "ix_data_notice_acknowledgements_organisation_version",
        "data_notice_acknowledgements",
        ["organisation_id", "notice_version"],
    )
    op.create_table(
        "onboarding_progress",
        sa.Column("organisation_id", uuid_type, nullable=False),
        sa.Column("user_id", uuid_type, nullable=False),
        sa.Column("current_step", sa.Integer(), server_default="0", nullable=False),
        sa.Column("skipped", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("current_step >= 0 AND current_step <= 9", name="ck_onboarding_progress_step"),
        sa.ForeignKeyConstraint(
            ["organisation_id"],
            ["organisations.id"],
            name="fk_onboarding_progress_organisation",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["organisation_id", "user_id"],
            ["organisation_memberships.organisation_id", "organisation_memberships.user_id"],
            name="fk_onboarding_progress_membership",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("organisation_id", "user_id"),
    )
    op.create_table(
        "ai_usage_counters",
        sa.Column("organisation_id", uuid_type, nullable=False),
        sa.Column("usage_date", sa.Date(), nullable=False),
        sa.Column("generation_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("provider_request_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("generation_count >= 0", name="ck_ai_usage_counters_generations"),
        sa.CheckConstraint("provider_request_count >= 0", name="ck_ai_usage_counters_provider_requests"),
        sa.ForeignKeyConstraint(
            ["organisation_id"],
            ["organisations.id"],
            name="fk_ai_usage_counters_organisation",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("organisation_id", "usage_date"),
    )
    op.create_index(
        "ix_ai_usage_counters_organisation_date",
        "ai_usage_counters",
        ["organisation_id", "usage_date"],
    )
    op.create_table(
        "beta_feedback",
        sa.Column("id", uuid_type, nullable=False),
        sa.Column("organisation_id", uuid_type, nullable=False),
        sa.Column("user_id", uuid_type, nullable=False),
        sa.Column("category", sa.String(length=40), nullable=False),
        sa.Column("rating", sa.Integer(), nullable=True),
        sa.Column("message", sa.String(length=2000), nullable=False),
        sa.Column("current_route", sa.String(length=500), nullable=False),
        sa.Column("meeting_id", uuid_type, nullable=True),
        sa.Column("opportunity_id", uuid_type, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "category IN ('bug', 'confusing', 'inaccurate_intelligence', 'missing_feature', 'other')",
            name="ck_beta_feedback_category",
        ),
        sa.CheckConstraint("rating IS NULL OR rating BETWEEN 1 AND 5", name="ck_beta_feedback_rating"),
        sa.CheckConstraint("length(trim(message)) BETWEEN 1 AND 2000", name="ck_beta_feedback_message"),
        sa.CheckConstraint("length(current_route) BETWEEN 1 AND 500", name="ck_beta_feedback_route"),
        sa.ForeignKeyConstraint(
            ["organisation_id"],
            ["organisations.id"],
            name="fk_beta_feedback_organisation",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["organisation_id", "user_id"],
            ["organisation_memberships.organisation_id", "organisation_memberships.user_id"],
            name="fk_beta_feedback_membership",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["organisation_id", "meeting_id"],
            ["meetings.organisation_id", "meetings.id"],
            name="fk_beta_feedback_meeting_tenant",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organisation_id", "opportunity_id"],
            ["opportunities.organisation_id", "opportunities.id"],
            name="fk_beta_feedback_opportunity_tenant",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organisation_id", "id", name="uq_beta_feedback_organisation_id_id"),
    )
    op.create_index("ix_beta_feedback_organisation_created", "beta_feedback", ["organisation_id", "created_at"])
    op.create_index(
        "ix_beta_feedback_user_created",
        "beta_feedback",
        ["organisation_id", "user_id", "created_at"],
    )
    op.create_table(
        "beta_data_requests",
        sa.Column("id", uuid_type, nullable=False),
        sa.Column("organisation_id", uuid_type, nullable=False),
        sa.Column("requested_by_user_id", uuid_type, nullable=False),
        sa.Column("request_type", sa.String(length=30), nullable=False),
        sa.Column("status", sa.String(length=20), server_default="pending", nullable=False),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("output_path", sa.String(length=1000), nullable=True),
        sa.Column("failure_code", sa.String(length=100), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "request_type IN ('export', 'organisation_deletion')",
            name="ck_beta_data_requests_type",
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'processing', 'completed', 'failed')",
            name="ck_beta_data_requests_status",
        ),
        sa.CheckConstraint(
            "failure_code IS NULL OR length(failure_code) <= 100",
            name="ck_beta_data_requests_failure_code",
        ),
        sa.ForeignKeyConstraint(
            ["organisation_id"],
            ["organisations.id"],
            name="fk_beta_data_requests_organisation",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["organisation_id", "requested_by_user_id"],
            ["organisation_memberships.organisation_id", "organisation_memberships.user_id"],
            name="fk_beta_data_requests_requester",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organisation_id", "id", name="uq_beta_data_requests_organisation_id_id"),
    )
    op.create_index(
        "ix_beta_data_requests_organisation_status",
        "beta_data_requests",
        ["organisation_id", "status", "created_at"],
    )
    op.create_table(
        "beta_system_events",
        sa.Column("id", uuid_type, nullable=False),
        sa.Column("organisation_id", uuid_type, nullable=False),
        sa.Column("actor_user_id", uuid_type, nullable=True),
        sa.Column("event_type", sa.String(length=100), nullable=False),
        sa.Column("subject_id", uuid_type, nullable=True),
        sa.Column("metadata_json", sa.JSON(none_as_null=True), server_default="{}", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("length(event_type) BETWEEN 1 AND 100", name="ck_beta_system_events_type"),
        sa.ForeignKeyConstraint(
            ["organisation_id"],
            ["organisations.id"],
            name="fk_beta_system_events_organisation",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["organisation_id", "actor_user_id"],
            ["organisation_memberships.organisation_id", "organisation_memberships.user_id"],
            name="fk_beta_system_events_actor_membership",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organisation_id", "id", name="uq_beta_system_events_organisation_id_id"),
    )
    op.create_index(
        "ix_beta_system_events_organisation_created",
        "beta_system_events",
        ["organisation_id", "created_at"],
    )
    _allow_approved_brain_deletion()
    _enable_tenant_rls()


def downgrade() -> None:
    _restore_brain_immutability()
    for table_name in reversed(TENANT_TABLES):
        op.drop_table(table_name)
    with op.batch_alter_table("organisation_memberships") as batch:
        batch.drop_constraint("ck_memberships_role", type_="check")
        batch.create_check_constraint("ck_memberships_role", "role IN ('admin', 'manager', 'member')")
        batch.drop_constraint("ck_memberships_status", type_="check")
        batch.drop_column("updated_at")
        batch.drop_column("status")
    with op.batch_alter_table("users") as batch:
        batch.drop_constraint("ck_users_status", type_="check")
        batch.drop_column("status")
    with op.batch_alter_table("organisations") as batch:
        batch.drop_constraint("uq_organisations_external_auth_id", type_="unique")
        batch.drop_column("external_auth_id")
