"""Add immutable tenant-owned Revenue Brain snapshots.

Revision ID: 0018_revenue_brain
Revises: 0017_opportunity_workspace
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0018_revenue_brain"
down_revision: str | None = "0017_opportunity_workspace"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _enable_tenant_rls() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return
    op.execute("ALTER TABLE revenue_brain_snapshots ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE revenue_brain_snapshots FORCE ROW LEVEL SECURITY")
    op.execute(
        """CREATE POLICY revenue_brain_snapshots_tenant_isolation
        ON revenue_brain_snapshots
        USING (organisation_id = NULLIF(current_setting('app.organisation_id', true), '')::uuid)
        WITH CHECK (organisation_id = NULLIF(current_setting('app.organisation_id', true), '')::uuid)"""
    )


def _create_immutability_guard() -> None:
    dialect = op.get_bind().dialect.name
    if dialect == "postgresql":
        op.execute(
            """
            CREATE FUNCTION prevent_revenue_brain_snapshot_mutation()
            RETURNS trigger
            LANGUAGE plpgsql
            AS $$
            BEGIN
                RAISE EXCEPTION 'Revenue Brain snapshots are append only';
            END;
            $$
            """
        )
        op.execute(
            """
            CREATE TRIGGER revenue_brain_snapshots_append_only
            BEFORE UPDATE OR DELETE ON revenue_brain_snapshots
            FOR EACH ROW
            EXECUTE FUNCTION prevent_revenue_brain_snapshot_mutation()
            """
        )
    elif dialect == "sqlite":
        op.execute(
            """
            CREATE TRIGGER revenue_brain_snapshots_prevent_update
            BEFORE UPDATE ON revenue_brain_snapshots
            FOR EACH ROW
            BEGIN
                SELECT RAISE(ABORT, 'Revenue Brain snapshots are append only');
            END
            """
        )
        op.execute(
            """
            CREATE TRIGGER revenue_brain_snapshots_prevent_delete
            BEFORE DELETE ON revenue_brain_snapshots
            FOR EACH ROW
            BEGIN
                SELECT RAISE(ABORT, 'Revenue Brain snapshots are append only');
            END
            """
        )


def _drop_immutability_guard() -> None:
    dialect = op.get_bind().dialect.name
    if dialect == "postgresql":
        op.execute("DROP TRIGGER revenue_brain_snapshots_append_only ON revenue_brain_snapshots")
        op.execute("DROP FUNCTION prevent_revenue_brain_snapshot_mutation()")
    elif dialect == "sqlite":
        op.execute("DROP TRIGGER revenue_brain_snapshots_prevent_delete")
        op.execute("DROP TRIGGER revenue_brain_snapshots_prevent_update")


def upgrade() -> None:
    uuid_type = sa.Uuid(as_uuid=True)
    op.create_table(
        "revenue_brain_snapshots",
        sa.Column("id", uuid_type, nullable=False),
        sa.Column("organisation_id", uuid_type, nullable=False),
        sa.Column("company_id", uuid_type, nullable=False),
        sa.Column("opportunity_id", uuid_type, nullable=True),
        sa.Column("meeting_id", uuid_type, nullable=False),
        sa.Column("transcript_version_id", uuid_type, nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("summary_reference", uuid_type, nullable=False),
        sa.Column("buying_signals_reference", uuid_type, nullable=False),
        sa.Column("objections_reference", uuid_type, nullable=False),
        sa.Column("stakeholders_reference", uuid_type, nullable=False),
        sa.Column("decisions_reference", uuid_type, nullable=False),
        sa.Column("actions_reference", uuid_type, nullable=False),
        sa.Column("risks_reference", uuid_type, nullable=False),
        sa.Column("questions_reference", uuid_type, nullable=False),
        sa.Column("next_best_action_reference", uuid_type, nullable=False),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.CheckConstraint(
            "version > 0",
            name="ck_revenue_brain_snapshots_version",
        ),
        sa.ForeignKeyConstraint(
            ["organisation_id"],
            ["organisations.id"],
            name="fk_revenue_brain_snapshots_organisation",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["organisation_id", "company_id"],
            ["companies.organisation_id", "companies.id"],
            name="fk_revenue_brain_snapshots_company_tenant",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organisation_id", "opportunity_id"],
            ["opportunities.organisation_id", "opportunities.id"],
            name="fk_revenue_brain_snapshots_opportunity_tenant",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organisation_id", "meeting_id"],
            ["meetings.organisation_id", "meetings.id"],
            name="fk_revenue_brain_snapshots_meeting_tenant",
            ondelete="RESTRICT",
        ),
        *(
            sa.ForeignKeyConstraint(
                ["organisation_id", column_name],
                ["ai_artifacts.organisation_id", "ai_artifacts.id"],
                name=constraint_name,
                ondelete="RESTRICT",
            )
            for column_name, constraint_name in (
                ("summary_reference", "fk_revenue_brain_snapshots_summary_tenant"),
                (
                    "buying_signals_reference",
                    "fk_revenue_brain_snapshots_buying_signals_tenant",
                ),
                (
                    "objections_reference",
                    "fk_revenue_brain_snapshots_objections_tenant",
                ),
                (
                    "stakeholders_reference",
                    "fk_revenue_brain_snapshots_stakeholders_tenant",
                ),
                (
                    "decisions_reference",
                    "fk_revenue_brain_snapshots_decisions_tenant",
                ),
                ("actions_reference", "fk_revenue_brain_snapshots_actions_tenant"),
                ("risks_reference", "fk_revenue_brain_snapshots_risks_tenant"),
                (
                    "questions_reference",
                    "fk_revenue_brain_snapshots_questions_tenant",
                ),
                (
                    "next_best_action_reference",
                    "fk_revenue_brain_snapshots_next_best_action_tenant",
                ),
            )
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organisation_id",
            "id",
            name="uq_revenue_brain_snapshots_organisation_id_id",
        ),
        sa.UniqueConstraint(
            "organisation_id",
            "meeting_id",
            "transcript_version_id",
            name="uq_revenue_brain_snapshots_meeting_transcript_version",
        ),
    )
    op.create_index(
        "ix_revenue_brain_snapshots_organisation_company_created",
        "revenue_brain_snapshots",
        ["organisation_id", "company_id", "created_at"],
    )
    op.create_index(
        "ix_revenue_brain_snapshots_organisation_meeting",
        "revenue_brain_snapshots",
        ["organisation_id", "meeting_id"],
    )
    _create_immutability_guard()
    _enable_tenant_rls()


def downgrade() -> None:
    _drop_immutability_guard()
    op.drop_table("revenue_brain_snapshots")
