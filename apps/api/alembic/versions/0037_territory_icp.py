"""Add versioned Target Markets and explainable account discovery.

Revision ID: 0037_territory_icp
Revises: 0036_prospect_people

WO-028 combines the customer-facing ICP and Territory setup into a bounded Target
Market while retaining immutable versions and discovery results. Candidate company
identity continues to use the WO-026 Prospect Research Target.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0037_territory_icp"
down_revision: str | None = "0036_prospect_people"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TENANT_TABLES = (
    "prospect_target_markets",
    "prospect_target_market_versions",
    "prospect_discovery_runs",
    "prospect_discovery_candidates",
    "prospect_candidate_reasons",
    "prospect_target_feedback",
)


def _enable_rls_and_immutability() -> None:
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
        """
        CREATE FUNCTION public.revenueos_reject_prospect_history_update()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
            RAISE EXCEPTION 'Prospect Target Market versions and discovery results are immutable';
        END;
        $$
        """
    )
    for table_name in (
        "prospect_target_market_versions",
        "prospect_discovery_candidates",
        "prospect_candidate_reasons",
    ):
        op.execute(
            f"""CREATE TRIGGER {table_name}_immutable_update
            BEFORE UPDATE ON {table_name}
            FOR EACH ROW EXECUTE FUNCTION public.revenueos_reject_prospect_history_update()"""
        )


def upgrade() -> None:
    uuid_type = sa.Uuid(as_uuid=True)

    with op.batch_alter_table("prospect_usage_counters") as batch:
        batch.add_column(sa.Column("discovery_run_count", sa.Integer(), server_default="0", nullable=False))
        batch.create_check_constraint("ck_prospect_discovery_count", "discovery_run_count >= 0")

    op.create_table(
        "prospect_target_markets",
        sa.Column("id", uuid_type, nullable=False),
        sa.Column("organisation_id", uuid_type, nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("status", sa.String(length=20), server_default="active", nullable=False),
        sa.Column("current_version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("created_by_user_id", uuid_type, nullable=False),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("length(trim(name)) BETWEEN 1 AND 120", name="ck_prospect_markets_name"),
        sa.CheckConstraint("status IN ('draft', 'active', 'archived')", name="ck_prospect_markets_status"),
        sa.CheckConstraint("current_version > 0", name="ck_prospect_markets_version"),
        sa.CheckConstraint(
            "(status = 'archived' AND archived_at IS NOT NULL) OR (status <> 'archived' AND archived_at IS NULL)",
            name="ck_prospect_markets_archive",
        ),
        sa.ForeignKeyConstraint(["organisation_id"], ["organisations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["organisation_id", "created_by_user_id"],
            ["organisation_memberships.organisation_id", "organisation_memberships.user_id"],
            name="fk_prospect_markets_creator",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organisation_id", "id", name="uq_prospect_markets_org_id"),
        sa.UniqueConstraint("organisation_id", "name", name="uq_prospect_markets_org_name"),
    )
    op.create_index("ix_prospect_markets_org_status", "prospect_target_markets", ["organisation_id", "status"])

    op.create_table(
        "prospect_target_market_versions",
        sa.Column("id", uuid_type, nullable=False),
        sa.Column("organisation_id", uuid_type, nullable=False),
        sa.Column("target_market_id", uuid_type, nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("description", sa.String(length=400), nullable=True),
        sa.Column("industries", sa.JSON(), nullable=False),
        sa.Column("countries", sa.JSON(), nullable=False),
        sa.Column("regions", sa.JSON(), nullable=False),
        sa.Column("minimum_employee_band", sa.String(length=20), nullable=True),
        sa.Column("organisation_types", sa.JSON(), nullable=False),
        sa.Column("preferred_business_characteristics", sa.JSON(), nullable=False),
        sa.Column("excluded_industries", sa.JSON(), nullable=False),
        sa.Column("exclude_existing_accounts", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("research_objective", sa.String(length=300), nullable=True),
        sa.Column("created_by_user_id", uuid_type, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("version > 0", name="ck_prospect_market_versions_number"),
        sa.CheckConstraint(
            "description IS NULL OR length(description) <= 400",
            name="ck_prospect_market_versions_description",
        ),
        sa.CheckConstraint(
            "research_objective IS NULL OR length(research_objective) <= 300",
            name="ck_prospect_market_versions_objective",
        ),
        sa.CheckConstraint(
            "minimum_employee_band IS NULL OR minimum_employee_band IN "
            "('50_199', '200_499', '500_999', '1000_4999', '5000_plus')",
            name="ck_prospect_market_versions_employee_band",
        ),
        sa.ForeignKeyConstraint(["organisation_id"], ["organisations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["organisation_id", "target_market_id"],
            ["prospect_target_markets.organisation_id", "prospect_target_markets.id"],
            name="fk_prospect_market_versions_market",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["organisation_id", "created_by_user_id"],
            ["organisation_memberships.organisation_id", "organisation_memberships.user_id"],
            name="fk_prospect_market_versions_creator",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organisation_id", "id", name="uq_prospect_market_versions_org_id"),
        sa.UniqueConstraint(
            "organisation_id", "id", "target_market_id", name="uq_prospect_market_versions_org_id_market"
        ),
        sa.UniqueConstraint(
            "organisation_id", "target_market_id", "version", name="uq_prospect_market_versions_number"
        ),
    )
    op.create_index(
        "ix_prospect_market_versions_org_market",
        "prospect_target_market_versions",
        ["organisation_id", "target_market_id", "version"],
    )

    op.create_table(
        "prospect_discovery_runs",
        sa.Column("id", uuid_type, nullable=False),
        sa.Column("organisation_id", uuid_type, nullable=False),
        sa.Column("target_market_id", uuid_type, nullable=False),
        sa.Column("target_market_version_id", uuid_type, nullable=False),
        sa.Column("requested_by_user_id", uuid_type, nullable=False),
        sa.Column("provider_key", sa.String(length=40), nullable=False),
        sa.Column("provider_version", sa.String(length=80), nullable=False),
        sa.Column("status", sa.String(length=20), server_default="pending", nullable=False),
        sa.Column("schema_version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("fingerprint", sa.String(length=64), nullable=False),
        sa.Column("idempotency_key", sa.String(length=200), nullable=False),
        sa.Column("refresh_of_run_id", uuid_type, nullable=True),
        sa.Column("requested_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("candidate_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("eligible_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("excluded_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("partial_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("failure_code", sa.String(length=80), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "status IN ('pending', 'running', 'completed', 'partial', 'failed')",
            name="ck_prospect_discovery_runs_status",
        ),
        sa.CheckConstraint("schema_version > 0", name="ck_prospect_discovery_runs_schema"),
        sa.CheckConstraint(
            "candidate_count >= 0 AND eligible_count >= 0 AND excluded_count >= 0 AND partial_count >= 0",
            name="ck_prospect_discovery_runs_counts",
        ),
        sa.ForeignKeyConstraint(["organisation_id"], ["organisations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["organisation_id", "target_market_id"],
            ["prospect_target_markets.organisation_id", "prospect_target_markets.id"],
            name="fk_prospect_discovery_runs_market",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["organisation_id", "target_market_version_id", "target_market_id"],
            [
                "prospect_target_market_versions.organisation_id",
                "prospect_target_market_versions.id",
                "prospect_target_market_versions.target_market_id",
            ],
            name="fk_prospect_discovery_runs_version",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organisation_id", "requested_by_user_id"],
            ["organisation_memberships.organisation_id", "organisation_memberships.user_id"],
            name="fk_prospect_discovery_runs_requester",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organisation_id", "refresh_of_run_id"],
            ["prospect_discovery_runs.organisation_id", "prospect_discovery_runs.id"],
            name="fk_prospect_discovery_runs_refresh",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organisation_id", "id", name="uq_prospect_discovery_runs_org_id"),
        sa.UniqueConstraint(
            "organisation_id",
            "target_market_id",
            "idempotency_key",
            name="uq_prospect_discovery_runs_idempotency",
        ),
    )
    op.create_index(
        "ix_prospect_discovery_runs_org_market",
        "prospect_discovery_runs",
        ["organisation_id", "target_market_id", "created_at"],
    )
    op.create_index(
        "ix_prospect_discovery_runs_org_status",
        "prospect_discovery_runs",
        ["organisation_id", "status"],
    )

    op.create_table(
        "prospect_discovery_candidates",
        sa.Column("id", uuid_type, nullable=False),
        sa.Column("organisation_id", uuid_type, nullable=False),
        sa.Column("run_id", uuid_type, nullable=False),
        sa.Column("target_id", uuid_type, nullable=False),
        sa.Column("match_state", sa.String(length=20), nullable=False),
        sa.Column("priority", sa.String(length=30), nullable=False),
        sa.Column("relationship_state", sa.String(length=50), server_default="new_prospect", nullable=False),
        sa.Column("matched_company_id", uuid_type, nullable=True),
        sa.Column("active_opportunity_id", uuid_type, nullable=True),
        sa.Column("employee_band", sa.String(length=20), nullable=True),
        sa.Column("country_code", sa.String(length=2), nullable=True),
        sa.Column("region", sa.String(length=120), nullable=True),
        sa.Column("organisation_type", sa.String(length=40), nullable=True),
        sa.Column("business_characteristics", sa.JSON(), nullable=False),
        sa.Column("provider_observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("data_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("match_state IN ('match', 'partial', 'excluded')", name="ck_prospect_candidates_state"),
        sa.CheckConstraint(
            "priority IN ('high', 'worth_researching', 'needs_more_information', 'excluded')",
            name="ck_prospect_candidates_priority",
        ),
        sa.CheckConstraint(
            "relationship_state IN ('new_prospect', 'existing_account_no_active_opportunity', 'active_opportunity')",
            name="ck_prospect_candidates_relationship",
        ),
        sa.CheckConstraint(
            "(match_state = 'excluded' AND priority = 'excluded') OR "
            "(match_state <> 'excluded' AND priority <> 'excluded')",
            name="ck_prospect_candidates_state_priority",
        ),
        sa.ForeignKeyConstraint(["organisation_id"], ["organisations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["organisation_id", "run_id"],
            ["prospect_discovery_runs.organisation_id", "prospect_discovery_runs.id"],
            name="fk_prospect_candidates_run",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["organisation_id", "target_id"],
            ["prospect_research_targets.organisation_id", "prospect_research_targets.id"],
            name="fk_prospect_candidates_target",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organisation_id", "matched_company_id"],
            ["companies.organisation_id", "companies.id"],
            name="fk_prospect_candidates_company",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organisation_id", "active_opportunity_id"],
            ["opportunities.organisation_id", "opportunities.id"],
            name="fk_prospect_candidates_opportunity",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organisation_id", "id", name="uq_prospect_candidates_org_id"),
        sa.UniqueConstraint("organisation_id", "id", "run_id", name="uq_prospect_candidates_org_id_run"),
        sa.UniqueConstraint("organisation_id", "run_id", "target_id", name="uq_prospect_candidates_run_target"),
    )
    op.create_index(
        "ix_prospect_candidates_org_run",
        "prospect_discovery_candidates",
        ["organisation_id", "run_id", "priority"],
    )

    op.create_table(
        "prospect_candidate_reasons",
        sa.Column("id", uuid_type, nullable=False),
        sa.Column("organisation_id", uuid_type, nullable=False),
        sa.Column("candidate_id", uuid_type, nullable=False),
        sa.Column("run_id", uuid_type, nullable=False),
        sa.Column("reason_code", sa.String(length=60), nullable=False),
        sa.Column("criterion_key", sa.String(length=60), nullable=False),
        sa.Column("state", sa.String(length=20), nullable=False),
        sa.Column("product_safe_text", sa.String(length=300), nullable=False),
        sa.Column("data_origin", sa.String(length=40), nullable=False),
        sa.Column("trust_state", sa.String(length=24), nullable=False),
        sa.Column("observed_value_class", sa.String(length=80), nullable=True),
        sa.Column("source_reference", sa.String(length=2048), nullable=True),
        sa.Column("display_order", sa.Integer(), server_default="0", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("state IN ('matched', 'missing', 'excluded', 'context')", name="ck_prospect_reasons_state"),
        sa.CheckConstraint(
            "data_origin IN ('provider_supplied', 'verified_research', 'existing_revenueos_data', 'unknown')",
            name="ck_prospect_reasons_origin",
        ),
        sa.CheckConstraint(
            "trust_state IN ('verified', 'provider_supplied', 'inferred', 'unknown')",
            name="ck_prospect_reasons_trust",
        ),
        sa.CheckConstraint("length(trim(product_safe_text)) BETWEEN 1 AND 300", name="ck_prospect_reasons_text"),
        sa.ForeignKeyConstraint(["organisation_id"], ["organisations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["organisation_id", "candidate_id", "run_id"],
            [
                "prospect_discovery_candidates.organisation_id",
                "prospect_discovery_candidates.id",
                "prospect_discovery_candidates.run_id",
            ],
            name="fk_prospect_reasons_candidate",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organisation_id", "id", name="uq_prospect_reasons_org_id"),
        sa.UniqueConstraint(
            "organisation_id", "candidate_id", "reason_code", name="uq_prospect_reasons_candidate_code"
        ),
    )
    op.create_index(
        "ix_prospect_reasons_org_candidate",
        "prospect_candidate_reasons",
        ["organisation_id", "candidate_id"],
    )

    op.create_table(
        "prospect_target_feedback",
        sa.Column("organisation_id", uuid_type, nullable=False),
        sa.Column("user_id", uuid_type, nullable=False),
        sa.Column("target_id", uuid_type, nullable=False),
        sa.Column("state", sa.String(length=20), server_default="saved", nullable=False),
        sa.Column("exclusion_reason", sa.String(length=40), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("state IN ('saved', 'excluded')", name="ck_prospect_feedback_state"),
        sa.CheckConstraint(
            "exclusion_reason IS NULL OR exclusion_reason IN "
            "('wrong_industry', 'too_small', 'too_large', 'outside_territory', "
            "'existing_relationship', 'not_relevant', 'other')",
            name="ck_prospect_feedback_reason",
        ),
        sa.CheckConstraint(
            "(state = 'saved' AND exclusion_reason IS NULL) OR state = 'excluded'",
            name="ck_prospect_feedback_state_reason",
        ),
        sa.ForeignKeyConstraint(["organisation_id"], ["organisations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["organisation_id", "user_id"],
            ["organisation_memberships.organisation_id", "organisation_memberships.user_id"],
            name="fk_prospect_feedback_membership",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["organisation_id", "target_id"],
            ["prospect_research_targets.organisation_id", "prospect_research_targets.id"],
            name="fk_prospect_feedback_target",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("organisation_id", "user_id", "target_id"),
    )
    op.create_index(
        "ix_prospect_feedback_org_user",
        "prospect_target_feedback",
        ["organisation_id", "user_id", "state"],
    )

    _enable_rls_and_immutability()


def downgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        op.execute("DROP FUNCTION IF EXISTS public.revenueos_reject_prospect_history_update() CASCADE")
    for table_name in reversed(TENANT_TABLES):
        op.drop_table(table_name)
    with op.batch_alter_table("prospect_usage_counters") as batch:
        batch.drop_constraint("ck_prospect_discovery_count", type_="check")
        batch.drop_column("discovery_run_count")
