"""Add tenant-isolated Event Intelligence foundations.

Revision ID: 0040_event_intelligence
Revises: 0039_campaign_sequences

WO-031 adds bounded business Events, deliberately supplied attendee-list
imports, explainable matching and planning, seller-reported encounters, and
explicit links to existing Interactions, Contacts and Engage Campaigns.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0040_event_intelligence"
down_revision: str | None = "0039_campaign_sequences"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TENANT_TABLES = (
    "sales_events",
    "event_attendee_imports",
    "event_attendees",
    "event_attendee_user_states",
    "event_encounters",
    "event_campaign_links",
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


def _drop_campaign_version_guard() -> None:
    if op.get_bind().dialect.name == "sqlite":
        op.execute("DROP TRIGGER engage_campaign_versions_immutable_update")
        op.execute("DROP TRIGGER engage_sequence_steps_immutable_update")
        op.execute("DROP TRIGGER engage_campaign_audience_immutable_update")


def _create_campaign_version_guard() -> None:
    if op.get_bind().dialect.name == "sqlite":
        op.execute(
            """CREATE TRIGGER engage_campaign_versions_immutable_update
            BEFORE UPDATE ON engage_campaign_versions
            FOR EACH ROW WHEN OLD.status = 'published'
            BEGIN SELECT RAISE(ABORT, 'Published campaign versions are immutable'); END"""
        )
        op.execute(
            """CREATE TRIGGER engage_sequence_steps_immutable_update
            BEFORE UPDATE ON engage_sequence_steps
            FOR EACH ROW WHEN (SELECT status FROM engage_campaign_versions
                WHERE organisation_id = OLD.organisation_id AND id = OLD.campaign_version_id) = 'published'
            BEGIN SELECT RAISE(ABORT, 'Published campaign audience and sequence are immutable'); END"""
        )
        op.execute(
            """CREATE TRIGGER engage_campaign_audience_immutable_update
            BEFORE UPDATE ON engage_campaign_audience
            FOR EACH ROW WHEN (SELECT status FROM engage_campaign_versions
                WHERE organisation_id = OLD.organisation_id AND id = OLD.campaign_version_id) = 'published'
                AND NOT (
                    OLD.contact_id IS NOT NULL AND NEW.contact_id IS NULL
                    AND OLD.campaign_version_id IS NEW.campaign_version_id
                    AND OLD.company_id IS NEW.company_id
                    AND OLD.recipient_name IS NEW.recipient_name
                    AND OLD.recipient_email IS NEW.recipient_email
                    AND OLD.recipient_trust IS NEW.recipient_trust
                    AND OLD.eligible IS NEW.eligible
                    AND OLD.eligibility_code IS NEW.eligibility_code
                    AND OLD.eligibility_reason IS NEW.eligibility_reason
                )
            BEGIN SELECT RAISE(ABORT, 'Published campaign audience and sequence are immutable'); END"""
        )


def _create_outreach_source_guard() -> None:
    """Restore the SQLite trigger lost when batch mode recreates the table."""
    if op.get_bind().dialect.name == "sqlite":
        op.execute(
            """CREATE TRIGGER outreach_personalization_sources_immutable_update
            BEFORE UPDATE ON outreach_personalization_sources
            FOR EACH ROW
            BEGIN
                SELECT RAISE(ABORT, 'Outreach versions and provenance are immutable');
            END"""
        )


def _expand_source_checks() -> None:
    with op.batch_alter_table("contact_field_sources") as batch:
        batch.drop_constraint("ck_contact_field_sources_type", type_="check")
        batch.create_check_constraint(
            "ck_contact_field_sources_type", "source_type IN ('prospect_person', 'event_list')"
        )
    with op.batch_alter_table("outreach_personalization_sources") as batch:
        batch.drop_constraint("ck_outreach_sources_type", type_="check")
        batch.drop_constraint("ck_outreach_sources_trust", type_="check")
        batch.create_check_constraint(
            "ck_outreach_sources_type",
            "source_type IN ('prospect_observation', 'prospect_person_observation', "
            "'approved_seller_context', 'event_attendance', 'event_encounter')",
        )
        batch.create_check_constraint(
            "ck_outreach_sources_trust",
            "trust_state IN ('verified', 'provider_supplied', 'approved', 'seller_reported')",
        )
    _create_outreach_source_guard()
    _drop_campaign_version_guard()
    with op.batch_alter_table("engage_campaign_versions") as batch:
        batch.drop_constraint("ck_engage_campaign_versions_source", type_="check")
        batch.create_check_constraint(
            "ck_engage_campaign_versions_source",
            "source_type IN ('manual_contacts', 'target_market', 'event_attendees')",
        )
    _create_campaign_version_guard()


def upgrade() -> None:
    uuid_type = sa.Uuid(as_uuid=True)
    _expand_source_checks()

    op.create_table(
        "sales_events",
        sa.Column("id", uuid_type, nullable=False),
        sa.Column("organisation_id", uuid_type, nullable=False),
        sa.Column("owner_user_id", uuid_type, nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("event_type", sa.String(length=40), nullable=False),
        sa.Column("start_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("timezone", sa.String(length=64), nullable=False),
        sa.Column("location_name", sa.String(length=200), nullable=True),
        sa.Column("city", sa.String(length=120), nullable=True),
        sa.Column("country", sa.String(length=100), nullable=True),
        sa.Column("event_url", sa.String(length=1000), nullable=True),
        sa.Column("organiser", sa.String(length=160), nullable=True),
        sa.Column("description", sa.String(length=1000), nullable=True),
        sa.Column("goal_type", sa.String(length=40), nullable=True),
        sa.Column("goal_detail", sa.String(length=300), nullable=True),
        sa.Column("source_type", sa.String(length=20), server_default="manual", nullable=False),
        sa.Column("state", sa.String(length=20), server_default="upcoming", nullable=False),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("length(trim(name)) BETWEEN 1 AND 160", name="ck_sales_events_name"),
        sa.CheckConstraint(
            "event_type IN ('conference', 'trade_show', 'networking_event', 'customer_event', "
            "'partner_event', 'industry_event', 'executive_roundtable', 'internal_hosted_event', "
            "'other_business_event')",
            name="ck_sales_events_type",
        ),
        sa.CheckConstraint(
            "state IN ('draft', 'upcoming', 'active', 'completed', 'archived')",
            name="ck_sales_events_state",
        ),
        sa.CheckConstraint(
            "goal_type IS NULL OR goal_type IN ('meet_new_prospects', 'progress_active_opportunities', "
            "'meet_strategic_accounts', 'reconnect_existing_contacts', 'find_partners', 'other')",
            name="ck_sales_events_goal",
        ),
        sa.CheckConstraint("end_at >= start_at", name="ck_sales_events_range"),
        sa.CheckConstraint("length(trim(timezone)) BETWEEN 1 AND 64", name="ck_sales_events_timezone"),
        sa.CheckConstraint("description IS NULL OR length(description) <= 1000", name="ck_sales_events_description"),
        sa.CheckConstraint("goal_detail IS NULL OR length(goal_detail) <= 300", name="ck_sales_events_goal_detail"),
        sa.CheckConstraint("source_type = 'manual'", name="ck_sales_events_source"),
        sa.ForeignKeyConstraint(["organisation_id"], ["organisations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["organisation_id", "owner_user_id"],
            ["organisation_memberships.organisation_id", "organisation_memberships.user_id"],
            name="fk_sales_events_owner",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organisation_id", "id", name="uq_sales_events_org_id"),
    )
    op.create_index("ix_sales_events_org_time", "sales_events", ["organisation_id", "start_at", "end_at"])
    op.create_index("ix_sales_events_org_state", "sales_events", ["organisation_id", "state", "start_at"])
    op.create_index("ix_sales_events_org_owner", "sales_events", ["organisation_id", "owner_user_id", "start_at"])

    op.create_table(
        "event_attendee_imports",
        sa.Column("id", uuid_type, nullable=False),
        sa.Column("organisation_id", uuid_type, nullable=False),
        sa.Column("event_id", uuid_type, nullable=False),
        sa.Column("requested_by_user_id", uuid_type, nullable=False),
        sa.Column("state", sa.String(length=20), server_default="previewed", nullable=False),
        sa.Column("display_filename", sa.String(length=255), nullable=False),
        sa.Column("file_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("file_size_bytes", sa.Integer(), nullable=False),
        sa.Column("row_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("valid_row_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("imported_row_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("column_mapping_json", sa.JSON(), nullable=False),
        sa.Column("recognised_columns_json", sa.JSON(), nullable=False),
        sa.Column("ignored_columns_json", sa.JSON(), nullable=False),
        sa.Column("issues_json", sa.JSON(), nullable=False),
        sa.Column("preview_rows_json", sa.JSON(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("attestation_version", sa.Integer(), nullable=True),
        sa.Column("attested_by_user_id", uuid_type, nullable=True),
        sa.Column("attested_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("state IN ('previewed', 'confirmed', 'expired', 'failed')", name="ck_event_imports_state"),
        sa.CheckConstraint("length(file_fingerprint) = 64", name="ck_event_imports_fingerprint"),
        sa.CheckConstraint("row_count BETWEEN 0 AND 500", name="ck_event_imports_rows"),
        sa.CheckConstraint("valid_row_count BETWEEN 0 AND 500", name="ck_event_imports_valid_rows"),
        sa.CheckConstraint("imported_row_count BETWEEN 0 AND 500", name="ck_event_imports_imported_rows"),
        sa.CheckConstraint(
            "attestation_version IS NULL OR attestation_version = 1", name="ck_event_imports_attestation"
        ),
        sa.ForeignKeyConstraint(["organisation_id"], ["organisations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["organisation_id", "event_id"],
            ["sales_events.organisation_id", "sales_events.id"],
            name="fk_event_imports_event",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["organisation_id", "requested_by_user_id"],
            ["organisation_memberships.organisation_id", "organisation_memberships.user_id"],
            name="fk_event_imports_requester",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organisation_id", "attested_by_user_id"],
            ["organisation_memberships.organisation_id", "organisation_memberships.user_id"],
            name="fk_event_imports_attester",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organisation_id", "id", name="uq_event_imports_org_id"),
        sa.UniqueConstraint("organisation_id", "event_id", "id", name="uq_event_imports_org_event_id"),
        sa.UniqueConstraint("organisation_id", "event_id", "file_fingerprint", name="uq_event_imports_org_event_file"),
    )
    op.create_index(
        "ix_event_imports_org_event", "event_attendee_imports", ["organisation_id", "event_id", "created_at"]
    )
    op.create_index("ix_event_imports_org_expiry", "event_attendee_imports", ["organisation_id", "state", "expires_at"])

    op.create_table(
        "event_attendees",
        sa.Column("id", uuid_type, nullable=False),
        sa.Column("organisation_id", uuid_type, nullable=False),
        sa.Column("event_id", uuid_type, nullable=False),
        sa.Column("import_id", uuid_type, nullable=False),
        sa.Column("first_name", sa.String(length=100), nullable=True),
        sa.Column("last_name", sa.String(length=100), nullable=True),
        sa.Column("company_name", sa.String(length=200), nullable=True),
        sa.Column("job_title", sa.String(length=200), nullable=True),
        sa.Column("business_email", sa.String(length=320), nullable=True),
        sa.Column("normalised_business_email", sa.String(length=320), nullable=True),
        sa.Column("country_or_location", sa.String(length=200), nullable=True),
        sa.Column("profile_url", sa.String(length=1000), nullable=True),
        sa.Column("normalised_profile_url", sa.String(length=1000), nullable=True),
        sa.Column("company_domain", sa.String(length=253), nullable=True),
        sa.Column("registration_category", sa.String(length=80), nullable=True),
        sa.Column("source_row", sa.Integer(), nullable=False),
        sa.Column("source_type", sa.String(length=24), server_default="event_list", nullable=False),
        sa.Column("email_trust_state", sa.String(length=24), server_default="unknown", nullable=False),
        sa.Column("contact_id", uuid_type, nullable=True),
        sa.Column("company_id", uuid_type, nullable=True),
        sa.Column("prospect_person_id", uuid_type, nullable=True),
        sa.Column("match_state", sa.String(length=32), server_default="unmatched", nullable=False),
        sa.Column("priority_state", sa.String(length=32), server_default="needs_more_information", nullable=False),
        sa.Column("priority_reasons_json", sa.JSON(), server_default=sa.text("'[]'"), nullable=False),
        sa.Column("active_opportunity_id", uuid_type, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "COALESCE(length(trim(normalised_business_email)), 0) > 0 OR "
            "(COALESCE(length(trim(first_name)), 0) > 0 AND COALESCE(length(trim(company_name)), 0) > 0)",
            name="ck_event_attendees_identity",
        ),
        sa.CheckConstraint("source_type = 'event_list'", name="ck_event_attendees_source"),
        sa.CheckConstraint(
            "email_trust_state IN ('provider_supplied', 'unknown')", name="ck_event_attendees_email_trust"
        ),
        sa.CheckConstraint(
            "match_state IN ('matched_contact', 'matched_prospect_person', 'matched_company', "
            "'possible_match', 'unmatched')",
            name="ck_event_attendees_match",
        ),
        sa.CheckConstraint(
            "priority_state IN ('priority_to_meet', 'worth_meeting', 'context_only', 'needs_more_information')",
            name="ck_event_attendees_priority",
        ),
        sa.ForeignKeyConstraint(["organisation_id"], ["organisations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["organisation_id", "event_id"],
            ["sales_events.organisation_id", "sales_events.id"],
            name="fk_event_attendees_event",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["organisation_id", "event_id", "import_id"],
            ["event_attendee_imports.organisation_id", "event_attendee_imports.event_id", "event_attendee_imports.id"],
            name="fk_event_attendees_import",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["organisation_id", "contact_id"],
            ["contacts.organisation_id", "contacts.id"],
            name="fk_event_attendees_contact",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organisation_id", "company_id"],
            ["companies.organisation_id", "companies.id"],
            name="fk_event_attendees_company",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organisation_id", "prospect_person_id"],
            ["prospect_people.organisation_id", "prospect_people.id"],
            name="fk_event_attendees_person",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organisation_id", "active_opportunity_id"],
            ["opportunities.organisation_id", "opportunities.id"],
            name="fk_event_attendees_opportunity",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organisation_id", "id", name="uq_event_attendees_org_id"),
        sa.UniqueConstraint("organisation_id", "event_id", "id", name="uq_event_attendees_org_event_id"),
        sa.UniqueConstraint(
            "organisation_id", "event_id", "normalised_business_email", name="uq_event_attendees_org_event_email"
        ),
        sa.UniqueConstraint(
            "organisation_id", "event_id", "normalised_profile_url", name="uq_event_attendees_org_event_profile"
        ),
        sa.UniqueConstraint(
            "organisation_id", "event_id", "import_id", "source_row", name="uq_event_attendees_import_row"
        ),
    )
    op.create_index(
        "ix_event_attendees_org_event_name",
        "event_attendees",
        ["organisation_id", "event_id", "last_name", "first_name"],
    )
    op.create_index(
        "ix_event_attendees_org_event_company", "event_attendees", ["organisation_id", "event_id", "company_name"]
    )
    op.create_index(
        "ix_event_attendees_org_event_priority", "event_attendees", ["organisation_id", "event_id", "priority_state"]
    )
    op.create_index("ix_event_attendees_org_contact", "event_attendees", ["organisation_id", "contact_id"])

    op.create_table(
        "event_attendee_user_states",
        sa.Column("id", uuid_type, nullable=False),
        sa.Column("organisation_id", uuid_type, nullable=False),
        sa.Column("event_id", uuid_type, nullable=False),
        sa.Column("attendee_id", uuid_type, nullable=False),
        sa.Column("user_id", uuid_type, nullable=False),
        sa.Column("plan_state", sa.String(length=24), server_default="not_planned", nullable=False),
        sa.Column("meeting_arranged", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "plan_state IN ('not_planned', 'planned', 'met', 'follow_up', 'complete', 'not_relevant')",
            name="ck_event_user_states_plan",
        ),
        sa.ForeignKeyConstraint(["organisation_id"], ["organisations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["organisation_id", "event_id"],
            ["sales_events.organisation_id", "sales_events.id"],
            name="fk_event_user_states_event",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["organisation_id", "event_id", "attendee_id"],
            ["event_attendees.organisation_id", "event_attendees.event_id", "event_attendees.id"],
            name="fk_event_user_states_attendee",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["organisation_id", "user_id"],
            ["organisation_memberships.organisation_id", "organisation_memberships.user_id"],
            name="fk_event_user_states_user",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organisation_id", "id", name="uq_event_user_states_org_id"),
        sa.UniqueConstraint(
            "organisation_id", "event_id", "attendee_id", "user_id", name="uq_event_user_states_person"
        ),
    )
    op.create_index(
        "ix_event_user_states_org_event_user",
        "event_attendee_user_states",
        ["organisation_id", "event_id", "user_id", "plan_state"],
    )

    with op.batch_alter_table("interactions") as batch:
        batch.add_column(sa.Column("event_id", uuid_type, nullable=True))
        batch.create_foreign_key(
            "fk_interactions_event_tenant",
            "sales_events",
            ["organisation_id", "event_id"],
            ["organisation_id", "id"],
            ondelete="RESTRICT",
        )
        batch.create_index("ix_interactions_organisation_event", ["organisation_id", "event_id"])

    op.create_table(
        "event_encounters",
        sa.Column("id", uuid_type, nullable=False),
        sa.Column("organisation_id", uuid_type, nullable=False),
        sa.Column("event_id", uuid_type, nullable=False),
        sa.Column("attendee_id", uuid_type, nullable=False),
        sa.Column("user_id", uuid_type, nullable=False),
        sa.Column("state", sa.String(length=20), server_default="met", nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("seller_note", sa.String(length=1000), nullable=True),
        sa.Column("note_origin", sa.String(length=32), server_default="seller_reported_activity", nullable=False),
        sa.Column("interaction_id", uuid_type, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("state IN ('met', 'follow_up', 'complete')", name="ck_event_encounters_state"),
        sa.CheckConstraint("seller_note IS NULL OR length(seller_note) <= 1000", name="ck_event_encounters_note"),
        sa.CheckConstraint("note_origin = 'seller_reported_activity'", name="ck_event_encounters_origin"),
        sa.ForeignKeyConstraint(["organisation_id"], ["organisations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["organisation_id", "event_id"],
            ["sales_events.organisation_id", "sales_events.id"],
            name="fk_event_encounters_event",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["organisation_id", "event_id", "attendee_id"],
            ["event_attendees.organisation_id", "event_attendees.event_id", "event_attendees.id"],
            name="fk_event_encounters_attendee",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["organisation_id", "user_id"],
            ["organisation_memberships.organisation_id", "organisation_memberships.user_id"],
            name="fk_event_encounters_user",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organisation_id", "interaction_id"],
            ["interactions.organisation_id", "interactions.id"],
            name="fk_event_encounters_interaction",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organisation_id", "id", name="uq_event_encounters_org_id"),
        sa.UniqueConstraint("organisation_id", "event_id", "attendee_id", "user_id", name="uq_event_encounters_person"),
    )
    op.create_index(
        "ix_event_encounters_org_event_user",
        "event_encounters",
        ["organisation_id", "event_id", "user_id", "occurred_at"],
    )
    op.create_index("ix_event_encounters_org_interaction", "event_encounters", ["organisation_id", "interaction_id"])

    op.create_table(
        "event_campaign_links",
        sa.Column("id", uuid_type, nullable=False),
        sa.Column("organisation_id", uuid_type, nullable=False),
        sa.Column("event_id", uuid_type, nullable=False),
        sa.Column("campaign_id", uuid_type, nullable=False),
        sa.Column("stage", sa.String(length=20), nullable=False),
        sa.Column("created_by_user_id", uuid_type, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("stage IN ('pre_event', 'post_event')", name="ck_event_campaign_links_stage"),
        sa.ForeignKeyConstraint(["organisation_id"], ["organisations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["organisation_id", "event_id"],
            ["sales_events.organisation_id", "sales_events.id"],
            name="fk_event_campaign_links_event",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["organisation_id", "campaign_id"],
            ["engage_campaigns.organisation_id", "engage_campaigns.id"],
            name="fk_event_campaign_links_campaign",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["organisation_id", "created_by_user_id"],
            ["organisation_memberships.organisation_id", "organisation_memberships.user_id"],
            name="fk_event_campaign_links_creator",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organisation_id", "id", name="uq_event_campaign_links_org_id"),
        sa.UniqueConstraint("organisation_id", "event_id", "campaign_id", name="uq_event_campaign_links_pair"),
    )
    op.create_index(
        "ix_event_campaign_links_org_event", "event_campaign_links", ["organisation_id", "event_id", "created_at"]
    )
    _enable_tenant_rls()


def downgrade() -> None:
    op.execute(
        "DELETE FROM outreach_personalization_sources WHERE source_type IN ('event_attendance', 'event_encounter')"
    )
    op.execute("DELETE FROM contact_field_sources WHERE source_type = 'event_list'")
    op.execute(
        "UPDATE engage_campaign_versions SET source_type = 'manual_contacts' WHERE source_type = 'event_attendees'"
    )

    op.drop_table("event_campaign_links")
    op.drop_table("event_encounters")
    with op.batch_alter_table("interactions") as batch:
        batch.drop_index("ix_interactions_organisation_event")
        batch.drop_constraint("fk_interactions_event_tenant", type_="foreignkey")
        batch.drop_column("event_id")
    op.drop_table("event_attendee_user_states")
    op.drop_table("event_attendees")
    op.drop_table("event_attendee_imports")
    op.drop_table("sales_events")

    with op.batch_alter_table("contact_field_sources") as batch:
        batch.drop_constraint("ck_contact_field_sources_type", type_="check")
        batch.create_check_constraint("ck_contact_field_sources_type", "source_type = 'prospect_person'")
    with op.batch_alter_table("outreach_personalization_sources") as batch:
        batch.drop_constraint("ck_outreach_sources_type", type_="check")
        batch.drop_constraint("ck_outreach_sources_trust", type_="check")
        batch.create_check_constraint(
            "ck_outreach_sources_type",
            "source_type IN ('prospect_observation', 'prospect_person_observation', 'approved_seller_context')",
        )
        batch.create_check_constraint(
            "ck_outreach_sources_trust", "trust_state IN ('verified', 'provider_supplied', 'approved')"
        )
    _create_outreach_source_guard()
    _drop_campaign_version_guard()
    with op.batch_alter_table("engage_campaign_versions") as batch:
        batch.drop_constraint("ck_engage_campaign_versions_source", type_="check")
        batch.create_check_constraint(
            "ck_engage_campaign_versions_source", "source_type IN ('manual_contacts', 'target_market')"
        )
    _create_campaign_version_guard()
