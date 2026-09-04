"""Add the tenant-owned Company & Selling Profile revision history.

Revision ID: 0051_selling_profile
Revises: 0050_real_data_operations

WO-046 stores one organisation profile and immutable approved revisions. Draft
content remains editable until approval. The tables are force-RLS protected in
PostgreSQL and contain organisation-approved context, not customer Evidence.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0051_selling_profile"
down_revision: str | None = "0050_real_data_operations"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TENANT_TABLES = ("selling_profiles", "selling_profile_revisions")


def _enable_rls_and_history_guard() -> None:
    dialect = op.get_bind().dialect.name
    if dialect == "postgresql":
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
            """CREATE FUNCTION public.revenueos_protect_selling_profile_history()
            RETURNS trigger AS $$
            BEGIN
                IF OLD.state <> 'draft' AND (
                    NEW.id IS DISTINCT FROM OLD.id OR
                    NEW.organisation_id IS DISTINCT FROM OLD.organisation_id OR
                    NEW.content_json IS DISTINCT FROM OLD.content_json OR
                    NEW.content_fingerprint IS DISTINCT FROM OLD.content_fingerprint OR
                    NEW.revision_number IS DISTINCT FROM OLD.revision_number OR
                    NEW.schema_version IS DISTINCT FROM OLD.schema_version OR
                    NEW.lock_version IS DISTINCT FROM OLD.lock_version OR
                    NEW.profile_id IS DISTINCT FROM OLD.profile_id OR
                    NEW.created_by_user_id IS DISTINCT FROM OLD.created_by_user_id OR
                    NEW.approved_by_user_id IS DISTINCT FROM OLD.approved_by_user_id OR
                    NEW.idempotency_key IS DISTINCT FROM OLD.idempotency_key OR
                    NEW.approved_at IS DISTINCT FROM OLD.approved_at OR
                    NEW.created_at IS DISTINCT FROM OLD.created_at OR
                    (OLD.state IN ('superseded', 'retired') AND (
                        NEW.state IS DISTINCT FROM OLD.state OR
                        NEW.superseded_at IS DISTINCT FROM OLD.superseded_at OR
                        NEW.retired_at IS DISTINCT FROM OLD.retired_at
                    ))
                ) THEN
                    RAISE EXCEPTION 'approved selling-profile history is immutable';
                END IF;
                RETURN NEW;
            END;
            $$ LANGUAGE plpgsql"""
        )
        op.execute(
            """CREATE TRIGGER selling_profile_revisions_history_guard
            BEFORE UPDATE ON selling_profile_revisions
            FOR EACH ROW EXECUTE FUNCTION public.revenueos_protect_selling_profile_history()"""
        )
    elif dialect == "sqlite":
        op.execute(
            """CREATE TRIGGER selling_profile_revisions_history_guard
            BEFORE UPDATE ON selling_profile_revisions
            WHEN OLD.state <> 'draft' AND (
                NEW.id IS NOT OLD.id OR
                NEW.organisation_id IS NOT OLD.organisation_id OR
                NEW.content_json IS NOT OLD.content_json OR
                NEW.content_fingerprint IS NOT OLD.content_fingerprint OR
                NEW.revision_number IS NOT OLD.revision_number OR
                NEW.schema_version IS NOT OLD.schema_version OR
                NEW.lock_version IS NOT OLD.lock_version OR
                NEW.profile_id IS NOT OLD.profile_id OR
                NEW.created_by_user_id IS NOT OLD.created_by_user_id OR
                NEW.approved_by_user_id IS NOT OLD.approved_by_user_id OR
                NEW.idempotency_key IS NOT OLD.idempotency_key OR
                NEW.approved_at IS NOT OLD.approved_at OR
                NEW.created_at IS NOT OLD.created_at OR
                (OLD.state IN ('superseded', 'retired') AND (
                    NEW.state IS NOT OLD.state OR
                    NEW.superseded_at IS NOT OLD.superseded_at OR
                    NEW.retired_at IS NOT OLD.retired_at
                ))
            )
            BEGIN SELECT RAISE(ABORT, 'approved selling-profile history is immutable'); END"""
        )


def upgrade() -> None:
    uuid_type = sa.Uuid(as_uuid=True)
    op.create_table(
        "selling_profiles",
        sa.Column("id", uuid_type, nullable=False),
        sa.Column("organisation_id", uuid_type, nullable=False),
        sa.Column("created_by_user_id", uuid_type, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["organisation_id"], ["organisations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["organisation_id", "created_by_user_id"],
            ["organisation_memberships.organisation_id", "organisation_memberships.user_id"],
            name="fk_selling_profiles_creator",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organisation_id", name="uq_selling_profiles_organisation"),
        sa.UniqueConstraint("organisation_id", "id", name="uq_selling_profiles_org_id"),
    )
    op.create_table(
        "selling_profile_revisions",
        sa.Column("id", uuid_type, nullable=False),
        sa.Column("organisation_id", uuid_type, nullable=False),
        sa.Column("profile_id", uuid_type, nullable=False),
        sa.Column("revision_number", sa.Integer(), nullable=False),
        sa.Column("schema_version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("state", sa.String(length=16), server_default="draft", nullable=False),
        sa.Column("lock_version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("content_json", sa.JSON(), nullable=False),
        sa.Column("content_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("created_by_user_id", uuid_type, nullable=False),
        sa.Column("approved_by_user_id", uuid_type, nullable=True),
        sa.Column("idempotency_key", sa.String(length=200), nullable=False),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("superseded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("retired_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "state IN ('draft', 'approved', 'superseded', 'retired')",
            name="ck_selling_profile_revisions_state",
        ),
        sa.CheckConstraint("revision_number > 0", name="ck_selling_profile_revisions_number"),
        sa.CheckConstraint("schema_version = 1", name="ck_selling_profile_revisions_schema"),
        sa.CheckConstraint("lock_version > 0", name="ck_selling_profile_revisions_lock"),
        sa.CheckConstraint(
            "length(content_fingerprint) = 64",
            name="ck_selling_profile_revisions_fingerprint",
        ),
        sa.CheckConstraint(
            "(state = 'draft' AND approved_by_user_id IS NULL AND approved_at IS NULL "
            "AND superseded_at IS NULL AND retired_at IS NULL) OR "
            "(state = 'approved' AND approved_by_user_id IS NOT NULL AND approved_at IS NOT NULL "
            "AND superseded_at IS NULL AND retired_at IS NULL) OR "
            "(state = 'superseded' AND approved_by_user_id IS NOT NULL AND approved_at IS NOT NULL "
            "AND superseded_at IS NOT NULL AND retired_at IS NULL) OR "
            "(state = 'retired' AND approved_by_user_id IS NOT NULL AND approved_at IS NOT NULL "
            "AND superseded_at IS NULL AND retired_at IS NOT NULL)",
            name="ck_selling_profile_revisions_lifecycle",
        ),
        sa.ForeignKeyConstraint(["organisation_id"], ["organisations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["organisation_id", "profile_id"],
            ["selling_profiles.organisation_id", "selling_profiles.id"],
            name="fk_selling_profile_revisions_profile",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["organisation_id", "created_by_user_id"],
            ["organisation_memberships.organisation_id", "organisation_memberships.user_id"],
            name="fk_selling_profile_revisions_creator",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organisation_id", "approved_by_user_id"],
            ["organisation_memberships.organisation_id", "organisation_memberships.user_id"],
            name="fk_selling_profile_revisions_approver",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organisation_id", "id", name="uq_selling_profile_revisions_org_id"),
        sa.UniqueConstraint(
            "organisation_id",
            "profile_id",
            "revision_number",
            name="uq_selling_profile_revisions_number",
        ),
        sa.UniqueConstraint(
            "organisation_id",
            "created_by_user_id",
            "idempotency_key",
            name="uq_selling_profile_revisions_idempotency",
        ),
    )
    op.create_index(
        "uq_selling_profile_revisions_draft",
        "selling_profile_revisions",
        ["organisation_id", "profile_id"],
        unique=True,
        postgresql_where=sa.text("state = 'draft'"),
        sqlite_where=sa.text("state = 'draft'"),
    )
    op.create_index(
        "uq_selling_profile_revisions_approved",
        "selling_profile_revisions",
        ["organisation_id", "profile_id"],
        unique=True,
        postgresql_where=sa.text("state = 'approved'"),
        sqlite_where=sa.text("state = 'approved'"),
    )
    op.create_index(
        "ix_selling_profile_revisions_org_history",
        "selling_profile_revisions",
        ["organisation_id", "profile_id", "revision_number"],
    )
    _enable_rls_and_history_guard()


def downgrade() -> None:
    dialect = op.get_bind().dialect.name
    if dialect == "postgresql":
        op.execute("DROP TRIGGER IF EXISTS selling_profile_revisions_history_guard ON selling_profile_revisions")
        op.execute("DROP FUNCTION IF EXISTS public.revenueos_protect_selling_profile_history()")
    elif dialect == "sqlite":
        op.execute("DROP TRIGGER IF EXISTS selling_profile_revisions_history_guard")
    op.drop_index("ix_selling_profile_revisions_org_history", table_name="selling_profile_revisions")
    op.drop_index("uq_selling_profile_revisions_approved", table_name="selling_profile_revisions")
    op.drop_index("uq_selling_profile_revisions_draft", table_name="selling_profile_revisions")
    op.drop_table("selling_profile_revisions")
    op.drop_table("selling_profiles")
