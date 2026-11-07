"""Add explicit user-confirmed conversation threads.

Revision ID: 0068_conversation_threads
Revises: 0067_conversation_foundations

Threads are lightweight initiative groupings. Company and participant overlap may
rank suggestions in application code, but only a durable assignment row created
by an authenticated user places an interaction in a thread.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0068_conversation_threads"
down_revision: str | None = "0067_conversation_foundations"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLES = (
    "conversation_threads",
    "conversation_thread_assignments",
    "conversation_thread_audit_events",
)


def _enable_rls() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return
    for table_name in TABLES:
        op.execute(f"ALTER TABLE {table_name} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table_name} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"""CREATE POLICY {table_name}_tenant_isolation ON {table_name}
            USING (organisation_id = NULLIF(current_setting('app.organisation_id', true), '')::uuid)
            WITH CHECK (organisation_id = NULLIF(current_setting('app.organisation_id', true), '')::uuid)"""
        )


def upgrade() -> None:
    uuid_type = sa.Uuid(as_uuid=True)
    op.create_table(
        "conversation_threads",
        sa.Column("id", uuid_type, nullable=False),
        sa.Column("organisation_id", uuid_type, nullable=False),
        sa.Column("company_id", uuid_type, nullable=True),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("status", sa.String(length=20), server_default="active", nullable=False),
        sa.Column("created_by_user_id", uuid_type, nullable=False),
        sa.Column("updated_by_user_id", uuid_type, nullable=False),
        sa.Column("lock_version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("length(trim(name)) BETWEEN 1 AND 200", name="ck_conversation_threads_name"),
        sa.CheckConstraint("status IN ('active', 'archived')", name="ck_conversation_threads_status"),
        sa.CheckConstraint("lock_version > 0", name="ck_conversation_threads_lock"),
        sa.ForeignKeyConstraint(["organisation_id"], ["organisations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["organisation_id", "company_id"],
            ["companies.organisation_id", "companies.id"],
            name="fk_conversation_threads_company",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organisation_id", "created_by_user_id"],
            ["organisation_memberships.organisation_id", "organisation_memberships.user_id"],
            name="fk_conversation_threads_creator",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organisation_id", "updated_by_user_id"],
            ["organisation_memberships.organisation_id", "organisation_memberships.user_id"],
            name="fk_conversation_threads_updater",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organisation_id", "id", name="uq_conversation_threads_org_id"),
    )
    op.create_index(
        "ix_conversation_threads_org_company_status",
        "conversation_threads",
        ["organisation_id", "company_id", "status"],
    )

    op.create_table(
        "conversation_thread_assignments",
        sa.Column("id", uuid_type, nullable=False),
        sa.Column("organisation_id", uuid_type, nullable=False),
        sa.Column("thread_id", uuid_type, nullable=False),
        sa.Column("interaction_id", uuid_type, nullable=False),
        sa.Column("confirmed_by_user_id", uuid_type, nullable=False),
        sa.Column(
            "confirmation_kind",
            sa.String(length=24),
            server_default="user_confirmed",
            nullable=False,
        ),
        sa.Column("lock_version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "confirmation_kind IN ('user_confirmed', 'user_corrected')",
            name="ck_conversation_thread_assignments_confirmation",
        ),
        sa.CheckConstraint("lock_version > 0", name="ck_conversation_thread_assignments_lock"),
        sa.ForeignKeyConstraint(["organisation_id"], ["organisations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["organisation_id", "thread_id"],
            ["conversation_threads.organisation_id", "conversation_threads.id"],
            name="fk_conversation_thread_assignments_thread",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["organisation_id", "interaction_id"],
            ["interactions.organisation_id", "interactions.id"],
            name="fk_conversation_thread_assignments_interaction",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["organisation_id", "confirmed_by_user_id"],
            ["organisation_memberships.organisation_id", "organisation_memberships.user_id"],
            name="fk_conversation_thread_assignments_confirmer",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organisation_id", "id", name="uq_conversation_thread_assignments_org_id"),
        sa.UniqueConstraint(
            "organisation_id",
            "interaction_id",
            name="uq_conversation_thread_assignments_interaction",
        ),
    )
    op.create_index(
        "ix_conversation_thread_assignments_org_thread",
        "conversation_thread_assignments",
        ["organisation_id", "thread_id", "created_at"],
    )

    op.create_table(
        "conversation_thread_audit_events",
        sa.Column("id", uuid_type, nullable=False),
        sa.Column("organisation_id", uuid_type, nullable=False),
        sa.Column("thread_id", uuid_type, nullable=False),
        sa.Column("interaction_id", uuid_type, nullable=True),
        sa.Column("actor_user_id", uuid_type, nullable=False),
        sa.Column("action", sa.String(length=20), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "action IN ('created', 'updated', 'archived', 'assigned', 'reassigned', 'unassigned')",
            name="ck_conversation_thread_audit_events_action",
        ),
        sa.ForeignKeyConstraint(["organisation_id"], ["organisations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["organisation_id", "thread_id"],
            ["conversation_threads.organisation_id", "conversation_threads.id"],
            name="fk_conversation_thread_audit_events_thread",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["organisation_id", "interaction_id"],
            ["interactions.organisation_id", "interactions.id"],
            name="fk_conversation_thread_audit_events_interaction",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["organisation_id", "actor_user_id"],
            ["organisation_memberships.organisation_id", "organisation_memberships.user_id"],
            name="fk_conversation_thread_audit_events_actor",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organisation_id", "id", name="uq_conversation_thread_audit_events_org_id"),
    )
    op.create_index(
        "ix_conversation_thread_audit_events_org_thread_created",
        "conversation_thread_audit_events",
        ["organisation_id", "thread_id", "created_at"],
    )
    _enable_rls()


def downgrade() -> None:
    op.drop_index(
        "ix_conversation_thread_audit_events_org_thread_created",
        table_name="conversation_thread_audit_events",
    )
    op.drop_table("conversation_thread_audit_events")
    op.drop_index(
        "ix_conversation_thread_assignments_org_thread",
        table_name="conversation_thread_assignments",
    )
    op.drop_table("conversation_thread_assignments")
    op.drop_index(
        "ix_conversation_threads_org_company_status",
        table_name="conversation_threads",
    )
    op.drop_table("conversation_threads")
