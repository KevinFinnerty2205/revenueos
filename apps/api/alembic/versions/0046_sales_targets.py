"""Add explicit-period sales Targets with immutable revisions.

Revision ID: 0046_sales_targets
Revises: 0045_sales_analytics
Create Date: 2026-08-30
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0046_sales_targets"
down_revision: str | None = "0045_sales_analytics"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TENANT_TABLES = ("sales_targets", "sales_target_revisions")


def _create_identity_index() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute(
            """CREATE UNIQUE INDEX uq_sales_targets_active_identity
            ON sales_targets (
                organisation_id,
                metric_id,
                metric_definition_version,
                scope,
                origin,
                COALESCE(owner_user_id, '00000000-0000-0000-0000-000000000000'::uuid),
                COALESCE(pipeline_id, '00000000-0000-0000-0000-000000000000'::uuid),
                period_start,
                period_end,
                COALESCE(currency, '')
            ) WHERE archived_at IS NULL"""
        )
    else:
        op.execute(
            """CREATE UNIQUE INDEX uq_sales_targets_active_identity
            ON sales_targets (
                organisation_id,
                metric_id,
                metric_definition_version,
                scope,
                origin,
                IFNULL(owner_user_id, ''),
                IFNULL(pipeline_id, ''),
                period_start,
                period_end,
                IFNULL(currency, '')
            ) WHERE archived_at IS NULL"""
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
        """CREATE FUNCTION protect_sales_target_identity() RETURNS trigger AS $$
        BEGIN
            IF current_setting('app.beta_maintenance', true) = 'approved' THEN
                RETURN NEW;
            END IF;
            IF ROW(
                NEW.id, NEW.organisation_id, NEW.metric_id, NEW.metric_definition_version,
                NEW.scope, NEW.origin, NEW.owner_user_id, NEW.pipeline_id,
                NEW.period_type, NEW.period_start, NEW.period_end, NEW.timezone,
                NEW.currency, NEW.created_by_user_id, NEW.created_at
            ) IS DISTINCT FROM ROW(
                OLD.id, OLD.organisation_id, OLD.metric_id, OLD.metric_definition_version,
                OLD.scope, OLD.origin, OLD.owner_user_id, OLD.pipeline_id,
                OLD.period_type, OLD.period_start, OLD.period_end, OLD.timezone,
                OLD.currency, OLD.created_by_user_id, OLD.created_at
            ) THEN
                RAISE EXCEPTION 'sales target identity is immutable';
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql"""
    )
    op.execute(
        """CREATE TRIGGER sales_targets_identity_immutable
        BEFORE UPDATE ON sales_targets
        FOR EACH ROW EXECUTE FUNCTION protect_sales_target_identity()"""
    )
    op.execute(
        """CREATE FUNCTION reject_sales_target_revision_mutation() RETURNS trigger AS $$
        BEGIN
            IF current_setting('app.beta_maintenance', true) = 'approved' THEN
                RETURN COALESCE(NEW, OLD);
            END IF;
            RAISE EXCEPTION 'sales target revisions are immutable';
        END;
        $$ LANGUAGE plpgsql"""
    )
    op.execute(
        """CREATE TRIGGER sales_target_revisions_immutable
        BEFORE UPDATE OR DELETE ON sales_target_revisions
        FOR EACH ROW EXECUTE FUNCTION reject_sales_target_revision_mutation()"""
    )


def upgrade() -> None:
    uuid_type = sa.Uuid(as_uuid=True)
    with op.batch_alter_table("organisations") as batch:
        batch.add_column(sa.Column("timezone", sa.String(length=64), server_default="UTC", nullable=False))
        batch.create_check_constraint(
            "ck_organisations_timezone",
            "length(trim(timezone)) BETWEEN 1 AND 64",
        )
    op.create_table(
        "sales_targets",
        sa.Column("id", uuid_type, nullable=False),
        sa.Column("organisation_id", uuid_type, nullable=False),
        sa.Column("metric_id", sa.String(length=80), nullable=False),
        sa.Column("metric_definition_version", sa.String(length=20), nullable=False),
        sa.Column("scope", sa.String(length=20), nullable=False),
        sa.Column("origin", sa.String(length=24), nullable=False),
        sa.Column("owner_user_id", uuid_type, nullable=True),
        sa.Column("pipeline_id", uuid_type, nullable=True),
        sa.Column("period_type", sa.String(length=12), nullable=False),
        sa.Column("period_start", sa.Date(), nullable=False),
        sa.Column("period_end", sa.Date(), nullable=False),
        sa.Column("timezone", sa.String(length=64), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=True),
        sa.Column("created_by_user_id", uuid_type, nullable=False),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("scope IN ('personal', 'organisation')", name="ck_sales_targets_scope"),
        sa.CheckConstraint("origin IN ('self_set', 'admin_assigned')", name="ck_sales_targets_origin"),
        sa.CheckConstraint("period_type IN ('month', 'quarter', 'year')", name="ck_sales_targets_period_type"),
        sa.CheckConstraint("period_end >= period_start", name="ck_sales_targets_period_bounds"),
        sa.CheckConstraint("length(trim(metric_id)) BETWEEN 1 AND 80", name="ck_sales_targets_metric_id"),
        sa.CheckConstraint(
            "length(trim(metric_definition_version)) BETWEEN 1 AND 20",
            name="ck_sales_targets_metric_version",
        ),
        sa.CheckConstraint("length(trim(timezone)) BETWEEN 1 AND 64", name="ck_sales_targets_timezone"),
        sa.CheckConstraint(
            "currency IS NULL OR (length(currency) = 3 AND currency = upper(currency))",
            name="ck_sales_targets_currency",
        ),
        sa.CheckConstraint(
            "(scope = 'personal' AND owner_user_id IS NOT NULL) OR "
            "(scope = 'organisation' AND owner_user_id IS NULL AND origin = 'admin_assigned')",
            name="ck_sales_targets_scope_owner",
        ),
        sa.CheckConstraint(
            "origin <> 'self_set' OR (scope = 'personal' AND owner_user_id = created_by_user_id)",
            name="ck_sales_targets_self_origin",
        ),
        sa.ForeignKeyConstraint(["organisation_id"], ["organisations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["organisation_id", "owner_user_id"],
            ["organisation_memberships.organisation_id", "organisation_memberships.user_id"],
            name="fk_sales_targets_owner_membership",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organisation_id", "pipeline_id"],
            ["sales_pipelines.organisation_id", "sales_pipelines.id"],
            name="fk_sales_targets_pipeline",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organisation_id", "created_by_user_id"],
            ["organisation_memberships.organisation_id", "organisation_memberships.user_id"],
            name="fk_sales_targets_creator_membership",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organisation_id", "id", name="uq_sales_targets_org_id"),
    )
    op.create_index(
        "ix_sales_targets_org_owner_period",
        "sales_targets",
        ["organisation_id", "owner_user_id", "period_end"],
    )
    op.create_index(
        "ix_sales_targets_org_scope_period",
        "sales_targets",
        ["organisation_id", "scope", "period_end"],
    )
    _create_identity_index()
    op.create_table(
        "sales_target_revisions",
        sa.Column("id", uuid_type, nullable=False),
        sa.Column("organisation_id", uuid_type, nullable=False),
        sa.Column("target_id", uuid_type, nullable=False),
        sa.Column("revision_number", sa.Integer(), nullable=False),
        sa.Column("goal_value", sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column("created_by_user_id", uuid_type, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("revision_number >= 1", name="ck_sales_target_revisions_number"),
        sa.CheckConstraint(
            "goal_value > 0 AND goal_value <= 1000000000000000",
            name="ck_sales_target_revisions_goal",
        ),
        sa.ForeignKeyConstraint(["organisation_id"], ["organisations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["organisation_id", "target_id"],
            ["sales_targets.organisation_id", "sales_targets.id"],
            name="fk_sales_target_revisions_target",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["organisation_id", "created_by_user_id"],
            ["organisation_memberships.organisation_id", "organisation_memberships.user_id"],
            name="fk_sales_target_revisions_creator_membership",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organisation_id", "id", name="uq_sales_target_revisions_org_id"),
        sa.UniqueConstraint("target_id", "revision_number", name="uq_sales_target_revisions_target_number"),
    )
    op.create_index(
        "ix_sales_target_revisions_org_target",
        "sales_target_revisions",
        ["organisation_id", "target_id", "revision_number"],
    )
    _enable_tenant_controls()


def downgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        op.execute("DROP TRIGGER sales_target_revisions_immutable ON sales_target_revisions")
        op.execute("DROP FUNCTION reject_sales_target_revision_mutation()")
        op.execute("DROP TRIGGER sales_targets_identity_immutable ON sales_targets")
        op.execute("DROP FUNCTION protect_sales_target_identity()")
    op.drop_index("ix_sales_target_revisions_org_target", table_name="sales_target_revisions")
    op.drop_table("sales_target_revisions")
    op.drop_index("uq_sales_targets_active_identity", table_name="sales_targets")
    op.drop_index("ix_sales_targets_org_scope_period", table_name="sales_targets")
    op.drop_index("ix_sales_targets_org_owner_period", table_name="sales_targets")
    op.drop_table("sales_targets")
    with op.batch_alter_table("organisations") as batch:
        batch.drop_constraint("ck_organisations_timezone", type_="check")
        batch.drop_column("timezone")
