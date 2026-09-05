"""Add provider-neutral Credits and variable-cost controls.

Revision ID: 0054_credits_variable_cost
Revises: 0053_billing_subscriptions

WO-049 creates TEST-only catalogues plus tenant-isolated ledger, balance,
reservation and reconciliation state. No live provider or production price is
activated. Ledger/catalogue history is immutable and commercial rows block
organisation deletion pending an approved accounting-retention decision.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0054_credits_variable_cost"
down_revision: str | None = "0053_billing_subscriptions"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TENANT_TABLES = (
    "organisation_credit_balances",
    "credit_organisation_policies",
    "credit_lots",
    "credit_quotes",
    "credit_operations",
    "credit_reservation_allocations",
    "credit_ledger_entries",
)

IMMUTABLE_TABLES = (
    "credit_pack_versions",
    "credit_action_price_versions",
    "credit_control_events",
    "credit_ledger_entries",
)


def _create_security() -> None:
    dialect = op.get_bind().dialect.name
    if dialect == "postgresql":
        for table_name in TENANT_TABLES:
            op.execute(f"ALTER TABLE {table_name} ENABLE ROW LEVEL SECURITY")
            op.execute(f"ALTER TABLE {table_name} FORCE ROW LEVEL SECURITY")
            op.execute(
                f"""CREATE POLICY {table_name}_tenant_isolation
                ON {table_name}
                USING (organisation_id = NULLIF(current_setting('app.organisation_id', true), '')::uuid)
                WITH CHECK (organisation_id = NULLIF(current_setting('app.organisation_id', true), '')::uuid)"""
            )
        op.execute(
            """CREATE FUNCTION public.revenueos_reject_credit_history_mutation()
            RETURNS trigger AS $$
            BEGIN
                RAISE EXCEPTION 'Credit ledger and catalogue versions are immutable';
            END;
            $$ LANGUAGE plpgsql"""
        )
        for table_name in IMMUTABLE_TABLES:
            op.execute(
                f"""CREATE TRIGGER {table_name}_immutable
                BEFORE UPDATE OR DELETE ON {table_name}
                FOR EACH ROW EXECUTE FUNCTION public.revenueos_reject_credit_history_mutation()"""
            )
    elif dialect == "sqlite":
        for table_name in IMMUTABLE_TABLES:
            for operation in ("UPDATE", "DELETE"):
                op.execute(
                    f"""CREATE TRIGGER {table_name}_immutable_{operation.lower()}
                    BEFORE {operation} ON {table_name}
                    BEGIN SELECT RAISE(ABORT, 'Credit ledger and catalogue versions are immutable'); END"""
                )


def _drop_security() -> None:
    dialect = op.get_bind().dialect.name
    if dialect == "postgresql":
        for table_name in IMMUTABLE_TABLES:
            op.execute(f"DROP TRIGGER IF EXISTS {table_name}_immutable ON {table_name}")
        op.execute("DROP FUNCTION IF EXISTS public.revenueos_reject_credit_history_mutation()")
    elif dialect == "sqlite":
        for table_name in IMMUTABLE_TABLES:
            for operation in ("update", "delete"):
                op.execute(f"DROP TRIGGER IF EXISTS {table_name}_immutable_{operation}")


def upgrade() -> None:
    uuid_type = sa.Uuid(as_uuid=True)
    op.create_table(
        "credit_pack_versions",
        sa.Column("id", uuid_type, nullable=False),
        sa.Column("pack_code", sa.String(length=80), nullable=False),
        sa.Column("display_name", sa.String(length=120), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("credit_quantity", sa.BigInteger(), nullable=False),
        sa.Column("price_minor_units", sa.BigInteger(), nullable=False),
        sa.Column("currency", sa.String(length=3), server_default="AUD", nullable=False),
        sa.Column("environment", sa.String(length=12), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("pricing_note", sa.String(length=240), nullable=False),
        sa.Column("effective_from", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by_actor", sa.String(length=200), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("version > 0", name="ck_credit_packs_version"),
        sa.CheckConstraint("credit_quantity > 0", name="ck_credit_packs_quantity"),
        sa.CheckConstraint("price_minor_units > 0", name="ck_credit_packs_price"),
        sa.CheckConstraint(
            "length(currency) = 3 AND currency = upper(currency)",
            name="ck_credit_packs_currency",
        ),
        sa.CheckConstraint("environment IN ('test', 'production')", name="ck_credit_packs_environment"),
        sa.CheckConstraint(
            "status IN ('draft', 'test_active', 'production_active', 'retired')",
            name="ck_credit_packs_status",
        ),
        sa.CheckConstraint(
            "(status <> 'test_active' OR environment = 'test') AND "
            "(status <> 'production_active' OR environment = 'production')",
            name="ck_credit_packs_activation",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("pack_code", "version", name="uq_credit_packs_code_version"),
    )
    op.create_index(
        "ix_credit_packs_environment_status",
        "credit_pack_versions",
        ["environment", "status", "pack_code"],
    )
    with op.batch_alter_table("billing_operations") as batch:
        batch.add_column(sa.Column("credit_pack_version_id", uuid_type, nullable=True))
        batch.create_foreign_key(
            "fk_billing_operations_credit_pack",
            "credit_pack_versions",
            ["credit_pack_version_id"],
            ["id"],
            ondelete="RESTRICT",
        )

    op.create_table(
        "credit_action_price_versions",
        sa.Column("id", uuid_type, nullable=False),
        sa.Column("action_code", sa.String(length=100), nullable=False),
        sa.Column("display_name", sa.String(length=140), nullable=False),
        sa.Column("required_module_code", sa.String(length=40), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("credit_charge_per_unit", sa.BigInteger(), nullable=False),
        sa.Column("customer_charge_basis", sa.String(length=24), nullable=False),
        sa.Column("max_units_per_operation", sa.Integer(), nullable=False),
        sa.Column("customer_revenue_micros_per_unit", sa.BigInteger(), nullable=False),
        sa.Column("customer_currency", sa.String(length=3), server_default="AUD", nullable=False),
        sa.Column("cost_basis", sa.String(length=32), nullable=False),
        sa.Column("provider_cost_minor_units", sa.BigInteger(), nullable=False),
        sa.Column("provider_currency", sa.String(length=3), nullable=False),
        sa.Column("provider_minor_units_per_major", sa.Integer(), server_default="100", nullable=False),
        sa.Column("fx_rate_to_aud", sa.Numeric(18, 8), nullable=False),
        sa.Column("fx_source", sa.String(length=120), nullable=False),
        sa.Column("fx_observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("other_variable_cost_micros", sa.BigInteger(), server_default="0", nullable=False),
        sa.Column("expected_variable_cost_micros_per_unit", sa.BigInteger(), nullable=False),
        sa.Column("maximum_variable_cost_micros_per_unit", sa.BigInteger(), nullable=False),
        sa.Column("gross_margin_basis_points", sa.Integer(), nullable=False),
        sa.Column("approved_margin_floor_basis_points", sa.Integer(), nullable=True),
        sa.Column("owner_approval_reference", sa.String(length=200), nullable=True),
        sa.Column("environment", sa.String(length=12), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("pricing_note", sa.String(length=240), nullable=False),
        sa.Column("effective_from", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by_actor", sa.String(length=200), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("version > 0", name="ck_credit_prices_version"),
        sa.CheckConstraint("credit_charge_per_unit > 0", name="ck_credit_prices_charge"),
        sa.CheckConstraint("max_units_per_operation > 0", name="ck_credit_prices_max_units"),
        sa.CheckConstraint(
            "customer_revenue_micros_per_unit > 0 AND expected_variable_cost_micros_per_unit >= 0 "
            "AND maximum_variable_cost_micros_per_unit >= expected_variable_cost_micros_per_unit",
            name="ck_credit_prices_economics",
        ),
        sa.CheckConstraint("customer_currency = 'AUD'", name="ck_credit_prices_currency"),
        sa.CheckConstraint("environment IN ('test', 'production')", name="ck_credit_prices_environment"),
        sa.CheckConstraint(
            "status IN ('draft', 'test_active', 'production_active', 'retired')",
            name="ck_credit_prices_status",
        ),
        sa.CheckConstraint(
            "cost_basis IN ('fixed_operation', 'successful_unit', 'provider_unit', 'message_segment', 'minute')",
            name="ck_credit_prices_cost_basis",
        ),
        sa.CheckConstraint(
            "customer_charge_basis IN ('successful_unit', 'requested_unit')",
            name="ck_credit_prices_customer_charge_basis",
        ),
        sa.CheckConstraint(
            "provider_cost_minor_units >= 0 AND provider_currency <> '' "
            "AND provider_minor_units_per_major > 0 AND provider_minor_units_per_major <= 1000000 "
            "AND other_variable_cost_micros >= 0",
            name="ck_credit_prices_provider_cost",
        ),
        sa.CheckConstraint("fx_rate_to_aud > 0 AND fx_source <> ''", name="ck_credit_prices_fx"),
        sa.CheckConstraint(
            "gross_margin_basis_points > -100000 AND gross_margin_basis_points <= 10000",
            name="ck_credit_prices_margin",
        ),
        sa.CheckConstraint(
            "(status <> 'test_active' OR environment = 'test') AND "
            "(status <> 'production_active' OR (environment = 'production' "
            "AND approved_margin_floor_basis_points IS NOT NULL "
            "AND owner_approval_reference IS NOT NULL "
            "AND customer_revenue_micros_per_unit > maximum_variable_cost_micros_per_unit "
            "AND gross_margin_basis_points >= approved_margin_floor_basis_points))",
            name="ck_credit_prices_activation",
        ),
        sa.CheckConstraint(
            "approved_margin_floor_basis_points IS NULL OR approved_margin_floor_basis_points BETWEEN 1 AND 9999",
            name="ck_credit_prices_margin_floor",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("action_code", "version", name="uq_credit_prices_code_version"),
    )
    op.create_index(
        "ix_credit_prices_environment_status",
        "credit_action_price_versions",
        ["environment", "status", "action_code"],
    )

    op.create_table(
        "credit_execution_controls",
        sa.Column("id", uuid_type, nullable=False),
        sa.Column("control_scope", sa.String(length=28), nullable=False),
        sa.Column("control_key", sa.String(length=120), nullable=False),
        sa.Column("enabled", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("actor_reference", sa.String(length=200), nullable=False),
        sa.Column("reason", sa.String(length=500), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "control_scope IN ('global', 'action', 'provider_capability')", name="ck_credit_controls_scope"
        ),
        sa.CheckConstraint("control_key <> ''", name="ck_credit_controls_key"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("control_scope", "control_key", name="uq_credit_controls_scope_key"),
    )
    op.create_table(
        "credit_control_events",
        sa.Column("id", uuid_type, nullable=False),
        sa.Column("control_scope", sa.String(length=28), nullable=False),
        sa.Column("control_key", sa.String(length=120), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("actor_reference", sa.String(length=200), nullable=False),
        sa.Column("reason", sa.String(length=500), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "control_scope IN ('global', 'action', 'provider_capability')",
            name="ck_credit_control_events_scope",
        ),
        sa.CheckConstraint("control_key <> ''", name="ck_credit_control_events_key"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_credit_control_events_created",
        "credit_control_events",
        ["control_scope", "control_key", "created_at"],
    )

    op.create_table(
        "organisation_credit_balances",
        sa.Column("organisation_id", uuid_type, nullable=False),
        sa.Column("purchased_available", sa.BigInteger(), server_default="0", nullable=False),
        sa.Column("promotional_available", sa.BigInteger(), server_default="0", nullable=False),
        sa.Column("purchased_reserved", sa.BigInteger(), server_default="0", nullable=False),
        sa.Column("promotional_reserved", sa.BigInteger(), server_default="0", nullable=False),
        sa.Column("lock_version", sa.BigInteger(), server_default="1", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "purchased_available >= 0 AND promotional_available >= 0 "
            "AND purchased_reserved >= 0 AND promotional_reserved >= 0",
            name="ck_credit_balances_non_negative",
        ),
        sa.CheckConstraint("lock_version > 0", name="ck_credit_balances_lock"),
        sa.ForeignKeyConstraint(["organisation_id"], ["organisations.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("organisation_id"),
    )

    op.create_table(
        "credit_organisation_policies",
        sa.Column("organisation_id", uuid_type, nullable=False),
        sa.Column("metered_actions_enabled", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("max_credits_per_operation", sa.BigInteger(), nullable=False),
        sa.Column("max_credits_per_day", sa.BigInteger(), nullable=False),
        sa.Column("max_provider_cost_micros_per_day", sa.BigInteger(), nullable=False),
        sa.Column("trial_max_credits_per_day", sa.BigInteger(), nullable=True),
        sa.Column("max_operations_per_minute", sa.Integer(), nullable=False),
        sa.Column("actor_reference", sa.String(length=200), nullable=False),
        sa.Column("reason", sa.String(length=500), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "max_credits_per_operation > 0 AND max_credits_per_day > 0 "
            "AND max_provider_cost_micros_per_day > 0 AND max_operations_per_minute > 0",
            name="ck_credit_policies_positive",
        ),
        sa.CheckConstraint(
            "trial_max_credits_per_day IS NULL OR trial_max_credits_per_day > 0",
            name="ck_credit_policies_trial",
        ),
        sa.ForeignKeyConstraint(["organisation_id"], ["organisations.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("organisation_id"),
    )

    op.create_table(
        "credit_lots",
        sa.Column("id", uuid_type, nullable=False),
        sa.Column("organisation_id", uuid_type, nullable=False),
        sa.Column("credit_type", sa.String(length=16), nullable=False),
        sa.Column("source_reference", sa.String(length=200), nullable=False),
        sa.Column("original_credits", sa.BigInteger(), nullable=False),
        sa.Column("available_credits", sa.BigInteger(), nullable=False),
        sa.Column("reserved_credits", sa.BigInteger(), server_default="0", nullable=False),
        sa.Column("consumed_credits", sa.BigInteger(), server_default="0", nullable=False),
        sa.Column("original_revenue_micros", sa.BigInteger(), server_default="0", nullable=False),
        sa.Column("remaining_revenue_micros", sa.BigInteger(), server_default="0", nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("trial_grant", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("pack_version_id", uuid_type, nullable=True),
        sa.Column("billing_operation_id", uuid_type, nullable=True),
        sa.Column("grant_actor_reference", sa.String(length=200), nullable=False),
        sa.Column("grant_reason", sa.String(length=500), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("credit_type IN ('purchased', 'promotional')", name="ck_credit_lots_type"),
        sa.CheckConstraint(
            "original_credits > 0 AND available_credits >= 0 AND reserved_credits >= 0 "
            "AND consumed_credits >= 0 AND available_credits + reserved_credits + consumed_credits <= original_credits",
            name="ck_credit_lots_amounts",
        ),
        sa.CheckConstraint(
            "original_revenue_micros >= 0 AND remaining_revenue_micros >= 0 "
            "AND remaining_revenue_micros <= original_revenue_micros",
            name="ck_credit_lots_revenue",
        ),
        sa.CheckConstraint(
            "credit_type = 'purchased' OR original_revenue_micros = 0", name="ck_credit_lots_promo_revenue"
        ),
        sa.CheckConstraint(
            "NOT trial_grant OR (credit_type = 'promotional' AND expires_at IS NOT NULL)",
            name="ck_credit_lots_trial_grant",
        ),
        sa.ForeignKeyConstraint(["organisation_id"], ["organisations.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["pack_version_id"], ["credit_pack_versions.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["organisation_id", "billing_operation_id"],
            ["billing_operations.organisation_id", "billing_operations.id"],
            name="fk_credit_lots_billing_operation",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organisation_id", "source_reference", name="uq_credit_lots_source"),
        sa.UniqueConstraint("organisation_id", "id", name="uq_credit_lots_org_id"),
    )
    op.create_index(
        "ix_credit_lots_consumption",
        "credit_lots",
        ["organisation_id", "credit_type", "expires_at", "created_at"],
    )
    op.create_index(
        "uq_credit_lots_org_trial_grant",
        "credit_lots",
        ["organisation_id"],
        unique=True,
        postgresql_where=sa.text("trial_grant"),
        sqlite_where=sa.text("trial_grant = 1"),
    )

    op.create_table(
        "credit_quotes",
        sa.Column("id", uuid_type, nullable=False),
        sa.Column("organisation_id", uuid_type, nullable=False),
        sa.Column("created_by_user_id", uuid_type, nullable=False),
        sa.Column("action_price_version_id", uuid_type, nullable=False),
        sa.Column("action_code", sa.String(length=100), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("required_credits", sa.BigInteger(), nullable=False),
        sa.Column("maximum_provider_cost_micros", sa.BigInteger(), nullable=False),
        sa.Column("quote_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=16), server_default="open", nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("quantity > 0 AND required_credits > 0", name="ck_credit_quotes_amounts"),
        sa.CheckConstraint("status IN ('open', 'reserved', 'expired')", name="ck_credit_quotes_status"),
        sa.CheckConstraint("length(quote_fingerprint) = 64", name="ck_credit_quotes_fingerprint"),
        sa.ForeignKeyConstraint(["organisation_id"], ["organisations.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["organisation_id", "created_by_user_id"],
            ["organisation_memberships.organisation_id", "organisation_memberships.user_id"],
            name="fk_credit_quotes_creator",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(["action_price_version_id"], ["credit_action_price_versions.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organisation_id", "id", name="uq_credit_quotes_org_id"),
    )
    op.create_index("ix_credit_quotes_org_expires", "credit_quotes", ["organisation_id", "expires_at", "status"])

    op.create_table(
        "credit_operations",
        sa.Column("id", uuid_type, nullable=False),
        sa.Column("organisation_id", uuid_type, nullable=False),
        sa.Column("requested_by_user_id", uuid_type, nullable=False),
        sa.Column("quote_id", uuid_type, nullable=False),
        sa.Column("action_price_version_id", uuid_type, nullable=False),
        sa.Column("action_code", sa.String(length=100), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("idempotency_key", sa.String(length=200), nullable=False),
        sa.Column("request_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("outcome", sa.String(length=24), server_default="pending", nullable=False),
        sa.Column("reserved_credits", sa.BigInteger(), nullable=False),
        sa.Column("settled_credits", sa.BigInteger(), server_default="0", nullable=False),
        sa.Column("released_credits", sa.BigInteger(), server_default="0", nullable=False),
        sa.Column("successful_units", sa.Integer(), server_default="0", nullable=False),
        sa.Column("customer_revenue_micros", sa.BigInteger(), server_default="0", nullable=False),
        sa.Column("provider_cost_micros", sa.BigInteger(), server_default="0", nullable=False),
        sa.Column("provider_cost_currency", sa.String(length=3), nullable=True),
        sa.Column("provider_request_id", sa.String(length=255), nullable=True),
        sa.Column("execution_started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("outcome_recorded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "status IN ('reserved', 'executing', 'unknown', 'settled', 'released')",
            name="ck_credit_operations_status",
        ),
        sa.CheckConstraint(
            "outcome IN ('pending', 'success', 'partial', 'failure', 'unknown', 'reconciled_success', "
            "'reconciled_failure')",
            name="ck_credit_operations_outcome",
        ),
        sa.CheckConstraint(
            "reserved_credits > 0 AND settled_credits >= 0 AND released_credits >= 0 "
            "AND settled_credits + released_credits <= reserved_credits AND successful_units >= 0",
            name="ck_credit_operations_amounts",
        ),
        sa.CheckConstraint(
            "customer_revenue_micros >= 0 AND provider_cost_micros >= 0", name="ck_credit_operations_costs"
        ),
        sa.CheckConstraint("length(request_fingerprint) = 64", name="ck_credit_operations_fingerprint"),
        sa.ForeignKeyConstraint(["organisation_id"], ["organisations.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["organisation_id", "requested_by_user_id"],
            ["organisation_memberships.organisation_id", "organisation_memberships.user_id"],
            name="fk_credit_operations_requester",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organisation_id", "quote_id"],
            ["credit_quotes.organisation_id", "credit_quotes.id"],
            name="fk_credit_operations_quote",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(["action_price_version_id"], ["credit_action_price_versions.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organisation_id", "idempotency_key", name="uq_credit_operations_key"),
        sa.UniqueConstraint("organisation_id", "id", name="uq_credit_operations_org_id"),
        sa.UniqueConstraint("organisation_id", "quote_id", name="uq_credit_operations_quote"),
    )
    op.create_index("ix_credit_operations_org_created", "credit_operations", ["organisation_id", "created_at", "id"])
    op.create_index("ix_credit_operations_org_status", "credit_operations", ["organisation_id", "status", "updated_at"])

    op.create_table(
        "credit_reservation_allocations",
        sa.Column("id", uuid_type, nullable=False),
        sa.Column("organisation_id", uuid_type, nullable=False),
        sa.Column("operation_id", uuid_type, nullable=False),
        sa.Column("lot_id", uuid_type, nullable=False),
        sa.Column("allocation_order", sa.Integer(), nullable=False),
        sa.Column("reserved_credits", sa.BigInteger(), nullable=False),
        sa.Column("consumed_credits", sa.BigInteger(), server_default="0", nullable=False),
        sa.Column("released_credits", sa.BigInteger(), server_default="0", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "allocation_order > 0 AND reserved_credits > 0 AND consumed_credits >= 0 AND released_credits >= 0 "
            "AND consumed_credits + released_credits <= reserved_credits",
            name="ck_credit_allocations_amounts",
        ),
        sa.ForeignKeyConstraint(["organisation_id"], ["organisations.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["organisation_id", "operation_id"],
            ["credit_operations.organisation_id", "credit_operations.id"],
            name="fk_credit_allocations_operation",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organisation_id", "lot_id"],
            ["credit_lots.organisation_id", "credit_lots.id"],
            name="fk_credit_allocations_lot",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organisation_id", "operation_id", "lot_id", name="uq_credit_allocations_lot"),
        sa.UniqueConstraint("organisation_id", "operation_id", "allocation_order", name="uq_credit_allocations_order"),
        sa.UniqueConstraint("organisation_id", "id", name="uq_credit_allocations_org_id"),
    )

    op.create_table(
        "credit_ledger_entries",
        sa.Column("id", uuid_type, nullable=False),
        sa.Column("organisation_id", uuid_type, nullable=False),
        sa.Column("event_type", sa.String(length=24), nullable=False),
        sa.Column("credit_type", sa.String(length=16), nullable=False),
        sa.Column("purchased_available_delta", sa.BigInteger(), server_default="0", nullable=False),
        sa.Column("promotional_available_delta", sa.BigInteger(), server_default="0", nullable=False),
        sa.Column("reserved_delta", sa.BigInteger(), server_default="0", nullable=False),
        sa.Column("lot_id", uuid_type, nullable=False),
        sa.Column("operation_id", uuid_type, nullable=True),
        sa.Column("referenced_entry_id", uuid_type, nullable=True),
        sa.Column("action_code", sa.String(length=100), nullable=True),
        sa.Column("quantity", sa.Integer(), nullable=True),
        sa.Column("idempotency_key", sa.String(length=200), nullable=False),
        sa.Column("request_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("actor_reference", sa.String(length=200), nullable=False),
        sa.Column("reason", sa.String(length=500), nullable=False),
        sa.Column("customer_revenue_micros", sa.BigInteger(), server_default="0", nullable=False),
        sa.Column("provider_cost_micros", sa.BigInteger(), server_default="0", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "event_type IN ('purchase', 'promotional_grant', 'reservation', 'consumption', 'release', "
            "'refund', 'correction', 'expiry')",
            name="ck_credit_ledger_type",
        ),
        sa.CheckConstraint("credit_type IN ('purchased', 'promotional')", name="ck_credit_ledger_credit_type"),
        sa.CheckConstraint(
            "purchased_available_delta <> 0 OR promotional_available_delta <> 0 OR reserved_delta <> 0",
            name="ck_credit_ledger_non_zero",
        ),
        sa.CheckConstraint("customer_revenue_micros >= 0 AND provider_cost_micros >= 0", name="ck_credit_ledger_costs"),
        sa.CheckConstraint("length(request_fingerprint) = 64", name="ck_credit_ledger_fingerprint"),
        sa.ForeignKeyConstraint(["organisation_id"], ["organisations.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["organisation_id", "lot_id"],
            ["credit_lots.organisation_id", "credit_lots.id"],
            name="fk_credit_ledger_lot",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organisation_id", "operation_id"],
            ["credit_operations.organisation_id", "credit_operations.id"],
            name="fk_credit_ledger_operation",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organisation_id", "referenced_entry_id"],
            ["credit_ledger_entries.organisation_id", "credit_ledger_entries.id"],
            name="fk_credit_ledger_reference",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organisation_id", "idempotency_key", name="uq_credit_ledger_key"),
        sa.UniqueConstraint("organisation_id", "id", name="uq_credit_ledger_org_id"),
    )
    op.create_index("ix_credit_ledger_org_created", "credit_ledger_entries", ["organisation_id", "created_at", "id"])
    op.create_index(
        "ix_credit_ledger_org_operation",
        "credit_ledger_entries",
        ["organisation_id", "operation_id", "event_type"],
    )
    _create_security()


def downgrade() -> None:
    _drop_security()
    op.drop_index("ix_credit_ledger_org_operation", table_name="credit_ledger_entries")
    op.drop_index("ix_credit_ledger_org_created", table_name="credit_ledger_entries")
    op.drop_table("credit_ledger_entries")
    op.drop_table("credit_reservation_allocations")
    op.drop_index("ix_credit_operations_org_status", table_name="credit_operations")
    op.drop_index("ix_credit_operations_org_created", table_name="credit_operations")
    op.drop_table("credit_operations")
    op.drop_index("ix_credit_quotes_org_expires", table_name="credit_quotes")
    op.drop_table("credit_quotes")
    op.drop_index("ix_credit_lots_consumption", table_name="credit_lots")
    op.drop_table("credit_lots")
    op.drop_table("credit_organisation_policies")
    op.drop_table("organisation_credit_balances")
    op.drop_index("ix_credit_control_events_created", table_name="credit_control_events")
    op.drop_table("credit_control_events")
    op.drop_table("credit_execution_controls")
    with op.batch_alter_table("billing_operations") as batch:
        batch.drop_constraint("fk_billing_operations_credit_pack", type_="foreignkey")
        batch.drop_column("credit_pack_version_id")
    op.drop_index("ix_credit_prices_environment_status", table_name="credit_action_price_versions")
    op.drop_table("credit_action_price_versions")
    op.drop_index("ix_credit_packs_environment_status", table_name="credit_pack_versions")
    op.drop_table("credit_pack_versions")
