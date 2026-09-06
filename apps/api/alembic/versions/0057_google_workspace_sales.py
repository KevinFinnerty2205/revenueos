"""Add Google Workspace to the provider-neutral mailbox/calendar foundation.

Revision ID: 0057_google_workspace_sales
Revises: 0056_microsoft_365_sales

No new customer entity is introduced. Existing connection, credential,
outbound-operation, reply, calendar-event and sync-state tables are widened to
accept the Google Workspace provider while preserving tenant-scoped keys and
forced PostgreSQL RLS.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0057_google_workspace_sales"
down_revision: str | None = "0056_microsoft_365_sales"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

MAILBOX_KEYS = "'microsoft_365', 'google_workspace'"


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


def _create_worker_discovery() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return
    op.execute(
        """
        CREATE FUNCTION public.revenueos_mailbox_sync_eligible_organisations(
            requested_provider text,
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
            WHERE requested_provider IN ('microsoft_365', 'google_workspace')
              AND connections.connector_key = requested_provider
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
    op.drop_index(
        "uq_integration_connections_org_microsoft_owner",
        table_name="integration_connections",
    )
    op.drop_index(
        "uq_integration_connections_org_key_non_microsoft",
        table_name="integration_connections",
    )
    op.create_index(
        "uq_integration_connections_org_key_non_mailbox",
        "integration_connections",
        ["organisation_id", "connector_key"],
        unique=True,
        postgresql_where=sa.text(f"connector_key NOT IN ({MAILBOX_KEYS})"),
        sqlite_where=sa.text(f"connector_key NOT IN ({MAILBOX_KEYS})"),
    )
    op.create_index(
        "uq_integration_connections_org_mailbox_owner",
        "integration_connections",
        ["organisation_id", "created_by_user_id"],
        unique=True,
        postgresql_where=sa.text(f"connector_key IN ({MAILBOX_KEYS}) AND connection_status <> 'revoked'"),
        sqlite_where=sa.text(f"connector_key IN ({MAILBOX_KEYS}) AND connection_status <> 'revoked'"),
    )
    _replace_check(
        "integration_connections",
        "ck_integration_connections_key",
        "connector_key IN ('mock_email', 'mock_calendar', 'mock_crm', 'mock_task', "
        "'hubspot', 'microsoft_365', 'google_workspace')",
    )
    _replace_check(
        "oauth_connection_states",
        "ck_oauth_connection_states_connector",
        "connector_key IN ('hubspot', 'microsoft_365', 'google_workspace')",
    )
    _replace_check(
        "encrypted_connector_credentials",
        "ck_encrypted_connector_credentials_connector",
        "connector_key IN ('hubspot', 'microsoft_365', 'google_workspace')",
    )
    _replace_check(
        "action_executions",
        "ck_action_executions_connector",
        "connector_key IN ('mock_email', 'mock_calendar', 'mock_crm', 'mock_task', "
        "'hubspot', 'microsoft_365', 'google_workspace')",
    )
    _restore_sqlite_execution_guards()
    for table in (
        "provider_outbound_operations",
        "provider_replies",
        "provider_calendar_events",
        "provider_sync_states",
    ):
        _replace_check(
            table,
            f"ck_{table}_provider",
            f"provider_key IN ({MAILBOX_KEYS})",
        )
    _create_worker_discovery()


def downgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        op.execute(
            """DROP FUNCTION IF EXISTS
            public.revenueos_mailbox_sync_eligible_organisations(text, timestamptz, integer)"""
        )
    op.execute("DELETE FROM provider_replies WHERE provider_key = 'google_workspace'")
    op.execute("DELETE FROM provider_calendar_events WHERE provider_key = 'google_workspace'")
    op.execute("DELETE FROM provider_sync_states WHERE provider_key = 'google_workspace'")
    op.execute("DELETE FROM provider_outbound_operations WHERE provider_key = 'google_workspace'")
    op.execute("DELETE FROM integration_audit_events WHERE connector_key = 'google_workspace'")
    op.execute(
        "DELETE FROM action_execution_attempts WHERE execution_id IN "
        "(SELECT id FROM action_executions WHERE connector_key = 'google_workspace')"
    )
    op.execute("DELETE FROM action_executions WHERE connector_key = 'google_workspace'")
    op.execute(
        "DELETE FROM execution_previews WHERE connection_id IN "
        "(SELECT id FROM integration_connections WHERE connector_key = 'google_workspace')"
    )
    op.execute("DELETE FROM encrypted_connector_credentials WHERE connector_key = 'google_workspace'")
    op.execute("DELETE FROM oauth_connection_states WHERE connector_key = 'google_workspace'")
    op.execute("DELETE FROM integration_connections WHERE connector_key = 'google_workspace'")
    for table in (
        "provider_outbound_operations",
        "provider_replies",
        "provider_calendar_events",
        "provider_sync_states",
    ):
        _replace_check(table, f"ck_{table}_provider", "provider_key = 'microsoft_365'")
    _replace_check(
        "action_executions",
        "ck_action_executions_connector",
        "connector_key IN ('mock_email', 'mock_calendar', 'mock_crm', 'mock_task', 'hubspot', 'microsoft_365')",
    )
    _restore_sqlite_execution_guards()
    _replace_check(
        "encrypted_connector_credentials",
        "ck_encrypted_connector_credentials_connector",
        "connector_key IN ('hubspot', 'microsoft_365')",
    )
    _replace_check(
        "oauth_connection_states",
        "ck_oauth_connection_states_connector",
        "connector_key IN ('hubspot', 'microsoft_365')",
    )
    _replace_check(
        "integration_connections",
        "ck_integration_connections_key",
        "connector_key IN ('mock_email', 'mock_calendar', 'mock_crm', 'mock_task', 'hubspot', 'microsoft_365')",
    )
    op.drop_index(
        "uq_integration_connections_org_mailbox_owner",
        table_name="integration_connections",
    )
    op.drop_index(
        "uq_integration_connections_org_key_non_mailbox",
        table_name="integration_connections",
    )
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
