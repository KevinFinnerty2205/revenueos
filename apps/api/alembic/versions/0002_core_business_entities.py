"""Add tenant-owned companies, contacts, opportunities and tasks.

Revision ID: 0002_core_business_entities
Revises: 0001_initial_schema
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002_core_business_entities"
down_revision: str | None = "0001_initial_schema"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _timestamps() -> tuple[sa.Column[object], sa.Column[object]]:
    return (
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )


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

    op.create_table(
        "companies",
        sa.Column("id", uuid_type, primary_key=True, nullable=False),
        sa.Column(
            "organisation_id",
            uuid_type,
            sa.ForeignKey("organisations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("website", sa.String(length=2048)),
        sa.Column("industry", sa.String(length=120)),
        sa.Column("employee_count", sa.Integer()),
        sa.Column("status", sa.String(length=20), server_default="prospect", nullable=False),
        sa.Column("owner_user_id", uuid_type, nullable=False),
        *_timestamps(),
        sa.CheckConstraint("length(trim(name)) > 0", name="ck_companies_name"),
        sa.CheckConstraint(
            "status IN ('prospect', 'active', 'inactive')",
            name="ck_companies_status",
        ),
        sa.CheckConstraint(
            "employee_count IS NULL OR employee_count >= 0",
            name="ck_companies_employee_count",
        ),
        sa.ForeignKeyConstraint(
            ["organisation_id", "owner_user_id"],
            [
                "organisation_memberships.organisation_id",
                "organisation_memberships.user_id",
            ],
            name="fk_companies_owner_membership",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint(
            "organisation_id",
            "id",
            name="uq_companies_organisation_id_id",
        ),
    )
    op.create_index(
        "ix_companies_organisation_name",
        "companies",
        ["organisation_id", "name"],
    )
    op.create_index(
        "ix_companies_organisation_status",
        "companies",
        ["organisation_id", "status"],
    )

    op.create_table(
        "contacts",
        sa.Column("id", uuid_type, primary_key=True, nullable=False),
        sa.Column(
            "organisation_id",
            uuid_type,
            sa.ForeignKey("organisations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("company_id", uuid_type, nullable=False),
        sa.Column("first_name", sa.String(length=100), nullable=False),
        sa.Column("last_name", sa.String(length=100), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("phone", sa.String(length=50)),
        sa.Column("job_title", sa.String(length=150)),
        sa.Column("linkedin_url", sa.String(length=2048)),
        sa.Column("owner_user_id", uuid_type, nullable=False),
        *_timestamps(),
        sa.CheckConstraint(
            "length(trim(first_name)) > 0",
            name="ck_contacts_first_name",
        ),
        sa.CheckConstraint(
            "length(trim(last_name)) > 0",
            name="ck_contacts_last_name",
        ),
        sa.ForeignKeyConstraint(
            ["organisation_id", "company_id"],
            ["companies.organisation_id", "companies.id"],
            name="fk_contacts_company_tenant",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organisation_id", "owner_user_id"],
            [
                "organisation_memberships.organisation_id",
                "organisation_memberships.user_id",
            ],
            name="fk_contacts_owner_membership",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint(
            "organisation_id",
            "id",
            name="uq_contacts_organisation_id_id",
        ),
    )
    op.create_index(
        "ix_contacts_organisation_name",
        "contacts",
        ["organisation_id", "last_name", "first_name"],
    )
    op.create_index(
        "ix_contacts_organisation_company",
        "contacts",
        ["organisation_id", "company_id"],
    )
    op.create_index(
        "ix_contacts_organisation_email",
        "contacts",
        ["organisation_id", "email"],
    )

    op.create_table(
        "opportunities",
        sa.Column("id", uuid_type, primary_key=True, nullable=False),
        sa.Column(
            "organisation_id",
            uuid_type,
            sa.ForeignKey("organisations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("company_id", uuid_type, nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column(
            "stage",
            sa.String(length=30),
            server_default="discovery",
            nullable=False,
        ),
        sa.Column(
            "value",
            sa.Numeric(precision=18, scale=2),
            server_default="0",
            nullable=False,
        ),
        sa.Column(
            "currency",
            sa.String(length=3),
            server_default="AUD",
            nullable=False,
        ),
        sa.Column(
            "probability",
            sa.Integer(),
            server_default="0",
            nullable=False,
        ),
        sa.Column("expected_close_date", sa.Date()),
        sa.Column("owner_user_id", uuid_type, nullable=False),
        *_timestamps(),
        sa.CheckConstraint(
            "length(trim(name)) > 0",
            name="ck_opportunities_name",
        ),
        sa.CheckConstraint(
            "stage IN ('discovery', 'qualification', 'proposal', 'negotiation', 'closed_won', 'closed_lost')",
            name="ck_opportunities_stage",
        ),
        sa.CheckConstraint("value >= 0", name="ck_opportunities_value"),
        sa.CheckConstraint(
            "probability >= 0 AND probability <= 100",
            name="ck_opportunities_probability",
        ),
        sa.CheckConstraint(
            "length(currency) = 3 AND currency = upper(currency)",
            name="ck_opportunities_currency",
        ),
        sa.ForeignKeyConstraint(
            ["organisation_id", "company_id"],
            ["companies.organisation_id", "companies.id"],
            name="fk_opportunities_company_tenant",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organisation_id", "owner_user_id"],
            [
                "organisation_memberships.organisation_id",
                "organisation_memberships.user_id",
            ],
            name="fk_opportunities_owner_membership",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint(
            "organisation_id",
            "id",
            name="uq_opportunities_organisation_id_id",
        ),
    )
    op.create_index(
        "ix_opportunities_organisation_name",
        "opportunities",
        ["organisation_id", "name"],
    )
    op.create_index(
        "ix_opportunities_organisation_company",
        "opportunities",
        ["organisation_id", "company_id"],
    )
    op.create_index(
        "ix_opportunities_organisation_stage",
        "opportunities",
        ["organisation_id", "stage"],
    )
    op.create_index(
        "ix_opportunities_organisation_close",
        "opportunities",
        ["organisation_id", "expected_close_date"],
    )

    op.create_table(
        "tasks",
        sa.Column("id", uuid_type, primary_key=True, nullable=False),
        sa.Column(
            "organisation_id",
            uuid_type,
            sa.ForeignKey("organisations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("company_id", uuid_type),
        sa.Column("contact_id", uuid_type),
        sa.Column("opportunity_id", uuid_type),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("status", sa.String(length=20), server_default="open", nullable=False),
        sa.Column(
            "priority",
            sa.String(length=20),
            server_default="medium",
            nullable=False,
        ),
        sa.Column("due_at", sa.DateTime(timezone=True)),
        sa.Column("assigned_user_id", uuid_type),
        sa.Column("created_by_user_id", uuid_type, nullable=False),
        *_timestamps(),
        sa.CheckConstraint("length(trim(title)) > 0", name="ck_tasks_title"),
        sa.CheckConstraint(
            "status IN ('open', 'in_progress', 'completed', 'cancelled')",
            name="ck_tasks_status",
        ),
        sa.CheckConstraint(
            "priority IN ('low', 'medium', 'high', 'urgent')",
            name="ck_tasks_priority",
        ),
        sa.ForeignKeyConstraint(
            ["organisation_id", "company_id"],
            ["companies.organisation_id", "companies.id"],
            name="fk_tasks_company_tenant",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organisation_id", "contact_id"],
            ["contacts.organisation_id", "contacts.id"],
            name="fk_tasks_contact_tenant",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organisation_id", "opportunity_id"],
            ["opportunities.organisation_id", "opportunities.id"],
            name="fk_tasks_opportunity_tenant",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organisation_id", "assigned_user_id"],
            [
                "organisation_memberships.organisation_id",
                "organisation_memberships.user_id",
            ],
            name="fk_tasks_assigned_membership",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organisation_id", "created_by_user_id"],
            [
                "organisation_memberships.organisation_id",
                "organisation_memberships.user_id",
            ],
            name="fk_tasks_creator_membership",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint(
            "organisation_id",
            "id",
            name="uq_tasks_organisation_id_id",
        ),
    )
    op.create_index(
        "ix_tasks_organisation_status",
        "tasks",
        ["organisation_id", "status"],
    )
    op.create_index(
        "ix_tasks_organisation_priority",
        "tasks",
        ["organisation_id", "priority"],
    )
    op.create_index(
        "ix_tasks_organisation_due",
        "tasks",
        ["organisation_id", "due_at"],
    )
    op.create_index(
        "ix_tasks_organisation_company",
        "tasks",
        ["organisation_id", "company_id"],
    )
    op.create_index(
        "ix_tasks_organisation_contact",
        "tasks",
        ["organisation_id", "contact_id"],
    )
    op.create_index(
        "ix_tasks_organisation_opportunity",
        "tasks",
        ["organisation_id", "opportunity_id"],
    )
    op.create_index(
        "ix_tasks_organisation_assignee",
        "tasks",
        ["organisation_id", "assigned_user_id"],
    )

    for table_name in ("companies", "contacts", "opportunities", "tasks"):
        _enable_tenant_rls(table_name)


def downgrade() -> None:
    op.drop_table("tasks")
    op.drop_table("opportunities")
    op.drop_table("contacts")
    op.drop_table("companies")
