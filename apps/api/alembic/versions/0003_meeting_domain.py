"""Add the tenant-owned Meeting Domain.

Revision ID: 0003_meeting_domain
Revises: 0002_core_business_entities
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003_meeting_domain"
down_revision: str | None = "0002_core_business_entities"
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
        "meetings",
        sa.Column("id", uuid_type, primary_key=True, nullable=False),
        sa.Column(
            "organisation_id",
            uuid_type,
            sa.ForeignKey("organisations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("meeting_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("meeting_type", sa.String(length=20), server_default="other", nullable=False),
        sa.Column("status", sa.String(length=20), server_default="scheduled", nullable=False),
        sa.Column("company_id", uuid_type),
        sa.Column("owner_user_id", uuid_type, nullable=False),
        sa.Column("created_by", uuid_type, nullable=False),
        sa.Column("updated_by", uuid_type, nullable=False),
        *_timestamps(),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint("length(trim(title)) > 0", name="ck_meetings_title"),
        sa.CheckConstraint(
            "meeting_type IN ('remote', 'phone', 'in_person', 'other')",
            name="ck_meetings_type",
        ),
        sa.CheckConstraint(
            "status IN ('scheduled', 'completed', 'cancelled')",
            name="ck_meetings_status",
        ),
        sa.ForeignKeyConstraint(
            ["organisation_id", "company_id"],
            ["companies.organisation_id", "companies.id"],
            name="fk_meetings_company_tenant",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organisation_id", "owner_user_id"],
            [
                "organisation_memberships.organisation_id",
                "organisation_memberships.user_id",
            ],
            name="fk_meetings_owner_membership",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organisation_id", "created_by"],
            [
                "organisation_memberships.organisation_id",
                "organisation_memberships.user_id",
            ],
            name="fk_meetings_created_by_membership",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organisation_id", "updated_by"],
            [
                "organisation_memberships.organisation_id",
                "organisation_memberships.user_id",
            ],
            name="fk_meetings_updated_by_membership",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint("organisation_id", "id", name="uq_meetings_organisation_id_id"),
    )
    op.create_index(
        "ix_meetings_organisation_date",
        "meetings",
        ["organisation_id", "meeting_date"],
    )
    op.create_index(
        "ix_meetings_organisation_status",
        "meetings",
        ["organisation_id", "status"],
    )
    op.create_index(
        "ix_meetings_organisation_type",
        "meetings",
        ["organisation_id", "meeting_type"],
    )
    op.create_index(
        "ix_meetings_organisation_company",
        "meetings",
        ["organisation_id", "company_id"],
    )
    op.create_index(
        "ix_meetings_organisation_deleted",
        "meetings",
        ["organisation_id", "deleted_at"],
    )

    op.create_table(
        "meeting_participants",
        sa.Column("id", uuid_type, primary_key=True, nullable=False),
        sa.Column(
            "organisation_id",
            uuid_type,
            sa.ForeignKey("organisations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("meeting_id", uuid_type, nullable=False),
        sa.Column("contact_id", uuid_type),
        sa.Column("display_name", sa.String(length=200)),
        sa.Column("email", sa.String(length=320)),
        sa.Column("attendance_status", sa.String(length=20), server_default="invited", nullable=False),
        sa.Column("role", sa.String(length=20), server_default="attendee", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint(
            "contact_id IS NOT NULL "
            "OR COALESCE(length(trim(display_name)), 0) > 0 "
            "OR COALESCE(length(trim(email)), 0) > 0",
            name="ck_meeting_participants_identity",
        ),
        sa.CheckConstraint(
            "attendance_status IN ('invited', 'attended', 'absent', 'unknown')",
            name="ck_meeting_participants_attendance",
        ),
        sa.CheckConstraint(
            "role IN ('host', 'attendee')",
            name="ck_meeting_participants_role",
        ),
        sa.ForeignKeyConstraint(
            ["organisation_id", "meeting_id"],
            ["meetings.organisation_id", "meetings.id"],
            name="fk_meeting_participants_meeting_tenant",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["organisation_id", "contact_id"],
            ["contacts.organisation_id", "contacts.id"],
            name="fk_meeting_participants_contact_tenant",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint(
            "organisation_id",
            "id",
            name="uq_meeting_participants_organisation_id_id",
        ),
    )
    op.create_index(
        "ix_meeting_participants_organisation_meeting",
        "meeting_participants",
        ["organisation_id", "meeting_id"],
    )
    op.create_index(
        "ix_meeting_participants_organisation_contact",
        "meeting_participants",
        ["organisation_id", "contact_id"],
    )
    op.create_index(
        "ix_meeting_participants_organisation_email",
        "meeting_participants",
        ["organisation_id", "email"],
    )

    op.create_table(
        "transcripts",
        sa.Column("id", uuid_type, primary_key=True, nullable=False),
        sa.Column(
            "organisation_id",
            uuid_type,
            sa.ForeignKey("organisations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("meeting_id", uuid_type, nullable=False),
        sa.Column("raw_text", sa.Text(), nullable=False),
        sa.Column("language", sa.String(length=16), server_default="en", nullable=False),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("source", sa.String(length=20), server_default="manual", nullable=False),
        *_timestamps(),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint("length(trim(raw_text)) > 0", name="ck_transcripts_raw_text"),
        sa.CheckConstraint("version > 0", name="ck_transcripts_version"),
        sa.CheckConstraint(
            "source IN ('manual', 'upload')",
            name="ck_transcripts_source",
        ),
        sa.ForeignKeyConstraint(
            ["organisation_id", "meeting_id"],
            ["meetings.organisation_id", "meetings.id"],
            name="fk_transcripts_meeting_tenant",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint("organisation_id", "id", name="uq_transcripts_organisation_id_id"),
        sa.UniqueConstraint(
            "organisation_id",
            "meeting_id",
            name="uq_transcripts_organisation_meeting",
        ),
    )
    op.create_index(
        "ix_transcripts_organisation_deleted",
        "transcripts",
        ["organisation_id", "deleted_at"],
    )

    op.create_table(
        "meeting_audit_events",
        sa.Column("id", uuid_type, primary_key=True, nullable=False),
        sa.Column(
            "organisation_id",
            uuid_type,
            sa.ForeignKey("organisations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("meeting_id", uuid_type, nullable=False),
        sa.Column("actor_user_id", uuid_type, nullable=False),
        sa.Column("action", sa.String(length=20), nullable=False),
        sa.Column("entity_type", sa.String(length=20), nullable=False),
        sa.Column("entity_id", uuid_type, nullable=False),
        sa.Column("changed_fields", sa.JSON(), nullable=False),
        sa.Column("version", sa.Integer()),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "action IN ('created', 'updated', 'deleted', 'restored')",
            name="ck_meeting_audit_events_action",
        ),
        sa.CheckConstraint(
            "entity_type IN ('meeting', 'participant', 'transcript')",
            name="ck_meeting_audit_events_entity_type",
        ),
        sa.ForeignKeyConstraint(
            ["organisation_id", "meeting_id"],
            ["meetings.organisation_id", "meetings.id"],
            name="fk_meeting_audit_events_meeting_tenant",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["organisation_id", "actor_user_id"],
            [
                "organisation_memberships.organisation_id",
                "organisation_memberships.user_id",
            ],
            name="fk_meeting_audit_events_actor_membership",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint(
            "organisation_id",
            "id",
            name="uq_meeting_audit_events_organisation_id_id",
        ),
    )
    op.create_index(
        "ix_meeting_audit_events_organisation_meeting_created",
        "meeting_audit_events",
        ["organisation_id", "meeting_id", "created_at"],
    )

    for table_name in (
        "meetings",
        "meeting_participants",
        "transcripts",
        "meeting_audit_events",
    ):
        _enable_tenant_rls(table_name)


def downgrade() -> None:
    op.drop_table("meeting_audit_events")
    op.drop_table("transcripts")
    op.drop_table("meeting_participants")
    op.drop_table("meetings")
