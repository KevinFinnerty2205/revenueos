"""Add deterministic ROI and Business Case Builder.

Revision ID: 0042_roi_business_case
Revises: 0041_create_studio

WO-033 adds immutable approved value-model versions and Account-bound calculation
snapshots. Formula definitions are validated application data, never executable code.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0042_roi_business_case"
down_revision: str | None = "0041_create_studio"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TENANT_TABLES = (
    "create_value_models",
    "create_value_model_versions",
    "create_business_cases",
    "create_business_case_versions",
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


def _create_immutability_guards() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return
    op.execute(
        """
        CREATE FUNCTION public.revenueos_protect_value_model_version()
        RETURNS trigger
        LANGUAGE plpgsql
        SET search_path = pg_catalog, public
        AS $$
        BEGIN
            IF OLD.state IN ('approved', 'archived') THEN
                RAISE EXCEPTION 'approved value model versions are immutable';
            END IF;
            RETURN NEW;
        END;
        $$
        """
    )
    op.execute(
        """
        CREATE TRIGGER protect_create_value_model_version
        BEFORE UPDATE ON create_value_model_versions
        FOR EACH ROW EXECUTE FUNCTION public.revenueos_protect_value_model_version()
        """
    )
    op.execute(
        """
        CREATE FUNCTION public.revenueos_protect_business_case_version()
        RETURNS trigger
        LANGUAGE plpgsql
        SET search_path = pg_catalog, public
        AS $$
        BEGIN
            IF OLD.review_state = 'approved' THEN
                RAISE EXCEPTION 'approved business case versions are immutable';
            END IF;
            RETURN NEW;
        END;
        $$
        """
    )
    op.execute(
        """
        CREATE TRIGGER protect_create_business_case_version
        BEFORE UPDATE ON create_business_case_versions
        FOR EACH ROW EXECUTE FUNCTION public.revenueos_protect_business_case_version()
        """
    )


def upgrade() -> None:
    uuid_type = sa.Uuid(as_uuid=True)
    op.create_table(
        "create_value_models",
        sa.Column("id", uuid_type, nullable=False),
        sa.Column("organisation_id", uuid_type, nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("description", sa.String(length=800), nullable=False),
        sa.Column("state", sa.String(length=20), server_default="active", nullable=False),
        sa.Column("created_by_user_id", uuid_type, nullable=False),
        sa.Column("idempotency_key", sa.String(length=200), nullable=False),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("length(trim(name)) BETWEEN 1 AND 200", name="ck_create_value_models_name"),
        sa.CheckConstraint("length(trim(description)) BETWEEN 1 AND 800", name="ck_create_value_models_description"),
        sa.CheckConstraint("state IN ('active', 'archived')", name="ck_create_value_models_state"),
        sa.ForeignKeyConstraint(["organisation_id"], ["organisations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["organisation_id", "created_by_user_id"],
            ["organisation_memberships.organisation_id", "organisation_memberships.user_id"],
            name="fk_create_value_models_creator",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organisation_id", "id", name="uq_create_value_models_org_id"),
        sa.UniqueConstraint("organisation_id", "name", name="uq_create_value_models_org_name"),
        sa.UniqueConstraint(
            "organisation_id", "created_by_user_id", "idempotency_key", name="uq_create_value_models_idempotency"
        ),
    )
    op.create_index(
        "ix_create_value_models_org_state", "create_value_models", ["organisation_id", "state", "updated_at"]
    )

    op.create_table(
        "create_value_model_versions",
        sa.Column("id", uuid_type, nullable=False),
        sa.Column("organisation_id", uuid_type, nullable=False),
        sa.Column("model_id", uuid_type, nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("state", sa.String(length=20), server_default="draft", nullable=False),
        sa.Column("definition_json", sa.JSON(), nullable=False),
        sa.Column("canonical_ast_json", sa.JSON(), nullable=False),
        sa.Column("formula_engine_version", sa.String(length=40), server_default="bounded_decimal_v1", nullable=False),
        sa.Column("fingerprint", sa.String(length=64), nullable=False),
        sa.Column("created_by_user_id", uuid_type, nullable=False),
        sa.Column("approved_by_user_id", uuid_type, nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("idempotency_key", sa.String(length=200), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("version > 0", name="ck_create_value_model_versions_number"),
        sa.CheckConstraint("state IN ('draft', 'approved', 'archived')", name="ck_create_value_model_versions_state"),
        sa.CheckConstraint(
            "formula_engine_version = 'bounded_decimal_v1'", name="ck_create_value_model_versions_engine"
        ),
        sa.CheckConstraint("length(fingerprint) = 64", name="ck_create_value_model_versions_fingerprint"),
        sa.ForeignKeyConstraint(["organisation_id"], ["organisations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["organisation_id", "model_id"],
            ["create_value_models.organisation_id", "create_value_models.id"],
            name="fk_create_value_model_versions_model",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["organisation_id", "created_by_user_id"],
            ["organisation_memberships.organisation_id", "organisation_memberships.user_id"],
            name="fk_create_value_model_versions_creator",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organisation_id", "approved_by_user_id"],
            ["organisation_memberships.organisation_id", "organisation_memberships.user_id"],
            name="fk_create_value_model_versions_approver",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organisation_id", "id", name="uq_create_value_model_versions_org_id"),
        sa.UniqueConstraint("organisation_id", "id", "model_id", name="uq_create_value_model_versions_org_id_model"),
        sa.UniqueConstraint("organisation_id", "model_id", "version", name="uq_create_value_model_versions_number"),
        sa.UniqueConstraint(
            "organisation_id", "model_id", "idempotency_key", name="uq_create_value_model_versions_idempotency"
        ),
    )
    op.create_index(
        "ix_create_value_model_versions_org_model",
        "create_value_model_versions",
        ["organisation_id", "model_id", "version"],
    )
    op.create_index(
        "ix_create_value_model_versions_org_state",
        "create_value_model_versions",
        ["organisation_id", "state", "created_at"],
    )

    op.create_table(
        "create_business_cases",
        sa.Column("id", uuid_type, nullable=False),
        sa.Column("organisation_id", uuid_type, nullable=False),
        sa.Column("account_id", uuid_type, nullable=False),
        sa.Column("opportunity_id", uuid_type, nullable=True),
        sa.Column("model_id", uuid_type, nullable=False),
        sa.Column("model_version_id", uuid_type, nullable=False),
        sa.Column("created_by_user_id", uuid_type, nullable=False),
        sa.Column("title", sa.String(length=240), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("state", sa.String(length=24), server_default="draft", nullable=False),
        sa.Column("idempotency_key", sa.String(length=200), nullable=False),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("length(trim(title)) BETWEEN 1 AND 240", name="ck_create_business_cases_title"),
        sa.CheckConstraint(
            "state IN ('draft', 'calculated', 'needs_review', 'approved', 'archived')",
            name="ck_create_business_cases_state",
        ),
        sa.CheckConstraint(
            "length(currency) = 3 AND currency = upper(currency)", name="ck_create_business_cases_currency"
        ),
        sa.ForeignKeyConstraint(["organisation_id"], ["organisations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["organisation_id", "account_id"],
            ["companies.organisation_id", "companies.id"],
            name="fk_create_business_cases_account",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organisation_id", "opportunity_id"],
            ["opportunities.organisation_id", "opportunities.id"],
            name="fk_create_business_cases_opportunity",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organisation_id", "model_id"],
            ["create_value_models.organisation_id", "create_value_models.id"],
            name="fk_create_business_cases_model",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organisation_id", "model_version_id", "model_id"],
            [
                "create_value_model_versions.organisation_id",
                "create_value_model_versions.id",
                "create_value_model_versions.model_id",
            ],
            name="fk_create_business_cases_model_version",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organisation_id", "created_by_user_id"],
            ["organisation_memberships.organisation_id", "organisation_memberships.user_id"],
            name="fk_create_business_cases_creator",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organisation_id", "id", name="uq_create_business_cases_org_id"),
        sa.UniqueConstraint(
            "organisation_id", "created_by_user_id", "idempotency_key", name="uq_create_business_cases_idempotency"
        ),
    )
    op.create_index(
        "ix_create_business_cases_org_account",
        "create_business_cases",
        ["organisation_id", "account_id", "updated_at"],
    )
    op.create_index(
        "ix_create_business_cases_org_opportunity",
        "create_business_cases",
        ["organisation_id", "opportunity_id", "updated_at"],
    )
    op.create_index(
        "ix_create_business_cases_org_state",
        "create_business_cases",
        ["organisation_id", "state", "updated_at"],
    )

    op.create_table(
        "create_business_case_versions",
        sa.Column("id", uuid_type, nullable=False),
        sa.Column("organisation_id", uuid_type, nullable=False),
        sa.Column("case_id", uuid_type, nullable=False),
        sa.Column("model_id", uuid_type, nullable=False),
        sa.Column("model_version_id", uuid_type, nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("formula_engine_version", sa.String(length=40), server_default="bounded_decimal_v1", nullable=False),
        sa.Column("model_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("calculation_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("inputs_json", sa.JSON(), nullable=False),
        sa.Column("scenarios_json", sa.JSON(), nullable=False),
        sa.Column("sensitivity_json", sa.JSON(), nullable=True),
        sa.Column("lineage_json", sa.JSON(), nullable=False),
        sa.Column("review_state", sa.String(length=20), server_default="pending", nullable=False),
        sa.Column("created_by_user_id", uuid_type, nullable=False),
        sa.Column("approved_by_user_id", uuid_type, nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("idempotency_key", sa.String(length=200), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("version > 0", name="ck_create_business_case_versions_number"),
        sa.CheckConstraint(
            "review_state IN ('pending', 'approved', 'needs_review')",
            name="ck_create_business_case_versions_review",
        ),
        sa.CheckConstraint(
            "formula_engine_version = 'bounded_decimal_v1'", name="ck_create_business_case_versions_engine"
        ),
        sa.CheckConstraint("length(model_fingerprint) = 64", name="ck_create_business_case_versions_model_hash"),
        sa.CheckConstraint(
            "length(calculation_fingerprint) = 64", name="ck_create_business_case_versions_calculation_hash"
        ),
        sa.CheckConstraint(
            "length(currency) = 3 AND currency = upper(currency)", name="ck_create_business_case_versions_currency"
        ),
        sa.ForeignKeyConstraint(["organisation_id"], ["organisations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["organisation_id", "case_id"],
            ["create_business_cases.organisation_id", "create_business_cases.id"],
            name="fk_create_business_case_versions_case",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["organisation_id", "model_version_id", "model_id"],
            [
                "create_value_model_versions.organisation_id",
                "create_value_model_versions.id",
                "create_value_model_versions.model_id",
            ],
            name="fk_create_business_case_versions_model",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organisation_id", "created_by_user_id"],
            ["organisation_memberships.organisation_id", "organisation_memberships.user_id"],
            name="fk_create_business_case_versions_creator",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organisation_id", "approved_by_user_id"],
            ["organisation_memberships.organisation_id", "organisation_memberships.user_id"],
            name="fk_create_business_case_versions_approver",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organisation_id", "id", name="uq_create_business_case_versions_org_id"),
        sa.UniqueConstraint(
            "organisation_id",
            "id",
            "case_id",
            name="uq_create_business_case_versions_org_id_case",
        ),
        sa.UniqueConstraint("organisation_id", "case_id", "version", name="uq_create_business_case_versions_number"),
        sa.UniqueConstraint(
            "organisation_id", "case_id", "idempotency_key", name="uq_create_business_case_versions_idempotency"
        ),
    )
    op.create_index(
        "ix_create_business_case_versions_org_case",
        "create_business_case_versions",
        ["organisation_id", "case_id", "version"],
    )
    op.create_index(
        "ix_create_business_case_versions_org_model",
        "create_business_case_versions",
        ["organisation_id", "model_version_id"],
    )
    op.create_index(
        "ix_create_business_case_versions_org_review",
        "create_business_case_versions",
        ["organisation_id", "review_state", "created_at"],
    )
    with op.batch_alter_table("create_presentations") as batch_op:
        batch_op.add_column(sa.Column("business_case_id", uuid_type, nullable=True))
        batch_op.add_column(sa.Column("business_case_version_id", uuid_type, nullable=True))
        batch_op.add_column(sa.Column("business_case_scenario", sa.String(length=12), nullable=True))
        batch_op.create_check_constraint(
            "ck_create_presentations_business_case_selection",
            "(business_case_id IS NULL AND business_case_version_id IS NULL AND business_case_scenario IS NULL) "
            "OR (business_case_id IS NOT NULL AND business_case_version_id IS NOT NULL "
            "AND business_case_scenario IN ('base', 'all'))",
        )
        batch_op.create_foreign_key(
            "fk_create_presentations_business_case",
            "create_business_cases",
            ["organisation_id", "business_case_id"],
            ["organisation_id", "id"],
            ondelete="RESTRICT",
        )
        batch_op.create_foreign_key(
            "fk_create_presentations_business_case_version",
            "create_business_case_versions",
            ["organisation_id", "business_case_version_id", "business_case_id"],
            ["organisation_id", "id", "case_id"],
            ondelete="RESTRICT",
        )
    _enable_tenant_rls()
    _create_immutability_guards()


def downgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        op.execute("DROP TRIGGER IF EXISTS protect_create_business_case_version ON create_business_case_versions")
        op.execute("DROP FUNCTION IF EXISTS public.revenueos_protect_business_case_version()")
        op.execute("DROP TRIGGER IF EXISTS protect_create_value_model_version ON create_value_model_versions")
        op.execute("DROP FUNCTION IF EXISTS public.revenueos_protect_value_model_version()")
    with op.batch_alter_table("create_presentations") as batch_op:
        batch_op.drop_constraint("fk_create_presentations_business_case_version", type_="foreignkey")
        batch_op.drop_constraint("fk_create_presentations_business_case", type_="foreignkey")
        batch_op.drop_constraint("ck_create_presentations_business_case_selection", type_="check")
        batch_op.drop_column("business_case_scenario")
        batch_op.drop_column("business_case_version_id")
        batch_op.drop_column("business_case_id")
    op.drop_index("ix_create_business_case_versions_org_review", table_name="create_business_case_versions")
    op.drop_index("ix_create_business_case_versions_org_model", table_name="create_business_case_versions")
    op.drop_index("ix_create_business_case_versions_org_case", table_name="create_business_case_versions")
    op.drop_table("create_business_case_versions")
    op.drop_index("ix_create_business_cases_org_state", table_name="create_business_cases")
    op.drop_index("ix_create_business_cases_org_opportunity", table_name="create_business_cases")
    op.drop_index("ix_create_business_cases_org_account", table_name="create_business_cases")
    op.drop_table("create_business_cases")
    op.drop_index("ix_create_value_model_versions_org_state", table_name="create_value_model_versions")
    op.drop_index("ix_create_value_model_versions_org_model", table_name="create_value_model_versions")
    op.drop_table("create_value_model_versions")
    op.drop_index("ix_create_value_models_org_state", table_name="create_value_models")
    op.drop_table("create_value_models")
