"""Create the Sprint 1 identity and organisation foundation.

Revision ID: 0001_initial_schema
Revises:
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001_initial_schema"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _enable_tenant_rls() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return
    op.execute("ALTER TABLE organisations ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE organisations FORCE ROW LEVEL SECURITY")
    op.execute(
        """CREATE POLICY organisations_tenant_isolation ON organisations
        USING (id = NULLIF(current_setting('app.organisation_id', true), '')::uuid)
        WITH CHECK (id = NULLIF(current_setting('app.organisation_id', true), '')::uuid)"""
    )
    op.execute("ALTER TABLE organisation_memberships ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE organisation_memberships FORCE ROW LEVEL SECURITY")
    op.execute(
        """CREATE POLICY memberships_tenant_isolation ON organisation_memberships
        USING (organisation_id = NULLIF(current_setting('app.organisation_id', true), '')::uuid)
        WITH CHECK (organisation_id = NULLIF(current_setting('app.organisation_id', true), '')::uuid)"""
    )


def upgrade() -> None:
    uuid_type = sa.Uuid(as_uuid=True)
    op.create_table(
        "organisations",
        sa.Column("id", uuid_type, primary_key=True, nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("slug", sa.String(length=100), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("slug", name="uq_organisations_slug"),
    )
    op.create_table(
        "users",
        sa.Column("id", uuid_type, primary_key=True, nullable=False),
        sa.Column("external_auth_id", sa.String(length=255), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("display_name", sa.String(length=200), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("external_auth_id", name="uq_users_external_auth_id"),
    )
    op.create_table(
        "organisation_memberships",
        sa.Column("organisation_id", uuid_type, nullable=False),
        sa.Column("user_id", uuid_type, nullable=False),
        sa.Column("role", sa.String(length=20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("role IN ('admin', 'manager', 'member')", name="ck_memberships_role"),
        sa.ForeignKeyConstraint(["organisation_id"], ["organisations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("organisation_id", "user_id", name="pk_organisation_memberships"),
    )
    op.create_index(
        "ix_memberships_organisation_role",
        "organisation_memberships",
        ["organisation_id", "role"],
    )
    _enable_tenant_rls()


def downgrade() -> None:
    op.drop_table("organisation_memberships")
    op.drop_table("users")
    op.drop_table("organisations")
