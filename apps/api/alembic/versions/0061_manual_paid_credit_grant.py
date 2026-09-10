"""Add immutable manual paid Credit grants.

Revision ID: 0061_manual_paid_credit_grant
Revises: 0060_closed_won_handover

WO-055 records only completed exceptional purchases after an authorised internal
operator confirms cleared funds. The record is tenant isolated and immutable; it
references the existing purchased lot and ledger rather than introducing another
balance or invoice lifecycle.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0061_manual_paid_credit_grant"
down_revision: str | None = "0060_closed_won_handover"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLE_NAME = "manual_paid_credit_grants"


def _create_security() -> None:
    dialect = op.get_bind().dialect.name
    if dialect == "postgresql":
        op.execute(f"ALTER TABLE {TABLE_NAME} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {TABLE_NAME} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"""CREATE POLICY {TABLE_NAME}_tenant_isolation
            ON {TABLE_NAME}
            USING (organisation_id = NULLIF(current_setting('app.organisation_id', true), '')::uuid)
            WITH CHECK (organisation_id = NULLIF(current_setting('app.organisation_id', true), '')::uuid)"""
        )
        op.execute(
            f"""CREATE TRIGGER {TABLE_NAME}_immutable
            BEFORE UPDATE OR DELETE ON {TABLE_NAME}
            FOR EACH ROW EXECUTE FUNCTION public.revenueos_reject_credit_history_mutation()"""
        )
    elif dialect == "sqlite":
        for operation in ("UPDATE", "DELETE"):
            op.execute(
                f"""CREATE TRIGGER {TABLE_NAME}_immutable_{operation.lower()}
                BEFORE {operation} ON {TABLE_NAME}
                BEGIN SELECT RAISE(ABORT, 'Manual paid Credit grants are immutable'); END"""
            )


def _drop_security() -> None:
    dialect = op.get_bind().dialect.name
    if dialect == "postgresql":
        op.execute(f"DROP TRIGGER IF EXISTS {TABLE_NAME}_immutable ON {TABLE_NAME}")
        op.execute(f"DROP POLICY IF EXISTS {TABLE_NAME}_tenant_isolation ON {TABLE_NAME}")
    elif dialect == "sqlite":
        for operation in ("update", "delete"):
            op.execute(f"DROP TRIGGER IF EXISTS {TABLE_NAME}_immutable_{operation}")


def upgrade() -> None:
    uuid_type = sa.Uuid(as_uuid=True)
    op.create_table(
        TABLE_NAME,
        sa.Column("id", uuid_type, nullable=False),
        sa.Column("organisation_id", uuid_type, nullable=False),
        sa.Column("credit_lot_id", uuid_type, nullable=False),
        sa.Column("status", sa.String(length=16), server_default="completed", nullable=False),
        sa.Column("credits_granted", sa.BigInteger(), nullable=False),
        sa.Column("amount_received_minor_units", sa.BigInteger(), nullable=False),
        sa.Column("currency", sa.String(length=3), server_default="AUD", nullable=False),
        sa.Column("payment_method", sa.String(length=32), nullable=False),
        sa.Column("payment_reference", sa.String(length=120), nullable=False),
        sa.Column("payment_reference_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("payment_received_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("cleared_funds_confirmed", sa.Boolean(), nullable=False),
        sa.Column("operator_reference", sa.String(length=200), nullable=False),
        sa.Column("reason", sa.String(length=500), nullable=False),
        sa.Column("idempotency_key_hash", sa.String(length=64), nullable=False),
        sa.Column("request_fingerprint", sa.String(length=64), nullable=False),
        sa.Column(
            "margin_review_status",
            sa.String(length=64),
            server_default="production_execution_blocked_pending_policy",
            nullable=False,
        ),
        sa.Column("granted_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("status = 'completed'", name="ck_manual_paid_credit_grants_status"),
        sa.CheckConstraint(
            "credits_granted > 0 AND credits_granted <= 9000000000000",
            name="ck_manual_paid_credit_grants_credits",
        ),
        sa.CheckConstraint(
            "amount_received_minor_units > 0 AND amount_received_minor_units <= 9000000000000",
            name="ck_manual_paid_credit_grants_amount",
        ),
        sa.CheckConstraint("currency = 'AUD'", name="ck_manual_paid_credit_grants_currency"),
        sa.CheckConstraint(
            "payment_method IN ('BANK_TRANSFER', 'CARD_OUTSIDE_AUTOMATIC_FLOW', 'OTHER_APPROVED')",
            name="ck_manual_paid_credit_grants_payment_method",
        ),
        sa.CheckConstraint(
            "length(trim(payment_reference)) BETWEEN 1 AND 120",
            name="ck_manual_paid_credit_grants_reference",
        ),
        sa.CheckConstraint(
            "length(payment_reference_fingerprint) = 64 "
            "AND payment_reference_fingerprint = lower(payment_reference_fingerprint)",
            name="ck_manual_paid_credit_grants_reference_fingerprint",
        ),
        sa.CheckConstraint(
            "length(idempotency_key_hash) = 64 AND idempotency_key_hash = lower(idempotency_key_hash)",
            name="ck_manual_paid_credit_grants_idempotency_key",
        ),
        sa.CheckConstraint(
            "length(request_fingerprint) = 64 AND request_fingerprint = lower(request_fingerprint)",
            name="ck_manual_paid_credit_grants_request_fingerprint",
        ),
        sa.CheckConstraint("cleared_funds_confirmed", name="ck_manual_paid_credit_grants_cleared_funds"),
        sa.CheckConstraint(
            "length(trim(operator_reference)) BETWEEN 1 AND 200",
            name="ck_manual_paid_credit_grants_operator",
        ),
        sa.CheckConstraint(
            "length(trim(reason)) BETWEEN 8 AND 500",
            name="ck_manual_paid_credit_grants_reason",
        ),
        sa.CheckConstraint(
            "margin_review_status = 'production_execution_blocked_pending_policy'",
            name="ck_manual_paid_credit_grants_margin_review",
        ),
        sa.ForeignKeyConstraint(["organisation_id"], ["organisations.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["organisation_id", "credit_lot_id"],
            ["credit_lots.organisation_id", "credit_lots.id"],
            name="fk_manual_paid_credit_grants_lot",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organisation_id", "id", name="uq_manual_paid_credit_grants_org_id"),
        sa.UniqueConstraint(
            "organisation_id",
            "idempotency_key_hash",
            name="uq_manual_paid_credit_grants_idempotency",
        ),
        sa.UniqueConstraint(
            "organisation_id",
            "payment_reference_fingerprint",
            name="uq_manual_paid_credit_grants_payment_reference",
        ),
        sa.UniqueConstraint("organisation_id", "credit_lot_id", name="uq_manual_paid_credit_grants_lot"),
    )
    op.create_index(
        "ix_manual_paid_credit_grants_org_granted",
        TABLE_NAME,
        ["organisation_id", "granted_at", "id"],
    )
    _create_security()


def downgrade() -> None:
    _drop_security()
    op.drop_index("ix_manual_paid_credit_grants_org_granted", table_name=TABLE_NAME)
    op.drop_table(TABLE_NAME)
