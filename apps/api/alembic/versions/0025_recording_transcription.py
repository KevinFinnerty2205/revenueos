"""Add browser recording, resumable upload and batch transcription foundation.

Revision ID: 0025_recording_transcription
Revises: 0024_visual_evidence

Downgrade warning: recording manifests, consent records, transcript history and
segments are removed. Private objects must be exported or deleted separately.
"""

import uuid
from collections.abc import Sequence
from datetime import datetime

import sqlalchemy as sa
from alembic import op

revision: str = "0025_recording_transcription"
down_revision: str | None = "0024_visual_evidence"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TENANT_TABLES = (
    "recording_usage_counters",
    "recording_sessions",
    "recording_consents",
    "recording_chunks",
    "transcript_versions",
    "transcript_segments",
)


def _drop_sqlite_transcript_reference_triggers() -> None:
    if op.get_bind().dialect.name != "sqlite":
        return
    op.execute("DROP TRIGGER IF EXISTS ai_jobs_validate_transcript_trace")
    op.execute("DROP TRIGGER IF EXISTS ai_jobs_prevent_trace_change")


def _restore_sqlite_transcript_reference_triggers() -> None:
    if op.get_bind().dialect.name != "sqlite":
        return
    op.execute(
        """
        CREATE TRIGGER ai_jobs_validate_transcript_trace
        BEFORE INSERT ON ai_jobs
        FOR EACH ROW
        WHEN NOT EXISTS (
            SELECT 1 FROM transcripts
            WHERE organisation_id = NEW.organisation_id
              AND id = NEW.transcript_id
              AND meeting_id = NEW.meeting_id
              AND version = NEW.transcript_version
        )
        BEGIN
            SELECT RAISE(ABORT, 'AI job transcript version must match the current transcript');
        END
        """
    )
    op.execute(
        """
        CREATE TRIGGER ai_jobs_prevent_trace_change
        BEFORE UPDATE OF organisation_id, meeting_id, transcript_id,
            transcript_version, job_type, composition_tone ON ai_jobs
        FOR EACH ROW
        WHEN NEW.organisation_id IS NOT OLD.organisation_id
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


def _widen_capture_types() -> None:
    with op.batch_alter_table("capture_sessions") as batch:
        batch.drop_constraint("ck_capture_sessions_type", type_="check")
        batch.create_check_constraint(
            "ck_capture_sessions_type",
            "capture_type IN ('ai_debrief', 'voice_journal', 'live_recording', "
            "'live_audio_recording', 'visual_capture', 'uploaded_transcript', "
            "'uploaded_recording', 'uploaded_audio_recording', "
            "'imported_audio_recording', 'manual_notes')",
        )


def _narrow_capture_types() -> None:
    op.execute(
        "UPDATE capture_sessions SET capture_type = 'live_recording' WHERE capture_type = 'live_audio_recording'"
    )
    op.execute(
        "UPDATE capture_sessions SET capture_type = 'uploaded_recording' "
        "WHERE capture_type IN ('uploaded_audio_recording', 'imported_audio_recording')"
    )
    with op.batch_alter_table("capture_sessions") as batch:
        batch.drop_constraint("ck_capture_sessions_type", type_="check")
        batch.create_check_constraint(
            "ck_capture_sessions_type",
            "capture_type IN ('ai_debrief', 'voice_journal', 'live_recording', 'visual_capture', "
            "'uploaded_transcript', 'uploaded_recording', 'manual_notes')",
        )


def _widen_transcript_sources() -> None:
    _drop_sqlite_transcript_reference_triggers()
    with op.batch_alter_table("transcripts") as batch:
        batch.drop_constraint("ck_transcripts_source", type_="check")
        batch.create_check_constraint(
            "ck_transcripts_source",
            "source IN ('manual', 'upload', 'recorded_audio', 'uploaded_audio', 'imported_audio')",
        )
    _restore_sqlite_transcript_reference_triggers()


def _narrow_transcript_sources() -> None:
    op.execute(
        "UPDATE transcripts SET source = 'upload' "
        "WHERE source IN ('recorded_audio', 'uploaded_audio', 'imported_audio')"
    )
    _drop_sqlite_transcript_reference_triggers()
    with op.batch_alter_table("transcripts") as batch:
        batch.drop_constraint("ck_transcripts_source", type_="check")
        batch.create_check_constraint("ck_transcripts_source", "source IN ('manual', 'upload')")
    _restore_sqlite_transcript_reference_triggers()


def _create_immutability_guards() -> None:
    dialect = op.get_bind().dialect.name
    if dialect == "postgresql":
        op.execute(
            """
            CREATE FUNCTION protect_transcript_version_history()
            RETURNS trigger LANGUAGE plpgsql AS $$
            BEGIN
                IF (to_jsonb(NEW) - ARRAY['status', 'deleted_at'])
                    IS DISTINCT FROM (to_jsonb(OLD) - ARRAY['status', 'deleted_at']) THEN
                    RAISE EXCEPTION 'Transcript versions are immutable';
                END IF;
                IF OLD.status = 'deleted' AND ROW(NEW.status, NEW.deleted_at)
                    IS DISTINCT FROM ROW(OLD.status, OLD.deleted_at) THEN
                    RAISE EXCEPTION 'Deleted transcript versions are immutable';
                END IF;
                RETURN NEW;
            END;
            $$
            """
        )
        op.execute(
            """CREATE TRIGGER transcript_versions_immutability_guard
            BEFORE UPDATE ON transcript_versions
            FOR EACH ROW EXECUTE FUNCTION protect_transcript_version_history()"""
        )
        op.execute(
            """
            CREATE FUNCTION protect_transcript_segment_history()
            RETURNS trigger LANGUAGE plpgsql AS $$
            BEGIN
                IF (to_jsonb(NEW) - 'deleted_at') IS DISTINCT FROM (to_jsonb(OLD) - 'deleted_at') THEN
                    RAISE EXCEPTION 'Transcript segments are immutable';
                END IF;
                IF OLD.deleted_at IS NOT NULL AND NEW.deleted_at IS DISTINCT FROM OLD.deleted_at THEN
                    RAISE EXCEPTION 'Deleted transcript segments are immutable';
                END IF;
                RETURN NEW;
            END;
            $$
            """
        )
        op.execute(
            """CREATE TRIGGER transcript_segments_immutability_guard
            BEFORE UPDATE ON transcript_segments
            FOR EACH ROW EXECUTE FUNCTION protect_transcript_segment_history()"""
        )
    elif dialect == "sqlite":
        op.execute(
            """
            CREATE TRIGGER transcript_versions_immutability_guard
            BEFORE UPDATE ON transcript_versions
            FOR EACH ROW WHEN
                NEW.id IS NOT OLD.id OR NEW.organisation_id IS NOT OLD.organisation_id
                OR NEW.interaction_id IS NOT OLD.interaction_id OR NEW.meeting_id IS NOT OLD.meeting_id
                OR NEW.transcript_id IS NOT OLD.transcript_id
                OR NEW.recording_session_id IS NOT OLD.recording_session_id
                OR NEW.evidence_id IS NOT OLD.evidence_id OR NEW.version IS NOT OLD.version
                OR NEW.raw_text IS NOT OLD.raw_text OR NEW.language IS NOT OLD.language
                OR NEW.source IS NOT OLD.source OR NEW.provider_name IS NOT OLD.provider_name
                OR NEW.provider_request_id IS NOT OLD.provider_request_id OR NEW.created_at IS NOT OLD.created_at
                OR (OLD.status = 'deleted' AND (NEW.status IS NOT OLD.status OR NEW.deleted_at IS NOT OLD.deleted_at))
            BEGIN
                SELECT RAISE(ABORT, 'Transcript versions are immutable');
            END
            """
        )
        op.execute(
            """
            CREATE TRIGGER transcript_segments_immutability_guard
            BEFORE UPDATE ON transcript_segments
            FOR EACH ROW WHEN
                NEW.id IS NOT OLD.id OR NEW.organisation_id IS NOT OLD.organisation_id
                OR NEW.transcript_version_id IS NOT OLD.transcript_version_id
                OR NEW.sequence_number IS NOT OLD.sequence_number OR NEW.start_ms IS NOT OLD.start_ms
                OR NEW.end_ms IS NOT OLD.end_ms OR NEW.speaker_label IS NOT OLD.speaker_label
                OR NEW.text IS NOT OLD.text OR NEW.source_confidence IS NOT OLD.source_confidence
                OR NEW.created_at IS NOT OLD.created_at
                OR (OLD.deleted_at IS NOT NULL AND NEW.deleted_at IS NOT OLD.deleted_at)
            BEGIN
                SELECT RAISE(ABORT, 'Transcript segments are immutable');
            END
            """
        )


def _drop_immutability_guards() -> None:
    dialect = op.get_bind().dialect.name
    if dialect == "postgresql":
        op.execute("DROP TRIGGER transcript_segments_immutability_guard ON transcript_segments")
        op.execute("DROP FUNCTION protect_transcript_segment_history()")
        op.execute("DROP TRIGGER transcript_versions_immutability_guard ON transcript_versions")
        op.execute("DROP FUNCTION protect_transcript_version_history()")
    elif dialect == "sqlite":
        op.execute("DROP TRIGGER transcript_segments_immutability_guard")
        op.execute("DROP TRIGGER transcript_versions_immutability_guard")


def _create_worker_discovery() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return
    op.execute(
        """
        CREATE FUNCTION public.revenueos_recording_worker_eligible_organisations(result_limit integer)
        RETURNS TABLE (organisation_id uuid)
        LANGUAGE sql
        SECURITY DEFINER
        SET search_path = pg_catalog, public
        AS $$
            SELECT DISTINCT recording_sessions.organisation_id
            FROM public.recording_sessions
            WHERE recording_sessions.lifecycle_status = 'uploaded'
              AND recording_sessions.deleted_at IS NULL
            ORDER BY recording_sessions.organisation_id
            LIMIT LEAST(GREATEST(result_limit, 1), 1000)
        $$
        """
    )


def upgrade() -> None:
    _widen_capture_types()
    _widen_transcript_sources()

    op.create_table(
        "recording_usage_counters",
        sa.Column("organisation_id", sa.Uuid(), nullable=False),
        sa.Column("usage_date", sa.Date(), nullable=False),
        sa.Column("uploaded_bytes", sa.BigInteger(), server_default="0", nullable=False),
        sa.Column("transcription_minutes", sa.Integer(), server_default="0", nullable=False),
        sa.Column("transcription_request_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("uploaded_bytes >= 0", name="ck_recording_usage_uploaded_bytes"),
        sa.CheckConstraint("transcription_minutes >= 0", name="ck_recording_usage_transcription_minutes"),
        sa.CheckConstraint("transcription_request_count >= 0", name="ck_recording_usage_request_count"),
        sa.ForeignKeyConstraint(["organisation_id"], ["organisations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("organisation_id", "usage_date"),
    )
    op.create_index(
        "ix_recording_usage_organisation_date",
        "recording_usage_counters",
        ["organisation_id", "usage_date"],
    )

    op.create_table(
        "recording_sessions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organisation_id", sa.Uuid(), nullable=False),
        sa.Column("interaction_id", sa.Uuid(), nullable=False),
        sa.Column("capture_session_id", sa.Uuid(), nullable=False),
        sa.Column("source_evidence_id", sa.Uuid(), nullable=False),
        sa.Column("transcript_evidence_id", sa.Uuid(), nullable=True),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("recording_type", sa.String(length=40), nullable=False),
        sa.Column("lifecycle_status", sa.String(length=20), server_default="created", nullable=False),
        sa.Column("consent_state", sa.String(length=20), server_default="acknowledged", nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("stopped_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_seconds", sa.Integer(), nullable=True),
        sa.Column("expected_mime_type", sa.String(length=40), nullable=False),
        sa.Column("final_mime_type", sa.String(length=40), nullable=True),
        sa.Column("language", sa.String(length=16), nullable=True),
        sa.Column("total_bytes", sa.BigInteger(), server_default="0", nullable=False),
        sa.Column("chunk_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("idempotency_key", sa.String(length=200), nullable=False),
        sa.Column("upload_completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("transcription_provider_key", sa.String(length=40), nullable=True),
        sa.Column("transcription_attempts", sa.Integer(), server_default="0", nullable=False),
        sa.Column("transcription_request_id", sa.String(length=255), nullable=True),
        sa.Column("transcription_started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("transcription_completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("transcript_version_id", sa.Uuid(), nullable=True),
        sa.Column("failure_code", sa.String(length=100), nullable=True),
        sa.Column("session_expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("auto_intelligence_status", sa.String(length=20), server_default="disabled", nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "recording_type IN ('live_audio_recording', 'uploaded_audio_recording', 'imported_audio_recording')",
            name="ck_recording_sessions_type",
        ),
        sa.CheckConstraint(
            "lifecycle_status IN ('created', 'recording', 'uploading', 'uploaded', 'transcribing', "
            "'completed', 'failed', 'cancelled', 'deleting', 'deleted')",
            name="ck_recording_sessions_lifecycle",
        ),
        sa.CheckConstraint("consent_state = 'acknowledged'", name="ck_recording_sessions_consent"),
        sa.CheckConstraint(
            "expected_mime_type IN ('audio/webm', 'audio/mp4', 'audio/m4a')",
            name="ck_recording_sessions_expected_mime",
        ),
        sa.CheckConstraint(
            "final_mime_type IS NULL OR final_mime_type IN ('audio/webm', 'audio/mp4', 'audio/m4a')",
            name="ck_recording_sessions_final_mime",
        ),
        sa.CheckConstraint(
            "duration_seconds IS NULL OR duration_seconds BETWEEN 1 AND 14400",
            name="ck_recording_sessions_duration",
        ),
        sa.CheckConstraint("total_bytes >= 0", name="ck_recording_sessions_total_bytes"),
        sa.CheckConstraint("chunk_count >= 0", name="ck_recording_sessions_chunk_count"),
        sa.CheckConstraint(
            "transcription_attempts BETWEEN 0 AND 5",
            name="ck_recording_sessions_transcription_attempts",
        ),
        sa.CheckConstraint(
            "stopped_at IS NULL OR started_at IS NULL OR stopped_at >= started_at",
            name="ck_recording_sessions_time_range",
        ),
        sa.CheckConstraint(
            "auto_intelligence_status IN ('disabled', 'not_requested', 'requested', 'failed')",
            name="ck_recording_sessions_auto_intelligence",
        ),
        sa.CheckConstraint(
            "length(trim(idempotency_key)) BETWEEN 1 AND 200",
            name="ck_recording_sessions_idempotency",
        ),
        sa.ForeignKeyConstraint(["organisation_id"], ["organisations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["organisation_id", "interaction_id"],
            ["interactions.organisation_id", "interactions.id"],
            name="fk_recording_sessions_interaction_tenant",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["organisation_id", "capture_session_id"],
            ["capture_sessions.organisation_id", "capture_sessions.id"],
            name="fk_recording_sessions_capture_tenant",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["organisation_id", "source_evidence_id"],
            ["evidence.organisation_id", "evidence.id"],
            name="fk_recording_sessions_source_evidence_tenant",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organisation_id", "transcript_evidence_id"],
            ["evidence.organisation_id", "evidence.id"],
            name="fk_recording_sessions_transcript_evidence_tenant",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organisation_id", "created_by_user_id"],
            ["organisation_memberships.organisation_id", "organisation_memberships.user_id"],
            name="fk_recording_sessions_creator_membership",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organisation_id", "id", name="uq_recording_sessions_organisation_id_id"),
        sa.UniqueConstraint(
            "organisation_id",
            "capture_session_id",
            name="uq_recording_sessions_capture_session",
        ),
        sa.UniqueConstraint(
            "organisation_id",
            "interaction_id",
            "created_by_user_id",
            "idempotency_key",
            name="uq_recording_sessions_idempotency",
        ),
    )
    op.create_index(
        "ix_recording_sessions_organisation_interaction_created",
        "recording_sessions",
        ["organisation_id", "interaction_id", "created_at"],
    )
    op.create_index(
        "ix_recording_sessions_organisation_lifecycle",
        "recording_sessions",
        ["organisation_id", "lifecycle_status"],
    )

    op.create_table(
        "recording_consents",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organisation_id", sa.Uuid(), nullable=False),
        sa.Column("interaction_id", sa.Uuid(), nullable=False),
        sa.Column("recording_session_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("notice_version", sa.Integer(), nullable=False),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("consent_method", sa.String(length=40), nullable=False),
        sa.Column("user_attested_authority", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.CheckConstraint("notice_version > 0", name="ck_recording_consents_notice_version"),
        sa.CheckConstraint(
            "consent_method IN ('participant_notice_confirmed', 'platform_notice', 'contractual_authority')",
            name="ck_recording_consents_method",
        ),
        sa.CheckConstraint("user_attested_authority", name="ck_recording_consents_authority"),
        sa.ForeignKeyConstraint(["organisation_id"], ["organisations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["organisation_id", "interaction_id"],
            ["interactions.organisation_id", "interactions.id"],
            name="fk_recording_consents_interaction_tenant",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["organisation_id", "recording_session_id"],
            ["recording_sessions.organisation_id", "recording_sessions.id"],
            name="fk_recording_consents_recording_tenant",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["organisation_id", "user_id"],
            ["organisation_memberships.organisation_id", "organisation_memberships.user_id"],
            name="fk_recording_consents_user_membership",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organisation_id", "id", name="uq_recording_consents_organisation_id_id"),
        sa.UniqueConstraint(
            "organisation_id",
            "recording_session_id",
            name="uq_recording_consents_recording",
        ),
    )

    op.create_table(
        "recording_chunks",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organisation_id", sa.Uuid(), nullable=False),
        sa.Column("recording_session_id", sa.Uuid(), nullable=False),
        sa.Column("sequence_number", sa.Integer(), nullable=False),
        sa.Column("byte_size", sa.BigInteger(), nullable=False),
        sa.Column("checksum_sha256", sa.String(length=64), nullable=False),
        sa.Column("storage_key", sa.String(length=360), nullable=False),
        sa.Column("upload_state", sa.String(length=24), server_default="pending", nullable=False),
        sa.Column("upload_idempotency_key", sa.String(length=200), nullable=False),
        sa.Column("completion_idempotency_key", sa.String(length=200), nullable=True),
        sa.Column("upload_expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("uploaded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("sequence_number >= 0", name="ck_recording_chunks_sequence"),
        sa.CheckConstraint("byte_size BETWEEN 1 AND 25000000", name="ck_recording_chunks_byte_size"),
        sa.CheckConstraint(
            "length(checksum_sha256) = 64 AND checksum_sha256 = lower(checksum_sha256)",
            name="ck_recording_chunks_checksum",
        ),
        sa.CheckConstraint(
            "upload_state IN ('pending', 'uploaded', 'verified', 'deletion_pending', 'delete_failed', 'deleted')",
            name="ck_recording_chunks_upload_state",
        ),
        sa.CheckConstraint(
            "length(trim(upload_idempotency_key)) BETWEEN 1 AND 200",
            name="ck_recording_chunks_upload_idempotency",
        ),
        sa.ForeignKeyConstraint(["organisation_id"], ["organisations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["organisation_id", "recording_session_id"],
            ["recording_sessions.organisation_id", "recording_sessions.id"],
            name="fk_recording_chunks_recording_tenant",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organisation_id", "id", name="uq_recording_chunks_organisation_id_id"),
        sa.UniqueConstraint(
            "organisation_id",
            "recording_session_id",
            "sequence_number",
            name="uq_recording_chunks_sequence",
        ),
        sa.UniqueConstraint("storage_key", name="uq_recording_chunks_storage_key"),
    )
    op.create_index(
        "ix_recording_chunks_organisation_recording_sequence",
        "recording_chunks",
        ["organisation_id", "recording_session_id", "sequence_number"],
    )

    op.create_table(
        "transcript_versions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organisation_id", sa.Uuid(), nullable=False),
        sa.Column("interaction_id", sa.Uuid(), nullable=False),
        sa.Column("meeting_id", sa.Uuid(), nullable=True),
        sa.Column("transcript_id", sa.Uuid(), nullable=True),
        sa.Column("recording_session_id", sa.Uuid(), nullable=True),
        sa.Column("evidence_id", sa.Uuid(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("raw_text", sa.Text(), nullable=False),
        sa.Column("language", sa.String(length=16), server_default="en", nullable=False),
        sa.Column("source", sa.String(length=24), nullable=False),
        sa.Column("status", sa.String(length=12), server_default="final", nullable=False),
        sa.Column("provider_name", sa.String(length=40), nullable=True),
        sa.Column("provider_request_id", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("version > 0", name="ck_transcript_versions_version"),
        sa.CheckConstraint("length(trim(raw_text)) > 0", name="ck_transcript_versions_raw_text"),
        sa.CheckConstraint(
            "source IN ('manual', 'upload', 'recorded_audio', 'uploaded_audio', 'imported_audio')",
            name="ck_transcript_versions_source",
        ),
        sa.CheckConstraint("status IN ('final', 'deleted')", name="ck_transcript_versions_status"),
        sa.CheckConstraint(
            "transcript_id IS NOT NULL OR recording_session_id IS NOT NULL",
            name="ck_transcript_versions_trace",
        ),
        sa.ForeignKeyConstraint(["organisation_id"], ["organisations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["organisation_id", "interaction_id"],
            ["interactions.organisation_id", "interactions.id"],
            name="fk_transcript_versions_interaction_tenant",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["organisation_id", "meeting_id"],
            ["meetings.organisation_id", "meetings.id"],
            name="fk_transcript_versions_meeting_tenant",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["organisation_id", "transcript_id", "meeting_id"],
            ["transcripts.organisation_id", "transcripts.id", "transcripts.meeting_id"],
            name="fk_transcript_versions_transcript_tenant",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["organisation_id", "recording_session_id"],
            ["recording_sessions.organisation_id", "recording_sessions.id"],
            name="fk_transcript_versions_recording_tenant",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organisation_id", "evidence_id"],
            ["evidence.organisation_id", "evidence.id"],
            name="fk_transcript_versions_evidence_tenant",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organisation_id", "id", name="uq_transcript_versions_organisation_id_id"),
        sa.UniqueConstraint(
            "organisation_id",
            "transcript_id",
            "version",
            name="uq_transcript_versions_logical_version",
        ),
        sa.UniqueConstraint(
            "organisation_id",
            "recording_session_id",
            name="uq_transcript_versions_recording",
        ),
    )
    op.create_index(
        "ix_transcript_versions_organisation_interaction_created",
        "transcript_versions",
        ["organisation_id", "interaction_id", "created_at"],
    )

    op.create_table(
        "transcript_segments",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organisation_id", sa.Uuid(), nullable=False),
        sa.Column("transcript_version_id", sa.Uuid(), nullable=False),
        sa.Column("sequence_number", sa.Integer(), nullable=False),
        sa.Column("start_ms", sa.Integer(), nullable=False),
        sa.Column("end_ms", sa.Integer(), nullable=False),
        sa.Column("speaker_label", sa.String(length=80), nullable=True),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("source_confidence", sa.Numeric(5, 4), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("sequence_number >= 0", name="ck_transcript_segments_sequence"),
        sa.CheckConstraint("start_ms >= 0 AND end_ms >= start_ms", name="ck_transcript_segments_time_range"),
        sa.CheckConstraint("length(trim(text)) BETWEEN 1 AND 12000", name="ck_transcript_segments_text"),
        sa.CheckConstraint(
            "speaker_label IS NULL OR length(trim(speaker_label)) BETWEEN 1 AND 80",
            name="ck_transcript_segments_speaker_label",
        ),
        sa.CheckConstraint(
            "source_confidence IS NULL OR (source_confidence >= 0 AND source_confidence <= 1)",
            name="ck_transcript_segments_confidence",
        ),
        sa.ForeignKeyConstraint(["organisation_id"], ["organisations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["organisation_id", "transcript_version_id"],
            ["transcript_versions.organisation_id", "transcript_versions.id"],
            name="fk_transcript_segments_version_tenant",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organisation_id", "id", name="uq_transcript_segments_organisation_id_id"),
        sa.UniqueConstraint(
            "organisation_id",
            "transcript_version_id",
            "sequence_number",
            name="uq_transcript_segments_sequence",
        ),
    )
    op.create_index(
        "ix_transcript_segments_organisation_version_sequence",
        "transcript_segments",
        ["organisation_id", "transcript_version_id", "sequence_number"],
    )

    with op.batch_alter_table("recording_sessions") as batch:
        batch.create_foreign_key(
            "fk_recording_sessions_transcript_version_tenant",
            "transcript_versions",
            ["organisation_id", "transcript_version_id"],
            ["organisation_id", "id"],
            ondelete="RESTRICT",
        )

    transcript_versions = sa.table(
        "transcript_versions",
        sa.column("id", sa.Uuid()),
        sa.column("organisation_id", sa.Uuid()),
        sa.column("interaction_id", sa.Uuid()),
        sa.column("meeting_id", sa.Uuid()),
        sa.column("transcript_id", sa.Uuid()),
        sa.column("version", sa.Integer()),
        sa.column("raw_text", sa.Text()),
        sa.column("language", sa.String()),
        sa.column("source", sa.String()),
        sa.column("status", sa.String()),
        sa.column("created_at", sa.DateTime(timezone=True)),
    )
    rows = (
        op.get_bind()
        .execute(
            sa.text(
                """SELECT t.organisation_id, m.interaction_id, t.meeting_id,
            t.id AS transcript_id, t.version, t.raw_text, t.language, t.source, t.created_at
            FROM transcripts AS t
            JOIN meetings AS m
              ON m.organisation_id = t.organisation_id AND m.id = t.meeting_id"""
            )
        )
        .mappings()
    )
    for row in rows:
        created_at = row["created_at"]
        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at)
        op.execute(
            transcript_versions.insert().values(
                id=uuid.uuid4(),
                organisation_id=uuid.UUID(str(row["organisation_id"])),
                interaction_id=uuid.UUID(str(row["interaction_id"])),
                meeting_id=uuid.UUID(str(row["meeting_id"])),
                transcript_id=uuid.UUID(str(row["transcript_id"])),
                version=row["version"],
                raw_text=row["raw_text"],
                language=row["language"],
                source=row["source"],
                status="final",
                created_at=created_at,
            )
        )

    _enable_tenant_rls()
    _create_immutability_guards()
    _create_worker_discovery()


def downgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        op.execute("DROP FUNCTION public.revenueos_recording_worker_eligible_organisations(integer)")
    _drop_immutability_guards()
    with op.batch_alter_table("recording_sessions") as batch:
        batch.drop_constraint("fk_recording_sessions_transcript_version_tenant", type_="foreignkey")
    op.drop_table("transcript_segments")
    op.drop_table("transcript_versions")
    op.drop_table("recording_chunks")
    op.drop_table("recording_consents")
    op.drop_table("recording_sessions")
    op.drop_table("recording_usage_counters")
    _narrow_transcript_sources()
    _narrow_capture_types()
