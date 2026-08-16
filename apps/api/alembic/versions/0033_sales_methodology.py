"""Add the deterministic Sales Methodology Engine.

Revision ID: 0033_sales_methodology
Revises: 0032_integration_execution

Downgrade warning: custom definitions, organisation selection, projections and
review history are permanently removed. Evidence and Revenue Brain history are
not changed by this downgrade.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0033_sales_methodology"
down_revision: str | None = "0032_integration_execution"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TENANT_TABLES = (
    "methodology_definitions",
    "methodology_definition_versions",
    "organisation_methodology_settings",
    "methodology_projections",
    "methodology_reviews",
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
    immutable_tables = (
        "methodology_definition_versions",
        "methodology_projections",
        "methodology_reviews",
    )
    dialect = op.get_bind().dialect.name
    if dialect == "postgresql":
        op.execute(
            """
            CREATE FUNCTION protect_wo024_immutable_rows()
            RETURNS trigger
            LANGUAGE plpgsql
            AS $$
            BEGIN
                RAISE EXCEPTION 'Methodology versions, projections and reviews are immutable';
            END;
            $$
            """
        )
        for table_name in immutable_tables:
            op.execute(
                f"""CREATE TRIGGER {table_name}_immutable
                BEFORE UPDATE ON {table_name}
                FOR EACH ROW EXECUTE FUNCTION protect_wo024_immutable_rows()"""
            )
    elif dialect == "sqlite":
        for table_name in immutable_tables:
            op.execute(
                f"""CREATE TRIGGER {table_name}_immutable
                BEFORE UPDATE ON {table_name}
                FOR EACH ROW
                BEGIN
                    SELECT RAISE(ABORT, 'Methodology versions, projections and reviews are immutable');
                END"""
            )


def _drop_immutability_guards() -> None:
    immutable_tables = (
        "methodology_definition_versions",
        "methodology_projections",
        "methodology_reviews",
    )
    dialect = op.get_bind().dialect.name
    if dialect == "postgresql":
        for table_name in immutable_tables:
            op.execute(f"DROP TRIGGER {table_name}_immutable ON {table_name}")
        op.execute("DROP FUNCTION protect_wo024_immutable_rows()")
    elif dialect == "sqlite":
        for table_name in immutable_tables:
            op.execute(f"DROP TRIGGER {table_name}_immutable")


def upgrade() -> None:
    op.create_table(
        "methodology_definitions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organisation_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(length=16), server_default="active", nullable=False),
        sa.Column("current_version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("status IN ('active', 'archived')", name="ck_methodology_definitions_status"),
        sa.CheckConstraint("current_version > 0", name="ck_methodology_definitions_version"),
        sa.ForeignKeyConstraint(["organisation_id"], ["organisations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["organisation_id", "created_by_user_id"],
            ["organisation_memberships.organisation_id", "organisation_memberships.user_id"],
            name="fk_methodology_definitions_creator",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organisation_id", "id", name="uq_methodology_definitions_org_id"),
    )
    op.create_index(
        "ix_methodology_definitions_org_status",
        "methodology_definitions",
        ["organisation_id", "status"],
    )

    op.create_table(
        "methodology_definition_versions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organisation_id", sa.Uuid(), nullable=False),
        sa.Column("definition_id", sa.Uuid(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("schema_version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("content_json", sa.JSON(), nullable=False),
        sa.Column("content_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("version > 0", name="ck_methodology_versions_version"),
        sa.CheckConstraint("schema_version = 1", name="ck_methodology_versions_schema"),
        sa.CheckConstraint("length(content_fingerprint) = 64", name="ck_methodology_versions_fingerprint"),
        sa.ForeignKeyConstraint(["organisation_id"], ["organisations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["organisation_id", "definition_id"],
            ["methodology_definitions.organisation_id", "methodology_definitions.id"],
            name="fk_methodology_versions_definition",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["organisation_id", "created_by_user_id"],
            ["organisation_memberships.organisation_id", "organisation_memberships.user_id"],
            name="fk_methodology_versions_creator",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organisation_id", "id", name="uq_methodology_versions_org_id"),
        sa.UniqueConstraint(
            "organisation_id",
            "definition_id",
            "version",
            name="uq_methodology_versions_definition_version",
        ),
    )
    op.create_index(
        "ix_methodology_versions_org_definition",
        "methodology_definition_versions",
        ["organisation_id", "definition_id", "version"],
    )

    op.create_table(
        "organisation_methodology_settings",
        sa.Column("organisation_id", sa.Uuid(), nullable=False),
        sa.Column("selection", sa.String(length=16), server_default="none", nullable=False),
        sa.Column("custom_definition_id", sa.Uuid(), nullable=True),
        sa.Column("updated_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "selection IN ('none', 'meddic', 'meddpicc', 'bant', 'spiced', 'custom')",
            name="ck_methodology_settings_selection",
        ),
        sa.CheckConstraint(
            "(selection = 'custom' AND custom_definition_id IS NOT NULL) OR "
            "(selection <> 'custom' AND custom_definition_id IS NULL)",
            name="ck_methodology_settings_custom",
        ),
        sa.ForeignKeyConstraint(["organisation_id"], ["organisations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["organisation_id", "custom_definition_id"],
            ["methodology_definitions.organisation_id", "methodology_definitions.id"],
            name="fk_methodology_settings_custom",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organisation_id", "updated_by_user_id"],
            ["organisation_memberships.organisation_id", "organisation_memberships.user_id"],
            name="fk_methodology_settings_updater",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("organisation_id"),
    )

    op.create_table(
        "methodology_projections",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organisation_id", sa.Uuid(), nullable=False),
        sa.Column("opportunity_id", sa.Uuid(), nullable=False),
        sa.Column("methodology_kind", sa.String(length=16), nullable=False),
        sa.Column("definition_key", sa.String(length=100), nullable=False),
        sa.Column("definition_id", sa.Uuid(), nullable=True),
        sa.Column("definition_version", sa.Integer(), nullable=False),
        sa.Column("projection_version", sa.Integer(), nullable=False),
        sa.Column("engine_version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("schema_version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("source_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("content_json", sa.JSON(), nullable=False),
        sa.Column("generated_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("methodology_kind IN ('standard', 'custom')", name="ck_methodology_projections_kind"),
        sa.CheckConstraint("definition_version > 0", name="ck_methodology_projections_definition_version"),
        sa.CheckConstraint("projection_version > 0", name="ck_methodology_projections_version"),
        sa.CheckConstraint("engine_version = 1", name="ck_methodology_projections_engine"),
        sa.CheckConstraint("schema_version = 1", name="ck_methodology_projections_schema"),
        sa.CheckConstraint("length(source_fingerprint) = 64", name="ck_methodology_projections_fingerprint"),
        sa.CheckConstraint(
            "(methodology_kind = 'custom' AND definition_id IS NOT NULL) OR "
            "(methodology_kind = 'standard' AND definition_id IS NULL)",
            name="ck_methodology_projections_definition",
        ),
        sa.ForeignKeyConstraint(["organisation_id"], ["organisations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["organisation_id", "opportunity_id"],
            ["opportunities.organisation_id", "opportunities.id"],
            name="fk_methodology_projections_opportunity",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["organisation_id", "definition_id"],
            ["methodology_definitions.organisation_id", "methodology_definitions.id"],
            name="fk_methodology_projections_definition",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organisation_id", "generated_by_user_id"],
            ["organisation_memberships.organisation_id", "organisation_memberships.user_id"],
            name="fk_methodology_projections_generator",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organisation_id", "id", name="uq_methodology_projections_org_id"),
        sa.UniqueConstraint(
            "organisation_id",
            "opportunity_id",
            "definition_key",
            "definition_version",
            "source_fingerprint",
            name="uq_methodology_projections_idempotency",
        ),
        sa.UniqueConstraint(
            "organisation_id",
            "opportunity_id",
            "projection_version",
            name="uq_methodology_projections_logical_version",
        ),
    )
    op.create_index(
        "ix_methodology_projections_org_opportunity_generated",
        "methodology_projections",
        ["organisation_id", "opportunity_id", "generated_at"],
    )
    op.create_index(
        "ix_methodology_projections_org_definition",
        "methodology_projections",
        ["organisation_id", "definition_key", "definition_version"],
    )

    op.create_table(
        "methodology_reviews",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organisation_id", sa.Uuid(), nullable=False),
        sa.Column("projection_id", sa.Uuid(), nullable=False),
        sa.Column("opportunity_id", sa.Uuid(), nullable=False),
        sa.Column("field_key", sa.String(length=64), nullable=False),
        sa.Column("action", sa.String(length=32), nullable=False),
        sa.Column("clarification_text", sa.String(length=1000), nullable=True),
        sa.Column("clarification_evidence_id", sa.Uuid(), nullable=True),
        sa.Column("reviewed_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("idempotency_key", sa.String(length=200), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "action IN ('confirm_interpretation', 'clarify', 'mark_not_known', 'mark_incorrect')",
            name="ck_methodology_reviews_action",
        ),
        sa.CheckConstraint("length(trim(field_key)) BETWEEN 1 AND 64", name="ck_methodology_reviews_field"),
        sa.CheckConstraint("length(trim(idempotency_key)) BETWEEN 1 AND 200", name="ck_methodology_reviews_key"),
        sa.CheckConstraint(
            "(action = 'clarify' AND clarification_text IS NOT NULL AND clarification_evidence_id IS NOT NULL) OR "
            "(action <> 'clarify' AND clarification_text IS NULL AND clarification_evidence_id IS NULL)",
            name="ck_methodology_reviews_clarification",
        ),
        sa.ForeignKeyConstraint(["organisation_id"], ["organisations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["organisation_id", "projection_id"],
            ["methodology_projections.organisation_id", "methodology_projections.id"],
            name="fk_methodology_reviews_projection",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["organisation_id", "opportunity_id"],
            ["opportunities.organisation_id", "opportunities.id"],
            name="fk_methodology_reviews_opportunity",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["organisation_id", "reviewed_by_user_id"],
            ["organisation_memberships.organisation_id", "organisation_memberships.user_id"],
            name="fk_methodology_reviews_reviewer",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organisation_id", "clarification_evidence_id"],
            ["evidence.organisation_id", "evidence.id"],
            name="fk_methodology_reviews_evidence",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organisation_id", "id", name="uq_methodology_reviews_org_id"),
        sa.UniqueConstraint(
            "organisation_id",
            "reviewed_by_user_id",
            "idempotency_key",
            name="uq_methodology_reviews_idempotency",
        ),
    )
    op.create_index(
        "ix_methodology_reviews_org_opportunity_field",
        "methodology_reviews",
        ["organisation_id", "opportunity_id", "field_key", "created_at"],
    )
    _enable_tenant_rls()
    _create_immutability_guards()


def downgrade() -> None:
    _drop_immutability_guards()
    op.drop_table("methodology_reviews")
    op.drop_table("methodology_projections")
    op.drop_table("organisation_methodology_settings")
    op.drop_table("methodology_definition_versions")
    op.drop_table("methodology_definitions")
