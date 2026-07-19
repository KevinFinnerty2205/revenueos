"""Add Follow-up Email composer jobs and artefacts.

Revision ID: 0012_follow_up_email
Revises: 0011_open_questions
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0012_follow_up_email"
down_revision: str | None = "0011_open_questions"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _restore_sqlite_job_trace_triggers(*, include_tone: bool) -> None:
    if op.get_bind().dialect.name != "sqlite":
        return
    op.execute("DROP TRIGGER IF EXISTS ai_jobs_validate_transcript_trace")
    op.execute("DROP TRIGGER IF EXISTS ai_jobs_prevent_trace_change")
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
    tone_columns = ", composition_tone" if include_tone else ""
    tone_condition = " OR NEW.composition_tone IS NOT OLD.composition_tone" if include_tone else ""
    op.execute(
        f"""
        CREATE TRIGGER ai_jobs_prevent_trace_change
        BEFORE UPDATE OF organisation_id, meeting_id, transcript_id,
            transcript_version, job_type{tone_columns} ON ai_jobs
        FOR EACH ROW
        WHEN
            NEW.organisation_id IS NOT OLD.organisation_id
            OR NEW.meeting_id IS NOT OLD.meeting_id
            OR NEW.transcript_id IS NOT OLD.transcript_id
            OR NEW.transcript_version IS NOT OLD.transcript_version
            OR NEW.job_type IS NOT OLD.job_type
            {tone_condition}
        BEGIN
            SELECT RAISE(ABORT, 'AI job trace is immutable');
        END
        """
    )


def _replace_postgresql_job_trace_guard(*, include_tone: bool) -> None:
    if op.get_bind().dialect.name != "postgresql":
        return
    tone_new = ", NEW.composition_tone" if include_tone else ""
    tone_old = ", OLD.composition_tone" if include_tone else ""
    tone_column = ", composition_tone" if include_tone else ""
    op.execute(
        f"""
        CREATE OR REPLACE FUNCTION enforce_ai_job_transcript_trace()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
            IF TG_OP = 'INSERT' THEN
                PERFORM 1
                FROM transcripts
                WHERE organisation_id = NEW.organisation_id
                    AND id = NEW.transcript_id
                    AND meeting_id = NEW.meeting_id
                    AND version = NEW.transcript_version;
                IF NOT FOUND THEN
                    RAISE EXCEPTION 'AI job transcript version must match the current transcript';
                END IF;
            ELSIF ROW(
                NEW.organisation_id,
                NEW.meeting_id,
                NEW.transcript_id,
                NEW.transcript_version,
                NEW.job_type{tone_new}
            ) IS DISTINCT FROM ROW(
                OLD.organisation_id,
                OLD.meeting_id,
                OLD.transcript_id,
                OLD.transcript_version,
                OLD.job_type{tone_old}
            ) THEN
                RAISE EXCEPTION 'AI job trace is immutable';
            END IF;
            RETURN NEW;
        END;
        $$
        """
    )
    op.execute("DROP TRIGGER ai_jobs_prevent_trace_change ON ai_jobs")
    op.execute(
        f"""
        CREATE TRIGGER ai_jobs_prevent_trace_change
        BEFORE UPDATE OF organisation_id, meeting_id, transcript_id,
            transcript_version, job_type{tone_column} ON ai_jobs
        FOR EACH ROW
        EXECUTE FUNCTION enforce_ai_job_transcript_trace()
        """
    )


def _restore_sqlite_artifact_immutability_triggers() -> None:
    if op.get_bind().dialect.name != "sqlite":
        return
    op.execute("DROP TRIGGER IF EXISTS ai_artifacts_prevent_overwrite")
    op.execute("DROP TRIGGER IF EXISTS ai_artifacts_prevent_resupersession")
    op.execute(
        """
        CREATE TRIGGER ai_artifacts_prevent_overwrite
        BEFORE UPDATE ON ai_artifacts
        FOR EACH ROW
        WHEN
            NEW.id IS NOT OLD.id
            OR NEW.organisation_id IS NOT OLD.organisation_id
            OR NEW.meeting_id IS NOT OLD.meeting_id
            OR NEW.transcript_id IS NOT OLD.transcript_id
            OR NEW.transcript_version IS NOT OLD.transcript_version
            OR NEW.job_id IS NOT OLD.job_id
            OR NEW.artifact_type IS NOT OLD.artifact_type
            OR NEW.artifact_version IS NOT OLD.artifact_version
            OR NEW.schema_version IS NOT OLD.schema_version
            OR NEW.prompt_key IS NOT OLD.prompt_key
            OR NEW.prompt_version IS NOT OLD.prompt_version
            OR NEW.provider_key IS NOT OLD.provider_key
            OR NEW.model_name IS NOT OLD.model_name
            OR NEW.content_json IS NOT OLD.content_json
            OR NEW.confidence IS NOT OLD.confidence
            OR NEW.created_at IS NOT OLD.created_at
        BEGIN
            SELECT RAISE(ABORT, 'AI artefact rows are immutable');
        END
        """
    )
    op.execute(
        """
        CREATE TRIGGER ai_artifacts_prevent_resupersession
        BEFORE UPDATE OF superseded_at ON ai_artifacts
        FOR EACH ROW
        WHEN OLD.superseded_at IS NOT NULL
            AND NEW.superseded_at IS NOT OLD.superseded_at
        BEGIN
            SELECT RAISE(ABORT, 'AI artefact supersession is immutable once set');
        END
        """
    )


def _replace_type_constraints(*, include_follow_up_email: bool) -> None:
    job_values = (
        "job_type IN ('infrastructure_test', 'executive_summary', 'decisions', "
        "'action_items', 'risks_blockers', 'open_questions', 'follow_up_email')"
        if include_follow_up_email
        else "job_type IN ('infrastructure_test', 'executive_summary', 'decisions', "
        "'action_items', 'risks_blockers', 'open_questions')"
    )
    artifact_values = (
        "artifact_type IN ('infrastructure_test', 'executive_summary', 'decisions', "
        "'action_items', 'risks_blockers', 'open_questions', 'follow_up_email')"
        if include_follow_up_email
        else "artifact_type IN ('infrastructure_test', 'executive_summary', 'decisions', "
        "'action_items', 'risks_blockers', 'open_questions')"
    )
    with op.batch_alter_table("ai_jobs") as batch_op:
        batch_op.drop_constraint("ck_ai_jobs_type", type_="check")
        batch_op.create_check_constraint("ck_ai_jobs_type", job_values)
    with op.batch_alter_table("ai_artifacts") as batch_op:
        batch_op.drop_constraint("ck_ai_artifacts_type", type_="check")
        batch_op.create_check_constraint("ck_ai_artifacts_type", artifact_values)


def upgrade() -> None:
    with op.batch_alter_table("ai_jobs") as batch_op:
        batch_op.add_column(sa.Column("composition_tone", sa.String(length=20), nullable=True))
    _replace_type_constraints(include_follow_up_email=True)
    with op.batch_alter_table("ai_jobs") as batch_op:
        batch_op.create_check_constraint(
            "ck_ai_jobs_composition_tone",
            "(job_type = 'follow_up_email' AND composition_tone IS NOT NULL AND composition_tone IN "
            "('professional', 'friendly', 'executive')) OR "
            "(job_type <> 'follow_up_email' AND composition_tone IS NULL)",
        )
    _restore_sqlite_job_trace_triggers(include_tone=True)
    _replace_postgresql_job_trace_guard(include_tone=True)
    _restore_sqlite_artifact_immutability_triggers()


def downgrade() -> None:
    op.execute("DELETE FROM ai_artifacts WHERE artifact_type = 'follow_up_email'")
    op.execute("DELETE FROM ai_jobs WHERE job_type = 'follow_up_email'")
    with op.batch_alter_table("ai_jobs") as batch_op:
        batch_op.drop_constraint("ck_ai_jobs_composition_tone", type_="check")
    _replace_type_constraints(include_follow_up_email=False)
    _replace_postgresql_job_trace_guard(include_tone=False)
    with op.batch_alter_table("ai_jobs") as batch_op:
        batch_op.drop_column("composition_tone")
    _restore_sqlite_job_trace_triggers(include_tone=False)
    _restore_sqlite_artifact_immutability_triggers()
