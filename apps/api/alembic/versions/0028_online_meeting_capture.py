"""Add provider-neutral online meeting metadata and transcript imports.

Revision ID: 0028_online_meeting_capture
Revises: 0027_phone_call_intelligence

Downgrade warning: online meeting provenance and import metadata are permanently
removed. Imported transcript text remains only after being mapped to legacy
transcript sources during downgrade.
"""

import uuid
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0028_online_meeting_capture"
down_revision: str | None = "0027_phone_call_intelligence"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TENANT_TABLES = ("online_meeting_metadata", "online_meeting_transcript_imports")


def _drop_sqlite_transcript_guards() -> None:
    if op.get_bind().dialect.name != "sqlite":
        return
    for trigger_name in (
        "ai_jobs_validate_transcript_trace",
        "ai_jobs_prevent_trace_change",
        "transcript_versions_immutability_guard",
    ):
        op.execute(f"DROP TRIGGER IF EXISTS {trigger_name}")


def _restore_sqlite_transcript_guards() -> None:
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


def _widen_transcript_sources() -> None:
    _drop_sqlite_transcript_guards()
    transcript_sources = (
        "source IN ('manual', 'upload', 'recorded_audio', 'uploaded_audio', 'imported_audio', "
        "'platform_generated', 'user_uploaded', 'externally_generated', 'manually_pasted')"
    )
    with op.batch_alter_table("transcripts") as batch:
        batch.drop_constraint("ck_transcripts_source", type_="check")
        batch.create_check_constraint("ck_transcripts_source", transcript_sources)
    with op.batch_alter_table("transcript_versions") as batch:
        batch.drop_constraint("ck_transcript_versions_source", type_="check")
        batch.create_check_constraint("ck_transcript_versions_source", transcript_sources)
    _restore_sqlite_transcript_guards()


def _narrow_transcript_sources() -> None:
    op.execute(
        "UPDATE transcripts SET source = 'upload' WHERE source IN "
        "('platform_generated', 'user_uploaded', 'externally_generated', 'manually_pasted')"
    )
    _drop_sqlite_transcript_guards()
    op.execute(
        "UPDATE transcript_versions SET source = 'upload' WHERE source IN "
        "('platform_generated', 'user_uploaded', 'externally_generated', 'manually_pasted')"
    )
    legacy_sources = "source IN ('manual', 'upload', 'recorded_audio', 'uploaded_audio', 'imported_audio')"
    with op.batch_alter_table("transcripts") as batch:
        batch.drop_constraint("ck_transcripts_source", type_="check")
        batch.create_check_constraint("ck_transcripts_source", legacy_sources)
    with op.batch_alter_table("transcript_versions") as batch:
        batch.drop_constraint("ck_transcript_versions_source", type_="check")
        batch.create_check_constraint("ck_transcript_versions_source", legacy_sources)
    _restore_sqlite_transcript_guards()


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


