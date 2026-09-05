"""Add provider-neutral test-mode billing and subscription projections.

Revision ID: 0053_billing_subscriptions
Revises: 0052_commercial_plans_trial

WO-048 stores safe provider references and projections only. Card/payment
credentials are never accepted. Tenant tables use forced PostgreSQL RLS and
billing retention blocks organisation cascade deletion.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0053_billing_subscriptions"
down_revision: str | None = "0052_commercial_plans_trial"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TENANT_TABLES = (
    "billing_accounts",
    "billing_subscriptions",
    "billing_invoice_projections",
    "billing_operations",
    "billing_provider_event_receipts",
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
            """CREATE FUNCTION public.revenueos_reject_billing_receipt_mutation()
            RETURNS trigger AS $$
            BEGIN
                RAISE EXCEPTION 'billing provider receipts are immutable';
            END;
            $$ LANGUAGE plpgsql"""
        )
        op.execute(
            """CREATE TRIGGER billing_provider_event_receipts_immutable
            BEFORE UPDATE OR DELETE ON billing_provider_event_receipts
            FOR EACH ROW EXECUTE FUNCTION public.revenueos_reject_billing_receipt_mutation()"""
        )
    elif dialect == "sqlite":
        for operation in ("UPDATE", "DELETE"):
            op.execute(
                f"""CREATE TRIGGER billing_provider_event_receipts_immutable_{operation.lower()}
                BEFORE {operation} ON billing_provider_event_receipts
                BEGIN SELECT RAISE(ABORT, 'billing provider receipts are immutable'); END"""
            )


def _drop_security() -> None:
    dialect = op.get_bind().dialect.name
    if dialect == "postgresql":
        op.execute(
            "DROP TRIGGER IF EXISTS billing_provider_event_receipts_immutable ON billing_provider_event_receipts"
        )
        op.execute("DROP FUNCTION IF EXISTS public.revenueos_reject_billing_receipt_mutation()")
    elif dialect == "sqlite":
        for operation in ("update", "delete"):
            op.execute(f"DROP TRIGGER IF EXISTS billing_provider_event_receipts_immutable_{operation}")


def upgrade() -> None:
    uuid_type = sa.Uuid(as_uuid=True)
    with op.batch_alter_table("organisation_commercial_states") as batch:
        batch.drop_constraint("ck_commercial_states_source", type_="check")
        batch.create_check_constraint(
            "ck_commercial_states_source",
            "source IN ('manual_support', 'migration', 'billing_provider')",
        )

    op.create_table(
        "billing_accounts",
        sa.Column("id", uuid_type, nullable=False),
        sa.Column("organisation_id", uuid_type, nullable=False),
        sa.Column("provider", sa.String(length=24), nullable=False),
        sa.Column("provider_mode", sa.String(length=12), server_default="test", nullable=False),
        sa.Column("provider_customer_id", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=24), server_default="active", nullable=False),
        sa.Column("last_reconciled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("provider IN ('deterministic', 'stripe')", name="ck_billing_accounts_provider"),
        sa.CheckConstraint("provider_mode = 'test'", name="ck_billing_accounts_mode"),
        sa.CheckConstraint("status IN ('active', 'manually_managed')", name="ck_billing_accounts_status"),
        sa.ForeignKeyConstraint(["organisation_id"], ["organisations.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organisation_id", "provider", "provider_mode", name="uq_billing_accounts_org_provider"),
        sa.UniqueConstraint("provider", "provider_mode", "provider_customer_id", name="uq_billing_accounts_customer"),
        sa.UniqueConstraint("organisation_id", "id", name="uq_billing_accounts_org_id"),
    )
    op.create_table(
        "billing_subscriptions",
        sa.Column("id", uuid_type, nullable=False),
        sa.Column("organisation_id", uuid_type, nullable=False),
        sa.Column("billing_account_id", uuid_type, nullable=False),
        sa.Column("provider_subscription_id", sa.String(length=255), nullable=False),
        sa.Column("plan_version_id", uuid_type, nullable=False),
        sa.Column("pending_plan_version_id", uuid_type, nullable=True),
        sa.Column("billing_interval", sa.String(length=12), nullable=False),
        sa.Column("pending_billing_interval", sa.String(length=12), nullable=True),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("currency", sa.String(length=3), server_default="AUD", nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("current_period_start", sa.DateTime(timezone=True), nullable=True),
        sa.Column("current_period_end", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancel_at_period_end", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("provider_updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_provider_event_id", sa.String(length=255), nullable=False),
        sa.Column("lock_version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "status IN ('pending', 'active', 'past_due', 'cancel_at_period_end', 'cancelled', "
            "'unpaid', 'incomplete', 'unknown_reconciliation')",
            name="ck_billing_subscriptions_status",
        ),
        sa.CheckConstraint("billing_interval IN ('monthly', 'annual')", name="ck_billing_subscriptions_interval"),
        sa.CheckConstraint(
            "pending_billing_interval IS NULL OR pending_billing_interval IN ('monthly', 'annual')",
            name="ck_billing_subscriptions_pending_interval",
        ),
        sa.CheckConstraint("currency = 'AUD'", name="ck_billing_subscriptions_currency"),
        sa.CheckConstraint("amount >= 0", name="ck_billing_subscriptions_amount"),
        sa.CheckConstraint("lock_version > 0", name="ck_billing_subscriptions_lock"),
        sa.CheckConstraint(
            "(pending_plan_version_id IS NULL AND pending_billing_interval IS NULL) OR "
            "(pending_plan_version_id IS NOT NULL AND pending_billing_interval IS NOT NULL)",
            name="ck_billing_subscriptions_pending_plan",
        ),
        sa.ForeignKeyConstraint(
            ["organisation_id", "billing_account_id"],
            ["billing_accounts.organisation_id", "billing_accounts.id"],
            name="fk_billing_subscriptions_account",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(["plan_version_id"], ["commercial_plan_versions.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["pending_plan_version_id"], ["commercial_plan_versions.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organisation_id", "id", name="uq_billing_subscriptions_org_id"),
        sa.UniqueConstraint(
            "billing_account_id", "provider_subscription_id", name="uq_billing_subscriptions_provider_id"
        ),
    )
    op.create_index(
        "ix_billing_subscriptions_org_status", "billing_subscriptions", ["organisation_id", "status", "updated_at"]
    )
    op.create_table(
        "billing_invoice_projections",
        sa.Column("id", uuid_type, nullable=False),
        sa.Column("organisation_id", uuid_type, nullable=False),
        sa.Column("subscription_id", uuid_type, nullable=False),
        sa.Column("provider_invoice_id", sa.String(length=255), nullable=False),
        sa.Column("invoice_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("amount_due", sa.Numeric(12, 2), nullable=False),
        sa.Column("amount_paid", sa.Numeric(12, 2), nullable=False),
        sa.Column("tax_amount", sa.Numeric(12, 2), nullable=True),
        sa.Column("currency", sa.String(length=3), server_default="AUD", nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("hosted_invoice_url", sa.String(length=2048), nullable=True),
        sa.Column("receipt_url", sa.String(length=2048), nullable=True),
        sa.Column("provider_updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "status IN ('draft', 'open', 'paid', 'void', 'uncollectible', 'refunded')",
            name="ck_billing_invoices_status",
        ),
        sa.CheckConstraint("currency = 'AUD'", name="ck_billing_invoices_currency"),
        sa.CheckConstraint(
            "amount_due >= 0 AND amount_paid >= 0 AND (tax_amount IS NULL OR tax_amount >= 0)",
            name="ck_billing_invoices_amounts",
        ),
        sa.ForeignKeyConstraint(
            ["organisation_id", "subscription_id"],
            ["billing_subscriptions.organisation_id", "billing_subscriptions.id"],
            name="fk_billing_invoices_subscription",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organisation_id", "id", name="uq_billing_invoices_org_id"),
        sa.UniqueConstraint("organisation_id", "provider_invoice_id", name="uq_billing_invoices_provider_id"),
    )
    op.create_index(
        "ix_billing_invoices_org_date", "billing_invoice_projections", ["organisation_id", "invoice_date", "id"]
    )
    op.create_table(
        "billing_operations",
        sa.Column("id", uuid_type, nullable=False),
        sa.Column("organisation_id", uuid_type, nullable=False),
        sa.Column("requested_by_user_id", uuid_type, nullable=False),
        sa.Column("operation_type", sa.String(length=24), nullable=False),
        sa.Column("idempotency_key", sa.String(length=200), nullable=False),
        sa.Column("request_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("plan_version_id", uuid_type, nullable=True),
        sa.Column("billing_interval", sa.String(length=12), nullable=True),
        sa.Column("amount", sa.Numeric(12, 2), nullable=True),
        sa.Column("currency", sa.String(length=3), nullable=True),
        sa.Column("provider_object_id", sa.String(length=255), nullable=True),
        sa.Column("hosted_url", sa.String(length=2048), nullable=True),
        sa.Column("safe_error_code", sa.String(length=100), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "operation_type IN ('checkout', 'portal', 'cancel', 'reactivate', 'plan_change', 'credit_purchase')",
            name="ck_billing_operations_type",
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'succeeded', 'failed', 'unknown')", name="ck_billing_operations_status"
        ),
        sa.CheckConstraint(
            "billing_interval IS NULL OR billing_interval IN ('monthly', 'annual')",
            name="ck_billing_operations_interval",
        ),
        sa.CheckConstraint("currency IS NULL OR currency = 'AUD'", name="ck_billing_operations_currency"),
        sa.CheckConstraint("amount IS NULL OR amount >= 0", name="ck_billing_operations_amount"),
        sa.CheckConstraint("length(request_fingerprint) = 64", name="ck_billing_operations_fingerprint"),
        sa.ForeignKeyConstraint(["organisation_id"], ["organisations.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["organisation_id", "requested_by_user_id"],
            ["organisation_memberships.organisation_id", "organisation_memberships.user_id"],
            name="fk_billing_operations_requester",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(["plan_version_id"], ["commercial_plan_versions.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organisation_id", "operation_type", "idempotency_key", name="uq_billing_operations_key"),
        sa.UniqueConstraint("organisation_id", "id", name="uq_billing_operations_org_id"),
    )
    op.create_index("ix_billing_operations_org_created", "billing_operations", ["organisation_id", "created_at", "id"])
    op.create_index(
        "uq_billing_operations_org_unresolved_checkout",
        "billing_operations",
        ["organisation_id"],
        unique=True,
        postgresql_where=sa.text("operation_type = 'checkout' AND status IN ('pending', 'unknown')"),
        sqlite_where=sa.text("operation_type = 'checkout' AND status IN ('pending', 'unknown')"),
    )
    op.create_table(
        "billing_provider_event_receipts",
        sa.Column("id", uuid_type, nullable=False),
        sa.Column("organisation_id", uuid_type, nullable=False),
        sa.Column("provider", sa.String(length=24), nullable=False),
        sa.Column("provider_mode", sa.String(length=12), server_default="test", nullable=False),
        sa.Column("provider_event_id", sa.String(length=255), nullable=False),
        sa.Column("event_type", sa.String(length=120), nullable=False),
        sa.Column("provider_created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("result", sa.String(length=32), nullable=False),
        sa.Column("safe_detail_code", sa.String(length=100), nullable=True),
        sa.Column("received_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("provider IN ('deterministic', 'stripe')", name="ck_billing_receipts_provider"),
        sa.CheckConstraint("provider_mode = 'test'", name="ck_billing_receipts_mode"),
        sa.CheckConstraint(
            "result IN ('processed', 'ignored_stale', 'reconciliation_required')",
            name="ck_billing_receipts_result",
        ),
        sa.ForeignKeyConstraint(["organisation_id"], ["organisations.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("provider", "provider_mode", "provider_event_id", name="uq_billing_receipts_event"),
    )
    op.create_index(
        "ix_billing_receipts_org_received",
        "billing_provider_event_receipts",
        ["organisation_id", "received_at", "id"],
    )
    _create_security()


def downgrade() -> None:
    _drop_security()
    op.drop_index("ix_billing_receipts_org_received", table_name="billing_provider_event_receipts")
    op.drop_table("billing_provider_event_receipts")
    op.drop_index("uq_billing_operations_org_unresolved_checkout", table_name="billing_operations")
    op.drop_index("ix_billing_operations_org_created", table_name="billing_operations")
    op.drop_table("billing_operations")
    op.drop_index("ix_billing_invoices_org_date", table_name="billing_invoice_projections")
    op.drop_table("billing_invoice_projections")
    op.drop_index("ix_billing_subscriptions_org_status", table_name="billing_subscriptions")
    op.drop_table("billing_subscriptions")
    op.drop_table("billing_accounts")
    with op.batch_alter_table("organisation_commercial_states") as batch:
        batch.drop_constraint("ck_commercial_states_source", type_="check")
        batch.create_check_constraint(
            "ck_commercial_states_source",
            "source IN ('manual_support', 'migration')",
        )
