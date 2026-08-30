"""Add transparent seller forecasting and immutable model snapshots.

Revision ID: 0047_transparent_forecast
Revises: 0046_sales_targets
Create Date: 2026-08-30
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0047_transparent_forecast"
down_revision: str | None = "0046_sales_targets"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TENANT_TABLES = (
    "sales_forecast_periods",
    "sales_forecast_judgments",
    "sales_forecast_judgment_revisions",
)


def _enable_tenant_controls() -> None:
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
    op.execute(
        """CREATE FUNCTION reject_sales_forecast_identity_mutation() RETURNS trigger AS $$
        BEGIN
            IF current_setting('app.beta_maintenance', true) = 'approved' THEN
                RETURN COALESCE(NEW, OLD);
            END IF;
            RAISE EXCEPTION 'sales forecast identities are immutable';
        END;
        $$ LANGUAGE plpgsql"""
    )
    for table_name in ("sales_forecast_periods", "sales_forecast_judgments"):
        op.execute(
            f"""CREATE TRIGGER {table_name}_immutable
            BEFORE UPDATE OR DELETE ON {table_name}
            FOR EACH ROW EXECUTE FUNCTION reject_sales_forecast_identity_mutation()"""
        )
    op.execute(
        """CREATE FUNCTION reject_sales_forecast_revision_mutation() RETURNS trigger AS $$
        BEGIN
            IF current_setting('app.beta_maintenance', true) = 'approved' THEN
                RETURN COALESCE(NEW, OLD);
            END IF;
            RAISE EXCEPTION 'sales forecast judgment revisions are immutable';
        END;
        $$ LANGUAGE plpgsql"""
    )
    op.execute(
        """CREATE TRIGGER sales_forecast_judgment_revisions_immutable
        BEFORE UPDATE OR DELETE ON sales_forecast_judgment_revisions
        FOR EACH ROW EXECUTE FUNCTION reject_sales_forecast_revision_mutation()"""
    )


def upgrade() -> None:
    uuid_type = sa.Uuid(as_uuid=True)
    op.create_table(
        "sales_forecast_periods",
        sa.Column("id", uuid_type, nullable=False),
        sa.Column("organisation_id", uuid_type, nullable=False),
        sa.Column("period_type", sa.String(length=12), nullable=False),
        sa.Column("period_start", sa.Date(), nullable=False),
        sa.Column("period_end", sa.Date(), nullable=False),
        sa.Column("timezone", sa.String(length=64), nullable=False),
        sa.Column("created_by_user_id", uuid_type, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("period_type IN ('month', 'quarter')", name="ck_sales_forecast_periods_type"),
        sa.CheckConstraint("period_end >= period_start", name="ck_sales_forecast_periods_bounds"),
        sa.CheckConstraint(
            "length(trim(timezone)) BETWEEN 1 AND 64",
            name="ck_sales_forecast_periods_timezone",
        ),
        sa.ForeignKeyConstraint(["organisation_id"], ["organisations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["organisation_id", "created_by_user_id"],
            ["organisation_memberships.organisation_id", "organisation_memberships.user_id"],
            name="fk_sales_forecast_periods_creator_membership",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organisation_id", "id", name="uq_sales_forecast_periods_org_id"),
        sa.UniqueConstraint(
            "organisation_id",
            "period_type",
            "period_start",
            "period_end",
            name="uq_sales_forecast_periods_identity",
        ),
    )
    op.create_index(
        "ix_sales_forecast_periods_org_end",
        "sales_forecast_periods",
        ["organisation_id", "period_type", "period_end"],
    )
    op.create_table(
        "sales_forecast_judgments",
        sa.Column("id", uuid_type, nullable=False),
        sa.Column("organisation_id", uuid_type, nullable=False),
        sa.Column("period_id", uuid_type, nullable=False),
        sa.Column("opportunity_id", uuid_type, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["organisation_id"], ["organisations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["organisation_id", "period_id"],
            ["sales_forecast_periods.organisation_id", "sales_forecast_periods.id"],
            name="fk_sales_forecast_judgments_period",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["organisation_id", "opportunity_id"],
            ["opportunities.organisation_id", "opportunities.id"],
            name="fk_sales_forecast_judgments_opportunity",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organisation_id", "id", name="uq_sales_forecast_judgments_org_id"),
        sa.UniqueConstraint(
            "organisation_id",
            "period_id",
            "opportunity_id",
            name="uq_sales_forecast_judgments_identity",
        ),
    )
    op.create_index(
        "ix_sales_forecast_judgments_org_period",
        "sales_forecast_judgments",
        ["organisation_id", "period_id", "opportunity_id"],
    )
    op.create_table(
        "sales_forecast_judgment_revisions",
        sa.Column("id", uuid_type, nullable=False),
        sa.Column("organisation_id", uuid_type, nullable=False),
        sa.Column("judgment_id", uuid_type, nullable=False),
        sa.Column("revision_number", sa.Integer(), nullable=False),
        sa.Column("category", sa.String(length=24), nullable=False),
        sa.Column("created_by_user_id", uuid_type, nullable=False),
        sa.Column("owner_user_id_snapshot", uuid_type, nullable=False),
        sa.Column("amount_snapshot", sa.Numeric(precision=18, scale=2), nullable=True),
        sa.Column("currency_snapshot", sa.String(length=3), nullable=True),
        sa.Column("expected_close_date_snapshot", sa.Date(), nullable=False),
        sa.Column("pipeline_id_snapshot", uuid_type, nullable=False),
        sa.Column("pipeline_name_snapshot", sa.String(length=100), nullable=False),
        sa.Column("stage_id_snapshot", uuid_type, nullable=False),
        sa.Column("stage_name_snapshot", sa.String(length=100), nullable=False),
        sa.Column("opportunity_status_snapshot", sa.String(length=20), nullable=False),
        sa.Column("model_version", sa.String(length=80), nullable=False),
        sa.Column("model_status", sa.String(length=24), nullable=False),
        sa.Column("model_won_count", sa.Integer(), nullable=False),
        sa.Column("model_lost_count", sa.Integer(), nullable=False),
        sa.Column("model_minimum_sample", sa.Integer(), nullable=False),
        sa.Column("model_lookback_start", sa.Date(), nullable=False),
        sa.Column("model_lookback_end", sa.Date(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("revision_number >= 1", name="ck_sales_forecast_revisions_number"),
        sa.CheckConstraint(
            "category IN ('commit', 'likely', 'possible', 'not_this_period')",
            name="ck_sales_forecast_revisions_category",
        ),
        sa.CheckConstraint(
            "(amount_snapshot IS NULL AND currency_snapshot IS NULL) OR "
            "(amount_snapshot IS NOT NULL AND amount_snapshot >= 0 AND currency_snapshot IS NOT NULL)",
            name="ck_sales_forecast_revisions_value_currency",
        ),
        sa.CheckConstraint(
            "currency_snapshot IS NULL OR "
            "(length(currency_snapshot) = 3 AND currency_snapshot = upper(currency_snapshot))",
            name="ck_sales_forecast_revisions_currency",
        ),
        sa.CheckConstraint(
            "opportunity_status_snapshot IN ('open', 'on_hold')",
            name="ck_sales_forecast_revisions_opportunity_status",
        ),
        sa.CheckConstraint(
            "model_status IN ('available', 'insufficient_sample', 'unavailable_stage')",
            name="ck_sales_forecast_revisions_model_status",
        ),
        sa.CheckConstraint("model_won_count >= 0", name="ck_sales_forecast_revisions_won_count"),
        sa.CheckConstraint("model_lost_count >= 0", name="ck_sales_forecast_revisions_lost_count"),
        sa.CheckConstraint("model_minimum_sample >= 1", name="ck_sales_forecast_revisions_minimum_sample"),
        sa.CheckConstraint(
            "model_lookback_end >= model_lookback_start",
            name="ck_sales_forecast_revisions_lookback",
        ),
        sa.CheckConstraint(
            "length(trim(model_version)) BETWEEN 1 AND 80",
            name="ck_sales_forecast_revisions_model_version",
        ),
        sa.ForeignKeyConstraint(["organisation_id"], ["organisations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["organisation_id", "judgment_id"],
            ["sales_forecast_judgments.organisation_id", "sales_forecast_judgments.id"],
            name="fk_sales_forecast_revisions_judgment",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["organisation_id", "created_by_user_id"],
            ["organisation_memberships.organisation_id", "organisation_memberships.user_id"],
            name="fk_sales_forecast_revisions_creator_membership",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organisation_id", "owner_user_id_snapshot"],
            ["organisation_memberships.organisation_id", "organisation_memberships.user_id"],
            name="fk_sales_forecast_revisions_owner_membership",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organisation_id", "pipeline_id_snapshot"],
            ["sales_pipelines.organisation_id", "sales_pipelines.id"],
            name="fk_sales_forecast_revisions_pipeline",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organisation_id", "pipeline_id_snapshot", "stage_id_snapshot"],
            [
                "sales_pipeline_stages.organisation_id",
                "sales_pipeline_stages.pipeline_id",
                "sales_pipeline_stages.id",
            ],
            name="fk_sales_forecast_revisions_stage",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organisation_id", "id", name="uq_sales_forecast_revisions_org_id"),
        sa.UniqueConstraint(
            "judgment_id",
            "revision_number",
            name="uq_sales_forecast_revisions_judgment_number",
        ),
    )
    op.create_index(
        "ix_sales_forecast_revisions_org_judgment",
        "sales_forecast_judgment_revisions",
        ["organisation_id", "judgment_id", "revision_number"],
    )
    op.create_index(
        "ix_sales_forecast_revisions_org_created",
        "sales_forecast_judgment_revisions",
        ["organisation_id", "created_at"],
    )
    _enable_tenant_controls()


def downgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        op.execute("DROP TRIGGER sales_forecast_judgment_revisions_immutable ON sales_forecast_judgment_revisions")
        op.execute("DROP FUNCTION reject_sales_forecast_revision_mutation()")
        op.execute("DROP TRIGGER sales_forecast_judgments_immutable ON sales_forecast_judgments")
        op.execute("DROP TRIGGER sales_forecast_periods_immutable ON sales_forecast_periods")
        op.execute("DROP FUNCTION reject_sales_forecast_identity_mutation()")
    op.drop_index(
        "ix_sales_forecast_revisions_org_created",
        table_name="sales_forecast_judgment_revisions",
    )
    op.drop_index(
        "ix_sales_forecast_revisions_org_judgment",
        table_name="sales_forecast_judgment_revisions",
    )
    op.drop_table("sales_forecast_judgment_revisions")
    op.drop_index(
        "ix_sales_forecast_judgments_org_period",
        table_name="sales_forecast_judgments",
    )
    op.drop_table("sales_forecast_judgments")
    op.drop_index("ix_sales_forecast_periods_org_end", table_name="sales_forecast_periods")
    op.drop_table("sales_forecast_periods")