def upgrade() -> None:
    _widen_transcript_sources()
    with op.batch_alter_table("recording_sessions") as batch:
        batch.drop_constraint("ck_recording_sessions_source", type_="check")
        batch.create_check_constraint(
            "ck_recording_sessions_source",
            "recording_source IS NULL OR recording_source IN ("
            "'customer_call_recording', 'business_phone_recording', 'user_uploaded_recording', "
            "'external_provider_recording', 'platform_recording')",
        )

    op.create_table(
        "online_meeting_metadata",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organisation_id", sa.Uuid(), nullable=False),
        sa.Column("interaction_id", sa.Uuid(), nullable=False),
        sa.Column("meeting_platform", sa.String(length=24), server_default="other", nullable=False),
        sa.Column("safe_meeting_url", sa.String(length=1000), nullable=True),
        sa.Column("meeting_host", sa.String(length=255), nullable=True),
        sa.Column("external_meeting_id", sa.String(length=255), nullable=True),
        sa.Column("capture_source", sa.String(length=40), nullable=True),
        sa.Column("ingestion_state", sa.String(length=24), server_default="not_started", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "meeting_platform IN ('microsoft_teams', 'zoom', 'google_meet', 'other')",
            name="ck_online_meeting_metadata_platform",
        ),
        sa.CheckConstraint(
            "capture_source IS NULL OR capture_source IN ("
            "'platform_recording', 'platform_transcript', 'user_uploaded_recording', "
            "'user_uploaded_transcript', 'native_integration', 'meeting_bot', "
            "'ai_debrief', 'voice_journal', 'manual_notes')",
            name="ck_online_meeting_metadata_capture_source",
        ),
        sa.CheckConstraint(
            "ingestion_state IN ('not_started', 'uploading', 'processing', 'ready', 'failed')",
            name="ck_online_meeting_metadata_ingestion_state",
        ),
        sa.CheckConstraint(
            "safe_meeting_url IS NULL OR length(trim(safe_meeting_url)) BETWEEN 1 AND 1000",
            name="ck_online_meeting_metadata_safe_url",
        ),
        sa.CheckConstraint(
            "meeting_host IS NULL OR length(trim(meeting_host)) BETWEEN 1 AND 255",
            name="ck_online_meeting_metadata_host",
        ),
        sa.CheckConstraint(
            "external_meeting_id IS NULL OR length(trim(external_meeting_id)) BETWEEN 1 AND 255",
            name="ck_online_meeting_metadata_external_id",
        ),
        sa.ForeignKeyConstraint(["organisation_id"], ["organisations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["organisation_id", "interaction_id"],
            ["interactions.organisation_id", "interactions.id"],
            name="fk_online_meeting_metadata_interaction_tenant",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organisation_id", "id", name="uq_online_meeting_metadata_organisation_id_id"),
        sa.UniqueConstraint("organisation_id", "interaction_id", name="uq_online_meeting_metadata_interaction"),
    )
    op.create_index(
        "ix_online_meeting_metadata_organisation_platform",
        "online_meeting_metadata",
        ["organisation_id", "meeting_platform"],
    )

    online_meetings = sa.table(
        "online_meeting_metadata",
        sa.column("id", sa.Uuid()),
        sa.column("organisation_id", sa.Uuid()),
        sa.column("interaction_id", sa.Uuid()),
        sa.column("meeting_platform", sa.String()),
        sa.column("ingestion_state", sa.String()),
    )
    rows = op.get_bind().execute(
        sa.text(
            "SELECT organisation_id, id FROM interactions "
            "WHERE interaction_type = 'online_meeting' AND deleted_at IS NULL"
        )
    )
    values = [
        {
            "id": uuid.uuid4(),
            "organisation_id": uuid.UUID(str(row.organisation_id)),
            "interaction_id": uuid.UUID(str(row.id)),
            "meeting_platform": "other",
            "ingestion_state": "not_started",
        }
        for row in rows
    ]
    if values:
        op.bulk_insert(online_meetings, values)

    op.create_table(
        "online_meeting_transcript_imports",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organisation_id", sa.Uuid(), nullable=False),
        sa.Column("interaction_id", sa.Uuid(), nullable=False),
        sa.Column("capture_session_id", sa.Uuid(), nullable=False),
        sa.Column("evidence_id", sa.Uuid(), nullable=False),
        sa.Column("transcript_version_id", sa.Uuid(), nullable=False),
        sa.Column("imported_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("provenance", sa.String(length=24), server_default="user_uploaded", nullable=False),
        sa.Column("source_format", sa.String(length=8), nullable=False),
        sa.Column("language", sa.String(length=16), server_default="en", nullable=False),
        sa.Column("content_sha256", sa.String(length=64), nullable=False),
        sa.Column("character_count", sa.Integer(), nullable=False),
        sa.Column("timestamps_present", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("speaker_labels_present", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("idempotency_key", sa.String(length=200), nullable=False),
        sa.Column("imported_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "provenance IN ('platform_generated', 'user_uploaded', 'externally_generated', 'manually_pasted')",
            name="ck_online_meeting_transcript_imports_provenance",
        ),
        sa.CheckConstraint(
            "source_format IN ('txt', 'vtt', 'srt')",
            name="ck_online_meeting_transcript_imports_format",
        ),
        sa.CheckConstraint(
            "character_count BETWEEN 1 AND 1000000",
            name="ck_online_meeting_transcript_imports_character_count",
        ),
        sa.CheckConstraint(
            "length(content_sha256) = 64 AND content_sha256 = lower(content_sha256)",
            name="ck_online_meeting_transcript_imports_checksum",
        ),
        sa.CheckConstraint(
            "length(trim(idempotency_key)) BETWEEN 1 AND 200",
            name="ck_online_meeting_transcript_imports_idempotency",
        ),
        sa.ForeignKeyConstraint(["organisation_id"], ["organisations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["organisation_id", "interaction_id"],
            ["interactions.organisation_id", "interactions.id"],
            name="fk_online_meeting_transcript_imports_interaction_tenant",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["organisation_id", "capture_session_id"],
            ["capture_sessions.organisation_id", "capture_sessions.id"],
            name="fk_online_meeting_transcript_imports_capture_tenant",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["organisation_id", "evidence_id"],
            ["evidence.organisation_id", "evidence.id"],
            name="fk_online_meeting_transcript_imports_evidence_tenant",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organisation_id", "transcript_version_id"],
            ["transcript_versions.organisation_id", "transcript_versions.id"],
            name="fk_online_meeting_transcript_imports_version_tenant",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organisation_id", "imported_by_user_id"],
            ["organisation_memberships.organisation_id", "organisation_memberships.user_id"],
            name="fk_online_meeting_transcript_imports_user_tenant",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organisation_id", "id", name="uq_online_meeting_transcript_imports_organisation_id_id"),
        sa.UniqueConstraint(
            "organisation_id",
            "interaction_id",
            "imported_by_user_id",
            "idempotency_key",
            name="uq_online_meeting_transcript_imports_idempotency",
        ),
        sa.UniqueConstraint(
            "organisation_id",
            "interaction_id",
            "content_sha256",
            name="uq_online_meeting_transcript_imports_content",
        ),
        sa.UniqueConstraint(
            "organisation_id",
            "transcript_version_id",
            name="uq_online_meeting_transcript_imports_version",
        ),
    )
    op.create_index(
        "ix_online_meeting_transcript_imports_organisation_interaction_imported",
        "online_meeting_transcript_imports",
        ["organisation_id", "interaction_id", "imported_at"],
    )
    _enable_tenant_rls()


def downgrade() -> None:
    op.drop_table("online_meeting_transcript_imports")
    op.drop_table("online_meeting_metadata")
    op.execute(
        "UPDATE recording_sessions SET recording_source = 'external_provider_recording' "
        "WHERE recording_source = 'platform_recording'"
    )
    with op.batch_alter_table("recording_sessions") as batch:
        batch.drop_constraint("ck_recording_sessions_source", type_="check")
        batch.create_check_constraint(
            "ck_recording_sessions_source",
            "recording_source IS NULL OR recording_source IN ("
            "'customer_call_recording', 'business_phone_recording', 'user_uploaded_recording', "
            "'external_provider_recording')",
        )
    _narrow_transcript_sources()
