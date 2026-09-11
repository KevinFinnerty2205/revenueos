"""Add mode-isolated live Stripe billing authority.

Revision ID: 0062_live_stripe_billing
Revises: 0061_manual_paid_credit_grant

WO-054B admits explicit live provider mode, isolates operations by mode and
persists current payment/paid-through authority. Existing tenant RLS policies
remain forced and unchanged.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0062_live_stripe_billing"
down_revision: str | None = "0061_manual_paid_credit_grant"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _drop_sqlite_receipt_guards() -> None:
    if op.get_bind().dialect.name == "sqlite":
        for operation in ("update", "delete"):
            op.execute(f"DROP TRIGGER IF EXISTS billing_provider_event_receipts_immutable_{operation}")


def _create_sqlite_receipt_guards() -> None:
    if op.get_bind().dialect.name == "sqlite":
        for operation in ("UPDATE", "DELETE"):
            op.execute(
                f"""CREATE TRIGGER billing_provider_event_receipts_immutable_{operation.lower()}
                BEFORE {operation} ON billing_provider_event_receipts
                BEGIN SELECT RAISE(ABORT, 'billing provider receipts are immutable'); END"""
            )


def upgrade() -> None:
    with op.batch_alter_table("billing_accounts") as batch:
        batch.drop_constraint("ck_billing_accounts_mode", type_="check")
        batch.create_check_constraint("ck_billing_accounts_mode", "provider_mode IN ('test', 'live')")
        batch.create_check_constraint(
            "ck_billing_accounts_provider_mode",
            "provider = 'stripe' OR provider_mode = 'test'",
        )

    with op.batch_alter_table("billing_subscriptions") as batch:
        batch.add_column(sa.Column("payment_status", sa.String(length=16), server_default="pending", nullable=False))
        batch.add_column(sa.Column("paid_period_start", sa.DateTime(timezone=True), nullable=True))
        batch.add_column(sa.Column("paid_through", sa.DateTime(timezone=True), nullable=True))
        batch.create_check_constraint(
            "ck_billing_subscriptions_payment_status",
            "payment_status IN ('pending', 'paid', 'failed')",
        )
        batch.create_check_constraint(
            "ck_billing_subscriptions_paid_period",
            "(paid_period_start IS NULL AND paid_through IS NULL) OR "
            "(paid_period_start IS NOT NULL AND paid_through IS NOT NULL AND paid_through > paid_period_start)",
        )
    op.create_index(
        "uq_billing_subscriptions_account_current",
        "billing_subscriptions",
        ["billing_account_id"],
        unique=True,
        postgresql_where=sa.text("status != 'cancelled'"),
        sqlite_where=sa.text("status != 'cancelled'"),
    )

    with op.batch_alter_table("billing_invoice_projections") as batch:
        batch.drop_constraint("uq_billing_invoices_provider_id", type_="unique")
        batch.create_unique_constraint(
            "uq_billing_invoices_provider_id",
            ["subscription_id", "provider_invoice_id"],
        )

    op.drop_index("uq_billing_operations_org_unresolved_checkout", table_name="billing_operations")
    with op.batch_alter_table("billing_operations") as batch:
        batch.drop_constraint("uq_billing_operations_key", type_="unique")
        batch.add_column(sa.Column("provider_mode", sa.String(length=12), server_default="test", nullable=False))
        batch.create_check_constraint("ck_billing_operations_mode", "provider_mode IN ('test', 'live')")
        batch.create_unique_constraint(
            "uq_billing_operations_key",
            ["organisation_id", "provider_mode", "operation_type", "idempotency_key"],
        )
    op.create_index(
        "uq_billing_operations_org_unresolved_checkout",
        "billing_operations",
        ["organisation_id", "provider_mode"],
        unique=True,
        postgresql_where=sa.text("operation_type = 'checkout' AND status IN ('pending', 'unknown')"),
        sqlite_where=sa.text("operation_type = 'checkout' AND status IN ('pending', 'unknown')"),
    )

    _drop_sqlite_receipt_guards()
    with op.batch_alter_table("billing_provider_event_receipts") as batch:
        batch.drop_constraint("ck_billing_receipts_mode", type_="check")
        batch.create_check_constraint("ck_billing_receipts_mode", "provider_mode IN ('test', 'live')")
        batch.create_check_constraint(
            "ck_billing_receipts_provider_mode",
            "provider = 'stripe' OR provider_mode = 'test'",
        )
    _create_sqlite_receipt_guards()


def downgrade() -> None:
    connection = op.get_bind()
    live_rows = sum(
        int(connection.execute(sa.text(f"SELECT count(*) FROM {table_name} WHERE provider_mode = 'live'")).scalar_one())
        for table_name in ("billing_accounts", "billing_operations", "billing_provider_event_receipts")
    )
    if live_rows:
        raise RuntimeError("Cannot downgrade live Stripe billing while live-mode billing authority exists.")

    _drop_sqlite_receipt_guards()
    with op.batch_alter_table("billing_provider_event_receipts") as batch:
        batch.drop_constraint("ck_billing_receipts_provider_mode", type_="check")
        batch.drop_constraint("ck_billing_receipts_mode", type_="check")
        batch.create_check_constraint("ck_billing_receipts_mode", "provider_mode = 'test'")
    _create_sqlite_receipt_guards()

    op.drop_index("uq_billing_operations_org_unresolved_checkout", table_name="billing_operations")
    with op.batch_alter_table("billing_operations") as batch:
        batch.drop_constraint("uq_billing_operations_key", type_="unique")
        batch.drop_constraint("ck_billing_operations_mode", type_="check")
        batch.create_unique_constraint(
            "uq_billing_operations_key",
            ["organisation_id", "operation_type", "idempotency_key"],
        )
        batch.drop_column("provider_mode")
    op.create_index(
        "uq_billing_operations_org_unresolved_checkout",
        "billing_operations",
        ["organisation_id"],
        unique=True,
        postgresql_where=sa.text("operation_type = 'checkout' AND status IN ('pending', 'unknown')"),
        sqlite_where=sa.text("operation_type = 'checkout' AND status IN ('pending', 'unknown')"),
    )

    with op.batch_alter_table("billing_invoice_projections") as batch:
        batch.drop_constraint("uq_billing_invoices_provider_id", type_="unique")
        batch.create_unique_constraint(
            "uq_billing_invoices_provider_id",
            ["organisation_id", "provider_invoice_id"],
        )

    op.drop_index("uq_billing_subscriptions_account_current", table_name="billing_subscriptions")
    with op.batch_alter_table("billing_subscriptions") as batch:
        batch.drop_constraint("ck_billing_subscriptions_paid_period", type_="check")
        batch.drop_constraint("ck_billing_subscriptions_payment_status", type_="check")
        batch.drop_column("paid_through")
        batch.drop_column("paid_period_start")
        batch.drop_column("payment_status")

    with op.batch_alter_table("billing_accounts") as batch:
        batch.drop_constraint("ck_billing_accounts_provider_mode", type_="check")
        batch.drop_constraint("ck_billing_accounts_mode", type_="check")
        batch.create_check_constraint("ck_billing_accounts_mode", "provider_mode = 'test'")
