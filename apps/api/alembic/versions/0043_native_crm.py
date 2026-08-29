"""Add the native CRM foundation around canonical sales records.

Revision ID: 0043_native_crm
Revises: 0042_roi_business_case

WO-034 deliberately reuses Company, Contact and Opportunity. The new tables hold
organisation CRM policy, bounded custom-field definitions/values and readable
record-change history; they do not introduce parallel CRM records.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0043_native_crm"
down_revision: str | None = "0042_roi_business_case"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TENANT_TABLES = (
    "organisation_crm_settings",
    "crm_custom_field_definitions",
    "crm_custom_field_values",
    "crm_record_changes",
)


def _replace_check(table: str, name: str, expression: str) -> None:
    with op.batch_alter_table(table) as batch:
        batch.drop_constraint(name, type_="check")
        batch.create_check_constraint(name, expression)


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


def _assert_no_strong_duplicates() -> None:
    bind = op.get_bind()
    duplicate_domains = bind.execute(
        sa.text(
            "SELECT COUNT(*) FROM ("
            "SELECT organisation_id, normalized_domain FROM companies "
            "WHERE normalized_domain IS NOT NULL "
            "GROUP BY organisation_id, normalized_domain HAVING COUNT(*) > 1"
            ") duplicates"
        )
    ).scalar_one()
    duplicate_emails = bind.execute(
        sa.text(
            "SELECT COUNT(*) FROM ("
            "SELECT organisation_id, lower(email) AS normalised_email FROM contacts "
            "WHERE email IS NOT NULL "
            "GROUP BY organisation_id, lower(email) HAVING COUNT(*) > 1"
            ") duplicates"
        )
    ).scalar_one()
    if duplicate_domains or duplicate_emails:
        raise RuntimeError(
            "WO-034 migration blocked: resolve duplicate company domains or contact business emails "
            "within each organisation before retrying."
        )


def upgrade() -> None:
    uuid_type = sa.Uuid(as_uuid=True)
    _replace_check(
        "organisation_module_entitlements",
        "ck_module_entitlements_key",
        "module_key IN ('prospect', 'engage', 'create', 'crm')",
    )
    _assert_no_strong_duplicates()

    with op.batch_alter_table("companies") as batch:
        batch.add_column(sa.Column("location", sa.String(length=200), nullable=True))
        batch.add_column(sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True))
    with op.batch_alter_table("contacts") as batch:
        batch.add_column(sa.Column("status", sa.String(length=24), server_default="active", nullable=False))
        batch.add_column(sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True))
        batch.create_check_constraint("ck_contacts_status", "status IN ('active', 'left_company')")
    with op.batch_alter_table("opportunities") as batch:
        batch.add_column(sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True))

    op.create_index(
        "uq_companies_org_normalized_domain",
        "companies",
        ["organisation_id", "normalized_domain"],
        unique=True,
        postgresql_where=sa.text("normalized_domain IS NOT NULL"),
        sqlite_where=sa.text("normalized_domain IS NOT NULL"),
    )
    op.execute(
        "CREATE UNIQUE INDEX uq_contacts_org_business_email "
        "ON contacts (organisation_id, lower(email)) WHERE email IS NOT NULL"
    )
    op.create_index(
        "ix_companies_org_archived",
        "companies",
        ["organisation_id", "archived_at", "name"],
    )
    op.create_index(
        "ix_contacts_org_archived",
        "contacts",
        ["organisation_id", "archived_at", "last_name", "first_name"],
    )
    op.create_index(
        "ix_opportunities_org_archived",
        "opportunities",
        ["organisation_id", "archived_at", "updated_at"],
    )

    op.create_table(
        "organisation_crm_settings",
        sa.Column("organisation_id", uuid_type, nullable=False),
        sa.Column("mode", sa.String(length=20), nullable=False),
        sa.Column("external_provider", sa.String(length=40), nullable=True),
        sa.Column("configured_by_user_id", uuid_type, nullable=False),
        sa.Column("configured_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("mode IN ('native', 'external')", name="ck_organisation_crm_settings_mode"),
        sa.CheckConstraint(
            "(mode = 'native' AND external_provider IS NULL) OR (mode = 'external' AND external_provider = 'hubspot')",
            name="ck_organisation_crm_settings_provider",
        ),
        sa.ForeignKeyConstraint(["organisation_id"], ["organisations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["organisation_id", "configured_by_user_id"],
            ["organisation_memberships.organisation_id", "organisation_memberships.user_id"],
            name="fk_organisation_crm_settings_configurer",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("organisation_id"),
    )

    op.create_table(
        "crm_custom_field_definitions",
        sa.Column("id", uuid_type, nullable=False),
        sa.Column("organisation_id", uuid_type, nullable=False),
        sa.Column("entity_type", sa.String(length=24), nullable=False),
        sa.Column("field_key", sa.String(length=64), nullable=False),
        sa.Column("label", sa.String(length=100), nullable=False),
        sa.Column("field_type", sa.String(length=24), nullable=False),
        sa.Column("options_json", sa.JSON(), server_default="[]", nullable=False),
        sa.Column("active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("display_order", sa.Integer(), server_default="0", nullable=False),
        sa.Column("created_by_user_id", uuid_type, nullable=False),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "entity_type IN ('account', 'contact', 'opportunity')",
            name="ck_crm_custom_fields_entity_type",
        ),
        sa.CheckConstraint(
            "field_type IN ('short_text', 'number', 'date', 'boolean', 'single_select', 'url')",
            name="ck_crm_custom_fields_field_type",
        ),
        sa.CheckConstraint("length(trim(field_key)) BETWEEN 1 AND 64", name="ck_crm_custom_fields_key"),
        sa.CheckConstraint("length(trim(label)) BETWEEN 1 AND 100", name="ck_crm_custom_fields_label"),
        sa.CheckConstraint("display_order BETWEEN 0 AND 24", name="ck_crm_custom_fields_order"),
        sa.CheckConstraint(
            "(active AND archived_at IS NULL) OR (NOT active AND archived_at IS NOT NULL)",
            name="ck_crm_custom_fields_archive",
        ),
        sa.ForeignKeyConstraint(["organisation_id"], ["organisations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["organisation_id", "created_by_user_id"],
            ["organisation_memberships.organisation_id", "organisation_memberships.user_id"],
            name="fk_crm_custom_fields_creator",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organisation_id", "id", name="uq_crm_custom_fields_org_id"),
        sa.UniqueConstraint("organisation_id", "entity_type", "field_key", name="uq_crm_custom_fields_org_entity_key"),
    )
    op.create_index(
        "ix_crm_custom_fields_org_entity",
        "crm_custom_field_definitions",
        ["organisation_id", "entity_type", "active", "display_order"],
    )

    op.create_table(
        "crm_custom_field_values",
        sa.Column("id", uuid_type, nullable=False),
        sa.Column("organisation_id", uuid_type, nullable=False),
        sa.Column("definition_id", uuid_type, nullable=False),
        sa.Column("entity_type", sa.String(length=24), nullable=False),
        sa.Column("entity_id", uuid_type, nullable=False),
        sa.Column("text_value", sa.String(length=2048), nullable=True),
        sa.Column("number_value", sa.Numeric(precision=18, scale=4), nullable=True),
        sa.Column("date_value", sa.Date(), nullable=True),
        sa.Column("boolean_value", sa.Boolean(), nullable=True),
        sa.Column("source", sa.String(length=32), server_default="manual_user_entry", nullable=False),
        sa.Column("changed_by_user_id", uuid_type, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "entity_type IN ('account', 'contact', 'opportunity')",
            name="ck_crm_custom_values_entity_type",
        ),
        sa.CheckConstraint(
            "source IN ('manual_user_entry', 'crm_import', 'prospect_promotion', "
            "'event_promotion', 'external_crm', 'reviewed_action', 'system')",
            name="ck_crm_custom_values_source",
        ),
        sa.CheckConstraint(
            "(CASE WHEN text_value IS NOT NULL THEN 1 ELSE 0 END + "
            "CASE WHEN number_value IS NOT NULL THEN 1 ELSE 0 END + "
            "CASE WHEN date_value IS NOT NULL THEN 1 ELSE 0 END + "
            "CASE WHEN boolean_value IS NOT NULL THEN 1 ELSE 0 END) = 1",
            name="ck_crm_custom_values_one_typed_value",
        ),
        sa.ForeignKeyConstraint(["organisation_id"], ["organisations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["organisation_id", "definition_id"],
            ["crm_custom_field_definitions.organisation_id", "crm_custom_field_definitions.id"],
            name="fk_crm_custom_values_definition",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["organisation_id", "changed_by_user_id"],
            ["organisation_memberships.organisation_id", "organisation_memberships.user_id"],
            name="fk_crm_custom_values_actor",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organisation_id", "id", name="uq_crm_custom_values_org_id"),
        sa.UniqueConstraint(
            "organisation_id",
            "definition_id",
            "entity_type",
            "entity_id",
            name="uq_crm_custom_values_record_field",
        ),
    )
    op.create_index(
        "ix_crm_custom_values_org_record",
        "crm_custom_field_values",
        ["organisation_id", "entity_type", "entity_id"],
    )

    op.create_table(
        "crm_record_changes",
        sa.Column("id", uuid_type, nullable=False),
        sa.Column("organisation_id", uuid_type, nullable=False),
        sa.Column("entity_type", sa.String(length=24), nullable=False),
        sa.Column("entity_id", uuid_type, nullable=False),
        sa.Column("field_key", sa.String(length=80), nullable=False),
        sa.Column("old_value_json", sa.JSON(none_as_null=True), nullable=True),
        sa.Column("new_value_json", sa.JSON(none_as_null=True), nullable=True),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column("changed_by_user_id", uuid_type, nullable=False),
        sa.Column("changed_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "entity_type IN ('account', 'contact', 'opportunity')",
            name="ck_crm_record_changes_entity_type",
        ),
        sa.CheckConstraint(
            "source IN ('manual_user_entry', 'crm_import', 'prospect_promotion', "
            "'event_promotion', 'external_crm', 'reviewed_action', 'system')",
            name="ck_crm_record_changes_source",
        ),
        sa.CheckConstraint("length(trim(field_key)) BETWEEN 1 AND 80", name="ck_crm_record_changes_field"),
        sa.ForeignKeyConstraint(["organisation_id"], ["organisations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["organisation_id", "changed_by_user_id"],
            ["organisation_memberships.organisation_id", "organisation_memberships.user_id"],
            name="fk_crm_record_changes_actor",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organisation_id", "id", name="uq_crm_record_changes_org_id"),
    )
    op.create_index(
        "ix_crm_record_changes_org_record",
        "crm_record_changes",
        ["organisation_id", "entity_type", "entity_id", "changed_at"],
    )
    _enable_tenant_rls()


def downgrade() -> None:
    for table_name in reversed(TENANT_TABLES):
        op.drop_table(table_name)

    op.drop_index("ix_opportunities_org_archived", table_name="opportunities")
    op.drop_index("ix_contacts_org_archived", table_name="contacts")
    op.drop_index("ix_companies_org_archived", table_name="companies")
    op.drop_index("uq_contacts_org_business_email", table_name="contacts")
    op.drop_index("uq_companies_org_normalized_domain", table_name="companies")

    with op.batch_alter_table("opportunities") as batch:
        batch.drop_column("archived_at")
    with op.batch_alter_table("contacts") as batch:
        batch.drop_constraint("ck_contacts_status", type_="check")
        batch.drop_column("archived_at")
        batch.drop_column("status")
    with op.batch_alter_table("companies") as batch:
        batch.drop_column("archived_at")
        batch.drop_column("location")

    _replace_check(
        "organisation_module_entitlements",
        "ck_module_entitlements_key",
        "module_key IN ('prospect', 'engage', 'create')",
    )
