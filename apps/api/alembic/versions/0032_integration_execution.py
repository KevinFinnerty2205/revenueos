"""Add simulation-first integrations and Action execution.

Revision ID: 0032_integration_execution
Revises: 0031_action_layer

Downgrade warning: connection metadata, execution previews, execution history,
attempt audits and deterministic mock state are permanently removed. WO-022
performs simulations only, so no real external action requires rollback.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0032_integration_execution"
down_revision: str | None = "0031_action_layer"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TENANT_TABLES = (
    "integration_connections",
    "execution_previews",
    "action_executions",
    "action_execution_attempts",
    "integration_audit_events",
    "mock_connector_objects",
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


def _create_execution_guards() -> None:
    dialect = op.get_bind().dialect.name
    immutable_tables = ("action_execution_attempts", "integration_audit_events")
    immutable_columns = (
        "organisation_id, action_id, action_version, connection_id, preview_id, "
        "connector_key, capability, risk_class, execution_mode, idempotency_key, "
        "preview_fingerprint, confirmed_by_user_id, confirmed_at"
    )
    if dialect == "postgresql":
        op.execute(
            """
            CREATE FUNCTION protect_wo022_immutable_rows()
            RETURNS trigger
            LANGUAGE plpgsql
            AS $$
            BEGIN
                RAISE EXCEPTION 'Execution attempts and integration audits are immutable';
            END;
            $$
            """
        )
        for table_name in immutable_tables:
            op.execute(
                f"""CREATE TRIGGER {table_name}_immutable
                BEFORE UPDATE ON {table_name}
                FOR EACH ROW EXECUTE FUNCTION protect_wo022_immutable_rows()"""
            )
        op.execute(
            f"""CREATE TRIGGER action_executions_intent_immutable
            BEFORE UPDATE OF {immutable_columns} ON action_executions
            FOR EACH ROW EXECUTE FUNCTION protect_wo022_immutable_rows()"""
        )
    elif dialect == "sqlite":
        for table_name in immutable_tables:
            op.execute(
                f"""CREATE TRIGGER {table_name}_immutable
                BEFORE UPDATE ON {table_name}
                FOR EACH ROW
                BEGIN
                    SELECT RAISE(ABORT, 'Execution attempts and integration audits are immutable');
                END"""
            )
        op.execute(
            f"""CREATE TRIGGER action_executions_intent_immutable
            BEFORE UPDATE OF {immutable_columns} ON action_executions
            FOR EACH ROW
            BEGIN
                SELECT RAISE(ABORT, 'Execution intent is immutable');
            END"""
        )


def _drop_execution_guards() -> None:
    dialect = op.get_bind().dialect.name
    if dialect == "postgresql":
        op.execute("DROP TRIGGER action_executions_intent_immutable ON action_executions")
        for table_name in ("action_execution_attempts", "integration_audit_events"):
            op.execute(f"DROP TRIGGER {table_name}_immutable ON {table_name}")
        op.execute("DROP FUNCTION protect_wo022_immutable_rows()")
    elif dialect == "sqlite":
        op.execute("DROP TRIGGER action_executions_intent_immutable")
        for table_name in ("action_execution_attempts", "integration_audit_events"):
            op.execute(f"DROP TRIGGER {table_name}_immutable")


def _create_worker_discovery() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return
    op.execute(
        """
        CREATE FUNCTION public.revenueos_execution_worker_eligible_organisations(
            eligible_at timestamptz,
            result_limit integer
        )
        RETURNS TABLE (organisation_id uuid)
        LANGUAGE sql
        SECURITY DEFINER
        SET search_path = pg_catalog, public
        AS $$
            SELECT DISTINCT action_executions.organisation_id
            FROM public.action_executions
            WHERE (
                action_executions.execution_status = 'queued'
            ) OR (
                action_executions.execution_status = 'failed_retryable'
                AND action_executions.attempt_count < action_executions.max_attempts
                AND action_executions.next_attempt_at IS NOT NULL
                AND action_executions.next_attempt_at <= eligible_at
            ) OR (
                action_executions.execution_status = 'executing'
                AND action_executions.lease_expires_at IS NOT NULL
                AND action_executions.lease_expires_at <= eligible_at
            )
            ORDER BY action_executions.organisation_id
            LIMIT LEAST(GREATEST(result_limit, 1), 1000)
        $$
        """
    )


def upgrade() -> None:
    op.create_table(
        "integration_connections",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organisation_id", sa.Uuid(), nullable=False),
        sa.Column("connector_key", sa.String(length=40), nullable=False),
        sa.Column("connection_status", sa.String(length=20), server_default="active", nullable=False),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("connected_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("last_verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("credential_reference", sa.String(length=255), nullable=True),
        sa.Column("capability_state_json", sa.JSON(), server_default=sa.text("'[]'"), nullable=False),
        sa.Column("metadata_version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "connector_key IN ('mock_email', 'mock_calendar', 'mock_crm', 'mock_task')",
            name="ck_integration_connections_key",
        ),
        sa.CheckConstraint(
            "connection_status IN ('active', 'revoked')",
            name="ck_integration_connections_status",
        ),
        sa.CheckConstraint("metadata_version > 0", name="ck_integration_connections_version"),
        sa.CheckConstraint(
            "(connection_status = 'active' AND revoked_at IS NULL) OR "
            "(connection_status = 'revoked' AND revoked_at IS NOT NULL)",
            name="ck_integration_connections_revoked",
        ),
        sa.ForeignKeyConstraint(["organisation_id"], ["organisations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["organisation_id", "created_by_user_id"],
            ["organisation_memberships.organisation_id", "organisation_memberships.user_id"],
            name="fk_integration_connections_creator",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organisation_id", "id", name="uq_integration_connections_org_id"),
        sa.UniqueConstraint(
            "organisation_id",
            "connector_key",
            name="uq_integration_connections_org_key",
        ),
    )
    op.create_index(
        "ix_integration_connections_org_status",
        "integration_connections",
        ["organisation_id", "connection_status"],
    )

    op.create_table(
        "execution_previews",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organisation_id", sa.Uuid(), nullable=False),
        sa.Column("action_id", sa.Uuid(), nullable=False),
        sa.Column("action_version", sa.Integer(), nullable=False),
        sa.Column("connection_id", sa.Uuid(), nullable=False),
        sa.Column("capability", sa.String(length=40), nullable=False),
        sa.Column("risk_class", sa.String(length=32), nullable=False),
        sa.Column("preview_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("confirmed_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("invalidated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "capability IN ('send_email', 'create_calendar_event', 'update_opportunity', "
            "'update_contact', 'create_task')",
            name="ck_execution_previews_capability",
        ),
        sa.CheckConstraint(
            "risk_class IN ('internal_low_risk', 'external_customer_facing', 'data_mutation')",
            name="ck_execution_previews_risk",
        ),
        sa.CheckConstraint("length(preview_fingerprint) = 64", name="ck_execution_previews_fingerprint"),
        sa.ForeignKeyConstraint(["organisation_id"], ["organisations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["organisation_id", "action_id", "action_version"],
            [
                "action_proposal_versions.organisation_id",
                "action_proposal_versions.action_id",
                "action_proposal_versions.version",
            ],
            name="fk_execution_previews_action_version",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["organisation_id", "connection_id"],
            ["integration_connections.organisation_id", "integration_connections.id"],
            name="fk_execution_previews_connection",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["organisation_id", "confirmed_by_user_id"],
            ["organisation_memberships.organisation_id", "organisation_memberships.user_id"],
            name="fk_execution_previews_confirmer",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organisation_id", "id", name="uq_execution_previews_org_id"),
    )
    op.create_index(
        "ix_execution_previews_org_action",
        "execution_previews",
        ["organisation_id", "action_id", "created_at"],
    )
    op.create_index(
        "ix_execution_previews_org_connection",
        "execution_previews",
        ["organisation_id", "connection_id"],
    )
    op.create_index(
        "ix_execution_previews_org_expiry",
        "execution_previews",
        ["organisation_id", "expires_at"],
    )

    op.create_table(
        "action_executions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organisation_id", sa.Uuid(), nullable=False),
        sa.Column("action_id", sa.Uuid(), nullable=False),
        sa.Column("action_version", sa.Integer(), nullable=False),
        sa.Column("connection_id", sa.Uuid(), nullable=False),
        sa.Column("preview_id", sa.Uuid(), nullable=False),
        sa.Column("connector_key", sa.String(length=40), nullable=False),
        sa.Column("capability", sa.String(length=40), nullable=False),
        sa.Column("risk_class", sa.String(length=32), nullable=False),
        sa.Column("execution_status", sa.String(length=32), server_default="queued", nullable=False),
        sa.Column("execution_mode", sa.String(length=16), server_default="simulation", nullable=False),
        sa.Column("idempotency_key", sa.String(length=64), nullable=False),
        sa.Column("preview_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("confirmed_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("safe_failure_code", sa.String(length=80), nullable=True),
        sa.Column("external_result_id", sa.String(length=255), nullable=True),
        sa.Column("attempt_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("max_attempts", sa.Integer(), server_default="3", nullable=False),
        sa.Column("worker_id", sa.String(length=200), nullable=True),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "connector_key IN ('mock_email', 'mock_calendar', 'mock_crm', 'mock_task')",
            name="ck_action_executions_connector",
        ),
        sa.CheckConstraint(
            "capability IN ('send_email', 'create_calendar_event', 'update_opportunity', "
            "'update_contact', 'create_task')",
            name="ck_action_executions_capability",
        ),
        sa.CheckConstraint(
            "risk_class IN ('internal_low_risk', 'external_customer_facing', 'data_mutation')",
            name="ck_action_executions_risk",
        ),
        sa.CheckConstraint(
            "execution_status IN ('queued', 'executing', 'simulated_success', "
            "'failed_retryable', 'failed_permanent', 'cancelled', 'unknown_external_state')",
            name="ck_action_executions_status",
        ),
        sa.CheckConstraint("execution_mode = 'simulation'", name="ck_action_executions_mode"),
        sa.CheckConstraint("length(idempotency_key) = 64", name="ck_action_executions_idempotency"),
        sa.CheckConstraint("length(preview_fingerprint) = 64", name="ck_action_executions_preview"),
        sa.CheckConstraint("attempt_count >= 0", name="ck_action_executions_attempts"),
        sa.CheckConstraint("max_attempts BETWEEN 1 AND 20", name="ck_action_executions_max_attempts"),
        sa.ForeignKeyConstraint(["organisation_id"], ["organisations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["organisation_id", "action_id", "action_version"],
            [
                "action_proposal_versions.organisation_id",
                "action_proposal_versions.action_id",
                "action_proposal_versions.version",
            ],
            name="fk_action_executions_action_version",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["organisation_id", "connection_id"],
            ["integration_connections.organisation_id", "integration_connections.id"],
            name="fk_action_executions_connection",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organisation_id", "preview_id"],
            ["execution_previews.organisation_id", "execution_previews.id"],
            name="fk_action_executions_preview",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organisation_id", "confirmed_by_user_id"],
            ["organisation_memberships.organisation_id", "organisation_memberships.user_id"],
            name="fk_action_executions_confirmer",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organisation_id", "id", name="uq_action_executions_org_id"),
        sa.UniqueConstraint("organisation_id", "preview_id", name="uq_action_executions_preview"),
        sa.UniqueConstraint("organisation_id", "idempotency_key", name="uq_action_executions_idempotency"),
        sa.UniqueConstraint(
            "organisation_id",
            "action_id",
            "action_version",
            "connection_id",
            "capability",
            name="uq_action_executions_action_connection",
        ),
    )
    op.create_index(
        "ix_action_executions_org_status_next",
        "action_executions",
        ["organisation_id", "execution_status", "next_attempt_at"],
    )
    op.create_index(
        "ix_action_executions_org_action",
        "action_executions",
        ["organisation_id", "action_id", "created_at"],
    )
    op.create_index(
        "ix_action_executions_org_connection_status",
        "action_executions",
        ["organisation_id", "connection_id", "execution_status"],
    )

    op.create_table(
        "action_execution_attempts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organisation_id", sa.Uuid(), nullable=False),
        sa.Column("execution_id", sa.Uuid(), nullable=False),
        sa.Column("attempt_number", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("safe_failure_code", sa.String(length=80), nullable=True),
        sa.Column("external_result_id", sa.String(length=255), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.CheckConstraint("attempt_number > 0", name="ck_action_execution_attempts_number"),
        sa.CheckConstraint("duration_ms IS NULL OR duration_ms >= 0", name="ck_action_execution_attempts_duration"),
        sa.ForeignKeyConstraint(["organisation_id"], ["organisations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["organisation_id", "execution_id"],
            ["action_executions.organisation_id", "action_executions.id"],
            name="fk_action_execution_attempts_execution",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organisation_id", "id", name="uq_action_execution_attempts_org_id"),
        sa.UniqueConstraint(
            "organisation_id",
            "execution_id",
            "attempt_number",
            name="uq_action_execution_attempts_number",
        ),
    )
    op.create_index(
        "ix_action_execution_attempts_org_execution",
        "action_execution_attempts",
        ["organisation_id", "execution_id", "attempt_number"],
    )

    op.create_table(
        "integration_audit_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organisation_id", sa.Uuid(), nullable=False),
        sa.Column("actor_user_id", sa.Uuid(), nullable=False),
        sa.Column("event_type", sa.String(length=40), nullable=False),
        sa.Column("subject_type", sa.String(length=24), nullable=False),
        sa.Column("subject_id", sa.Uuid(), nullable=False),
        sa.Column("connector_key", sa.String(length=40), nullable=False),
        sa.Column("capability", sa.String(length=40), nullable=True),
        sa.Column("risk_class", sa.String(length=32), nullable=True),
        sa.Column("attempt_count", sa.Integer(), nullable=True),
        sa.Column("safe_failure_code", sa.String(length=80), nullable=True),
        sa.Column("external_result_id", sa.String(length=255), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "event_type IN ('connection_created', 'connection_tested', 'connection_revoked', "
            "'execution_preview_created', 'execution_confirmed', 'execution_started', "
            "'execution_succeeded', 'execution_failed', 'execution_unknown_state')",
            name="ck_integration_audit_events_type",
        ),
        sa.CheckConstraint("duration_ms IS NULL OR duration_ms >= 0", name="ck_integration_audit_events_duration"),
        sa.ForeignKeyConstraint(["organisation_id"], ["organisations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["organisation_id", "actor_user_id"],
            ["organisation_memberships.organisation_id", "organisation_memberships.user_id"],
            name="fk_integration_audit_events_actor",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organisation_id", "id", name="uq_integration_audit_events_org_id"),
    )
    op.create_index(
        "ix_integration_audit_events_org_subject",
        "integration_audit_events",
        ["organisation_id", "subject_id", "created_at"],
    )

    op.create_table(
        "mock_connector_objects",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organisation_id", sa.Uuid(), nullable=False),
        sa.Column("connection_id", sa.Uuid(), nullable=False),
        sa.Column("last_execution_id", sa.Uuid(), nullable=False),
        sa.Column("connector_key", sa.String(length=40), nullable=False),
        sa.Column("object_type", sa.String(length=32), nullable=False),
        sa.Column("object_key", sa.String(length=255), nullable=False),
        sa.Column("last_idempotency_key", sa.String(length=64), nullable=False),
        sa.Column("external_result_id", sa.String(length=255), nullable=False),
        sa.Column("state_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "connector_key IN ('mock_email', 'mock_calendar', 'mock_crm', 'mock_task')",
            name="ck_mock_connector_objects_key",
        ),
        sa.ForeignKeyConstraint(["organisation_id"], ["organisations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["organisation_id", "connection_id"],
            ["integration_connections.organisation_id", "integration_connections.id"],
            name="fk_mock_connector_objects_connection",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["organisation_id", "last_execution_id"],
            ["action_executions.organisation_id", "action_executions.id"],
            name="fk_mock_connector_objects_execution",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organisation_id", "id", name="uq_mock_connector_objects_org_id"),
        sa.UniqueConstraint(
            "organisation_id",
            "connection_id",
            "object_key",
            name="uq_mock_connector_objects_key",
        ),
    )

    _enable_tenant_rls()
    _create_execution_guards()
    _create_worker_discovery()


def downgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        op.execute(
            """DROP FUNCTION IF EXISTS
            public.revenueos_execution_worker_eligible_organisations(timestamptz, integer)"""
        )
    _drop_execution_guards()
    op.drop_table("mock_connector_objects")
    op.drop_table("integration_audit_events")
    op.drop_table("action_execution_attempts")
    op.drop_table("action_executions")
    op.drop_table("execution_previews")
    op.drop_table("integration_connections")
