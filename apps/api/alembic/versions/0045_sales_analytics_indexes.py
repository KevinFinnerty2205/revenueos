"""Add bounded query indexes for canonical sales analytics.

Revision ID: 0045_sales_analytics
Revises: 0044_native_pipeline
Create Date: 2026-08-30
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0045_sales_analytics"
down_revision: str | None = "0044_native_pipeline"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index(
        "ix_opportunities_org_actual_close_status",
        "opportunities",
        ["organisation_id", "actual_close_date", "status"],
        unique=False,
    )
    op.create_index(
        "ix_opportunity_stage_events_org_to_pipeline_time",
        "opportunity_stage_events",
        ["organisation_id", "to_pipeline_id", "changed_at"],
        unique=False,
    )
    op.create_index(
        "ix_opportunity_stage_events_org_from_pipeline_time",
        "opportunity_stage_events",
        ["organisation_id", "from_pipeline_id", "changed_at"],
        unique=False,
    )
    op.create_index(
        "ix_interactions_org_completed_type",
        "interactions",
        ["organisation_id", "actual_end_at", "interaction_type", "lifecycle_status"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_interactions_org_completed_type", table_name="interactions")
    op.drop_index(
        "ix_opportunity_stage_events_org_from_pipeline_time",
        table_name="opportunity_stage_events",
    )
    op.drop_index(
        "ix_opportunity_stage_events_org_to_pipeline_time",
        table_name="opportunity_stage_events",
    )
    op.drop_index("ix_opportunities_org_actual_close_status", table_name="opportunities")
