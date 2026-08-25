"""Add company-scoped Prospect Person intelligence.

Revision ID: 0036_prospect_people
Revises: 0035_prospect_research

WO-027 reuses the immutable Prospect run/source/observation pipeline while keeping
unpromoted people, buying-role hypotheses and business contact provenance separate
from canonical Contacts and customer Evidence.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0036_prospect_people"
down_revision: str | None = "0035_prospect_research"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

NEW_TENANT_TABLES = (
    "prospect_people",
    "prospect_buying_role_hypotheses",
    "prospect_buying_role_sources",
    "prospect_contact_points",
    "contact_field_sources",
)

PERSON_SOURCE_TYPES = (
    "'official_website', 'company_newsroom', 'careers_page', 'structured_provider', "
    "'public_filing', 'reputable_news', 'other_public', 'company_leadership', "
    "'professional_profile', 'professional_article', 'professional_post', 'interview', "
    "'conference', 'association', 'contact_provider', 'company_contact_page'"
)

PERSON_OBSERVATION_CATEGORIES = (
    "'company_profile', 'industry', 'location', 'size', 'business_model', 'product_service', "
    "'strategic_initiative', 'expansion', 'hiring', 'leadership_change', 'funding_financial', "
    "'technology', 'regulatory', 'partnership', 'customer_market', 'trigger', 'potential_fit', "
    "'current_role', 'current_company', 'career_history', 'responsibility', 'expertise', "
    "'professional_interest', 'professional_activity', 'company_initiative', 'public_statement', "
    "'authored_content', 'conference_activity', 'why_person_matters', 'conversation_context', "
    "'other_professional', 'other'"
)


def _enable_rls() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return
    for table_name in NEW_TENANT_TABLES:
        op.execute(f"ALTER TABLE {table_name} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table_name} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"""CREATE POLICY {table_name}_tenant_isolation
            ON {table_name}
            USING (organisation_id = NULLIF(current_setting('app.organisation_id', true), '')::uuid)
            WITH CHECK (organisation_id = NULLIF(current_setting('app.organisation_id', true), '')::uuid)"""
        )


def upgrade() -> None:
    uuid_type = sa.Uuid(as_uuid=True)

    with op.batch_alter_table("prospect_usage_counters") as batch:
        batch.add_column(sa.Column("people_discovery_count", sa.Integer(), server_default="0", nullable=False))
        batch.create_check_constraint(
            "ck_prospect_people_discovery_count",
            "people_discovery_count >= 0",
        )

    with op.batch_alter_table("contacts") as batch:
        batch.alter_column("email", existing_type=sa.String(length=320), nullable=True)

    op.create_table(
        "prospect_people",
        sa.Column("id", uuid_type, nullable=False),
        sa.Column("organisation_id", uuid_type, nullable=False),
        sa.Column("target_id", uuid_type, nullable=False),
        sa.Column("provider_key", sa.String(length=40), nullable=False),
        sa.Column("provider_person_id", sa.String(length=200), nullable=False),
        sa.Column("display_name", sa.String(length=200), nullable=False),
        sa.Column("first_name", sa.String(length=100), nullable=False),
        sa.Column("last_name", sa.String(length=100), nullable=False),
        sa.Column("current_role", sa.String(length=200), nullable=False),
        sa.Column("current_company", sa.String(length=200), nullable=False),
        sa.Column("public_professional_location", sa.String(length=200), nullable=True),
        sa.Column("public_profile_url", sa.String(length=2048), nullable=True),
        sa.Column("relevant_function", sa.String(length=80), nullable=False),
        sa.Column("why_may_matter", sa.String(length=600), nullable=False),
        sa.Column("discovery_source", sa.String(length=80), nullable=False),
        sa.Column("provider_attribution", sa.String(length=120), nullable=False),
        sa.Column("identity_state", sa.String(length=20), server_default="supported", nullable=False),
        sa.Column("employment_state", sa.String(length=24), server_default="current", nullable=False),
        sa.Column("promoted_contact_id", uuid_type, nullable=True),
        sa.Column("promoted_by_user_id", uuid_type, nullable=True),
        sa.Column("promoted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("length(trim(display_name)) > 0", name="ck_prospect_people_name"),
        sa.CheckConstraint("length(trim(first_name)) > 0", name="ck_prospect_people_first_name"),
        sa.CheckConstraint("length(trim(last_name)) > 0", name="ck_prospect_people_last_name"),
        sa.CheckConstraint(
            "identity_state IN ('supported', 'ambiguous')",
            name="ck_prospect_people_identity_state",
        ),
        sa.CheckConstraint(
            "employment_state IN ('current', 'uncertain', 'no_longer_current')",
            name="ck_prospect_people_employment_state",
        ),
        sa.CheckConstraint(
            "(promoted_contact_id IS NULL AND promoted_by_user_id IS NULL AND promoted_at IS NULL) OR "
            "(promoted_contact_id IS NOT NULL AND promoted_by_user_id IS NOT NULL AND promoted_at IS NOT NULL)",
            name="ck_prospect_people_promotion",
        ),
        sa.ForeignKeyConstraint(["organisation_id"], ["organisations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["organisation_id", "target_id"],
            ["prospect_research_targets.organisation_id", "prospect_research_targets.id"],
            name="fk_prospect_people_target",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["organisation_id", "promoted_contact_id"],
            ["contacts.organisation_id", "contacts.id"],
            name="fk_prospect_people_contact",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organisation_id", "promoted_by_user_id"],
            ["organisation_memberships.organisation_id", "organisation_memberships.user_id"],
            name="fk_prospect_people_promoter",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organisation_id", "id", name="uq_prospect_people_org_id"),
        sa.UniqueConstraint("organisation_id", "id", "target_id", name="uq_prospect_people_org_id_target"),
        sa.UniqueConstraint(
            "organisation_id",
            "target_id",
            "provider_key",
            "provider_person_id",
            name="uq_prospect_people_provider_identity",
        ),
    )
    op.create_index("ix_prospect_people_org_target", "prospect_people", ["organisation_id", "target_id"])
    op.create_index("ix_prospect_people_org_contact", "prospect_people", ["organisation_id", "promoted_contact_id"])
    op.create_index("ix_prospect_people_org_name", "prospect_people", ["organisation_id", "display_name"])

    with op.batch_alter_table("prospect_research_runs") as batch:
        batch.add_column(sa.Column("person_id", uuid_type, nullable=True))
        batch.create_foreign_key(
            "fk_prospect_runs_person",
            "prospect_people",
            ["organisation_id", "person_id", "target_id"],
            ["organisation_id", "id", "target_id"],
            ondelete="CASCADE",
        )
        batch.create_index(
            "ix_prospect_runs_org_person_created",
            ["organisation_id", "person_id", "created_at"],
        )

    with op.batch_alter_table("prospect_research_sources") as batch:
        batch.drop_constraint("ck_prospect_sources_type", type_="check")
        batch.create_check_constraint("ck_prospect_sources_type", f"source_type IN ({PERSON_SOURCE_TYPES})")

    with op.batch_alter_table("prospect_research_observations") as batch:
        batch.drop_constraint("ck_prospect_observations_category", type_="check")
        batch.create_check_constraint(
            "ck_prospect_observations_category",
            f"category IN ({PERSON_OBSERVATION_CATEGORIES})",
        )

    op.create_table(
        "prospect_buying_role_hypotheses",
        sa.Column("id", uuid_type, nullable=False),
        sa.Column("organisation_id", uuid_type, nullable=False),
        sa.Column("target_id", uuid_type, nullable=False),
        sa.Column("person_id", uuid_type, nullable=False),
        sa.Column("run_id", uuid_type, nullable=False),
        sa.Column("hypothesized_role", sa.String(length=40), nullable=False),
        sa.Column("rationale", sa.String(length=600), nullable=False),
        sa.Column("trust_state", sa.String(length=24), nullable=False),
        sa.Column("review_state", sa.String(length=24), server_default="needs_validation", nullable=False),
        sa.Column("assessment_origin", sa.String(length=24), server_default="system_hypothesis", nullable=False),
        sa.Column("reviewed_by_user_id", uuid_type, nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "hypothesized_role IN ('executive_sponsor', 'economic_buyer_candidate', 'champion_candidate', "
            "'business_buyer', 'technical_evaluator', 'security', 'procurement', 'legal', 'finance', "
            "'end_user_influencer', 'other_relevant')",
            name="ck_prospect_buying_roles_role",
        ),
        sa.CheckConstraint(
            "trust_state IN ('verified', 'provider_supplied', 'inferred', 'unknown')",
            name="ck_prospect_buying_roles_trust",
        ),
        sa.CheckConstraint(
            "review_state IN ('needs_validation', 'relevant', 'not_relevant')",
            name="ck_prospect_buying_roles_review",
        ),
        sa.CheckConstraint(
            "assessment_origin IN ('system_hypothesis', 'seller_assessed')",
            name="ck_prospect_buying_roles_origin",
        ),
        sa.CheckConstraint(
            "length(trim(rationale)) BETWEEN 1 AND 600",
            name="ck_prospect_buying_roles_rationale",
        ),
        sa.ForeignKeyConstraint(["organisation_id"], ["organisations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["organisation_id", "person_id", "target_id"],
            ["prospect_people.organisation_id", "prospect_people.id", "prospect_people.target_id"],
            name="fk_prospect_buying_roles_person",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["organisation_id", "run_id", "target_id"],
            [
                "prospect_research_runs.organisation_id",
                "prospect_research_runs.id",
                "prospect_research_runs.target_id",
            ],
            name="fk_prospect_buying_roles_run",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["organisation_id", "reviewed_by_user_id"],
            ["organisation_memberships.organisation_id", "organisation_memberships.user_id"],
            name="fk_prospect_buying_roles_reviewer",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organisation_id", "id", name="uq_prospect_buying_roles_org_id"),
        sa.UniqueConstraint(
            "organisation_id",
            "run_id",
            "person_id",
            "hypothesized_role",
            name="uq_prospect_buying_roles_run_role",
        ),
    )
    op.create_index(
        "ix_prospect_buying_roles_org_person",
        "prospect_buying_role_hypotheses",
        ["organisation_id", "person_id"],
    )

    op.create_table(
        "prospect_buying_role_sources",
        sa.Column("organisation_id", uuid_type, nullable=False),
        sa.Column("hypothesis_id", uuid_type, nullable=False),
        sa.Column("source_id", uuid_type, nullable=False),
        sa.Column("run_id", uuid_type, nullable=False),
        sa.ForeignKeyConstraint(["organisation_id"], ["organisations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["organisation_id", "hypothesis_id"],
            ["prospect_buying_role_hypotheses.organisation_id", "prospect_buying_role_hypotheses.id"],
            name="fk_prospect_buying_role_sources_hypothesis",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["organisation_id", "source_id", "run_id"],
            [
                "prospect_research_sources.organisation_id",
                "prospect_research_sources.id",
                "prospect_research_sources.run_id",
            ],
            name="fk_prospect_buying_role_sources_source",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("organisation_id", "hypothesis_id", "source_id"),
    )
    op.create_index(
        "ix_prospect_buying_role_sources_org_run",
        "prospect_buying_role_sources",
        ["organisation_id", "run_id"],
    )

    op.create_table(
        "prospect_contact_points",
        sa.Column("id", uuid_type, nullable=False),
        sa.Column("organisation_id", uuid_type, nullable=False),
        sa.Column("target_id", uuid_type, nullable=False),
        sa.Column("person_id", uuid_type, nullable=False),
        sa.Column("run_id", uuid_type, nullable=False),
        sa.Column("source_id", uuid_type, nullable=False),
        sa.Column("point_type", sa.String(length=40), nullable=False),
        sa.Column("value", sa.String(length=2048), nullable=False),
        sa.Column("value_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("trust_state", sa.String(length=24), nullable=False),
        sa.Column("verification_method", sa.String(length=40), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("export_allowed", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "point_type IN ('business_email', 'business_phone', 'company_switchboard', 'public_professional_profile')",
            name="ck_prospect_contact_points_type",
        ),
        sa.CheckConstraint(
            "trust_state IN ('verified', 'provider_supplied', 'inferred', 'unknown')",
            name="ck_prospect_contact_points_trust",
        ),
        sa.CheckConstraint(
            "verification_method IN ('authoritative_public', 'provider_reported', 'not_verified')",
            name="ck_prospect_contact_points_verification",
        ),
        sa.CheckConstraint(
            "length(trim(value)) BETWEEN 1 AND 2048",
            name="ck_prospect_contact_points_value",
        ),
        sa.ForeignKeyConstraint(["organisation_id"], ["organisations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["organisation_id", "person_id", "target_id"],
            ["prospect_people.organisation_id", "prospect_people.id", "prospect_people.target_id"],
            name="fk_prospect_contact_points_person",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["organisation_id", "run_id", "target_id"],
            [
                "prospect_research_runs.organisation_id",
                "prospect_research_runs.id",
                "prospect_research_runs.target_id",
            ],
            name="fk_prospect_contact_points_run",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["organisation_id", "source_id", "run_id"],
            [
                "prospect_research_sources.organisation_id",
                "prospect_research_sources.id",
                "prospect_research_sources.run_id",
            ],
            name="fk_prospect_contact_points_source",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organisation_id", "id", name="uq_prospect_contact_points_org_id"),
        sa.UniqueConstraint(
            "organisation_id",
            "run_id",
            "person_id",
            "point_type",
            "value_fingerprint",
            name="uq_prospect_contact_points_run_value",
        ),
    )
    op.create_index(
        "ix_prospect_contact_points_org_person",
        "prospect_contact_points",
        ["organisation_id", "person_id"],
    )
    op.create_index(
        "ix_prospect_contact_points_org_fingerprint",
        "prospect_contact_points",
        ["organisation_id", "point_type", "value_fingerprint"],
    )

    op.create_table(
        "contact_field_sources",
        sa.Column("id", uuid_type, nullable=False),
        sa.Column("organisation_id", uuid_type, nullable=False),
        sa.Column("contact_id", uuid_type, nullable=False),
        sa.Column("field_key", sa.String(length=40), nullable=False),
        sa.Column("value_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("source_type", sa.String(length=40), server_default="prospect_person", nullable=False),
        sa.Column("source_organisation_id", uuid_type, nullable=True),
        sa.Column("source_prospect_person_id", uuid_type, nullable=True),
        sa.Column("provider_key", sa.String(length=40), nullable=False),
        sa.Column("trust_state", sa.String(length=24), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "field_key IN ('email', 'phone', 'job_title', 'linkedin_url')",
            name="ck_contact_field_sources_field",
        ),
        sa.CheckConstraint(
            "trust_state IN ('verified', 'provider_supplied', 'inferred', 'unknown')",
            name="ck_contact_field_sources_trust",
        ),
        sa.CheckConstraint("source_type = 'prospect_person'", name="ck_contact_field_sources_type"),
        sa.CheckConstraint(
            "source_organisation_id IS NULL OR source_organisation_id = organisation_id",
            name="ck_contact_field_sources_tenant",
        ),
        sa.ForeignKeyConstraint(["organisation_id"], ["organisations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["organisation_id", "contact_id"],
            ["contacts.organisation_id", "contacts.id"],
            name="fk_contact_field_sources_contact",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["source_organisation_id", "source_prospect_person_id"],
            ["prospect_people.organisation_id", "prospect_people.id"],
            name="fk_contact_field_sources_person",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organisation_id", "id", name="uq_contact_field_sources_org_id"),
        sa.UniqueConstraint(
            "organisation_id",
            "contact_id",
            "field_key",
            "value_fingerprint",
            name="uq_contact_field_sources_value",
        ),
    )
    op.create_index(
        "ix_contact_field_sources_org_contact",
        "contact_field_sources",
        ["organisation_id", "contact_id"],
    )

    _enable_rls()


def downgrade() -> None:
    for table_name in (
        "contact_field_sources",
        "prospect_contact_points",
        "prospect_buying_role_sources",
        "prospect_buying_role_hypotheses",
    ):
        op.drop_table(table_name)

    with op.batch_alter_table("prospect_research_observations") as batch:
        batch.drop_constraint("ck_prospect_observations_category", type_="check")
        batch.create_check_constraint(
            "ck_prospect_observations_category",
            "category IN ('company_profile', 'industry', 'location', 'size', 'business_model', "
            "'product_service', 'strategic_initiative', 'expansion', 'hiring', 'leadership_change', "
            "'funding_financial', 'technology', 'regulatory', 'partnership', 'customer_market', "
            "'trigger', 'potential_fit', 'other')",
        )

    with op.batch_alter_table("prospect_research_sources") as batch:
        batch.drop_constraint("ck_prospect_sources_type", type_="check")
        batch.create_check_constraint(
            "ck_prospect_sources_type",
            "source_type IN ('official_website', 'company_newsroom', 'careers_page', "
            "'structured_provider', 'public_filing', 'reputable_news', 'other_public')",
        )

    with op.batch_alter_table("prospect_research_runs") as batch:
        batch.drop_index("ix_prospect_runs_org_person_created")
        batch.drop_constraint("fk_prospect_runs_person", type_="foreignkey")
        batch.drop_column("person_id")

    op.drop_table("prospect_people")

    with op.batch_alter_table("contacts") as batch:
        batch.alter_column("email", existing_type=sa.String(length=320), nullable=False)

    with op.batch_alter_table("prospect_usage_counters") as batch:
        batch.drop_constraint("ck_prospect_people_discovery_count", type_="check")
        batch.drop_column("people_discovery_count")
