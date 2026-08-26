"""Add bounded Engage campaigns and sequences.

Revision ID: 0039_campaign_sequences
Revises: 0038_personalized_outreach

WO-030 adds an immutable launch snapshot, explicit canonical-Contact audience,
per-recipient enrolments and leased scheduled steps. Actual content and execution
continue to use the WO-029 Outreach Message and Action/Execution foundations.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0039_campaign_sequences"
down_revision: str | None = "0038_personalized_outreach"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TENANT_TABLES = (
    "engage_campaigns",
    "engage_campaign_versions",
    "engage_sequence_steps",
    "engage_campaign_audience",
    "engage_campaign_enrollments",
    "engage_enrollment_steps",
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


def _create_immutable_guards() -> None:
    dialect = op.get_bind().dialect.name
    if dialect == "postgresql":
        op.execute(
            """
            CREATE FUNCTION public.revenueos_reject_published_campaign_update()
            RETURNS trigger
            LANGUAGE plpgsql
            AS $$
            BEGIN
                IF TG_TABLE_NAME = 'engage_campaign_versions' AND OLD.status = 'published' THEN
                    RAISE EXCEPTION 'Published campaign versions are immutable';
                END IF;
                IF TG_TABLE_NAME = 'engage_campaign_audience'
                   AND OLD.contact_id IS NOT NULL
                   AND NEW.contact_id IS NULL
                   AND OLD.campaign_version_id IS NOT DISTINCT FROM NEW.campaign_version_id
                   AND OLD.company_id IS NOT DISTINCT FROM NEW.company_id
                   AND OLD.recipient_name IS NOT DISTINCT FROM NEW.recipient_name
                   AND OLD.recipient_email IS NOT DISTINCT FROM NEW.recipient_email
                   AND OLD.recipient_trust IS NOT DISTINCT FROM NEW.recipient_trust
                   AND OLD.eligible IS NOT DISTINCT FROM NEW.eligible
                   AND OLD.eligibility_code IS NOT DISTINCT FROM NEW.eligibility_code
                   AND OLD.eligibility_reason IS NOT DISTINCT FROM NEW.eligibility_reason THEN
                    RETURN NEW;
                END IF;
                IF TG_TABLE_NAME <> 'engage_campaign_versions' AND EXISTS (
                    SELECT 1 FROM engage_campaign_versions
                    WHERE organisation_id = OLD.organisation_id
                      AND id = OLD.campaign_version_id
                      AND status = 'published'
                ) THEN
                    RAISE EXCEPTION 'Published campaign audience and sequence are immutable';
                END IF;
                RETURN NEW;
            END;
            $$
            """
        )
        op.execute(
            """CREATE TRIGGER engage_campaign_versions_immutable
            BEFORE UPDATE ON engage_campaign_versions
            FOR EACH ROW EXECUTE FUNCTION public.revenueos_reject_published_campaign_update()"""
        )
        for table_name in ("engage_sequence_steps", "engage_campaign_audience"):
            op.execute(
                f"""CREATE TRIGGER {table_name}_immutable
                BEFORE UPDATE ON {table_name}
                FOR EACH ROW EXECUTE FUNCTION public.revenueos_reject_published_campaign_update()"""
            )
    elif dialect == "sqlite":
        op.execute(
            """CREATE TRIGGER engage_campaign_versions_immutable_update
            BEFORE UPDATE ON engage_campaign_versions
            FOR EACH ROW WHEN OLD.status = 'published'
            BEGIN SELECT RAISE(ABORT, 'Published campaign versions are immutable'); END"""
        )
        op.execute(
            """CREATE TRIGGER engage_sequence_steps_immutable_update
            BEFORE UPDATE ON engage_sequence_steps
            FOR EACH ROW WHEN (SELECT status FROM engage_campaign_versions
                WHERE organisation_id = OLD.organisation_id AND id = OLD.campaign_version_id) = 'published'
            BEGIN SELECT RAISE(ABORT, 'Published campaign audience and sequence are immutable'); END"""
        )
        op.execute(
            """CREATE TRIGGER engage_campaign_audience_immutable_update
            BEFORE UPDATE ON engage_campaign_audience
            FOR EACH ROW WHEN (SELECT status FROM engage_campaign_versions
                WHERE organisation_id = OLD.organisation_id AND id = OLD.campaign_version_id) = 'published'
                AND NOT (
                    OLD.contact_id IS NOT NULL AND NEW.contact_id IS NULL
                    AND OLD.campaign_version_id IS NEW.campaign_version_id
                    AND OLD.company_id IS NEW.company_id
                    AND OLD.recipient_name IS NEW.recipient_name
                    AND OLD.recipient_email IS NEW.recipient_email
                    AND OLD.recipient_trust IS NEW.recipient_trust
                    AND OLD.eligible IS NEW.eligible
                    AND OLD.eligibility_code IS NEW.eligibility_code
                    AND OLD.eligibility_reason IS NEW.eligibility_reason
                )
            BEGIN SELECT RAISE(ABORT, 'Published campaign audience and sequence are immutable'); END"""
        )


def _drop_immutable_guards() -> None:
    dialect = op.get_bind().dialect.name
    if dialect == "postgresql":
        for table_name in (
            "engage_campaign_versions",
            "engage_sequence_steps",
            "engage_campaign_audience",
        ):
            op.execute(f"DROP TRIGGER {table_name}_immutable ON {table_name}")
        op.execute("DROP FUNCTION public.revenueos_reject_published_campaign_update()")
    elif dialect == "sqlite":
        op.execute("DROP TRIGGER engage_campaign_versions_immutable_update")
        for table_name in ("engage_sequence_steps", "engage_campaign_audience"):
            op.execute(f"DROP TRIGGER {table_name}_immutable_update")


def upgrade() -> None:
    uuid_type = sa.Uuid(as_uuid=True)

    with op.batch_alter_table("outreach_policies") as batch:
        batch.add_column(sa.Column("version", sa.Integer(), server_default="1", nullable=False))
        batch.add_column(
            sa.Column("campaign_auto_send_allowed", sa.Boolean(), server_default=sa.false(), nullable=False)
        )
        batch.create_check_constraint("ck_outreach_policies_version", "version > 0")

    op.create_table(
        "engage_campaigns",
        sa.Column("id", uuid_type, nullable=False),
        sa.Column("organisation_id", uuid_type, nullable=False),
        sa.Column("owner_user_id", uuid_type, nullable=False),
        sa.Column("state", sa.String(length=24), server_default="draft", nullable=False),
        sa.Column("current_version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("needs_attention_reason", sa.String(length=64), nullable=True),
        sa.Column("launched_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("paused_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("stopped_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "state IN ('draft', 'ready', 'active', 'paused', 'completed', 'stopped', 'needs_attention')",
            name="ck_engage_campaigns_state",
        ),
        sa.CheckConstraint("current_version > 0", name="ck_engage_campaigns_version"),
        sa.ForeignKeyConstraint(["organisation_id"], ["organisations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["organisation_id", "owner_user_id"],
            ["organisation_memberships.organisation_id", "organisation_memberships.user_id"],
            name="fk_engage_campaigns_owner",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organisation_id", "id", name="uq_engage_campaigns_org_id"),
    )
    op.create_index(
        "ix_engage_campaigns_org_owner_state",
        "engage_campaigns",
        ["organisation_id", "owner_user_id", "state", "updated_at"],
    )
    op.create_index(
        "ix_engage_campaigns_org_state",
        "engage_campaigns",
        ["organisation_id", "state", "updated_at"],
    )

    op.create_table(
        "engage_campaign_versions",
        sa.Column("id", uuid_type, nullable=False),
        sa.Column("organisation_id", uuid_type, nullable=False),
        sa.Column("campaign_id", uuid_type, nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=16), server_default="draft", nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("purpose", sa.String(length=300), nullable=False),
        sa.Column("approval_mode", sa.String(length=40), nullable=False),
        sa.Column("sender_user_id", uuid_type, nullable=False),
        sa.Column("source_type", sa.String(length=32), server_default="manual_contacts", nullable=False),
        sa.Column("sender_timezone", sa.String(length=64), nullable=False),
        sa.Column("send_days_json", sa.JSON(), server_default=sa.text("'[1,2,3,4,5]'"), nullable=False),
        sa.Column("send_window_start_minutes", sa.Integer(), server_default="510", nullable=False),
        sa.Column("send_window_end_minutes", sa.Integer(), server_default="1020", nullable=False),
        sa.Column("stop_on_active_opportunity", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("policy_version", sa.Integer(), nullable=True),
        sa.Column("policy_fingerprint", sa.String(length=64), nullable=True),
        sa.Column("launch_fingerprint", sa.String(length=64), nullable=True),
        sa.Column("audience_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("approved_by_user_id", uuid_type, nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("auto_send_confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by_user_id", uuid_type, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("version > 0", name="ck_engage_campaign_versions_number"),
        sa.CheckConstraint("status IN ('draft', 'published')", name="ck_engage_campaign_versions_status"),
        sa.CheckConstraint("length(trim(name)) BETWEEN 1 AND 160", name="ck_engage_campaign_versions_name"),
        sa.CheckConstraint("length(trim(purpose)) BETWEEN 1 AND 300", name="ck_engage_campaign_versions_purpose"),
        sa.CheckConstraint(
            "approval_mode IN ('review_each_send', 'approved_campaign_auto_send')",
            name="ck_engage_campaign_versions_approval",
        ),
        sa.CheckConstraint(
            "source_type IN ('manual_contacts', 'target_market')",
            name="ck_engage_campaign_versions_source",
        ),
        sa.CheckConstraint(
            "send_window_start_minutes BETWEEN 0 AND 1438 AND "
            "send_window_end_minutes BETWEEN 1 AND 1439 AND "
            "send_window_start_minutes < send_window_end_minutes",
            name="ck_engage_campaign_versions_window",
        ),
        sa.CheckConstraint("audience_count BETWEEN 0 AND 50", name="ck_engage_campaign_versions_audience"),
        sa.CheckConstraint(
            "policy_fingerprint IS NULL OR length(policy_fingerprint) = 64",
            name="ck_engage_campaign_versions_policy_fp",
        ),
        sa.CheckConstraint(
            "launch_fingerprint IS NULL OR length(launch_fingerprint) = 64",
            name="ck_engage_campaign_versions_launch_fp",
        ),
        sa.ForeignKeyConstraint(["organisation_id"], ["organisations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["organisation_id", "campaign_id"],
            ["engage_campaigns.organisation_id", "engage_campaigns.id"],
            name="fk_engage_campaign_versions_campaign",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["organisation_id", "sender_user_id"],
            ["organisation_memberships.organisation_id", "organisation_memberships.user_id"],
            name="fk_engage_campaign_versions_sender",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organisation_id", "approved_by_user_id"],
            ["organisation_memberships.organisation_id", "organisation_memberships.user_id"],
            name="fk_engage_campaign_versions_approver",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organisation_id", "created_by_user_id"],
            ["organisation_memberships.organisation_id", "organisation_memberships.user_id"],
            name="fk_engage_campaign_versions_creator",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organisation_id", "id", name="uq_engage_campaign_versions_org_id"),
        sa.UniqueConstraint("organisation_id", "campaign_id", "version", name="uq_engage_campaign_versions_number"),
        sa.UniqueConstraint("organisation_id", "campaign_id", "id", name="uq_engage_campaign_versions_campaign_id"),
    )
    op.create_index(
        "ix_engage_campaign_versions_org_campaign",
        "engage_campaign_versions",
        ["organisation_id", "campaign_id", "version"],
    )

    op.create_table(
        "engage_sequence_steps",
        sa.Column("id", uuid_type, nullable=False),
        sa.Column("organisation_id", uuid_type, nullable=False),
        sa.Column("campaign_version_id", uuid_type, nullable=False),
        sa.Column("step_order", sa.Integer(), nullable=False),
        sa.Column("delay_days", sa.Integer(), nullable=False),
        sa.Column("objective", sa.String(length=40), nullable=False),
        sa.Column("content_strategy", sa.String(length=40), nullable=False),
        sa.Column("enabled", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("step_order BETWEEN 1 AND 4", name="ck_engage_sequence_steps_order"),
        sa.CheckConstraint("delay_days BETWEEN 0 AND 30", name="ck_engage_sequence_steps_delay"),
        sa.CheckConstraint(
            "objective IN ('introduction', 'follow_up', 'share_relevant_information', 'different_angle', "
            "'meeting_request', 'final_follow_up')",
            name="ck_engage_sequence_steps_objective",
        ),
        sa.CheckConstraint(
            "content_strategy IN ('source_backed_value', 'truthful_follow_up', 'source_backed_new_angle', "
            "'respectful_close')",
            name="ck_engage_sequence_steps_strategy",
        ),
        sa.ForeignKeyConstraint(["organisation_id"], ["organisations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["organisation_id", "campaign_version_id"],
            ["engage_campaign_versions.organisation_id", "engage_campaign_versions.id"],
            name="fk_engage_sequence_steps_version",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organisation_id", "id", name="uq_engage_sequence_steps_org_id"),
        sa.UniqueConstraint(
            "organisation_id", "campaign_version_id", "step_order", name="uq_engage_sequence_steps_order"
        ),
    )
    op.create_index(
        "ix_engage_sequence_steps_org_version",
        "engage_sequence_steps",
        ["organisation_id", "campaign_version_id", "step_order"],
    )

    op.create_table(
        "engage_campaign_audience",
        sa.Column("id", uuid_type, nullable=False),
        sa.Column("organisation_id", uuid_type, nullable=False),
        sa.Column("campaign_version_id", uuid_type, nullable=False),
        sa.Column("contact_id", uuid_type, nullable=True),
        sa.Column("company_id", uuid_type, nullable=True),
        sa.Column("recipient_name", sa.String(length=200), nullable=False),
        sa.Column("recipient_email", sa.String(length=320), nullable=True),
        sa.Column("recipient_trust", sa.String(length=24), nullable=False),
        sa.Column("eligible", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("eligibility_code", sa.String(length=64), nullable=False),
        sa.Column("eligibility_reason", sa.String(length=300), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "recipient_trust IN ('verified', 'provider_supplied', 'unknown')",
            name="ck_engage_campaign_audience_trust",
        ),
        sa.CheckConstraint(
            "length(trim(eligibility_code)) BETWEEN 1 AND 64",
            name="ck_engage_campaign_audience_code",
        ),
        sa.CheckConstraint(
            "length(trim(eligibility_reason)) BETWEEN 1 AND 300",
            name="ck_engage_campaign_audience_reason",
        ),
        sa.ForeignKeyConstraint(["organisation_id"], ["organisations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["organisation_id", "campaign_version_id"],
            ["engage_campaign_versions.organisation_id", "engage_campaign_versions.id"],
            name="fk_engage_campaign_audience_version",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["organisation_id", "contact_id"],
            ["contacts.organisation_id", "contacts.id"],
            name="fk_engage_campaign_audience_contact",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organisation_id", "company_id"],
            ["companies.organisation_id", "companies.id"],
            name="fk_engage_campaign_audience_company",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organisation_id", "id", name="uq_engage_campaign_audience_org_id"),
        sa.UniqueConstraint(
            "organisation_id", "campaign_version_id", "contact_id", name="uq_engage_campaign_audience_contact"
        ),
    )
    op.create_index(
        "ix_engage_campaign_audience_org_version",
        "engage_campaign_audience",
        ["organisation_id", "campaign_version_id", "eligible", "created_at"],
    )

    op.create_table(
        "engage_campaign_enrollments",
        sa.Column("id", uuid_type, nullable=False),
        sa.Column("organisation_id", uuid_type, nullable=False),
        sa.Column("campaign_id", uuid_type, nullable=False),
        sa.Column("campaign_version_id", uuid_type, nullable=False),
        sa.Column("contact_id", uuid_type, nullable=True),
        sa.Column("company_id", uuid_type, nullable=True),
        sa.Column("sender_user_id", uuid_type, nullable=False),
        sa.Column("recipient_name", sa.String(length=200), nullable=False),
        sa.Column("recipient_email", sa.String(length=320), nullable=False),
        sa.Column("recipient_trust", sa.String(length=24), nullable=False),
        sa.Column("job_title_snapshot", sa.String(length=200), nullable=True),
        sa.Column("state", sa.String(length=24), server_default="ready", nullable=False),
        sa.Column("current_step_order", sa.Integer(), server_default="1", nullable=False),
        sa.Column("next_scheduled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("stop_reason", sa.String(length=64), nullable=True),
        sa.Column("outcome", sa.String(length=32), nullable=True),
        sa.Column("outcome_provenance", sa.String(length=24), nullable=True),
        sa.Column("outcome_reported_by_user_id", uuid_type, nullable=True),
        sa.Column("outcome_reported_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("used_source_ids_json", sa.JSON(), server_default=sa.text("'[]'"), nullable=False),
        sa.Column("created_by_user_id", uuid_type, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "state IN ('ready', 'active', 'paused', 'stopped', 'completed', 'blocked', 'needs_attention')",
            name="ck_engage_campaign_enrollments_state",
        ),
        sa.CheckConstraint("current_step_order BETWEEN 1 AND 4", name="ck_engage_campaign_enrollments_step"),
        sa.CheckConstraint(
            "recipient_trust IN ('verified', 'provider_supplied')",
            name="ck_engage_campaign_enrollments_trust",
        ),
        sa.CheckConstraint(
            "outcome IS NULL OR outcome IN ('replied', 'meeting_booked', 'not_interested')",
            name="ck_engage_campaign_enrollments_outcome",
        ),
        sa.CheckConstraint(
            "outcome_provenance IS NULL OR outcome_provenance = 'seller_reported'",
            name="ck_engage_campaign_enrollments_provenance",
        ),
        sa.ForeignKeyConstraint(["organisation_id"], ["organisations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["organisation_id", "campaign_id"],
            ["engage_campaigns.organisation_id", "engage_campaigns.id"],
            name="fk_engage_campaign_enrollments_campaign",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["organisation_id", "campaign_id", "campaign_version_id"],
            [
                "engage_campaign_versions.organisation_id",
                "engage_campaign_versions.campaign_id",
                "engage_campaign_versions.id",
            ],
            name="fk_engage_campaign_enrollments_version",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["organisation_id", "contact_id"],
            ["contacts.organisation_id", "contacts.id"],
            name="fk_engage_campaign_enrollments_contact",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organisation_id", "company_id"],
            ["companies.organisation_id", "companies.id"],
            name="fk_engage_campaign_enrollments_company",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organisation_id", "sender_user_id"],
            ["organisation_memberships.organisation_id", "organisation_memberships.user_id"],
            name="fk_engage_campaign_enrollments_sender",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organisation_id", "outcome_reported_by_user_id"],
            ["organisation_memberships.organisation_id", "organisation_memberships.user_id"],
            name="fk_engage_campaign_enrollments_outcome_user",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organisation_id", "created_by_user_id"],
            ["organisation_memberships.organisation_id", "organisation_memberships.user_id"],
            name="fk_engage_campaign_enrollments_creator",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organisation_id", "id", name="uq_engage_campaign_enrollments_org_id"),
        sa.UniqueConstraint(
            "organisation_id", "campaign_id", "contact_id", name="uq_engage_campaign_enrollments_contact"
        ),
    )
    op.create_index(
        "ix_engage_campaign_enrollments_org_campaign",
        "engage_campaign_enrollments",
        ["organisation_id", "campaign_id", "state", "next_scheduled_at"],
    )
    op.create_index(
        "ix_engage_campaign_enrollments_org_contact",
        "engage_campaign_enrollments",
        ["organisation_id", "contact_id", "state"],
    )

    op.create_table(
        "engage_enrollment_steps",
        sa.Column("id", uuid_type, nullable=False),
        sa.Column("organisation_id", uuid_type, nullable=False),
        sa.Column("enrollment_id", uuid_type, nullable=False),
        sa.Column("sequence_step_id", uuid_type, nullable=False),
        sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("prepare_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("state", sa.String(length=32), server_default="pending", nullable=False),
        sa.Column("outreach_message_id", uuid_type, nullable=True),
        sa.Column("safe_status_code", sa.String(length=64), nullable=True),
        sa.Column("worker_id", sa.String(length=200), nullable=True),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("attempt_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("prepared_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "state IN ('pending', 'processing', 'ready_for_review', 'prepared', 'queued', 'sent', "
            "'deferred', 'blocked', 'cancelled', 'unknown_delivery_state')",
            name="ck_engage_enrollment_steps_state",
        ),
        sa.CheckConstraint("attempt_count BETWEEN 0 AND 20", name="ck_engage_enrollment_steps_attempts"),
        sa.ForeignKeyConstraint(["organisation_id"], ["organisations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["organisation_id", "enrollment_id"],
            ["engage_campaign_enrollments.organisation_id", "engage_campaign_enrollments.id"],
            name="fk_engage_enrollment_steps_enrollment",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["organisation_id", "sequence_step_id"],
            ["engage_sequence_steps.organisation_id", "engage_sequence_steps.id"],
            name="fk_engage_enrollment_steps_sequence",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organisation_id", "outreach_message_id"],
            ["outreach_messages.organisation_id", "outreach_messages.id"],
            name="fk_engage_enrollment_steps_outreach",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organisation_id", "id", name="uq_engage_enrollment_steps_org_id"),
        sa.UniqueConstraint(
            "organisation_id", "enrollment_id", "sequence_step_id", name="uq_engage_enrollment_steps_sequence"
        ),
        sa.UniqueConstraint("organisation_id", "outreach_message_id", name="uq_engage_enrollment_steps_outreach"),
    )
    op.create_index(
        "ix_engage_enrollment_steps_due",
        "engage_enrollment_steps",
        ["organisation_id", "state", "prepare_at", "scheduled_at"],
    )
    op.create_index(
        "ix_engage_enrollment_steps_lease",
        "engage_enrollment_steps",
        ["organisation_id", "state", "lease_expires_at"],
    )

    _enable_tenant_rls()
    _create_immutable_guards()
    if op.get_bind().dialect.name == "postgresql":
        op.execute(
            """
            CREATE FUNCTION public.revenueos_campaign_worker_eligible_organisations(
                eligible_at timestamptz,
                result_limit integer
            )
            RETURNS TABLE (organisation_id uuid)
            LANGUAGE sql
            SECURITY DEFINER
            SET search_path = pg_catalog, public
            AS $$
                SELECT DISTINCT engage_enrollment_steps.organisation_id
                FROM public.engage_enrollment_steps
                WHERE (
                    engage_enrollment_steps.state IN ('pending', 'deferred')
                    AND engage_enrollment_steps.prepare_at <= eligible_at
                ) OR (
                    engage_enrollment_steps.state = 'prepared'
                    AND engage_enrollment_steps.scheduled_at <= eligible_at
                ) OR engage_enrollment_steps.state = 'queued'
                OR (
                    engage_enrollment_steps.state = 'processing'
                    AND engage_enrollment_steps.lease_expires_at IS NOT NULL
                    AND engage_enrollment_steps.lease_expires_at <= eligible_at
                ) OR (
                    engage_enrollment_steps.state = 'ready_for_review'
                    AND engage_enrollment_steps.outreach_message_id IN (
                        SELECT outreach_messages.id
                        FROM public.outreach_messages
                        JOIN public.action_executions
                          ON action_executions.organisation_id = outreach_messages.organisation_id
                         AND action_executions.action_id = outreach_messages.action_id
                    )
                )
                ORDER BY engage_enrollment_steps.organisation_id
                LIMIT LEAST(GREATEST(result_limit, 1), 1000)
            $$
            """
        )


def downgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        op.execute(
            """DROP FUNCTION IF EXISTS
            public.revenueos_campaign_worker_eligible_organisations(timestamptz, integer)"""
        )
    _drop_immutable_guards()
    op.drop_index("ix_engage_enrollment_steps_lease", table_name="engage_enrollment_steps")
    op.drop_index("ix_engage_enrollment_steps_due", table_name="engage_enrollment_steps")
    op.drop_table("engage_enrollment_steps")
    op.drop_index("ix_engage_campaign_enrollments_org_contact", table_name="engage_campaign_enrollments")
    op.drop_index("ix_engage_campaign_enrollments_org_campaign", table_name="engage_campaign_enrollments")
    op.drop_table("engage_campaign_enrollments")
    op.drop_index("ix_engage_campaign_audience_org_version", table_name="engage_campaign_audience")
    op.drop_table("engage_campaign_audience")
    op.drop_index("ix_engage_sequence_steps_org_version", table_name="engage_sequence_steps")
    op.drop_table("engage_sequence_steps")
    op.drop_index("ix_engage_campaign_versions_org_campaign", table_name="engage_campaign_versions")
    op.drop_table("engage_campaign_versions")
    op.drop_index("ix_engage_campaigns_org_state", table_name="engage_campaigns")
    op.drop_index("ix_engage_campaigns_org_owner_state", table_name="engage_campaigns")
    op.drop_table("engage_campaigns")

    with op.batch_alter_table("outreach_policies") as batch:
        batch.drop_constraint("ck_outreach_policies_version", type_="check")
        batch.drop_column("campaign_auto_send_allowed")
        batch.drop_column("version")
