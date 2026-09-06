"""Add provider-neutral Microsoft 365 sales integration state.

Revision ID: 0056_microsoft_365_sales
Revises: 0055_live_prospect_provider

Only bounded Oryntela-related mail and calendar metadata is retained. OAuth
credentials remain in the existing encrypted connector credential envelope.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0056_microsoft_365_sales"
down_revision: str | None = "0055_live_prospect_provider"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TENANT_TABLES = (
    "provider_outbound_operations",
    "provider_replies",
    "provider_calendar_events",
    "provider_sync_states",
)


def _replace_check(table: str, name: str, expression: str) -> None:
    with op.batch_alter_table(table) as batch:
        batch.drop_constraint(name, type_="check")
        batch.create_check_constraint(name, expression)


def _restore_sqlite_execution_guards() -> None:
    if op.get_bind().dialect.name != "sqlite":
        return
    immutable_columns = (
        "organisation_id, action_id, action_version, connection_id, preview_id, "
        "connector_key, capability, risk_class, execution_mode, idempotency_key, "
        "preview_fingerprint, confirmed_by_user_id, confirmed_at"
    )
    op.execute("DROP TRIGGER IF EXISTS action_executions_intent_immutable")
    op.execute(
        f"""CREATE TRIGGER action_executions_intent_immutable
        BEFORE UPDATE OF {immutable_columns} ON action_executions
        FOR EACH ROW BEGIN SELECT RAISE(ABORT, 'Execution intent is immutable'); END"""
    )


def _enable_tenant_rls() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return
    for table_name in TENANT_TABLES:
        op.execute(f"ALTER TABLE {table_name} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table_name} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"""CREATE POLICY {table_name}_tenant_isolation ON {table_name}
            USING (organisation_id = NULLIF(current_setting('app.organisation_id', true), '')::uuid)
            WITH CHECK (organisation_id = NULLIF(current_setting('app.organisation_id', true), '')::uuid)"""
        )


def _create_worker_discovery() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return
    op.execute(
        """
        CREATE FUNCTION public.revenueos_microsoft_sync_eligible_organisations(
            due_before timestamptz,
            result_limit integer
        )
        RETURNS TABLE (organisation_id uuid)
        LANGUAGE sql
        SECURITY DEFINER
        SET search_path = pg_catalog, public
        AS $$
            SELECT DISTINCT connections.organisation_id
            FROM public.integration_connections AS connections
            JOIN public.organisation_memberships AS memberships
              ON memberships.organisation_id = connections.organisation_id
             AND memberships.user_id = connections.created_by_user_id
            JOIN public.users AS users
              ON users.id = connections.created_by_user_id
            WHERE connections.connector_key = 'microsoft_365'
              AND connections.connection_status = 'active'
              AND memberships.status = 'active'
              AND users.status = 'active'
              AND NOT EXISTS (
                  SELECT 1
                  FROM public.provider_sync_states AS sync_states
                  WHERE sync_states.organisation_id = connections.organisation_id
                    AND sync_states.connection_id = connections.id
                    AND sync_states.resource_kind = 'calendar'
                    AND sync_states.updated_at > due_before
              )
            ORDER BY connections.organisation_id
            LIMIT LEAST(GREATEST(result_limit, 1), 1000)
        $$
        """
    )


def upgrade() -> None:
    with op.batch_alter_table("integration_connections") as batch:
        batch.drop_constraint("uq_integration_connections_org_key", type_="unique")
        batch.add_column(sa.Column("external_account_email", sa.String(length=320), nullable=True))
        batch.add_column(sa.Column("external_tenant_id", sa.String(length=128), nullable=True))
    op.create_index(
        "uq_integration_connections_org_key_non_microsoft",
        "integration_connections",
        ["organisation_id", "connector_key"],
        unique=True,
        postgresql_where=sa.text("connector_key <> 'microsoft_365'"),
        sqlite_where=sa.text("connector_key <> 'microsoft_365'"),
    )
    op.create_index(
        "uq_integration_connections_org_microsoft_owner",
        "integration_connections",
        ["organisation_id", "connector_key", "created_by_user_id"],
        unique=True,
        postgresql_where=sa.text("connector_key = 'microsoft_365' AND connection_status <> 'revoked'"),
        sqlite_where=sa.text("connector_key = 'microsoft_365' AND connection_status <> 'revoked'"),
    )
    _replace_check(
        "integration_connections",
        "ck_integration_connections_key",
        "connector_key IN ('mock_email', 'mock_calendar', 'mock_crm', 'mock_task', 'hubspot', 'microsoft_365')",
    )
    with op.batch_alter_table("oauth_connection_states") as batch:
        batch.add_column(sa.Column("pkce_verifier_encrypted", sa.LargeBinary(), nullable=True))
        batch.add_column(sa.Column("pkce_nonce", sa.LargeBinary(length=12), nullable=True))
        batch.add_column(sa.Column("oidc_nonce_hash", sa.String(length=64), nullable=True))
    _replace_check(
        "oauth_connection_states",
        "ck_oauth_connection_states_connector",
        "connector_key IN ('hubspot', 'microsoft_365')",
    )
    _replace_check(
        "encrypted_connector_credentials",
        "ck_encrypted_connector_credentials_connector",
        "connector_key IN ('hubspot', 'microsoft_365')",
    )
    _replace_check(
        "action_executions",
        "ck_action_executions_connector",
        "connector_key IN ('mock_email', 'mock_calendar', 'mock_crm', 'mock_task', 'hubspot', 'microsoft_365')",
    )
    _restore_sqlite_execution_guards()
    _replace_check(
        "engage_campaign_enrollments",
        "ck_engage_campaign_enrollments_provenance",
        "outcome_provenance IS NULL OR outcome_provenance IN ('seller_reported', 'provider')",
    )
    _replace_check(
        "integration_audit_events",
        "ck_integration_audit_events_type",
        "event_type IN ('connection_created', 'connection_tested', 'connection_revoked', "
        "'connection_reauthorisation_required', 'mapping_created', 'mapping_changed', 'mapping_removed', "
        "'field_mapping_changed', 'stage_mapping_changed', 'execution_preview_created', "
        "'execution_confirmed', 'execution_started', 'execution_succeeded', 'execution_failed', "
        "'execution_unknown_state', 'execution_reconciled', 'provider_sync_completed')",
    )

    op.create_table(
        "provider_outbound_operations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organisation_id", sa.Uuid(), nullable=False),
        sa.Column("connection_id", sa.Uuid(), nullable=False),
        sa.Column("action_id", sa.Uuid(), nullable=False),
        sa.Column("provider_key", sa.String(length=40), nullable=False),
        sa.Column("idempotency_key", sa.String(length=64), nullable=False),
        sa.Column("state", sa.String(length=24), nullable=False),
        sa.Column("sender_email", sa.String(length=320), nullable=False),
        sa.Column("recipient_email", sa.String(length=320), nullable=False),
        sa.Column("provider_message_id", sa.String(length=255), nullable=True),
        sa.Column("internet_message_id", sa.String(length=998), nullable=True),
        sa.Column("conversation_id", sa.String(length=255), nullable=True),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reconciled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("safe_failure_code", sa.String(length=80), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("provider_key = 'microsoft_365'", name="ck_provider_outbound_operations_provider"),
        sa.CheckConstraint(
            "state IN ('queued', 'submitting', 'accepted', 'reconciled', 'unknown', 'failed')",
            name="ck_provider_outbound_operations_state",
        ),
        sa.CheckConstraint("length(idempotency_key) = 64", name="ck_provider_outbound_operations_idempotency"),
        sa.ForeignKeyConstraint(["organisation_id"], ["organisations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["organisation_id", "connection_id"],
            ["integration_connections.organisation_id", "integration_connections.id"],
            name="fk_provider_outbound_operations_connection",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["organisation_id", "action_id"],
            ["action_proposals.organisation_id", "action_proposals.id"],
            name="fk_provider_outbound_operations_action",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organisation_id", "id", name="uq_provider_outbound_operations_org_id"),
        sa.UniqueConstraint(
            "organisation_id",
            "connection_id",
            "idempotency_key",
            name="uq_provider_outbound_operations_idempotency",
        ),
        sa.UniqueConstraint(
            "organisation_id",
            "connection_id",
            "provider_message_id",
            name="uq_provider_outbound_operations_provider_message",
        ),
    )
    op.create_index(
        "ix_provider_outbound_operations_org_state",
        "provider_outbound_operations",
        ["organisation_id", "connection_id", "state", "submitted_at"],
    )

    op.create_table(
        "provider_replies",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organisation_id", sa.Uuid(), nullable=False),
        sa.Column("connection_id", sa.Uuid(), nullable=False),
        sa.Column("outbound_operation_id", sa.Uuid(), nullable=False),
        sa.Column("provider_key", sa.String(length=40), nullable=False),
        sa.Column("provider_message_id", sa.String(length=255), nullable=False),
        sa.Column("internet_message_id", sa.String(length=998), nullable=True),
        sa.Column("conversation_id", sa.String(length=255), nullable=True),
        sa.Column("sender_email", sa.String(length=320), nullable=False),
        sa.Column("recipient_emails_json", sa.JSON(), server_default="[]", nullable=False),
        sa.Column("subject", sa.String(length=500), nullable=False),
        sa.Column("body_text", sa.Text(), nullable=False),
        sa.Column("kind", sa.String(length=24), nullable=False),
        sa.Column("match_state", sa.String(length=24), nullable=False),
        sa.Column("contact_id", sa.Uuid(), nullable=True),
        sa.Column("company_id", sa.Uuid(), nullable=True),
        sa.Column("opportunity_id", sa.Uuid(), nullable=True),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("provider_key = 'microsoft_365'", name="ck_provider_replies_provider"),
        sa.CheckConstraint("kind IN ('reply', 'automatic_reply', 'ndr')", name="ck_provider_replies_kind"),
        sa.CheckConstraint("match_state IN ('matched', 'review_required')", name="ck_provider_replies_match_state"),
        sa.ForeignKeyConstraint(["organisation_id"], ["organisations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["organisation_id", "connection_id"],
            ["integration_connections.organisation_id", "integration_connections.id"],
            name="fk_provider_replies_connection",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["organisation_id", "outbound_operation_id"],
            ["provider_outbound_operations.organisation_id", "provider_outbound_operations.id"],
            name="fk_provider_replies_outbound",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organisation_id", "contact_id"],
            ["contacts.organisation_id", "contacts.id"],
            name="fk_provider_replies_contact",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organisation_id", "company_id"],
            ["companies.organisation_id", "companies.id"],
            name="fk_provider_replies_company",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organisation_id", "opportunity_id"],
            ["opportunities.organisation_id", "opportunities.id"],
            name="fk_provider_replies_opportunity",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organisation_id", "id", name="uq_provider_replies_org_id"),
        sa.UniqueConstraint(
            "organisation_id",
            "connection_id",
            "provider_message_id",
            name="uq_provider_replies_provider_message",
        ),
    )
    op.create_index("ix_provider_replies_org_received", "provider_replies", ["organisation_id", "received_at"])
    op.create_index(
        "ix_provider_replies_org_outbound",
        "provider_replies",
        ["organisation_id", "outbound_operation_id"],
    )

    op.create_table(
        "provider_calendar_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organisation_id", sa.Uuid(), nullable=False),
        sa.Column("connection_id", sa.Uuid(), nullable=False),
        sa.Column("provider_key", sa.String(length=40), nullable=False),
        sa.Column("provider_event_id", sa.String(length=255), nullable=False),
        sa.Column("i_cal_uid", sa.String(length=255), nullable=True),
        sa.Column("series_master_id", sa.String(length=255), nullable=True),
        sa.Column("change_key", sa.String(length=255), nullable=True),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("start_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("provider_timezone", sa.String(length=100), nullable=False),
        sa.Column("organiser_email", sa.String(length=320), nullable=True),
        sa.Column("attendee_emails_json", sa.JSON(), server_default="[]", nullable=False),
        sa.Column("location", sa.String(length=500), nullable=True),
        sa.Column("online_meeting_url", sa.String(length=2048), nullable=True),
        sa.Column("sensitivity", sa.String(length=24), server_default="normal", nullable=False),
        sa.Column("state", sa.String(length=20), nullable=False),
        sa.Column("match_state", sa.String(length=24), nullable=False),
        sa.Column("contact_id", sa.Uuid(), nullable=True),
        sa.Column("company_id", sa.Uuid(), nullable=True),
        sa.Column("opportunity_id", sa.Uuid(), nullable=True),
        sa.Column("interaction_id", sa.Uuid(), nullable=True),
        sa.Column("provider_last_modified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("provider_key = 'microsoft_365'", name="ck_provider_calendar_events_provider"),
        sa.CheckConstraint("state IN ('active', 'cancelled', 'deleted')", name="ck_provider_calendar_events_state"),
        sa.CheckConstraint(
            "match_state IN ('unmatched', 'matched', 'review_required', 'internal', 'private')",
            name="ck_provider_calendar_events_match_state",
        ),
        sa.CheckConstraint("end_at > start_at", name="ck_provider_calendar_events_time"),
        sa.ForeignKeyConstraint(["organisation_id"], ["organisations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["organisation_id", "connection_id"],
            ["integration_connections.organisation_id", "integration_connections.id"],
            name="fk_provider_calendar_events_connection",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["organisation_id", "contact_id"],
            ["contacts.organisation_id", "contacts.id"],
            name="fk_provider_calendar_events_contact",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organisation_id", "company_id"],
            ["companies.organisation_id", "companies.id"],
            name="fk_provider_calendar_events_company",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organisation_id", "opportunity_id"],
            ["opportunities.organisation_id", "opportunities.id"],
            name="fk_provider_calendar_events_opportunity",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organisation_id", "interaction_id"],
            ["interactions.organisation_id", "interactions.id"],
            name="fk_provider_calendar_events_interaction",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organisation_id", "id", name="uq_provider_calendar_events_org_id"),
        sa.UniqueConstraint(
            "organisation_id",
            "connection_id",
            "provider_event_id",
            name="uq_provider_calendar_events_provider_event",
        ),
    )
    op.create_index(
        "ix_provider_calendar_events_org_start",
        "provider_calendar_events",
        ["organisation_id", "start_at", "state"],
    )
    op.create_index(
        "ix_provider_calendar_events_org_interaction",
        "provider_calendar_events",
        ["organisation_id", "interaction_id"],
    )

    op.create_table(
        "provider_sync_states",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organisation_id", sa.Uuid(), nullable=False),
        sa.Column("connection_id", sa.Uuid(), nullable=False),
        sa.Column("provider_key", sa.String(length=40), nullable=False),
        sa.Column("resource_kind", sa.String(length=24), nullable=False),
        sa.Column("delta_link", sa.Text(), nullable=True),
        sa.Column("window_start_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("window_end_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_successful_sync_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error_category", sa.String(length=80), nullable=True),
        sa.Column("consecutive_failures", sa.Integer(), server_default="0", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("provider_key = 'microsoft_365'", name="ck_provider_sync_states_provider"),
        sa.CheckConstraint(
            "resource_kind IN ('mail_inbox', 'mail_sent', 'calendar')",
            name="ck_provider_sync_states_resource",
        ),
        sa.CheckConstraint("consecutive_failures >= 0", name="ck_provider_sync_states_failures"),
        sa.ForeignKeyConstraint(["organisation_id"], ["organisations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["organisation_id", "connection_id"],
            ["integration_connections.organisation_id", "integration_connections.id"],
            name="fk_provider_sync_states_connection",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organisation_id", "id", name="uq_provider_sync_states_org_id"),
        sa.UniqueConstraint(
            "organisation_id",
            "connection_id",
            "resource_kind",
            name="uq_provider_sync_states_resource",
        ),
    )
    op.create_index(
        "ix_provider_sync_states_org_health",
        "provider_sync_states",
        ["organisation_id", "last_error_category"],
    )
    _enable_tenant_rls()
    _create_worker_discovery()


def downgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        op.execute(
            """DROP FUNCTION IF EXISTS
            public.revenueos_microsoft_sync_eligible_organisations(timestamptz, integer)"""
        )
    for table_name in reversed(TENANT_TABLES):
        op.drop_table(table_name)
    op.execute("DELETE FROM integration_audit_events WHERE connector_key = 'microsoft_365'")
    op.execute(
        "DELETE FROM action_execution_attempts WHERE execution_id IN "
        "(SELECT id FROM action_executions WHERE connector_key = 'microsoft_365')"
    )
    op.execute("DELETE FROM action_executions WHERE connector_key = 'microsoft_365'")
    op.execute(
        "DELETE FROM execution_previews WHERE connection_id IN "
        "(SELECT id FROM integration_connections WHERE connector_key = 'microsoft_365')"
    )
    op.execute("DELETE FROM encrypted_connector_credentials WHERE connector_key = 'microsoft_365'")
    op.execute("DELETE FROM oauth_connection_states WHERE connector_key = 'microsoft_365'")
    op.execute("DELETE FROM integration_connections WHERE connector_key = 'microsoft_365'")
    op.execute("DELETE FROM integration_audit_events WHERE event_type = 'provider_sync_completed'")
    _replace_check(
        "integration_audit_events",
        "ck_integration_audit_events_type",
        "event_type IN ('connection_created', 'connection_tested', 'connection_revoked', "
        "'connection_reauthorisation_required', 'mapping_created', 'mapping_changed', 'mapping_removed', "
        "'field_mapping_changed', 'stage_mapping_changed', 'execution_preview_created', "
        "'execution_confirmed', 'execution_started', 'execution_succeeded', 'execution_failed', "
        "'execution_unknown_state', 'execution_reconciled')",
    )
    _replace_check(
        "engage_campaign_enrollments",
        "ck_engage_campaign_enrollments_provenance",
        "outcome_provenance IS NULL OR outcome_provenance = 'seller_reported'",
    )
    _replace_check(
        "action_executions",
        "ck_action_executions_connector",
        "connector_key IN ('mock_email', 'mock_calendar', 'mock_crm', 'mock_task', 'hubspot')",
    )
    _restore_sqlite_execution_guards()
    _replace_check(
        "encrypted_connector_credentials",
        "ck_encrypted_connector_credentials_connector",
        "connector_key = 'hubspot'",
    )
    _replace_check("oauth_connection_states", "ck_oauth_connection_states_connector", "connector_key = 'hubspot'")
    with op.batch_alter_table("oauth_connection_states") as batch:
        batch.drop_column("oidc_nonce_hash")
        batch.drop_column("pkce_nonce")
        batch.drop_column("pkce_verifier_encrypted")
    _replace_check(
        "integration_connections",
        "ck_integration_connections_key",
        "connector_key IN ('mock_email', 'mock_calendar', 'mock_crm', 'mock_task', 'hubspot')",
    )
    op.drop_index(
        "uq_integration_connections_org_microsoft_owner",
        table_name="integration_connections",
    )
    op.drop_index(
        "uq_integration_connections_org_key_non_microsoft",
        table_name="integration_connections",
    )
    with op.batch_alter_table("integration_connections") as batch:
        batch.drop_column("external_tenant_id")
        batch.drop_column("external_account_email")
        batch.create_unique_constraint(
            "uq_integration_connections_org_key",
            ["organisation_id", "connector_key"],
        )
