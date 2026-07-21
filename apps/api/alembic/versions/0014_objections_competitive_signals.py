"""Allow Objections & Competitive Signals AI jobs and artefacts.

Revision ID: 0014_objections
Revises: 0013_buying_signals
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0014_objections"
down_revision: str | None = "0013_buying_signals"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _restore_sqlite_job_trace_triggers() -> None:
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
    op.execute(
        """
        CREATE TRIGGER ai_jobs_prevent_trace_change
        BEFORE UPDATE OF organisation_id, meeting_id, transcript_id,
            transcript_version, job_type, composition_tone ON ai_jobs
        FOR EACH ROW
        WHEN
            NEW.organisation_id IS NOT OLD.organisation_id
            OR NEW.meeting_id IS NOT OLD.meeting_id
            OR NEW.transcript_id IS NOT OLD.transcript_id
            OR NEW.transcript_version IS NOT OLD.transcript_version
            OR NEW.job_type IS NOT OLD.job_type
            OR NEW.composition_tone IS NOT OLD.composition_tone
        BEGIN
            SELECT RAISE(ABORT, 'AI job trace is immutable');
        END
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


def _replace_type_constraints(*, include_objections: bool) -> None:
    common_job_values = (
        "job_type IN ('infrastructure_test', 'executive_summary', 'decisions', "
        "'action_items', 'risks_blockers', 'open_questions', 'buying_signals', "
    )
    common_artifact_values = (
        "artifact_type IN ('infrastructure_test', 'executive_summary', 'decisions', "
        "'action_items', 'risks_blockers', 'open_questions', 'buying_signals', "
    )
    job_values = (
        common_job_values + "'objections_competitive_signals', 'follow_up_email')"
        if include_objections
        else common_job_values + "'follow_up_email')"
    )
    artifact_values = (
        common_artifact_values + "'objections_competitive_signals', 'follow_up_email')"
        if include_objections
        else common_artifact_values + "'follow_up_email')"
    )
    with op.batch_alter_table("ai_jobs") as batch_op:
        batch_op.drop_constraint("ck_ai_jobs_type", type_="check")
        batch_op.create_check_constraint("ck_ai_jobs_type", job_values)
    with op.batch_alter_table("ai_artifacts") as batch_op:
        batch_op.drop_constraint("ck_ai_artifacts_type", type_="check")
        batch_op.create_check_constraint("ck_ai_artifacts_type", artifact_values)
    _restore_sqlite_job_trace_triggers()
    _restore_sqlite_artifact_immutability_triggers()


def upgrade() -> None:
    _replace_type_constraints(include_objections=True)


def downgrade() -> None:
    op.execute("DELETE FROM ai_artifacts WHERE artifact_type = 'objections_competitive_signals'")
    op.execute("DELETE FROM ai_jobs WHERE job_type = 'objections_competitive_signals'")
    _replace_type_constraints(include_objections=False)
