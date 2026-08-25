"""Add tenant-owned Prospect account research.

Revision ID: 0035_prospect_research
Revises: 0034_crm_sync

WO-026 keeps public research separate from customer Evidence and canonical Company
records until an explicit, duplicate-safe promotion.
"""

from collections.abc import Sequence
from urllib.parse import urlsplit

import sqlalchemy as sa
from alembic import op

revision: str = "0035_prospect_research"
down_revision: str | None = "0034_crm_sync"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TENANT_TABLES = (
    "organisation_module_entitlements",
    "prospect_usage_counters",
    "prospect_research_targets",
    "prospect_research_runs",
    "prospect_research_sources",
    "prospect_research_observations",
    "prospect_research_observation_sources",
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


def _normalise_existing_domain(value: str | None) -> str | None:
    if value is None:
        return None
    candidate = value.strip()
    if not candidate:
        return None
    parsed = urlsplit(candidate if "://" in candidate else f"https://{candidate}")
    host = parsed.hostname
    if host is None:
        return None
    try:
        ascii_host = host.encode("idna").decode("ascii").lower().rstrip(".")
    except UnicodeError:
        return None
    return ascii_host[4:] if ascii_host.startswith("www.") else ascii_host


def _backfill_company_domains() -> None:
    bind = op.get_bind()
    rows = bind.execute(sa.text("SELECT id, organisation_id, website FROM companies ORDER BY created_at, id"))
    for row in rows.mappings():
        domain = _normalise_existing_domain(row["website"])
        if domain is None:
            continue
        bind.execute(
            sa.text("UPDATE companies SET normalized_domain = :domain WHERE id = :company_id"),
            {"domain": domain, "company_id": row["id"]},
        )


def upgrade() -> None:
    uuid_type = sa.Uuid(as_uuid=True)

    with op.batch_alter_table("companies") as batch:
        batch.add_column(sa.Column("normalized_domain", sa.String(length=253), nullable=True))
    _backfill_company_domains()
    with op.batch_alter_table("companies") as batch:
        batch.create_index("ix_companies_organisation_domain", ["organisation_id", "normalized_domain"])

    op.create_table(
        "organisation_module_entitlements",
        sa.Column("organisation_id", uuid_type, nullable=False),
        sa.Column("module_key", sa.String(length=40), nullable=False),
        sa.Column("enabled", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("source", sa.String(length=40), server_default="manual_private_beta", nullable=False),
        sa.Column("configured_by_user_id", uuid_type, nullable=False),
        sa.Column("enabled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("disabled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("module_key = 'prospect'", name="ck_module_entitlements_key"),
        sa.CheckConstraint("source = 'manual_private_beta'", name="ck_module_entitlements_source"),
        sa.ForeignKeyConstraint(["organisation_id"], ["organisations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["organisation_id", "configured_by_user_id"],
            ["organisation_memberships.organisation_id", "organisation_memberships.user_id"],
            name="fk_module_entitlements_configurer",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("organisation_id", "module_key"),
    )

    op.create_table(
        "prospect_usage_counters",
        sa.Column("organisation_id", uuid_type, nullable=False),
        sa.Column("usage_date", sa.Date(), nullable=False),
        sa.Column("scope_key", sa.String(length=50), nullable=False),
        sa.Column("research_run_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "scope_key = 'organisation' OR scope_key LIKE 'user:%'",
            name="ck_prospect_usage_scope",
        ),
        sa.CheckConstraint("research_run_count >= 0", name="ck_prospect_usage_count"),
        sa.ForeignKeyConstraint(["organisation_id"], ["organisations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("organisation_id", "usage_date", "scope_key"),
    )

    op.create_table(
        "prospect_research_targets",
        sa.Column("id", uuid_type, nullable=False),
        sa.Column("organisation_id", uuid_type, nullable=False),
        sa.Column("provider_key", sa.String(length=40), nullable=False),
        sa.Column("provider_candidate_id", sa.String(length=200), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("normalized_domain", sa.String(length=253), nullable=False),
        sa.Column("website_url", sa.String(length=2048), nullable=False),
        sa.Column("location", sa.String(length=200), nullable=True),
        sa.Column("industry", sa.String(length=120), nullable=True),
        sa.Column("provider_attribution", sa.String(length=120), nullable=False),
        sa.Column("promoted_company_id", uuid_type, nullable=True),
        sa.Column("promoted_by_user_id", uuid_type, nullable=True),
        sa.Column("promoted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("length(trim(name)) > 0", name="ck_prospect_targets_name"),
        sa.CheckConstraint("length(trim(normalized_domain)) > 0", name="ck_prospect_targets_domain"),
        sa.CheckConstraint(
            "(promoted_company_id IS NULL AND promoted_by_user_id IS NULL AND promoted_at IS NULL) OR "
            "(promoted_company_id IS NOT NULL AND promoted_by_user_id IS NOT NULL AND promoted_at IS NOT NULL)",
            name="ck_prospect_targets_promotion",
        ),
        sa.ForeignKeyConstraint(["organisation_id"], ["organisations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["organisation_id", "promoted_company_id"],
            ["companies.organisation_id", "companies.id"],
            name="fk_prospect_targets_company",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organisation_id", "promoted_by_user_id"],
            ["organisation_memberships.organisation_id", "organisation_memberships.user_id"],
            name="fk_prospect_targets_promoter",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organisation_id", "id", name="uq_prospect_targets_org_id"),
        sa.UniqueConstraint("organisation_id", "normalized_domain", name="uq_prospect_targets_org_domain"),
        sa.UniqueConstraint(
            "organisation_id",
            "provider_key",
            "provider_candidate_id",
            name="uq_prospect_targets_provider_candidate",
        ),
    )
    op.create_index(
        "ix_prospect_targets_org_updated",
        "prospect_research_targets",
        ["organisation_id", "updated_at"],
    )
    op.create_index(
        "ix_prospect_targets_org_company",
        "prospect_research_targets",
        ["organisation_id", "promoted_company_id"],
    )

    op.create_table(
        "prospect_research_runs",
        sa.Column("id", uuid_type, nullable=False),
        sa.Column("organisation_id", uuid_type, nullable=False),
        sa.Column("target_id", uuid_type, nullable=False),
        sa.Column("requested_by_user_id", uuid_type, nullable=False),
        sa.Column("refresh_of_run_id", uuid_type, nullable=True),
        sa.Column("status", sa.String(length=24), server_default="pending", nullable=False),
        sa.Column("provider_key", sa.String(length=40), nullable=False),
        sa.Column("provider_version", sa.String(length=80), nullable=False),
        sa.Column("schema_version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("request_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("idempotency_key", sa.String(length=200), nullable=False),
        sa.Column("attempt_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("max_attempts", sa.Integer(), server_default="3", nullable=False),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("worker_id", sa.String(length=200), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error_code", sa.String(length=100), nullable=True),
        sa.Column("last_error_message_safe", sa.String(length=500), nullable=True),
        sa.Column("source_fingerprint", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "status IN ('pending', 'fetching', 'synthesizing', 'completed', 'partial', 'failed')",
            name="ck_prospect_runs_status",
        ),
        sa.CheckConstraint("schema_version > 0", name="ck_prospect_runs_schema_version"),
        sa.CheckConstraint("attempt_count >= 0", name="ck_prospect_runs_attempts"),
        sa.CheckConstraint("max_attempts >= 1", name="ck_prospect_runs_max_attempts"),
        sa.CheckConstraint(
            "last_error_message_safe IS NULL OR length(last_error_message_safe) <= 500",
            name="ck_prospect_runs_error_length",
        ),
        sa.ForeignKeyConstraint(["organisation_id"], ["organisations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["organisation_id", "target_id"],
            ["prospect_research_targets.organisation_id", "prospect_research_targets.id"],
            name="fk_prospect_runs_target",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["organisation_id", "requested_by_user_id"],
            ["organisation_memberships.organisation_id", "organisation_memberships.user_id"],
            name="fk_prospect_runs_requester",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organisation_id", "refresh_of_run_id", "target_id"],
            [
                "prospect_research_runs.organisation_id",
                "prospect_research_runs.id",
                "prospect_research_runs.target_id",
            ],
            name="fk_prospect_runs_refresh",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organisation_id", "id", name="uq_prospect_runs_org_id"),
        sa.UniqueConstraint("organisation_id", "id", "target_id", name="uq_prospect_runs_org_id_target"),
        sa.UniqueConstraint(
            "organisation_id",
            "target_id",
            "idempotency_key",
            name="uq_prospect_runs_idempotency",
        ),
    )
    op.create_index(
        "ix_prospect_runs_org_target_created",
        "prospect_research_runs",
        ["organisation_id", "target_id", "created_at"],
    )
    op.create_index("ix_prospect_runs_org_status", "prospect_research_runs", ["organisation_id", "status"])
    op.create_index("ix_prospect_runs_status_attempt", "prospect_research_runs", ["status", "next_attempt_at"])
    op.create_index("ix_prospect_runs_status_lease", "prospect_research_runs", ["status", "lease_expires_at"])

    op.create_table(
        "prospect_research_sources",
        sa.Column("id", uuid_type, nullable=False),
        sa.Column("organisation_id", uuid_type, nullable=False),
        sa.Column("run_id", uuid_type, nullable=False),
        sa.Column("target_id", uuid_type, nullable=False),
        sa.Column("source_key", sa.String(length=80), nullable=False),
        sa.Column("source_type", sa.String(length=40), nullable=False),
        sa.Column("url", sa.String(length=2048), nullable=False),
        sa.Column("canonical_url", sa.String(length=2048), nullable=False),
        sa.Column("domain", sa.String(length=253), nullable=False),
        sa.Column("title", sa.String(length=300), nullable=False),
        sa.Column("publisher", sa.String(length=200), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("retrieved_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("authority_class", sa.String(length=40), nullable=False),
        sa.Column("provider_source_id", sa.String(length=200), nullable=True),
        sa.Column("content_fingerprint", sa.String(length=64), nullable=False),
        sa.CheckConstraint(
            "source_type IN ('official_website', 'company_newsroom', 'careers_page', "
            "'structured_provider', 'public_filing', 'reputable_news', 'other_public')",
            name="ck_prospect_sources_type",
        ),
        sa.CheckConstraint(
            "authority_class IN ('primary', 'official_public', 'regulatory', 'reputable_secondary', "
            "'structured_provider', 'other_public')",
            name="ck_prospect_sources_authority",
        ),
        sa.ForeignKeyConstraint(["organisation_id"], ["organisations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["organisation_id", "run_id", "target_id"],
            [
                "prospect_research_runs.organisation_id",
                "prospect_research_runs.id",
                "prospect_research_runs.target_id",
            ],
            name="fk_prospect_sources_run",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organisation_id", "id", name="uq_prospect_sources_org_id"),
        sa.UniqueConstraint("organisation_id", "id", "run_id", name="uq_prospect_sources_org_id_run"),
        sa.UniqueConstraint("organisation_id", "run_id", "source_key", name="uq_prospect_sources_run_key"),
        sa.UniqueConstraint("organisation_id", "run_id", "canonical_url", name="uq_prospect_sources_run_url"),
        sa.UniqueConstraint(
            "organisation_id",
            "run_id",
            "content_fingerprint",
            name="uq_prospect_sources_run_fingerprint",
        ),
    )
    op.create_index(
        "ix_prospect_sources_org_run",
        "prospect_research_sources",
        ["organisation_id", "run_id"],
    )

    op.create_table(
        "prospect_research_observations",
        sa.Column("id", uuid_type, nullable=False),
        sa.Column("organisation_id", uuid_type, nullable=False),
        sa.Column("run_id", uuid_type, nullable=False),
        sa.Column("target_id", uuid_type, nullable=False),
        sa.Column("observation_key", sa.String(length=80), nullable=False),
        sa.Column("category", sa.String(length=40), nullable=False),
        sa.Column("statement", sa.String(length=600), nullable=False),
        sa.Column("trust_state", sa.String(length=24), nullable=False),
        sa.Column("relevance", sa.String(length=12), server_default="normal", nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("freshness", sa.String(length=24), nullable=False),
        sa.Column("status", sa.String(length=20), server_default="current", nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "category IN ('company_profile', 'industry', 'location', 'size', 'business_model', "
            "'product_service', 'strategic_initiative', 'expansion', 'hiring', 'leadership_change', "
            "'funding_financial', 'technology', 'regulatory', 'partnership', 'customer_market', "
            "'trigger', 'potential_fit', 'other')",
            name="ck_prospect_observations_category",
        ),
        sa.CheckConstraint(
            "trust_state IN ('verified', 'provider_supplied', 'inferred', 'unknown')",
            name="ck_prospect_observations_trust",
        ),
        sa.CheckConstraint("relevance IN ('high', 'normal')", name="ck_prospect_observations_relevance"),
        sa.CheckConstraint(
            "freshness IN ('stable', 'time_sensitive')",
            name="ck_prospect_observations_freshness",
        ),
        sa.CheckConstraint("status = 'current'", name="ck_prospect_observations_status"),
        sa.CheckConstraint(
            "length(trim(statement)) BETWEEN 1 AND 600",
            name="ck_prospect_observations_statement",
        ),
        sa.ForeignKeyConstraint(["organisation_id"], ["organisations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["organisation_id", "run_id", "target_id"],
            [
                "prospect_research_runs.organisation_id",
                "prospect_research_runs.id",
                "prospect_research_runs.target_id",
            ],
            name="fk_prospect_observations_run",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organisation_id", "id", name="uq_prospect_observations_org_id"),
        sa.UniqueConstraint(
            "organisation_id",
            "id",
            "run_id",
            name="uq_prospect_observations_org_id_run",
        ),
        sa.UniqueConstraint(
            "organisation_id",
            "run_id",
            "observation_key",
            name="uq_prospect_observations_run_key",
        ),
    )
    op.create_index(
        "ix_prospect_observations_org_run",
        "prospect_research_observations",
        ["organisation_id", "run_id"],
    )
    op.create_index(
        "ix_prospect_observations_org_trust",
        "prospect_research_observations",
        ["organisation_id", "trust_state"],
    )

    op.create_table(
        "prospect_research_observation_sources",
        sa.Column("organisation_id", uuid_type, nullable=False),
        sa.Column("observation_id", uuid_type, nullable=False),
        sa.Column("source_id", uuid_type, nullable=False),
        sa.Column("run_id", uuid_type, nullable=False),
        sa.ForeignKeyConstraint(["organisation_id"], ["organisations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["organisation_id", "observation_id", "run_id"],
            [
                "prospect_research_observations.organisation_id",
                "prospect_research_observations.id",
                "prospect_research_observations.run_id",
            ],
            name="fk_prospect_observation_sources_observation",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["organisation_id", "source_id", "run_id"],
            [
                "prospect_research_sources.organisation_id",
                "prospect_research_sources.id",
                "prospect_research_sources.run_id",
            ],
            name="fk_prospect_observation_sources_source",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("organisation_id", "observation_id", "source_id"),
    )
    op.create_index(
        "ix_prospect_observation_sources_org_run",
        "prospect_research_observation_sources",
        ["organisation_id", "run_id"],
    )

    _enable_tenant_rls()
    if op.get_bind().dialect.name == "postgresql":
        op.execute(
            """
            CREATE FUNCTION public.revenueos_prospect_worker_eligible_organisations(
                eligible_at timestamptz,
                result_limit integer
            )
            RETURNS TABLE (organisation_id uuid)
            LANGUAGE sql
            SECURITY DEFINER
            SET search_path = pg_catalog, public
            AS $$
                SELECT DISTINCT prospect_research_runs.organisation_id
                FROM public.prospect_research_runs
                WHERE (
                    prospect_research_runs.status = 'pending'
                    AND prospect_research_runs.attempt_count < prospect_research_runs.max_attempts
                    AND (
                        prospect_research_runs.next_attempt_at IS NULL
                        OR prospect_research_runs.next_attempt_at <= eligible_at
                    )
                ) OR (
                    prospect_research_runs.status IN ('fetching', 'synthesizing')
                    AND prospect_research_runs.lease_expires_at IS NOT NULL
                    AND prospect_research_runs.lease_expires_at <= eligible_at
                )
                ORDER BY prospect_research_runs.organisation_id
                LIMIT LEAST(GREATEST(result_limit, 1), 1000)
            $$
            """
        )


def downgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        op.execute(
            """DROP FUNCTION IF EXISTS
            public.revenueos_prospect_worker_eligible_organisations(timestamptz, integer)"""
        )
    for table_name in reversed(TENANT_TABLES):
        op.drop_table(table_name)
    with op.batch_alter_table("companies") as batch:
        batch.drop_index("ix_companies_organisation_domain")
        batch.drop_column("normalized_domain")
