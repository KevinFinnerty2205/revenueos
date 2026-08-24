"""Add focused HubSpot CRM synchronisation.

Revision ID: 0034_crm_sync
Revises: 0033_sales_methodology

Downgrade removes RevenueOS-side OAuth state, encrypted credentials, CRM mappings,
field/stage policy and live execution metadata. It never reverses an external CRM
change.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0034_crm_sync"
down_revision: str | None = "0033_sales_methodology"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TENANT_TABLES = (
    "oauth_connection_states",
    "encrypted_connector_credentials",
    "crm_entity_mappings",
    "crm_field_mappings",
    "crm_stage_mappings",
)

ACTION_TYPES = (
    "'follow_up_email', 'send_requested_material', 'create_task', 'follow_up_stakeholder', "
    "'schedule_interaction', 'update_opportunity', 'update_contact', 'log_interaction', "
    "'update_stakeholder', 'add_decision', 'add_commitment', 'add_risk', 'update_timeline', "
    "'update_procurement', 'update_security_legal', 'create_reminder', 'notify_internal', "
    "'prepare_next_interaction', 'resolve_open_question', 'review_conflict', 'other'"
)
OLD_ACTION_TYPES = ACTION_TYPES.replace("'log_interaction', ", "")
CAPABILITIES = (
    "'send_email', 'create_calendar_event', 'update_opportunity', 'update_contact', 'create_activity', 'create_task'"
)
OLD_CAPABILITIES = CAPABILITIES.replace("'create_activity', ", "")
CONNECTORS = "'mock_email', 'mock_calendar', 'mock_crm', 'mock_task', 'hubspot'"
OLD_CONNECTORS = "'mock_email', 'mock_calendar', 'mock_crm', 'mock_task'"
EXECUTION_STATUSES = (
    "'queued', 'executing', 'simulated_success', 'succeeded', 'failed_retryable', "
    "'failed_permanent', 'cancelled', 'unknown_external_state'"
)
OLD_EXECUTION_STATUSES = EXECUTION_STATUSES.replace("'succeeded', ", "")
AUDIT_EVENTS = (
    "'connection_created', 'connection_tested', 'connection_revoked', "
    "'connection_reauthorisation_required', 'mapping_created', 'mapping_changed', 'mapping_removed', "
    "'field_mapping_changed', 'stage_mapping_changed', 'execution_preview_created', 'execution_confirmed', "
    "'execution_started', 'execution_succeeded', 'execution_failed', "
    "'execution_unknown_state', 'execution_reconciled'"
)
OLD_AUDIT_EVENTS = (
    "'connection_created', 'connection_tested', 'connection_revoked', "
    "'execution_preview_created', 'execution_confirmed', 'execution_started', "
    "'execution_succeeded', 'execution_failed', 'execution_unknown_state'"
)


def _replace_check(table: str, name: str, expression: str) -> None:
    with op.batch_alter_table(table) as batch:
        batch.drop_constraint(name, type_="check")
        batch.create_check_constraint(name, expression)


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


def _restore_sqlite_execution_guards() -> None:
    """SQLite batch table rebuilds drop triggers; preserve WO-022 immutability."""
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
        FOR EACH ROW
        BEGIN
            SELECT RAISE(ABORT, 'Execution intent is immutable');
        END"""
    )
    op.execute("DROP TRIGGER IF EXISTS integration_audit_events_immutable")
    op.execute(
        """CREATE TRIGGER integration_audit_events_immutable
        BEFORE UPDATE ON integration_audit_events
        FOR EACH ROW
        BEGIN
            SELECT RAISE(ABORT, 'Execution attempts and integration audits are immutable');
        END"""
    )


