"""Add immutable tenant-owned Revenue Brain longitudinal insights.

Revision ID: 0019_revenue_brain_reasoning
Revises: 0018_revenue_brain
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0019_revenue_brain_reasoning"
down_revision: str | None = "0018_revenue_brain"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _enable_tenant_rls() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return
    op.execute("ALTER TABLE revenue_brain_insights ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE revenue_brain_insights FORCE ROW LEVEL SECURITY")
    op.execute(
        """CREATE POLICY revenue_brain_insights_tenant_isolation
        ON revenue_brain_insights
        USING (organisation_id = NULLIF(current_setting('app.organisation_id', true), '')::uuid)
        WITH CHECK (organisation_id = NULLIF(current_setting('app.organisation_id', true), '')::uuid)"""
    )


def _create_immutability_guard() -> None:
    dialect = op.get_bind().dialect.name
    if dialect == "postgresql":
        op.execute(
            """
            CREATE FUNCTION prevent_revenue_brain_insight_mutation()
            RETURNS trigger
            LANGUAGE plpgsql
            AS $$
            BEGIN
                RAISE EXCEPTION 'Revenue Brain insights are append only';
            END;
            $$
            """
        )
        op.execute(
            """
            CREATE TRIGGER revenue_brain_insights_append_only
            BEFORE UPDATE OR DELETE ON revenue_brain_insights
            FOR EACH ROW
            EXECUTE FUNCTION prevent_revenue_brain_insight_mutation()
            """
        )
    elif dialect == "sqlite":
        op.execute(
            """
            CREATE TRIGGER revenue_brain_insights_prevent_update
            BEFORE UPDATE ON revenue_brain_insights
            FOR EACH ROW
            BEGIN
                SELECT RAISE(ABORT, 'Revenue Brain insights are append only');
            END
            """
        )
        op.execute(
            """
            CREATE TRIGGER revenue_brain_insights_prevent_delete
            BEFORE DELETE ON revenue_brain_insights
            FOR EACH ROW
            BEGIN
                SELECT RAISE(ABORT, 'Revenue Brain insights are append only');
            END
            """
        )


def _drop_immutability_guard() -> None:
    dialect = op.get_bind().dialect.name
    if dialect == "postgresql":
        op.execute("DROP TRIGGER revenue_brain_insights_append_only ON revenue_brain_insights")
        op.execute("DROP FUNCTION prevent_revenue_brain_insight_mutation()")
    elif dialect == "sqlite":
        op.execute("DROP TRIGGER revenue_brain_insights_prevent_delete")
        op.execute("DROP TRIGGER revenue_brain_insights_prevent_update")


def upgrade() -> None:
    uuid_type = sa.Uuid(as_uuid=True)
    op.create_table(
        "revenue_brain_insights",
        sa.Column("id", uuid_type, nullable=False),
        sa.Column("organisation_id", uuid_type, nullable=False),
        sa.Column("company_id", uuid_type, nullable=False),
        sa.Column("opportunity_id", uuid_type, nullable=True),
        sa.Column("scope", sa.String(length=20), nullable=False),
        sa.Column("scope_target_id", uuid_type, nullable=False),
        sa.Column("from_snapshot_id", uuid_type, nullable=False),
        sa.Column("to_snapshot_id", uuid_type, nullable=False),
        sa.Column("reasoning_version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("status", sa.String(length=20), server_default="completed", nullable=False),
        sa.Column("content_json", sa.JSON(none_as_null=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "scope IN ('account', 'opportunity')",
            name="ck_revenue_brain_insights_scope",
        ),
        sa.CheckConstraint(
            "status = 'completed'",
            name="ck_revenue_brain_insights_status",
        ),
        sa.CheckConstraint(
            "reasoning_version > 0",
            name="ck_revenue_brain_insights_reasoning_version",
        ),
        sa.CheckConstraint(
            "from_snapshot_id <> to_snapshot_id",
            name="ck_revenue_brain_insights_distinct_snapshots",
        ),
        sa.CheckConstraint(
            "(scope = 'account' AND opportunity_id IS NULL AND scope_target_id = company_id) "
            "OR (scope = 'opportunity' AND opportunity_id IS NOT NULL "
            "AND scope_target_id = opportunity_id)",
            name="ck_revenue_brain_insights_scope_target",
        ),
        sa.ForeignKeyConstraint(
            ["organisation_id"],
            ["organisations.id"],
            name="fk_revenue_brain_insights_organisation",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["organisation_id", "company_id"],
            ["companies.organisation_id", "companies.id"],
            name="fk_revenue_brain_insights_company_tenant",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organisation_id", "opportunity_id"],
            ["opportunities.organisation_id", "opportunities.id"],
            name="fk_revenue_brain_insights_opportunity_tenant",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organisation_id", "from_snapshot_id"],
            ["revenue_brain_snapshots.organisation_id", "revenue_brain_snapshots.id"],
            name="fk_revenue_brain_insights_from_snapshot_tenant",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organisation_id", "to_snapshot_id"],
            ["revenue_brain_snapshots.organisation_id", "revenue_brain_snapshots.id"],
            name="fk_revenue_brain_insights_to_snapshot_tenant",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organisation_id",
            "id",
            name="uq_revenue_brain_insights_organisation_id_id",
        ),
        sa.UniqueConstraint(
            "organisation_id",
            "scope",
            "scope_target_id",
            "from_snapshot_id",
            "to_snapshot_id",
            "reasoning_version",
            name="uq_revenue_brain_insights_comparison_version",
        ),
    )
    op.create_index(
        "ix_revenue_brain_insights_organisation_company_created",
        "revenue_brain_insights",
        ["organisation_id", "company_id", "created_at"],
    )
    op.create_index(
        "ix_revenue_brain_insights_organisation_opportunity_created",
        "revenue_brain_insights",
        ["organisation_id", "opportunity_id", "created_at"],
    )
    _create_immutability_guard()
    _enable_tenant_rls()


def downgrade() -> None:
    _drop_immutability_guard()
    op.drop_table("revenue_brain_insights")
