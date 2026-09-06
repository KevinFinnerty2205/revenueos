"""Add provider-neutral production CRM connector state and Salesforce.

Revision ID: 0058_production_crm_connectors
Revises: 0057_google_workspace_sales

The migration preserves the canonical Oryntela CRM entities. It adds only
tenant-scoped connector control, owner mapping, resumable sync, immutable
receipts and bounded conflict state. Provider payloads and tokens are not
stored in these tables.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0058_production_crm_connectors"
down_revision: str | None = "0057_google_workspace_sales"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

CRM_TABLES = (
    "crm_connection_states",
    "crm_owner_mappings",
    "crm_sync_cursors",
    "crm_sync_jobs",
    "crm_sync_receipts",
    "crm_conflicts",
    "crm_writeback_previews",
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
    for table_name in CRM_TABLES:
        op.execute(f"ALTER TABLE {table_name} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table_name} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"""CREATE POLICY {table_name}_tenant_isolation ON {table_name}
            USING (organisation_id = NULLIF(current_setting('app.organisation_id', true), '')::uuid)
            WITH CHECK (organisation_id = NULLIF(current_setting('app.organisation_id', true), '')::uuid)"""
        )


def _create_receipt_guards() -> None:
    if op.get_bind().dialect.name == "postgresql":
        op.execute(
            """
            CREATE FUNCTION public.revenueos_crm_receipt_immutable()
            RETURNS trigger LANGUAGE plpgsql AS $$
            BEGIN
                IF TG_OP = 'DELETE'
                   AND current_setting('app.beta_maintenance', true) = 'approved' THEN
                    RETURN OLD;
                END IF;
                RAISE EXCEPTION 'CRM sync receipts are immutable';
            END;
            $$
            """
        )
        op.execute(
            """CREATE TRIGGER crm_sync_receipts_immutable
            BEFORE UPDATE OR DELETE ON crm_sync_receipts
            FOR EACH ROW EXECUTE FUNCTION public.revenueos_crm_receipt_immutable()"""
        )
        return
    op.execute(
        """CREATE TRIGGER crm_sync_receipts_immutable_update
        BEFORE UPDATE ON crm_sync_receipts
        FOR EACH ROW BEGIN SELECT RAISE(ABORT, 'CRM sync receipts are immutable'); END"""
    )


def _drop_receipt_guards() -> None:
    if op.get_bind().dialect.name == "postgresql":
        op.execute("DROP TRIGGER IF EXISTS crm_sync_receipts_immutable ON crm_sync_receipts")
        op.execute("DROP FUNCTION IF EXISTS public.revenueos_crm_receipt_immutable()")
        return
    for operation in ("UPDATE", "DELETE"):
        op.execute(f"DROP TRIGGER IF EXISTS crm_sync_receipts_immutable_{operation.lower()}")


def _create_worker_discovery() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return
    op.execute(
        """
        CREATE FUNCTION public.revenueos_crm_sync_eligible_organisations(
            due_before timestamptz,
            result_limit integer
        )
        RETURNS TABLE (organisation_id uuid)
        LANGUAGE sql
        SECURITY DEFINER
        SET search_path = pg_catalog, public
        AS $$
            SELECT DISTINCT jobs.organisation_id
            FROM public.crm_sync_jobs AS jobs
            JOIN public.crm_connection_states AS states
              ON states.organisation_id = jobs.organisation_id
             AND states.connection_id = jobs.connection_id
            JOIN public.integration_connections AS connections
              ON connections.organisation_id = jobs.organisation_id
             AND connections.id = jobs.connection_id
            WHERE jobs.status IN ('queued', 'running')
              AND (jobs.lease_expires_at IS NULL OR jobs.lease_expires_at <= due_before)
              AND states.connector_enabled
              AND connections.connection_status = 'active'
            ORDER BY jobs.organisation_id
            LIMIT LEAST(GREATEST(result_limit, 1), 1000)
        $$
        """
    )
    op.execute(
        """
        CREATE FUNCTION public.revenueos_crm_sync_due_connections(
            due_before timestamptz,
            result_limit integer
        )
        RETURNS TABLE (organisation_id uuid, connection_id uuid, requested_by_user_id uuid)
        LANGUAGE sql
        SECURITY DEFINER
        SET search_path = pg_catalog, public
        AS $$
            SELECT states.organisation_id, states.connection_id, states.configured_by_user_id
            FROM public.crm_connection_states AS states
            JOIN public.integration_connections AS connections
              ON connections.organisation_id = states.organisation_id
             AND connections.id = states.connection_id
            JOIN public.organisation_memberships AS memberships
              ON memberships.organisation_id = states.organisation_id
             AND memberships.user_id = states.configured_by_user_id
            JOIN public.users AS users
              ON users.id = states.configured_by_user_id
            WHERE states.connector_enabled
              AND states.initial_sync_completed_at IS NOT NULL
              AND (states.last_successful_sync_at IS NULL OR states.last_successful_sync_at <= due_before)
              AND connections.connection_status = 'active'
              AND memberships.status = 'active'
              AND users.status = 'active'
              AND NOT EXISTS (
                  SELECT 1
                  FROM public.crm_sync_jobs AS jobs
                  WHERE jobs.organisation_id = states.organisation_id
                    AND jobs.connection_id = states.connection_id
                    AND jobs.status IN ('queued', 'running', 'paused')
              )
            ORDER BY states.last_successful_sync_at NULLS FIRST, states.organisation_id, states.connection_id
            LIMIT LEAST(GREATEST(result_limit, 1), 1000)
        $$
        """
    )


def _connection_fk(name: str, *, ondelete: str = "CASCADE") -> sa.ForeignKeyConstraint:
    return sa.ForeignKeyConstraint(
        ["organisation_id", "connection_id"],
        ["integration_connections.organisation_id", "integration_connections.id"],
        name=name,
        ondelete=ondelete,
    )


def _membership_fk(column: str, name: str) -> sa.ForeignKeyConstraint:
    return sa.ForeignKeyConstraint(
        ["organisation_id", column],
        ["organisation_memberships.organisation_id", "organisation_memberships.user_id"],
        name=name,
        ondelete="RESTRICT",
    )


def upgrade() -> None:
    _replace_check(
        "integration_connections",
        "ck_integration_connections_key",
        "connector_key IN ('mock_email', 'mock_calendar', 'mock_crm', 'mock_task', 'hubspot', "
        "'salesforce', 'microsoft_365', 'google_workspace')",
    )
    _replace_check(
        "oauth_connection_states",
        "ck_oauth_connection_states_connector",
        "connector_key IN ('hubspot', 'salesforce', 'microsoft_365', 'google_workspace')",
    )
    _replace_check(
        "encrypted_connector_credentials",
        "ck_encrypted_connector_credentials_connector",
        "connector_key IN ('hubspot', 'salesforce', 'microsoft_365', 'google_workspace')",
    )
    _replace_check(
        "action_executions",
        "ck_action_executions_connector",
        "connector_key IN ('mock_email', 'mock_calendar', 'mock_crm', 'mock_task', 'hubspot', "
        "'salesforce', 'microsoft_365', 'google_workspace')",
    )
    _restore_sqlite_execution_guards()
    _replace_check(
        "integration_audit_events",
        "ck_integration_audit_events_type",
        "event_type IN ('connection_created', 'connection_tested', 'connection_revoked', "
        "'connection_reauthorisation_required', 'mapping_created', 'mapping_changed', 'mapping_removed', "
        "'field_mapping_changed', 'stage_mapping_changed', 'execution_preview_created', "
        "'execution_confirmed', 'execution_started', 'execution_succeeded', 'execution_failed', "
        "'execution_unknown_state', 'execution_reconciled', 'provider_sync_completed', 'crm_sync_queued', "
        "'crm_sync_completed', 'crm_mapping_reviewed', 'crm_connector_changed', 'crm_writeback_changed', "
        "'crm_writeback_reconciled', 'crm_conflict_resolved', 'crm_provider_switched')",
    )
    _replace_check(
        "crm_entity_mappings",
        "ck_crm_entity_mappings_object_type",
        "external_object_type IN ('account', 'company', 'contact', 'opportunity', 'deal')",
    )
    with op.batch_alter_table("crm_entity_mappings") as batch:
        batch.add_column(sa.Column("external_version", sa.String(length=255), nullable=True))
        batch.add_column(sa.Column("authority_version", sa.Integer(), server_default="1", nullable=False))
        batch.add_column(sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True))
        batch.create_check_constraint("ck_crm_entity_mappings_authority_version", "authority_version > 0")
    _replace_check(
        "crm_field_mappings",
        "ck_crm_field_mappings_entity_type",
        "entity_type IN ('company', 'contact', 'opportunity')",
    )
    with op.batch_alter_table("crm_field_mappings") as batch:
        batch.add_column(sa.Column("mapping_version", sa.Integer(), server_default="1", nullable=False))
        batch.create_check_constraint("ck_crm_field_mappings_version", "mapping_version > 0")
    with op.batch_alter_table("crm_stage_mappings") as batch:
        batch.add_column(sa.Column("mapping_version", sa.Integer(), server_default="1", nullable=False))
        batch.create_check_constraint("ck_crm_stage_mappings_version", "mapping_version > 0")
    _replace_check(
        "organisation_crm_settings",
        "ck_organisation_crm_settings_provider",
        "(mode = 'native' AND external_provider IS NULL) OR "
        "(mode = 'external' AND external_provider IN ('hubspot', 'salesforce'))",
    )
    op.create_index(
        "uq_integration_connections_org_active_external_crm",
        "integration_connections",
        ["organisation_id"],
        unique=True,
        postgresql_where=sa.text("connector_key IN ('hubspot', 'salesforce') AND connection_status <> 'revoked'"),
        sqlite_where=sa.text("connector_key IN ('hubspot', 'salesforce') AND connection_status <> 'revoked'"),
    )
    op.create_index(
        "uq_integration_connections_external_crm_tenant",
        "integration_connections",
        ["connector_key", sa.text("coalesce(external_tenant_id, external_account_id)")],
        unique=True,
        postgresql_where=sa.text(
            "connector_key IN ('hubspot', 'salesforce') AND connection_status <> 'revoked' "
            "AND coalesce(external_tenant_id, external_account_id) IS NOT NULL"
        ),
        sqlite_where=sa.text(
            "connector_key IN ('hubspot', 'salesforce') AND connection_status <> 'revoked' "
            "AND coalesce(external_tenant_id, external_account_id) IS NOT NULL"
        ),
    )

    op.create_table(
        "crm_connection_states",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organisation_id", sa.Uuid(), nullable=False),
        sa.Column("connection_id", sa.Uuid(), nullable=False),
        sa.Column("provider_key", sa.String(length=40), nullable=False),
        sa.Column("lifecycle", sa.String(length=32), server_default="connected_read_only", nullable=False),
        sa.Column("health_status", sa.String(length=24), server_default="unknown", nullable=False),
        sa.Column("connector_enabled", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("writeback_enabled", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("mapping_version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("records_seen", sa.Integer(), server_default="0", nullable=False),
        sa.Column("records_applied", sa.Integer(), server_default="0", nullable=False),
        sa.Column("conflict_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("initial_sync_started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("initial_sync_completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_successful_sync_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_health_checked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_safe_error_code", sa.String(length=80), nullable=True),
        sa.Column("configured_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("provider_key IN ('hubspot', 'salesforce')", name="ck_crm_connection_states_provider"),
        sa.CheckConstraint(
            "lifecycle IN ('connected_read_only', 'initial_sync', 'mapping_required', 'ready', "
            "'needs_attention', 'disabled')",
            name="ck_crm_connection_states_lifecycle",
        ),
        sa.CheckConstraint(
            "health_status IN ('unknown', 'healthy', 'degraded', 'needs_reauth', 'rate_limited', 'unavailable')",
            name="ck_crm_connection_states_health",
        ),
        sa.CheckConstraint("mapping_version > 0", name="ck_crm_connection_states_mapping_version"),
        sa.CheckConstraint(
            "records_seen >= 0 AND records_applied >= 0 AND conflict_count >= 0",
            name="ck_crm_connection_states_counts",
        ),
        sa.ForeignKeyConstraint(["organisation_id"], ["organisations.id"], ondelete="CASCADE"),
        _connection_fk("fk_crm_connection_states_connection"),
        _membership_fk("configured_by_user_id", "fk_crm_connection_states_configurer"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organisation_id", "id", name="uq_crm_connection_states_org_id"),
        sa.UniqueConstraint("organisation_id", "connection_id", name="uq_crm_connection_states_connection"),
    )
    op.create_index(
        "ix_crm_connection_states_org_health",
        "crm_connection_states",
        ["organisation_id", "health_status", "updated_at"],
    )

    op.create_table(
        "crm_owner_mappings",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organisation_id", sa.Uuid(), nullable=False),
        sa.Column("connection_id", sa.Uuid(), nullable=False),
        sa.Column("provider_key", sa.String(length=40), nullable=False),
        sa.Column("external_owner_id", sa.String(length=128), nullable=False),
        sa.Column("external_owner_name", sa.String(length=200), nullable=True),
        sa.Column("external_owner_email", sa.String(length=320), nullable=True),
        sa.Column("user_id", sa.Uuid(), nullable=True),
        sa.Column("state", sa.String(length=16), server_default="unmapped", nullable=False),
        sa.Column("configured_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("provider_key IN ('hubspot', 'salesforce')", name="ck_crm_owner_mappings_provider"),
        sa.CheckConstraint("state IN ('unmapped', 'mapped', 'inactive')", name="ck_crm_owner_mappings_state"),
        sa.CheckConstraint(
            "(state = 'mapped' AND user_id IS NOT NULL) OR (state <> 'mapped' AND user_id IS NULL)",
            name="ck_crm_owner_mappings_user",
        ),
        sa.ForeignKeyConstraint(["organisation_id"], ["organisations.id"], ondelete="CASCADE"),
        _connection_fk("fk_crm_owner_mappings_connection"),
        _membership_fk("user_id", "fk_crm_owner_mappings_user"),
        _membership_fk("configured_by_user_id", "fk_crm_owner_mappings_configurer"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organisation_id", "id", name="uq_crm_owner_mappings_org_id"),
        sa.UniqueConstraint(
            "organisation_id", "connection_id", "external_owner_id", name="uq_crm_owner_mappings_external_owner"
        ),
    )

    op.create_table(
        "crm_sync_cursors",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organisation_id", sa.Uuid(), nullable=False),
        sa.Column("connection_id", sa.Uuid(), nullable=False),
        sa.Column("provider_key", sa.String(length=40), nullable=False),
        sa.Column("object_type", sa.String(length=24), nullable=False),
        sa.Column("strategy", sa.String(length=16), nullable=False),
        sa.Column("cursor_token", sa.String(length=2048), nullable=True),
        sa.Column("high_watermark_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("page_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("record_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("provider_key IN ('hubspot', 'salesforce')", name="ck_crm_sync_cursors_provider"),
        sa.CheckConstraint("object_type IN ('account', 'contact', 'opportunity')", name="ck_crm_sync_cursors_object"),
        sa.CheckConstraint("strategy IN ('full', 'incremental')", name="ck_crm_sync_cursors_strategy"),
        sa.CheckConstraint("page_count >= 0 AND record_count >= 0", name="ck_crm_sync_cursors_counts"),
        sa.ForeignKeyConstraint(["organisation_id"], ["organisations.id"], ondelete="CASCADE"),
        _connection_fk("fk_crm_sync_cursors_connection"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organisation_id", "id", name="uq_crm_sync_cursors_org_id"),
        sa.UniqueConstraint("organisation_id", "connection_id", "object_type", name="uq_crm_sync_cursors_object"),
    )

    op.create_table(
        "crm_sync_jobs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organisation_id", sa.Uuid(), nullable=False),
        sa.Column("connection_id", sa.Uuid(), nullable=False),
        sa.Column("provider_key", sa.String(length=40), nullable=False),
        sa.Column("mode", sa.String(length=16), nullable=False),
        sa.Column("status", sa.String(length=16), server_default="queued", nullable=False),
        sa.Column("idempotency_key", sa.String(length=64), nullable=False),
        sa.Column("requested_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("attempt_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("worker_id", sa.String(length=200), nullable=True),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("safe_failure_code", sa.String(length=80), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("provider_key IN ('hubspot', 'salesforce')", name="ck_crm_sync_jobs_provider"),
        sa.CheckConstraint("mode IN ('initial', 'incremental', 'reconcile')", name="ck_crm_sync_jobs_mode"),
        sa.CheckConstraint(
            "status IN ('queued', 'running', 'paused', 'succeeded', 'degraded', 'cancelled', 'failed')",
            name="ck_crm_sync_jobs_status",
        ),
        sa.CheckConstraint("attempt_count >= 0", name="ck_crm_sync_jobs_attempts"),
        sa.ForeignKeyConstraint(["organisation_id"], ["organisations.id"], ondelete="CASCADE"),
        _connection_fk("fk_crm_sync_jobs_connection"),
        _membership_fk("requested_by_user_id", "fk_crm_sync_jobs_requester"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organisation_id", "id", name="uq_crm_sync_jobs_org_id"),
        sa.UniqueConstraint("organisation_id", "connection_id", "idempotency_key", name="uq_crm_sync_jobs_key"),
    )
    op.create_index("ix_crm_sync_jobs_org_status", "crm_sync_jobs", ["organisation_id", "status", "created_at"])
    op.create_index(
        "uq_crm_sync_jobs_connection_active",
        "crm_sync_jobs",
        ["organisation_id", "connection_id"],
        unique=True,
        postgresql_where=sa.text("status IN ('queued', 'running', 'paused')"),
        sqlite_where=sa.text("status IN ('queued', 'running', 'paused')"),
    )

    op.create_table(
        "crm_sync_receipts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organisation_id", sa.Uuid(), nullable=False),
        sa.Column("connection_id", sa.Uuid(), nullable=False),
        sa.Column("provider_key", sa.String(length=40), nullable=False),
        sa.Column("direction", sa.String(length=12), nullable=False),
        sa.Column("object_type", sa.String(length=24), nullable=False),
        sa.Column("operation", sa.String(length=16), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("idempotency_key", sa.String(length=64), nullable=False),
        sa.Column("revenueos_entity_id", sa.Uuid(), nullable=True),
        sa.Column("external_object_id", sa.String(length=128), nullable=True),
        sa.Column("external_version", sa.String(length=255), nullable=True),
        sa.Column("field_keys_json", sa.JSON(), server_default="[]", nullable=False),
        sa.Column("safe_failure_code", sa.String(length=80), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("provider_key IN ('hubspot', 'salesforce')", name="ck_crm_sync_receipts_provider"),
        sa.CheckConstraint("direction IN ('inbound', 'outbound')", name="ck_crm_sync_receipts_direction"),
        sa.CheckConstraint("object_type IN ('account', 'contact', 'opportunity')", name="ck_crm_sync_receipts_object"),
        sa.CheckConstraint(
            "operation IN ('observe', 'create', 'update', 'archive', 'reconcile')",
            name="ck_crm_sync_receipts_operation",
        ),
        sa.CheckConstraint(
            "status IN ('applied', 'skipped', 'conflict', 'reconciled', 'unknown', 'failed')",
            name="ck_crm_sync_receipts_status",
        ),
        sa.CheckConstraint("length(idempotency_key) = 64", name="ck_crm_sync_receipts_key"),
        sa.ForeignKeyConstraint(["organisation_id"], ["organisations.id"], ondelete="CASCADE"),
        _connection_fk("fk_crm_sync_receipts_connection", ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organisation_id", "id", name="uq_crm_sync_receipts_org_id"),
        sa.UniqueConstraint("organisation_id", "connection_id", "idempotency_key", name="uq_crm_sync_receipts_key"),
    )
    op.create_index(
        "ix_crm_sync_receipts_org_created",
        "crm_sync_receipts",
        ["organisation_id", "connection_id", "created_at"],
    )

    op.create_table(
        "crm_conflicts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organisation_id", sa.Uuid(), nullable=False),
        sa.Column("connection_id", sa.Uuid(), nullable=False),
        sa.Column("provider_key", sa.String(length=40), nullable=False),
        sa.Column("object_type", sa.String(length=24), nullable=False),
        sa.Column("revenueos_entity_id", sa.Uuid(), nullable=True),
        sa.Column("external_object_id", sa.String(length=128), nullable=False),
        sa.Column("field_key", sa.String(length=64), nullable=False),
        sa.Column("oryntela_value_json", sa.JSON(), nullable=True),
        sa.Column("provider_value_json", sa.JSON(), nullable=True),
        sa.Column("oryntela_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("provider_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=16), server_default="open", nullable=False),
        sa.Column("resolution", sa.String(length=16), nullable=True),
        sa.Column("resolved_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("provider_key IN ('hubspot', 'salesforce')", name="ck_crm_conflicts_provider"),
        sa.CheckConstraint("object_type IN ('account', 'contact', 'opportunity')", name="ck_crm_conflicts_object"),
        sa.CheckConstraint("status IN ('open', 'resolved', 'ignored')", name="ck_crm_conflicts_status"),
        sa.CheckConstraint(
            "resolution IS NULL OR resolution IN ('provider', 'oryntela', 'manual')",
            name="ck_crm_conflicts_resolution",
        ),
        sa.CheckConstraint(
            "(status = 'open' AND resolution IS NULL AND resolved_at IS NULL AND resolved_by_user_id IS NULL) OR "
            "(status <> 'open' AND resolution IS NOT NULL AND resolved_at IS NOT NULL "
            "AND resolved_by_user_id IS NOT NULL)",
            name="ck_crm_conflicts_lifecycle",
        ),
        sa.ForeignKeyConstraint(["organisation_id"], ["organisations.id"], ondelete="CASCADE"),
        _connection_fk("fk_crm_conflicts_connection", ondelete="RESTRICT"),
        _membership_fk("resolved_by_user_id", "fk_crm_conflicts_resolver"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organisation_id", "id", name="uq_crm_conflicts_org_id"),
    )
    op.create_index(
        "uq_crm_conflicts_open_field",
        "crm_conflicts",
        ["organisation_id", "connection_id", "object_type", "external_object_id", "field_key"],
        unique=True,
        postgresql_where=sa.text("status = 'open'"),
        sqlite_where=sa.text("status = 'open'"),
    )
    op.create_index("ix_crm_conflicts_org_status", "crm_conflicts", ["organisation_id", "status", "created_at"])
    op.create_table(
        "crm_writeback_previews",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organisation_id", sa.Uuid(), nullable=False),
        sa.Column("connection_id", sa.Uuid(), nullable=False),
        sa.Column("entity_type", sa.String(length=24), nullable=False),
        sa.Column("entity_id", sa.Uuid(), nullable=False),
        sa.Column("operation", sa.String(length=16), nullable=False),
        sa.Column("external_object_id", sa.String(length=128), nullable=True),
        sa.Column("external_version", sa.String(length=255), nullable=True),
        sa.Column("changes_json", sa.JSON(), nullable=False),
        sa.Column("preview_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("mapping_version", sa.Integer(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("confirmed_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("receipt_id", sa.Uuid(), nullable=True),
        sa.Column("invalidated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "entity_type IN ('company', 'contact', 'opportunity')",
            name="ck_crm_writeback_previews_entity",
        ),
        sa.CheckConstraint("operation IN ('create', 'update')", name="ck_crm_writeback_previews_operation"),
        sa.CheckConstraint("length(preview_fingerprint) = 64", name="ck_crm_writeback_previews_fingerprint"),
        sa.CheckConstraint(
            "(confirmed_at IS NULL AND confirmed_by_user_id IS NULL AND receipt_id IS NULL) OR "
            "(confirmed_at IS NOT NULL AND confirmed_by_user_id IS NOT NULL AND receipt_id IS NOT NULL)",
            name="ck_crm_writeback_previews_confirmation",
        ),
        sa.ForeignKeyConstraint(["organisation_id"], ["organisations.id"], ondelete="CASCADE"),
        _connection_fk("fk_crm_writeback_previews_connection"),
        _membership_fk("confirmed_by_user_id", "fk_crm_writeback_previews_confirmer"),
        sa.ForeignKeyConstraint(
            ["organisation_id", "receipt_id"],
            ["crm_sync_receipts.organisation_id", "crm_sync_receipts.id"],
            name="fk_crm_writeback_previews_receipt",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organisation_id", "id", name="uq_crm_writeback_previews_org_id"),
    )
    op.create_index(
        "ix_crm_writeback_previews_org_expiry",
        "crm_writeback_previews",
        ["organisation_id", "expires_at"],
    )
    _enable_tenant_rls()
    _create_receipt_guards()
    _create_worker_discovery()


def downgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        op.execute("DROP FUNCTION IF EXISTS public.revenueos_crm_sync_due_connections(timestamptz, integer)")
        op.execute("DROP FUNCTION IF EXISTS public.revenueos_crm_sync_eligible_organisations(timestamptz, integer)")
    _drop_receipt_guards()
    for table_name in reversed(CRM_TABLES):
        op.drop_table(table_name)
    op.drop_index("uq_integration_connections_external_crm_tenant", table_name="integration_connections")
    op.drop_index("uq_integration_connections_org_active_external_crm", table_name="integration_connections")
    op.execute(
        "UPDATE organisation_crm_settings SET mode = 'native', external_provider = NULL "
        "WHERE external_provider = 'salesforce'"
    )
    _replace_check(
        "organisation_crm_settings",
        "ck_organisation_crm_settings_provider",
        "(mode = 'native' AND external_provider IS NULL) OR (mode = 'external' AND external_provider = 'hubspot')",
    )
    with op.batch_alter_table("crm_stage_mappings") as batch:
        batch.drop_constraint("ck_crm_stage_mappings_version", type_="check")
        batch.drop_column("mapping_version")
    with op.batch_alter_table("crm_field_mappings") as batch:
        batch.drop_constraint("ck_crm_field_mappings_version", type_="check")
        batch.drop_column("mapping_version")
    op.execute("DELETE FROM crm_field_mappings WHERE entity_type = 'company'")
    _replace_check(
        "crm_field_mappings",
        "ck_crm_field_mappings_entity_type",
        "entity_type IN ('opportunity', 'contact')",
    )
    with op.batch_alter_table("crm_entity_mappings") as batch:
        batch.drop_constraint("ck_crm_entity_mappings_authority_version", type_="check")
        batch.drop_column("archived_at")
        batch.drop_column("authority_version")
        batch.drop_column("external_version")
    op.execute("DELETE FROM crm_entity_mappings WHERE external_object_type IN ('account', 'opportunity')")
    _replace_check(
        "crm_entity_mappings",
        "ck_crm_entity_mappings_object_type",
        "external_object_type IN ('company', 'contact', 'deal')",
    )
    op.execute("DELETE FROM integration_audit_events WHERE connector_key = 'salesforce'")
    op.execute(
        "DELETE FROM integration_audit_events WHERE event_type IN ('crm_sync_queued', 'crm_sync_completed', "
        "'crm_mapping_reviewed', 'crm_writeback_changed', 'crm_writeback_reconciled', "
        "'crm_conflict_resolved', 'crm_provider_switched')"
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
    op.execute(
        "DELETE FROM action_execution_attempts WHERE execution_id IN "
        "(SELECT id FROM action_executions WHERE connector_key = 'salesforce')"
    )
    op.execute("DELETE FROM action_executions WHERE connector_key = 'salesforce'")
    _replace_check(
        "action_executions",
        "ck_action_executions_connector",
        "connector_key IN ('mock_email', 'mock_calendar', 'mock_crm', 'mock_task', 'hubspot', "
        "'microsoft_365', 'google_workspace')",
    )
    _restore_sqlite_execution_guards()
    op.execute("DELETE FROM encrypted_connector_credentials WHERE connector_key = 'salesforce'")
    op.execute("DELETE FROM oauth_connection_states WHERE connector_key = 'salesforce'")
    op.execute("DELETE FROM integration_connections WHERE connector_key = 'salesforce'")
    _replace_check(
        "encrypted_connector_credentials",
        "ck_encrypted_connector_credentials_connector",
        "connector_key IN ('hubspot', 'microsoft_365', 'google_workspace')",
    )
    _replace_check(
        "oauth_connection_states",
        "ck_oauth_connection_states_connector",
        "connector_key IN ('hubspot', 'microsoft_365', 'google_workspace')",
    )
    _replace_check(
        "integration_connections",
        "ck_integration_connections_key",
        "connector_key IN ('mock_email', 'mock_calendar', 'mock_crm', 'mock_task', 'hubspot', "
        "'microsoft_365', 'google_workspace')",
    )
