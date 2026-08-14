"""Add immutable tenant-owned pre-interaction briefs.

Revision ID: 0022_pre_interaction_brief
Revises: 0021_interaction_foundation

Downgrade warning: downgrading permanently removes all generated brief versions,
their source fingerprints, provenance references and review metadata.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0022_pre_interaction_brief"
down_revision: str | None = "0021_interaction_foundation"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _enable_tenant_rls() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return
    op.execute("ALTER TABLE pre_interaction_briefs ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE pre_interaction_briefs FORCE ROW LEVEL SECURITY")
    op.execute(
        """CREATE POLICY pre_interaction_briefs_tenant_isolation
        ON pre_interaction_briefs
        USING (organisation_id = NULLIF(current_setting('app.organisation_id', true), '')::uuid)
        WITH CHECK (organisation_id = NULLIF(current_setting('app.organisation_id', true), '')::uuid)"""
    )


def _create_immutability_guard() -> None:
    dialect = op.get_bind().dialect.name
    if dialect == "postgresql":
        op.execute(
            """
            CREATE FUNCTION protect_pre_interaction_brief()
            RETURNS trigger
            LANGUAGE plpgsql
            AS $$
            BEGIN
                IF TG_OP = 'DELETE'
                   AND current_setting('app.beta_maintenance', true) = 'approved'
                   AND OLD.organisation_id = NULLIF(current_setting('app.organisation_id', true), '')::uuid THEN
                    RETURN OLD;
                END IF;
                IF TG_OP = 'UPDATE'
                   AND OLD.organisation_id = NEW.organisation_id
                   AND OLD.id = NEW.id
                   AND OLD.interaction_id = NEW.interaction_id
                   AND OLD.company_id IS NOT DISTINCT FROM NEW.company_id
                   AND OLD.opportunity_id IS NOT DISTINCT FROM NEW.opportunity_id
                   AND OLD.source_context_fingerprint = NEW.source_context_fingerprint
                   AND OLD.brief_version = NEW.brief_version
                   AND OLD.schema_version = NEW.schema_version
                   AND OLD.status = NEW.status
                   AND OLD.content_json::jsonb = NEW.content_json::jsonb
                   AND OLD.source_references_json::jsonb = NEW.source_references_json::jsonb
                   AND OLD.created_by_user_id = NEW.created_by_user_id
                   AND OLD.created_at = NEW.created_at
                   AND OLD.reviewed_at IS NULL
                   AND OLD.reviewed_by_user_id IS NULL
                   AND NEW.reviewed_at IS NOT NULL
                   AND NEW.reviewed_by_user_id IS NOT NULL THEN
                    RETURN NEW;
                END IF;
                RAISE EXCEPTION 'Pre-interaction brief content is immutable';
            END;
            $$
            """
        )
        op.execute(
            """
            CREATE TRIGGER pre_interaction_briefs_immutable
            BEFORE UPDATE OR DELETE ON pre_interaction_briefs
            FOR EACH ROW
            EXECUTE FUNCTION protect_pre_interaction_brief()
            """
        )
    elif dialect == "sqlite":
        immutable_columns = (
            "OLD.organisation_id IS NOT NEW.organisation_id OR "
            "OLD.id IS NOT NEW.id OR "
            "OLD.interaction_id IS NOT NEW.interaction_id OR "
            "OLD.company_id IS NOT NEW.company_id OR "
            "OLD.opportunity_id IS NOT NEW.opportunity_id OR "
            "OLD.source_context_fingerprint IS NOT NEW.source_context_fingerprint OR "
            "OLD.brief_version IS NOT NEW.brief_version OR "
            "OLD.schema_version IS NOT NEW.schema_version OR "
            "OLD.status IS NOT NEW.status OR "
            "OLD.content_json IS NOT NEW.content_json OR "
            "OLD.source_references_json IS NOT NEW.source_references_json OR "
            "OLD.created_by_user_id IS NOT NEW.created_by_user_id OR "
            "OLD.created_at IS NOT NEW.created_at"
        )
        op.execute(
            f"""
            CREATE TRIGGER pre_interaction_briefs_prevent_content_update
            BEFORE UPDATE ON pre_interaction_briefs
            FOR EACH ROW WHEN {immutable_columns}
            BEGIN
                SELECT RAISE(ABORT, 'Pre-interaction brief content is immutable');
            END
            """
        )
        op.execute(
            """
            CREATE TRIGGER pre_interaction_briefs_protect_review
            BEFORE UPDATE ON pre_interaction_briefs
            FOR EACH ROW WHEN
                (
                    OLD.reviewed_at IS NOT NEW.reviewed_at
                    OR OLD.reviewed_by_user_id IS NOT NEW.reviewed_by_user_id
                )
                AND (
                    OLD.reviewed_at IS NOT NULL
                    OR OLD.reviewed_by_user_id IS NOT NULL
                    OR NEW.reviewed_at IS NULL
                    OR NEW.reviewed_by_user_id IS NULL
                )
            BEGIN
                SELECT RAISE(ABORT, 'Pre-interaction brief review metadata is append only');
            END
            """
        )


def _drop_immutability_guard() -> None:
    dialect = op.get_bind().dialect.name
    if dialect == "postgresql":
        op.execute("DROP TRIGGER pre_interaction_briefs_immutable ON pre_interaction_briefs")
        op.execute("DROP FUNCTION protect_pre_interaction_brief()")
    elif dialect == "sqlite":
        op.execute("DROP TRIGGER pre_interaction_briefs_protect_review")
        op.execute("DROP TRIGGER pre_interaction_briefs_prevent_content_update")


def upgrade() -> None:
    uuid_type = sa.Uuid(as_uuid=True)
    op.create_table(
        "pre_interaction_briefs",
        sa.Column("id", uuid_type, primary_key=True, nullable=False),
        sa.Column(
            "organisation_id",
            uuid_type,
            sa.ForeignKey("organisations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("interaction_id", uuid_type, nullable=False),
        sa.Column("company_id", uuid_type),
        sa.Column("opportunity_id", uuid_type),
        sa.Column("source_context_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("brief_version", sa.Integer(), nullable=False),
        sa.Column("schema_version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("status", sa.String(length=20), server_default="completed", nullable=False),
        sa.Column("content_json", sa.JSON(none_as_null=True), nullable=False),
        sa.Column("source_references_json", sa.JSON(none_as_null=True), nullable=False),
        sa.Column("created_by_user_id", uuid_type, nullable=False),
        sa.Column("reviewed_at", sa.DateTime(timezone=True)),
        sa.Column("reviewed_by_user_id", uuid_type),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("brief_version > 0", name="ck_pre_interaction_briefs_version"),
        sa.CheckConstraint("schema_version > 0", name="ck_pre_interaction_briefs_schema_version"),
        sa.CheckConstraint(
            "status IN ('completed', 'failed', 'cancelled')",
            name="ck_pre_interaction_briefs_status",
        ),
        sa.CheckConstraint(
            "length(source_context_fingerprint) = 64",
            name="ck_pre_interaction_briefs_fingerprint",
        ),
        sa.ForeignKeyConstraint(
            ["organisation_id", "interaction_id"],
            ["interactions.organisation_id", "interactions.id"],
            name="fk_pre_interaction_briefs_interaction_tenant",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["organisation_id", "company_id"],
            ["companies.organisation_id", "companies.id"],
            name="fk_pre_interaction_briefs_company_tenant",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organisation_id", "opportunity_id"],
            ["opportunities.organisation_id", "opportunities.id"],
            name="fk_pre_interaction_briefs_opportunity_tenant",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organisation_id", "created_by_user_id"],
            ["organisation_memberships.organisation_id", "organisation_memberships.user_id"],
            name="fk_pre_interaction_briefs_creator_membership",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organisation_id", "reviewed_by_user_id"],
            ["organisation_memberships.organisation_id", "organisation_memberships.user_id"],
            name="fk_pre_interaction_briefs_reviewer_membership",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint(
            "organisation_id",
            "id",
            name="uq_pre_interaction_briefs_organisation_id_id",
        ),
        sa.UniqueConstraint(
            "organisation_id",
            "interaction_id",
            "brief_version",
            name="uq_pre_interaction_briefs_logical_version",
        ),
        sa.UniqueConstraint(
            "organisation_id",
            "interaction_id",
            "source_context_fingerprint",
            "schema_version",
            name="uq_pre_interaction_briefs_idempotency",
        ),
    )
    op.create_index(
        "ix_pre_interaction_briefs_organisation_interaction_created",
        "pre_interaction_briefs",
        ["organisation_id", "interaction_id", "created_at"],
    )
    op.create_index(
        "ix_pre_interaction_briefs_organisation_company",
        "pre_interaction_briefs",
        ["organisation_id", "company_id"],
    )
    op.create_index(
        "ix_pre_interaction_briefs_organisation_opportunity",
        "pre_interaction_briefs",
        ["organisation_id", "opportunity_id"],
    )
    _create_immutability_guard()
    _enable_tenant_rls()


def downgrade() -> None:
    _drop_immutability_guard()
    op.drop_table("pre_interaction_briefs")
