"""Add source-backed one-to-one personalised outreach.

Revision ID: 0038_personalized_outreach
Revises: 0037_territory_icp

WO-029 adds an Engage entitlement, organisation sending policy, immutable message
versions and provenance, durable contact suppression, and a Contact-scoped Action.
Production mailbox adapters remain deliberately absent.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0038_personalized_outreach"
down_revision: str | None = "0037_territory_icp"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TENANT_TABLES = (
    "outreach_policies",
    "outreach_messages",
    "outreach_versions",
    "outreach_personalization_sources",
    "contact_suppressions",
)

ACTION_TYPES = (
    "action_type IN ('follow_up_email', 'personalized_outreach', 'send_requested_material', 'create_task', "
    "'follow_up_stakeholder', 'schedule_interaction', 'update_opportunity', 'update_contact', "
    "'log_interaction', 'update_stakeholder', 'add_decision', 'add_commitment', 'add_risk', "
    "'update_timeline', 'update_procurement', 'update_security_legal', 'create_reminder', "
    "'notify_internal', 'prepare_next_interaction', 'resolve_open_question', 'review_conflict', 'other')"
)

OLD_ACTION_TYPES = ACTION_TYPES.replace("'personalized_outreach', ", "")


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
    tables = ("outreach_versions", "outreach_personalization_sources")
    if dialect == "postgresql":
        op.execute(
            """
            CREATE FUNCTION public.revenueos_reject_outreach_history_update()
            RETURNS trigger
            LANGUAGE plpgsql
            AS $$
            BEGIN
                RAISE EXCEPTION 'Outreach versions and provenance are immutable';
            END;
            $$
            """
        )
        for table_name in tables:
            op.execute(
                f"""CREATE TRIGGER {table_name}_immutable_update
                BEFORE UPDATE ON {table_name}
                FOR EACH ROW EXECUTE FUNCTION public.revenueos_reject_outreach_history_update()"""
            )
    elif dialect == "sqlite":
        for table_name in tables:
            op.execute(
                f"""CREATE TRIGGER {table_name}_immutable_update
                BEFORE UPDATE ON {table_name}
                FOR EACH ROW
                BEGIN
                    SELECT RAISE(ABORT, 'Outreach versions and provenance are immutable');
                END"""
            )


def _drop_immutable_guards() -> None:
    dialect = op.get_bind().dialect.name
    tables = ("outreach_versions", "outreach_personalization_sources")
    if dialect == "postgresql":
        for table_name in tables:
            op.execute(f"DROP TRIGGER {table_name}_immutable_update ON {table_name}")
        op.execute("DROP FUNCTION public.revenueos_reject_outreach_history_update()")
    elif dialect == "sqlite":
        for table_name in tables:
            op.execute(f"DROP TRIGGER {table_name}_immutable_update")


def upgrade() -> None:
    uuid_type = sa.Uuid(as_uuid=True)

    with op.batch_alter_table("organisation_module_entitlements") as batch:
        batch.drop_constraint("ck_module_entitlements_key", type_="check")
        batch.create_check_constraint("ck_module_entitlements_key", "module_key IN ('prospect', 'engage')")

    with op.batch_alter_table("action_proposals") as batch:
        batch.drop_constraint("ck_action_proposals_type", type_="check")
        batch.create_check_constraint("ck_action_proposals_type", ACTION_TYPES)
        batch.alter_column("opportunity_id", existing_type=uuid_type, nullable=True)

    op.create_table(
        "outreach_policies",
        sa.Column("organisation_id", uuid_type, nullable=False),
        sa.Column("configured", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("outbound_enabled", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("provider_supplied_email_allowed", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("cooldown_hours", sa.Integer(), server_default="72", nullable=False),
        sa.Column("max_daily_sends_user", sa.Integer(), server_default="25", nullable=False),
        sa.Column("max_daily_sends_org", sa.Integer(), server_default="100", nullable=False),
        sa.Column("require_opt_out_mechanism", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("offering_name", sa.String(length=120), nullable=False),
        sa.Column("value_proposition", sa.String(length=1000), nullable=False),
        sa.Column("approved_cta", sa.String(length=300), nullable=False),
        sa.Column("configured_by_user_id", uuid_type, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("cooldown_hours BETWEEN 0 AND 720", name="ck_outreach_policies_cooldown"),
        sa.CheckConstraint("max_daily_sends_user BETWEEN 1 AND 500", name="ck_outreach_policies_user_limit"),
        sa.CheckConstraint("max_daily_sends_org BETWEEN 1 AND 2000", name="ck_outreach_policies_org_limit"),
        sa.CheckConstraint("length(trim(offering_name)) BETWEEN 1 AND 120", name="ck_outreach_policies_offering"),
        sa.CheckConstraint("length(trim(value_proposition)) BETWEEN 1 AND 1000", name="ck_outreach_policies_value"),
        sa.CheckConstraint("length(trim(approved_cta)) BETWEEN 1 AND 300", name="ck_outreach_policies_cta"),
        sa.ForeignKeyConstraint(["organisation_id"], ["organisations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["organisation_id", "configured_by_user_id"],
            ["organisation_memberships.organisation_id", "organisation_memberships.user_id"],
            name="fk_outreach_policies_configurer",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("organisation_id"),
    )

    op.create_table(
        "outreach_messages",
        sa.Column("id", uuid_type, nullable=False),
        sa.Column("organisation_id", uuid_type, nullable=False),
        sa.Column("contact_id", uuid_type, nullable=True),
        sa.Column("sender_user_id", uuid_type, nullable=False),
        sa.Column("action_id", uuid_type, nullable=False),
        sa.Column("purpose", sa.String(length=40), nullable=False),
        sa.Column("state", sa.String(length=20), server_default="draft", nullable=False),
        sa.Column("current_version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("approved_version", sa.Integer(), nullable=True),
        sa.Column("approved_by_user_id", uuid_type, nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "purpose IN ('introduction', 'request_meeting', 'share_relevant_information', 're_engage')",
            name="ck_outreach_messages_purpose",
        ),
        sa.CheckConstraint("state IN ('draft', 'approved', 'cancelled')", name="ck_outreach_messages_state"),
        sa.CheckConstraint("current_version > 0", name="ck_outreach_messages_version"),
        sa.CheckConstraint(
            "approved_version IS NULL OR approved_version BETWEEN 1 AND current_version",
            name="ck_outreach_messages_approved",
        ),
        sa.ForeignKeyConstraint(["organisation_id"], ["organisations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["organisation_id", "contact_id"],
            ["contacts.organisation_id", "contacts.id"],
            name="fk_outreach_messages_contact",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organisation_id", "sender_user_id"],
            ["organisation_memberships.organisation_id", "organisation_memberships.user_id"],
            name="fk_outreach_messages_sender",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organisation_id", "approved_by_user_id"],
            ["organisation_memberships.organisation_id", "organisation_memberships.user_id"],
            name="fk_outreach_messages_approver",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organisation_id", "action_id"],
            ["action_proposals.organisation_id", "action_proposals.id"],
            name="fk_outreach_messages_action",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organisation_id", "id", name="uq_outreach_messages_org_id"),
        sa.UniqueConstraint("organisation_id", "action_id", name="uq_outreach_messages_action"),
    )
    op.create_index(
        "ix_outreach_messages_org_contact",
        "outreach_messages",
        ["organisation_id", "contact_id", "created_at"],
    )
    op.create_index(
        "ix_outreach_messages_org_sender",
        "outreach_messages",
        ["organisation_id", "sender_user_id", "created_at"],
    )

    op.create_table(
        "outreach_versions",
        sa.Column("id", uuid_type, nullable=False),
        sa.Column("organisation_id", uuid_type, nullable=False),
        sa.Column("outreach_id", uuid_type, nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("subject", sa.String(length=200), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("sender_name", sa.String(length=200), nullable=False),
        sa.Column("sender_email", sa.String(length=320), nullable=False),
        sa.Column("recipient_name", sa.String(length=200), nullable=False),
        sa.Column("recipient_email", sa.String(length=320), nullable=False),
        sa.Column("recipient_trust", sa.String(length=24), nullable=False),
        sa.Column("offering_name", sa.String(length=120), nullable=False),
        sa.Column("value_proposition", sa.String(length=1000), nullable=False),
        sa.Column("approved_cta", sa.String(length=300), nullable=False),
        sa.Column("personalization_plan_json", sa.JSON(), server_default=sa.text("'{}'"), nullable=False),
        sa.Column("composer_version", sa.String(length=80), nullable=False),
        sa.Column("creation_type", sa.String(length=20), nullable=False),
        sa.Column("content_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("created_by_user_id", uuid_type, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("version > 0", name="ck_outreach_versions_version"),
        sa.CheckConstraint("length(trim(subject)) BETWEEN 1 AND 200", name="ck_outreach_versions_subject"),
        sa.CheckConstraint("length(trim(body)) BETWEEN 1 AND 10000", name="ck_outreach_versions_body"),
        sa.CheckConstraint("creation_type IN ('generated', 'user_edited')", name="ck_outreach_versions_creation"),
        sa.CheckConstraint("recipient_trust IN ('verified', 'provider_supplied')", name="ck_outreach_versions_trust"),
        sa.CheckConstraint("length(content_fingerprint) = 64", name="ck_outreach_versions_fingerprint"),
        sa.ForeignKeyConstraint(["organisation_id"], ["organisations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["organisation_id", "outreach_id"],
            ["outreach_messages.organisation_id", "outreach_messages.id"],
            name="fk_outreach_versions_message",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["organisation_id", "created_by_user_id"],
            ["organisation_memberships.organisation_id", "organisation_memberships.user_id"],
            name="fk_outreach_versions_creator",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organisation_id", "id", name="uq_outreach_versions_org_id"),
        sa.UniqueConstraint("organisation_id", "outreach_id", "version", name="uq_outreach_versions_number"),
    )
    op.create_index(
        "ix_outreach_versions_org_message",
        "outreach_versions",
        ["organisation_id", "outreach_id", "version"],
    )

    op.create_table(
        "outreach_personalization_sources",
        sa.Column("id", uuid_type, nullable=False),
        sa.Column("organisation_id", uuid_type, nullable=False),
        sa.Column("outreach_version_id", uuid_type, nullable=False),
        sa.Column("source_type", sa.String(length=40), nullable=False),
        sa.Column("source_id", uuid_type, nullable=False),
        sa.Column("supporting_source_id", uuid_type, nullable=True),
        sa.Column("label", sa.String(length=300), nullable=False),
        sa.Column("trust_state", sa.String(length=24), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "source_type IN ('prospect_observation', 'prospect_person_observation', 'approved_seller_context')",
            name="ck_outreach_sources_type",
        ),
        sa.CheckConstraint(
            "trust_state IN ('verified', 'provider_supplied', 'approved')", name="ck_outreach_sources_trust"
        ),
        sa.CheckConstraint("length(trim(label)) BETWEEN 1 AND 300", name="ck_outreach_sources_label"),
        sa.ForeignKeyConstraint(["organisation_id"], ["organisations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["organisation_id", "outreach_version_id"],
            ["outreach_versions.organisation_id", "outreach_versions.id"],
            name="fk_outreach_sources_version",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organisation_id", "id", name="uq_outreach_sources_org_id"),
        sa.UniqueConstraint(
            "organisation_id",
            "outreach_version_id",
            "source_type",
            "source_id",
            name="uq_outreach_sources_ref",
        ),
    )
    op.create_index(
        "ix_outreach_sources_org_version",
        "outreach_personalization_sources",
        ["organisation_id", "outreach_version_id"],
    )

    op.create_table(
        "contact_suppressions",
        sa.Column("id", uuid_type, nullable=False),
        sa.Column("organisation_id", uuid_type, nullable=False),
        sa.Column("contact_id", uuid_type, nullable=True),
        sa.Column("email_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("reason", sa.String(length=40), nullable=False),
        sa.Column("source", sa.String(length=20), nullable=False),
        sa.Column("active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("created_by_user_id", uuid_type, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("revoked_by_user_id", uuid_type, nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("length(email_fingerprint) = 64", name="ck_contact_suppressions_fingerprint"),
        sa.CheckConstraint(
            "reason IN ('manual_do_not_contact', 'recipient_opt_out', 'complaint', 'permanent_bounce')",
            name="ck_contact_suppressions_reason",
        ),
        sa.CheckConstraint("source IN ('user', 'recipient', 'provider')", name="ck_contact_suppressions_source"),
        sa.ForeignKeyConstraint(["organisation_id"], ["organisations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["organisation_id", "contact_id"],
            ["contacts.organisation_id", "contacts.id"],
            name="fk_contact_suppressions_contact",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organisation_id", "created_by_user_id"],
            ["organisation_memberships.organisation_id", "organisation_memberships.user_id"],
            name="fk_contact_suppressions_creator",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organisation_id", "revoked_by_user_id"],
            ["organisation_memberships.organisation_id", "organisation_memberships.user_id"],
            name="fk_contact_suppressions_revoker",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organisation_id", "id", name="uq_contact_suppressions_org_id"),
        sa.UniqueConstraint("organisation_id", "email_fingerprint", name="uq_contact_suppressions_email"),
    )
    op.create_index(
        "ix_contact_suppressions_org_contact",
        "contact_suppressions",
        ["organisation_id", "contact_id"],
    )

    _enable_tenant_rls()
    _create_immutable_guards()


def downgrade() -> None:
    _drop_immutable_guards()
    op.drop_index("ix_contact_suppressions_org_contact", table_name="contact_suppressions")
    op.drop_table("contact_suppressions")
    op.drop_index("ix_outreach_sources_org_version", table_name="outreach_personalization_sources")
    op.drop_table("outreach_personalization_sources")
    op.drop_index("ix_outreach_versions_org_message", table_name="outreach_versions")
    op.drop_table("outreach_versions")
    op.drop_index("ix_outreach_messages_org_sender", table_name="outreach_messages")
    op.drop_index("ix_outreach_messages_org_contact", table_name="outreach_messages")
    op.drop_table("outreach_messages")
    op.drop_table("outreach_policies")

    op.execute("DELETE FROM action_proposals WHERE action_type = 'personalized_outreach'")
    with op.batch_alter_table("action_proposals") as batch:
        batch.drop_constraint("ck_action_proposals_type", type_="check")
        batch.create_check_constraint("ck_action_proposals_type", OLD_ACTION_TYPES)
        batch.alter_column("opportunity_id", existing_type=sa.Uuid(as_uuid=True), nullable=False)

    op.execute("DELETE FROM organisation_module_entitlements WHERE module_key = 'engage'")
    with op.batch_alter_table("organisation_module_entitlements") as batch:
        batch.drop_constraint("ck_module_entitlements_key", type_="check")
        batch.create_check_constraint("ck_module_entitlements_key", "module_key = 'prospect'")