def upgrade() -> None:
    with op.batch_alter_table("integration_connections") as batch:
        batch.add_column(sa.Column("external_account_id", sa.String(length=128), nullable=True))
        batch.add_column(sa.Column("external_account_name", sa.String(length=200), nullable=True))
        batch.add_column(sa.Column("granted_scopes_json", sa.JSON(), server_default="[]", nullable=False))

    _replace_check("action_proposals", "ck_action_proposals_type", f"action_type IN ({ACTION_TYPES})")
    _replace_check(
        "integration_connections",
        "ck_integration_connections_key",
        f"connector_key IN ({CONNECTORS})",
    )
    _replace_check(
        "integration_connections",
        "ck_integration_connections_status",
        "connection_status IN ('active', 'reauthorisation_required', 'revoked')",
    )
    _replace_check(
        "integration_connections",
        "ck_integration_connections_revoked",
        "(connection_status IN ('active', 'reauthorisation_required') AND revoked_at IS NULL) OR "
        "(connection_status = 'revoked' AND revoked_at IS NOT NULL)",
    )
    _replace_check(
        "execution_previews",
        "ck_execution_previews_capability",
        f"capability IN ({CAPABILITIES})",
    )
    _replace_check(
        "action_executions",
        "ck_action_executions_connector",
        f"connector_key IN ({CONNECTORS})",
    )
    _replace_check(
        "action_executions",
        "ck_action_executions_capability",
        f"capability IN ({CAPABILITIES})",
    )
    _replace_check(
        "action_executions",
        "ck_action_executions_status",
        f"execution_status IN ({EXECUTION_STATUSES})",
    )
    _replace_check(
        "action_executions",
        "ck_action_executions_mode",
        "execution_mode IN ('simulation', 'live')",
    )
    _replace_check(
        "integration_audit_events",
        "ck_integration_audit_events_type",
        f"event_type IN ({AUDIT_EVENTS})",
    )
    _restore_sqlite_execution_guards()

    op.create_table(
        "oauth_connection_states",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organisation_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("connector_key", sa.String(length=40), server_default="hubspot", nullable=False),
        sa.Column("state_hash", sa.String(length=64), nullable=False),
        sa.Column("redirect_uri", sa.String(length=2048), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("connector_key = 'hubspot'", name="ck_oauth_connection_states_connector"),
        sa.CheckConstraint("length(state_hash) = 64", name="ck_oauth_connection_states_hash"),
        sa.CheckConstraint("length(trim(redirect_uri)) > 0", name="ck_oauth_connection_states_redirect"),
        sa.ForeignKeyConstraint(["organisation_id"], ["organisations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["organisation_id", "user_id"],
            ["organisation_memberships.organisation_id", "organisation_memberships.user_id"],
            name="fk_oauth_connection_states_membership",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organisation_id", "id", name="uq_oauth_connection_states_org_id"),
        sa.UniqueConstraint("state_hash", name="uq_oauth_connection_states_hash"),
    )
    op.create_index(
        "ix_oauth_connection_states_org_expiry",
        "oauth_connection_states",
        ["organisation_id", "expires_at"],
    )

    op.create_table(
        "encrypted_connector_credentials",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organisation_id", sa.Uuid(), nullable=False),
        sa.Column("connection_id", sa.Uuid(), nullable=False),
        sa.Column("connector_key", sa.String(length=40), server_default="hubspot", nullable=False),
        sa.Column("encrypted_payload", sa.LargeBinary(), nullable=False),
        sa.Column("nonce", sa.LargeBinary(length=12), nullable=False),
        sa.Column("key_version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("connector_key = 'hubspot'", name="ck_encrypted_connector_credentials_connector"),
        sa.CheckConstraint("length(nonce) = 12", name="ck_encrypted_connector_credentials_nonce"),
        sa.CheckConstraint("key_version > 0", name="ck_encrypted_connector_credentials_key_version"),
        sa.ForeignKeyConstraint(["organisation_id"], ["organisations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["organisation_id", "connection_id"],
            ["integration_connections.organisation_id", "integration_connections.id"],
            name="fk_encrypted_connector_credentials_connection",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organisation_id", "id", name="uq_encrypted_connector_credentials_org_id"),
        sa.UniqueConstraint("organisation_id", "connection_id", name="uq_encrypted_connector_credentials_connection"),
    )

    op.create_table(
        "crm_entity_mappings",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organisation_id", sa.Uuid(), nullable=False),
        sa.Column("connection_id", sa.Uuid(), nullable=False),
        sa.Column("revenueos_entity_type", sa.String(length=24), nullable=False),
        sa.Column("revenueos_entity_id", sa.Uuid(), nullable=False),
        sa.Column("external_object_type", sa.String(length=24), nullable=False),
        sa.Column("external_object_id", sa.String(length=128), nullable=False),
        sa.Column("external_updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sync_state", sa.String(length=24), server_default="active", nullable=False),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "revenueos_entity_type IN ('company', 'contact', 'opportunity')",
            name="ck_crm_entity_mappings_entity_type",
        ),
        sa.CheckConstraint(
            "external_object_type IN ('company', 'contact', 'deal')",
            name="ck_crm_entity_mappings_object_type",
        ),
        sa.CheckConstraint("sync_state IN ('active', 'external_missing')", name="ck_crm_entity_mappings_state"),
        sa.CheckConstraint(
            "length(trim(external_object_id)) BETWEEN 1 AND 128",
            name="ck_crm_entity_mappings_external_id",
        ),
        sa.ForeignKeyConstraint(["organisation_id"], ["organisations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["organisation_id", "connection_id"],
            ["integration_connections.organisation_id", "integration_connections.id"],
            name="fk_crm_entity_mappings_connection",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["organisation_id", "created_by_user_id"],
            ["organisation_memberships.organisation_id", "organisation_memberships.user_id"],
            name="fk_crm_entity_mappings_creator",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organisation_id", "id", name="uq_crm_entity_mappings_org_id"),
        sa.UniqueConstraint(
            "organisation_id",
            "connection_id",
            "revenueos_entity_type",
            "revenueos_entity_id",
            name="uq_crm_entity_mappings_revenueos_entity",
        ),
        sa.UniqueConstraint(
            "organisation_id",
            "connection_id",
            "external_object_type",
            "external_object_id",
            name="uq_crm_entity_mappings_external_object",
        ),
    )
    op.create_index(
        "ix_crm_entity_mappings_org_entity",
        "crm_entity_mappings",
        ["organisation_id", "revenueos_entity_type", "revenueos_entity_id"],
    )

    op.create_table(
        "crm_field_mappings",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organisation_id", sa.Uuid(), nullable=False),
        sa.Column("connection_id", sa.Uuid(), nullable=False),
        sa.Column("entity_type", sa.String(length=24), nullable=False),
        sa.Column("revenueos_field", sa.String(length=64), nullable=False),
        sa.Column("external_property_name", sa.String(length=128), nullable=False),
        sa.Column("external_property_type", sa.String(length=24), nullable=False),
        sa.Column("authority", sa.String(length=32), server_default="review_before_sync", nullable=False),
        sa.Column("enabled", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("configured_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("entity_type IN ('opportunity', 'contact')", name="ck_crm_field_mappings_entity_type"),
        sa.CheckConstraint(
            "external_property_type IN ('string', 'number', 'date', 'datetime', 'enumeration')",
            name="ck_crm_field_mappings_property_type",
        ),
        sa.CheckConstraint(
            "authority IN ('crm_authoritative', 'revenueos_authoritative', 'review_before_sync')",
            name="ck_crm_field_mappings_authority",
        ),
        sa.CheckConstraint("length(trim(revenueos_field)) BETWEEN 1 AND 64", name="ck_crm_field_mappings_field"),
        sa.CheckConstraint(
            "length(trim(external_property_name)) BETWEEN 1 AND 128",
            name="ck_crm_field_mappings_property",
        ),
        sa.ForeignKeyConstraint(["organisation_id"], ["organisations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["organisation_id", "connection_id"],
            ["integration_connections.organisation_id", "integration_connections.id"],
            name="fk_crm_field_mappings_connection",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["organisation_id", "configured_by_user_id"],
            ["organisation_memberships.organisation_id", "organisation_memberships.user_id"],
            name="fk_crm_field_mappings_configurer",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organisation_id", "id", name="uq_crm_field_mappings_org_id"),
        sa.UniqueConstraint(
            "organisation_id",
            "connection_id",
            "entity_type",
            "revenueos_field",
            name="uq_crm_field_mappings_field",
        ),
    )

    op.create_table(
        "crm_stage_mappings",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organisation_id", sa.Uuid(), nullable=False),
        sa.Column("connection_id", sa.Uuid(), nullable=False),
        sa.Column("revenueos_stage", sa.String(length=30), nullable=False),
        sa.Column("external_pipeline_id", sa.String(length=128), nullable=False),
        sa.Column("external_stage_id", sa.String(length=128), nullable=False),
        sa.Column("configured_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "revenueos_stage IN ('qualification', 'discovery', 'evaluation', 'proposal', 'negotiation', "
            "'procurement', 'closed_won', 'closed_lost', 'other')",
            name="ck_crm_stage_mappings_stage",
        ),
        sa.CheckConstraint(
            "length(trim(external_pipeline_id)) BETWEEN 1 AND 128", name="ck_crm_stage_mappings_pipeline"
        ),
        sa.CheckConstraint(
            "length(trim(external_stage_id)) BETWEEN 1 AND 128",
            name="ck_crm_stage_mappings_external_stage",
        ),
        sa.ForeignKeyConstraint(["organisation_id"], ["organisations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["organisation_id", "connection_id"],
            ["integration_connections.organisation_id", "integration_connections.id"],
            name="fk_crm_stage_mappings_connection",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["organisation_id", "configured_by_user_id"],
            ["organisation_memberships.organisation_id", "organisation_memberships.user_id"],
            name="fk_crm_stage_mappings_configurer",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organisation_id", "id", name="uq_crm_stage_mappings_org_id"),
        sa.UniqueConstraint("organisation_id", "connection_id", "revenueos_stage", name="uq_crm_stage_mappings_stage"),
    )
    _enable_tenant_rls()


def downgrade() -> None:
    op.execute("DELETE FROM action_executions WHERE connector_key = 'hubspot'")
    op.execute("DELETE FROM integration_connections WHERE connector_key = 'hubspot'")
    op.execute("DELETE FROM action_proposals WHERE action_type = 'log_interaction'")

    for table_name in reversed(TENANT_TABLES):
        op.drop_table(table_name)

    _replace_check(
        "integration_audit_events",
        "ck_integration_audit_events_type",
        f"event_type IN ({OLD_AUDIT_EVENTS})",
    )
    _replace_check("action_executions", "ck_action_executions_mode", "execution_mode = 'simulation'")
    _replace_check(
        "action_executions",
        "ck_action_executions_status",
        f"execution_status IN ({OLD_EXECUTION_STATUSES})",
    )
    _replace_check(
        "action_executions",
        "ck_action_executions_capability",
        f"capability IN ({OLD_CAPABILITIES})",
    )
    _replace_check(
        "action_executions",
        "ck_action_executions_connector",
        f"connector_key IN ({OLD_CONNECTORS})",
    )
    _replace_check(
        "execution_previews",
        "ck_execution_previews_capability",
        f"capability IN ({OLD_CAPABILITIES})",
    )
    _replace_check(
        "integration_connections",
        "ck_integration_connections_revoked",
        "(connection_status = 'active' AND revoked_at IS NULL) OR "
        "(connection_status = 'revoked' AND revoked_at IS NOT NULL)",
    )
    _replace_check(
        "integration_connections",
        "ck_integration_connections_status",
        "connection_status IN ('active', 'revoked')",
    )
    _replace_check(
        "integration_connections",
        "ck_integration_connections_key",
        f"connector_key IN ({OLD_CONNECTORS})",
    )
    _replace_check("action_proposals", "ck_action_proposals_type", f"action_type IN ({OLD_ACTION_TYPES})")

    with op.batch_alter_table("integration_connections") as batch:
        batch.drop_column("granted_scopes_json")
        batch.drop_column("external_account_name")
        batch.drop_column("external_account_id")
    _restore_sqlite_execution_guards()
