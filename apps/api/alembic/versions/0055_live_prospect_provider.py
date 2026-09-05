"""Add live Prospect provider execution metadata.

Revision ID: 0055_live_prospect_provider
Revises: 0054_credits_variable_cost
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0055_live_prospect_provider"
down_revision: str | None = "0054_credits_variable_cost"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("prospect_research_runs") as batch:
        batch.drop_constraint("ck_prospect_runs_status", type_="check")
        batch.add_column(sa.Column("credit_operation_id", sa.Uuid(), nullable=True))
        batch.add_column(sa.Column("selling_profile_revision_id", sa.Uuid(), nullable=True))
        batch.add_column(
            sa.Column("provider_mode", sa.String(length=20), server_default="deterministic", nullable=False)
        )
        batch.add_column(sa.Column("provider_request_id", sa.String(length=255), nullable=True))
        batch.add_column(sa.Column("provider_outcome", sa.String(length=24), nullable=True))
        batch.add_column(sa.Column("provider_units", sa.Integer(), server_default="0", nullable=False))
        batch.add_column(sa.Column("successful_units", sa.Integer(), server_default="0", nullable=False))
        batch.add_column(sa.Column("provider_cost_micros", sa.BigInteger(), server_default="0", nullable=False))
        batch.add_column(sa.Column("provider_cost_currency", sa.String(length=3), nullable=True))
        batch.create_check_constraint(
            "ck_prospect_runs_status",
            "status IN ('pending', 'fetching', 'synthesizing', 'completed', 'partial', 'no_result', 'unknown', 'failed')",
        )
        batch.create_check_constraint(
            "ck_prospect_runs_provider_mode",
            "provider_mode IN ('deterministic', 'external')",
        )
        batch.create_check_constraint(
            "ck_prospect_runs_provider_outcome",
            "provider_outcome IS NULL OR provider_outcome IN ('completed', 'partial', 'no_result', 'unknown')",
        )
        batch.create_check_constraint(
            "ck_prospect_runs_provider_amounts",
            "provider_units >= 0 AND successful_units >= 0 AND successful_units <= provider_units "
            "AND provider_cost_micros >= 0",
        )
        batch.create_check_constraint(
            "ck_prospect_runs_provider_currency",
            "provider_cost_currency IS NULL OR "
            "(length(provider_cost_currency) = 3 AND provider_cost_currency = upper(provider_cost_currency))",
        )
        batch.create_foreign_key(
            "fk_prospect_runs_credit_operation",
            "credit_operations",
            ["organisation_id", "credit_operation_id"],
            ["organisation_id", "id"],
            ondelete="RESTRICT",
        )
        batch.create_foreign_key(
            "fk_prospect_runs_selling_profile_revision",
            "selling_profile_revisions",
            ["organisation_id", "selling_profile_revision_id"],
            ["organisation_id", "id"],
            ondelete="RESTRICT",
        )
        batch.create_unique_constraint("uq_prospect_runs_credit_operation", ["organisation_id", "credit_operation_id"])
        batch.create_index(
            "ix_prospect_runs_org_provider_outcome",
            ["organisation_id", "provider_outcome"],
        )


def downgrade() -> None:
    with op.batch_alter_table("prospect_research_runs") as batch:
        batch.drop_index("ix_prospect_runs_org_provider_outcome")
        batch.drop_constraint("uq_prospect_runs_credit_operation", type_="unique")
        batch.drop_constraint("fk_prospect_runs_selling_profile_revision", type_="foreignkey")
        batch.drop_constraint("fk_prospect_runs_credit_operation", type_="foreignkey")
        batch.drop_constraint("ck_prospect_runs_provider_currency", type_="check")
        batch.drop_constraint("ck_prospect_runs_provider_amounts", type_="check")
        batch.drop_constraint("ck_prospect_runs_provider_outcome", type_="check")
        batch.drop_constraint("ck_prospect_runs_provider_mode", type_="check")
        batch.drop_constraint("ck_prospect_runs_status", type_="check")
        for column in (
            "provider_cost_currency",
            "provider_cost_micros",
            "successful_units",
            "provider_units",
            "provider_outcome",
            "provider_request_id",
            "provider_mode",
            "selling_profile_revision_id",
            "credit_operation_id",
        ):
            batch.drop_column(column)
        batch.create_check_constraint(
            "ck_prospect_runs_status",
            "status IN ('pending', 'fetching', 'synthesizing', 'completed', 'partial', 'failed')",
        )
