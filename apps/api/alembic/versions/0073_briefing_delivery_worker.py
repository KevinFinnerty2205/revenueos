"""Add leased, idempotent briefing delivery lifecycle state.

Revision ID: 0073_briefing_delivery_worker
Revises: 0072_post_conversation_drafts

The worker remains disabled by default; checked-in launch profiles do not
activate provider delivery. The schema separates non-deliverable previews from
scheduled rows and makes claims, retries, authority cancellation and ambiguous
provider outcomes durable.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0073_briefing_delivery_worker"
down_revision: str | None = "0072_post_conversation_drafts"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    uuid_type = sa.Uuid(as_uuid=True)
    op.add_column(
        "conversation_delivery_preferences",
        sa.Column("last_scheduler_discovered_at", sa.DateTime(timezone=True), nullable=True),
    )
    with op.batch_alter_table("conversation_briefing_outbox") as batch:
        batch.drop_constraint("ck_conversation_briefing_outbox_status", type_="check")
        batch.add_column(sa.Column("delivery_intent", sa.String(length=16), server_default="preview", nullable=False))
        batch.add_column(sa.Column("delivery_timezone", sa.String(length=64), server_default="UTC", nullable=False))
        batch.add_column(sa.Column("operation_key", sa.String(length=64), nullable=True))
        batch.add_column(sa.Column("attempt_count", sa.Integer(), server_default="0", nullable=False))
        batch.add_column(sa.Column("max_attempts", sa.Integer(), server_default="3", nullable=False))
        batch.add_column(sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=True))
        batch.add_column(sa.Column("worker_id", sa.String(length=200), nullable=True))
        batch.add_column(sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True))
        batch.add_column(sa.Column("connection_id", uuid_type, nullable=True))
        batch.add_column(sa.Column("submission_started_at", sa.DateTime(timezone=True), nullable=True))
        batch.add_column(sa.Column("provider_message_id", sa.String(length=255), nullable=True))
        batch.add_column(sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True))
        batch.add_column(sa.Column("failed_at", sa.DateTime(timezone=True), nullable=True))
        batch.add_column(sa.Column("failure_code", sa.String(length=100), nullable=True))
    # Legacy rows were preview-only artefacts and were never authorised for
    # delivery. Fail closed so a later feature activation cannot send stale
    # historical previews merely because the lifecycle gained a worker.
    op.execute("UPDATE conversation_briefing_outbox SET status = 'cancelled' WHERE status = 'prepared'")
    op.execute(
        "UPDATE conversation_briefing_outbox "
        "SET operation_key = 'preview_' || substr(replace(CAST(id AS VARCHAR), '-', ''), 1, 56) "
        "WHERE operation_key IS NULL"
    )
    with op.batch_alter_table("conversation_briefing_outbox") as batch:
        batch.alter_column(
            "status",
            existing_type=sa.String(length=20),
            server_default="queued",
            nullable=False,
        )
        batch.alter_column(
            "operation_key",
            existing_type=sa.String(length=64),
            nullable=False,
        )
        batch.create_check_constraint(
            "ck_conversation_briefing_outbox_status",
            "status IN ('queued', 'sending', 'sent', 'failed', 'superseded', 'cancelled')",
        )
        batch.create_check_constraint(
            "ck_conversation_briefing_outbox_delivery_intent",
            "delivery_intent IN ('preview', 'scheduled')",
        )
        batch.create_check_constraint(
            "ck_conversation_briefing_outbox_attempts",
            "attempt_count >= 0",
        )
        batch.create_check_constraint(
            "ck_conversation_briefing_outbox_max_attempts",
            "max_attempts BETWEEN 1 AND 20",
        )
        batch.create_foreign_key(
            "fk_conversation_briefing_outbox_connection",
            "integration_connections",
            ["organisation_id", "connection_id"],
            ["organisation_id", "id"],
            ondelete="RESTRICT",
        )
    op.create_index(
        "ix_conversation_briefing_outbox_due",
        "conversation_briefing_outbox",
        ["organisation_id", "user_id", "status", "prepared_for_at", "next_attempt_at"],
    )
    op.create_index(
        "ix_conversation_briefing_outbox_lease",
        "conversation_briefing_outbox",
        ["organisation_id", "user_id", "status", "lease_expires_at"],
    )
    if op.get_bind().dialect.name == "postgresql":
        op.execute(
            """
            CREATE FUNCTION public.revenueos_briefing_worker_eligible_owners(
                eligible_at timestamptz,
                result_limit integer
            )
            RETURNS TABLE (organisation_id uuid, user_id uuid)
            LANGUAGE sql
            SECURITY DEFINER
            SET search_path = pg_catalog, public
            AS $$
                WITH due AS (
                    SELECT DISTINCT outbox.organisation_id, outbox.user_id
                    FROM public.conversation_briefing_outbox AS outbox
                    WHERE outbox.delivery_intent = 'scheduled'
                    AND ((
                        outbox.status = 'queued'
                        AND outbox.prepared_for_at <= eligible_at
                        AND (outbox.next_attempt_at IS NULL OR outbox.next_attempt_at <= eligible_at)
                        AND outbox.attempt_count < outbox.max_attempts
                    ) OR (
                        outbox.status = 'sending'
                        AND outbox.lease_expires_at IS NOT NULL
                        AND outbox.lease_expires_at <= eligible_at
                    ))
                ), preference_candidates AS (
                    SELECT preference.organisation_id,
                           preference.user_id,
                           preference.last_scheduler_discovered_at
                    FROM public.conversation_delivery_preferences AS preference
                    JOIN public.organisation_memberships AS membership
                      ON membership.organisation_id = preference.organisation_id
                     AND membership.user_id = preference.user_id
                     AND membership.status = 'active'
                    JOIN public.users AS owner ON owner.id = preference.user_id
                    WHERE owner.status = 'active'
                      AND (preference.morning_digest_enabled OR preference.pre_meeting_enabled)
                      AND NOT EXISTS (
                          SELECT 1
                          FROM due
                          WHERE due.organisation_id = preference.organisation_id
                            AND due.user_id = preference.user_id
                      )
                ), eligible AS (
                    SELECT due.organisation_id,
                           due.user_id,
                           0 AS priority,
                           NULL::timestamptz AS last_scheduler_discovered_at
                    FROM due
                    UNION ALL
                    SELECT preference_candidates.organisation_id,
                           preference_candidates.user_id,
                           1 AS priority,
                           preference_candidates.last_scheduler_discovered_at
                    FROM preference_candidates
                )
                SELECT eligible.organisation_id, eligible.user_id
                FROM eligible
                ORDER BY eligible.priority,
                         eligible.last_scheduler_discovered_at NULLS FIRST,
                         eligible.organisation_id,
                         eligible.user_id
                LIMIT LEAST(GREATEST(COALESCE(result_limit, 1), 1), 1000)
            $$
            """
        )
        # Cross-tenant/private-owner discovery is privileged and must never be
        # executable by every database role. Activation grants this exact
        # function only to the approved runtime role.
        op.execute(
            "REVOKE ALL ON FUNCTION public.revenueos_briefing_worker_eligible_owners(timestamptz, integer) FROM PUBLIC"
        )


def downgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        op.execute(
            """DROP FUNCTION IF EXISTS
            public.revenueos_briefing_worker_eligible_owners(timestamptz, integer)"""
        )
    op.drop_index("ix_conversation_briefing_outbox_lease", table_name="conversation_briefing_outbox")
    op.drop_index("ix_conversation_briefing_outbox_due", table_name="conversation_briefing_outbox")
    # The legacy preview-only lifecycle cannot represent attempts or successful
    # delivery. Fail closed on downgrade instead of making a sent item sendable.
    op.execute(
        "UPDATE conversation_briefing_outbox SET status = 'cancelled' "
        "WHERE status IN ('queued', 'sending', 'sent', 'failed')"
    )
    with op.batch_alter_table("conversation_briefing_outbox") as batch:
        batch.drop_constraint("fk_conversation_briefing_outbox_connection", type_="foreignkey")
        batch.drop_constraint("ck_conversation_briefing_outbox_max_attempts", type_="check")
        batch.drop_constraint("ck_conversation_briefing_outbox_attempts", type_="check")
        batch.drop_constraint("ck_conversation_briefing_outbox_delivery_intent", type_="check")
        batch.drop_constraint("ck_conversation_briefing_outbox_status", type_="check")
        batch.create_check_constraint(
            "ck_conversation_briefing_outbox_status",
            "status IN ('prepared', 'superseded', 'cancelled')",
        )
        batch.alter_column(
            "status",
            existing_type=sa.String(length=20),
            server_default="prepared",
            nullable=False,
        )
        batch.drop_column("failure_code")
        batch.drop_column("failed_at")
        batch.drop_column("sent_at")
        batch.drop_column("provider_message_id")
        batch.drop_column("submission_started_at")
        batch.drop_column("connection_id")
        batch.drop_column("lease_expires_at")
        batch.drop_column("worker_id")
        batch.drop_column("next_attempt_at")
        batch.drop_column("max_attempts")
        batch.drop_column("attempt_count")
        batch.drop_column("operation_key")
        batch.drop_column("delivery_timezone")
        batch.drop_column("delivery_intent")
    op.drop_column("conversation_delivery_preferences", "last_scheduler_discovered_at")
