"""Add durable AI worker ownership metadata.

Revision ID: 0006_ai_worker_queue
Revises: 0005_ai_domain_services
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0006_ai_worker_queue"
down_revision: str | None = "0005_ai_domain_services"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _restore_sqlite_job_trace_triggers() -> None:
    if op.get_bind().dialect.name != "sqlite":
        return
    op.execute(
        """
        CREATE TRIGGER ai_jobs_validate_transcript_trace
        BEFORE INSERT ON ai_jobs
        FOR EACH ROW
        WHEN NOT EXISTS (
            SELECT 1
            FROM transcripts
            WHERE organisation_id = NEW.organisation_id
                AND id = NEW.transcript_id
                AND meeting_id = NEW.meeting_id
                AND version = NEW.transcript_version
        )
        BEGIN
            SELECT RAISE(
                ABORT,
                'AI job transcript version must match the current transcript'
            );
        END
        """
    )
    op.execute(
        """
        CREATE TRIGGER ai_jobs_prevent_trace_change
        BEFORE UPDATE OF organisation_id, meeting_id, transcript_id,
            transcript_version, job_type ON ai_jobs
        FOR EACH ROW
        WHEN
            NEW.organisation_id IS NOT OLD.organisation_id
            OR NEW.meeting_id IS NOT OLD.meeting_id
            OR NEW.transcript_id IS NOT OLD.transcript_id
            OR NEW.transcript_version IS NOT OLD.transcript_version
            OR NEW.job_type IS NOT OLD.job_type
        BEGIN
            SELECT RAISE(ABORT, 'AI job trace is immutable');
        END
        """
    )


def upgrade() -> None:
    with op.batch_alter_table("ai_jobs") as batch_op:
        batch_op.add_column(sa.Column("worker_id", sa.String(length=200), nullable=True))
        batch_op.add_column(sa.Column("heartbeat_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.create_check_constraint(
            "ck_ai_jobs_worker_id",
            "worker_id IS NULL OR (length(trim(worker_id)) > 0 AND length(worker_id) <= 200)",
        )
    _restore_sqlite_job_trace_triggers()
    if op.get_bind().dialect.name == "postgresql":
        op.execute(
            """
            CREATE FUNCTION public.revenueos_ai_worker_eligible_organisations(
                eligible_at timestamptz,
                result_limit integer
            )
            RETURNS TABLE (organisation_id uuid)
            LANGUAGE sql
            SECURITY DEFINER
            SET search_path = pg_catalog, public
            AS $$
                SELECT DISTINCT ai_jobs.organisation_id
                FROM public.ai_jobs
                WHERE (
                    ai_jobs.status = 'pending'
                    AND (
                        ai_jobs.cancellation_requested_at IS NOT NULL
                        OR (
                            ai_jobs.attempt_count < ai_jobs.max_attempts
                            AND (
                                ai_jobs.next_attempt_at IS NULL
                                OR ai_jobs.next_attempt_at <= eligible_at
                            )
                        )
                    )
                ) OR (
                    ai_jobs.status = 'running'
                    AND ai_jobs.lease_expires_at IS NOT NULL
                    AND ai_jobs.lease_expires_at <= eligible_at
                )
                ORDER BY ai_jobs.organisation_id
                LIMIT LEAST(GREATEST(result_limit, 1), 1000)
            $$
            """
        )


def downgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        op.execute(
            """
            DROP FUNCTION IF EXISTS
            public.revenueos_ai_worker_eligible_organisations(timestamptz, integer)
            """
        )
    with op.batch_alter_table("ai_jobs") as batch_op:
        batch_op.drop_constraint("ck_ai_jobs_worker_id", type_="check")
        batch_op.drop_column("heartbeat_at")
        batch_op.drop_column("worker_id")
    _restore_sqlite_job_trace_triggers()
