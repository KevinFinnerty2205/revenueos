"""Add the opportunity workspace foundation.

Revision ID: 0017_opportunity_workspace
Revises: 0016_next_best_action

Downgrade removes opportunity audit history and meeting associations. It also
removes opportunities without a company because the earlier schema required a
company, and maps newer stages back to discovery.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0017_opportunity_workspace"
down_revision: str | None = "0016_next_best_action"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _enable_tenant_rls(table_name: str) -> None:
    if op.get_bind().dialect.name != "postgresql":
        return
    policy_name = f"{table_name}_tenant_isolation"
    op.execute(f"ALTER TABLE {table_name} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {table_name} FORCE ROW LEVEL SECURITY")
    op.execute(
        f"""CREATE POLICY {policy_name} ON {table_name}
        USING (organisation_id = NULLIF(current_setting('app.organisation_id', true), '')::uuid)
        WITH CHECK (organisation_id = NULLIF(current_setting('app.organisation_id', true), '')::uuid)"""
    )


def upgrade() -> None:
    uuid_type = sa.Uuid(as_uuid=True)
    with op.batch_alter_table("opportunities") as batch_op:
        batch_op.drop_constraint("ck_opportunities_stage", type_="check")
        batch_op.drop_constraint("ck_opportunities_value", type_="check")
        batch_op.drop_constraint("ck_opportunities_probability", type_="check")
        batch_op.drop_constraint("ck_opportunities_currency", type_="check")
        batch_op.add_column(
            sa.Column(
                "status",
                sa.String(length=20),
                server_default="open",
                nullable=False,
            )
        )
        batch_op.add_column(sa.Column("description", sa.Text()))
        batch_op.alter_column(
            "company_id",
            existing_type=uuid_type,
            nullable=True,
        )
        batch_op.alter_column(
            "value",
            new_column_name="estimated_value",
            existing_type=sa.Numeric(precision=18, scale=2),
            nullable=True,
            server_default=None,
        )
        batch_op.alter_column(
            "currency",
            existing_type=sa.String(length=3),
            nullable=True,
            server_default=None,
        )
        batch_op.drop_column("probability")
        batch_op.create_check_constraint(
            "ck_opportunities_stage",
            "stage IN ('qualification', 'discovery', 'evaluation', 'proposal', "
            "'negotiation', 'procurement', 'closed_won', 'closed_lost', 'other')",
        )
        batch_op.create_check_constraint(
            "ck_opportunities_status",
            "status IN ('open', 'won', 'lost', 'on_hold')",
        )
        batch_op.create_check_constraint(
            "ck_opportunities_value_currency",
            "(estimated_value IS NULL AND currency IS NULL) OR "
            "(estimated_value IS NOT NULL AND estimated_value >= 0 AND currency IS NOT NULL)",
        )
        batch_op.create_check_constraint(
            "ck_opportunities_currency",
            "currency IS NULL OR (length(currency) = 3 AND currency = upper(currency))",
        )

    op.execute(
        "UPDATE opportunities SET status = CASE "
        "WHEN stage = 'closed_won' THEN 'won' "
        "WHEN stage = 'closed_lost' THEN 'lost' ELSE 'open' END"
    )
    op.execute("UPDATE opportunities SET estimated_value = NULL, currency = NULL WHERE estimated_value = 0")
    op.create_index(
        "ix_opportunities_organisation_status",
        "opportunities",
        ["organisation_id", "status"],
    )
    op.create_index(
        "ix_opportunities_organisation_updated",
        "opportunities",
        ["organisation_id", "updated_at"],
    )

    with op.batch_alter_table("meetings") as batch_op:
        batch_op.add_column(sa.Column("opportunity_id", uuid_type))
        batch_op.create_foreign_key(
            "fk_meetings_opportunity_tenant",
            "opportunities",
            ["organisation_id", "opportunity_id"],
            ["organisation_id", "id"],
            ondelete="RESTRICT",
        )
        batch_op.create_index(
            "ix_meetings_organisation_opportunity_date",
            ["organisation_id", "opportunity_id", "meeting_date"],
        )

    op.create_table(
        "opportunity_audit_events",
        sa.Column("id", uuid_type, primary_key=True, nullable=False),
        sa.Column(
            "organisation_id",
            uuid_type,
            sa.ForeignKey("organisations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("opportunity_id", uuid_type, nullable=False),
        sa.Column("actor_user_id", uuid_type, nullable=False),
        sa.Column("action", sa.String(length=40), nullable=False),
        sa.Column("changed_fields", sa.JSON(), nullable=False),
        sa.Column(
            "metadata_json",
            sa.JSON(),
            server_default=sa.text("'{}'"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "action IN ('created', 'updated', 'deleted', 'meeting_associated', 'meeting_disassociated')",
            name="ck_opportunity_audit_events_action",
        ),
        sa.ForeignKeyConstraint(
            ["organisation_id", "actor_user_id"],
            [
                "organisation_memberships.organisation_id",
                "organisation_memberships.user_id",
            ],
            name="fk_opportunity_audit_events_actor_membership",
            ondelete="RESTRICT",
        ),
    )
    op.create_index(
        "ix_opportunity_audit_events_organisation_entity_created",
        "opportunity_audit_events",
        ["organisation_id", "opportunity_id", "created_at"],
    )
    _enable_tenant_rls("opportunity_audit_events")


def downgrade() -> None:
    op.drop_table("opportunity_audit_events")

    with op.batch_alter_table("meetings") as batch_op:
        batch_op.drop_index("ix_meetings_organisation_opportunity_date")
        batch_op.drop_constraint("fk_meetings_opportunity_tenant", type_="foreignkey")
        batch_op.drop_column("opportunity_id")

    op.execute(
        "UPDATE tasks SET opportunity_id = NULL WHERE opportunity_id IN "
        "(SELECT id FROM opportunities WHERE company_id IS NULL)"
    )
    op.execute("DELETE FROM opportunities WHERE company_id IS NULL")
    op.execute("UPDATE opportunities SET stage = 'discovery' WHERE stage IN ('evaluation', 'procurement', 'other')")
    op.execute("UPDATE opportunities SET estimated_value = 0, currency = 'AUD' WHERE estimated_value IS NULL")
    op.drop_index("ix_opportunities_organisation_updated", table_name="opportunities")
    op.drop_index("ix_opportunities_organisation_status", table_name="opportunities")
    with op.batch_alter_table("opportunities") as batch_op:
        batch_op.drop_constraint("ck_opportunities_stage", type_="check")
        batch_op.drop_constraint("ck_opportunities_status", type_="check")
        batch_op.drop_constraint("ck_opportunities_value_currency", type_="check")
        batch_op.drop_constraint("ck_opportunities_currency", type_="check")
        batch_op.add_column(
            sa.Column(
                "probability",
                sa.Integer(),
                server_default="0",
                nullable=False,
            )
        )
        batch_op.drop_column("description")
        batch_op.drop_column("status")
        batch_op.alter_column(
            "company_id",
            existing_type=sa.Uuid(as_uuid=True),
            nullable=False,
        )
        batch_op.alter_column(
            "estimated_value",
            new_column_name="value",
            existing_type=sa.Numeric(precision=18, scale=2),
            nullable=False,
            server_default="0",
        )
        batch_op.alter_column(
            "currency",
            existing_type=sa.String(length=3),
            nullable=False,
            server_default="AUD",
        )
        batch_op.create_check_constraint(
            "ck_opportunities_stage",
            "stage IN ('discovery', 'qualification', 'proposal', 'negotiation', 'closed_won', 'closed_lost')",
        )
        batch_op.create_check_constraint("ck_opportunities_value", "value >= 0")
        batch_op.create_check_constraint(
            "ck_opportunities_probability",
            "probability >= 0 AND probability <= 100",
        )
        batch_op.create_check_constraint(
            "ck_opportunities_currency",
            "length(currency) = 3 AND currency = upper(currency)",
        )
