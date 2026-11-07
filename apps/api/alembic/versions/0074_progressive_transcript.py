"""Permit the bounded progressive transcript lifecycle.

Revision ID: 0074_progressive_transcript
Revises: 0073_briefing_delivery_worker

Final and deleted transcript history remains immutable. Only progressive,
provisional rows may receive live text updates, be retired, or be promoted once
to an authoritative recording transcript.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0074_progressive_transcript"
down_revision: str | None = "0073_briefing_delivery_worker"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _install_postgres_guards() -> None:
    op.execute(
        """
        CREATE OR REPLACE FUNCTION protect_transcript_version_history()
        RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            IF OLD.source = 'progressive' AND OLD.status = 'provisional' THEN
                IF NEW.source = 'progressive' AND NEW.status = 'provisional' THEN
                    IF (to_jsonb(NEW) - ARRAY['raw_text', 'provider_name'])
                        IS DISTINCT FROM (to_jsonb(OLD) - ARRAY['raw_text', 'provider_name']) THEN
                        RAISE EXCEPTION 'Progressive transcript update is invalid';
                    END IF;
                ELSIF NEW.source = 'progressive' AND NEW.status = 'deleted'
                    AND NEW.deleted_at IS NOT NULL THEN
                    IF (to_jsonb(NEW) - ARRAY['status', 'deleted_at'])
                        IS DISTINCT FROM (to_jsonb(OLD) - ARRAY['status', 'deleted_at']) THEN
                        RAISE EXCEPTION 'Progressive transcript retirement is invalid';
                    END IF;
                ELSIF NEW.status = 'final'
                    AND NEW.source IN ('recorded_audio', 'uploaded_audio')
                    AND NEW.deleted_at IS NULL THEN
                    IF ROW(NEW.id, NEW.organisation_id, NEW.interaction_id,
                           NEW.recording_session_id, NEW.created_at)
                        IS DISTINCT FROM
                       ROW(OLD.id, OLD.organisation_id, OLD.interaction_id,
                           OLD.recording_session_id, OLD.created_at) THEN
                        RAISE EXCEPTION 'Progressive transcript promotion is invalid';
                    END IF;
                ELSE
                    RAISE EXCEPTION 'Progressive transcript lifecycle transition is invalid';
                END IF;
            ELSIF OLD.status = 'final' THEN
                IF (to_jsonb(NEW) - ARRAY['status', 'deleted_at'])
                    IS DISTINCT FROM (to_jsonb(OLD) - ARRAY['status', 'deleted_at'])
                    OR NOT (
                        (NEW.status = 'final' AND NEW.deleted_at IS NOT DISTINCT FROM OLD.deleted_at)
                        OR (NEW.status = 'deleted' AND NEW.deleted_at IS NOT NULL)
                    ) THEN
                    RAISE EXCEPTION 'Transcript versions are immutable';
                END IF;
            ELSIF OLD.status = 'deleted' THEN
                IF to_jsonb(NEW) IS DISTINCT FROM to_jsonb(OLD) THEN
                    RAISE EXCEPTION 'Deleted transcript versions are immutable';
                END IF;
            ELSE
                RAISE EXCEPTION 'Transcript version lifecycle is invalid';
            END IF;
            RETURN NEW;
        END;
        $$
        """
    )
    op.execute(
        """
        CREATE OR REPLACE FUNCTION protect_transcript_segment_history()
        RETURNS trigger LANGUAGE plpgsql AS $$
        DECLARE
            parent_source text;
            parent_status text;
        BEGIN
            SELECT source, status INTO parent_source, parent_status
            FROM transcript_versions
            WHERE id = OLD.transcript_version_id
              AND organisation_id = OLD.organisation_id;

            IF to_jsonb(NEW) IS NOT DISTINCT FROM to_jsonb(OLD) THEN
                RETURN NEW;
            END IF;
            IF OLD.deleted_at IS NULL AND NEW.deleted_at IS NULL
                AND parent_source = 'progressive' AND parent_status = 'provisional'
                AND ROW(NEW.id, NEW.organisation_id, NEW.transcript_version_id,
                        NEW.sequence_number, NEW.created_at)
                    IS NOT DISTINCT FROM
                    ROW(OLD.id, OLD.organisation_id, OLD.transcript_version_id,
                        OLD.sequence_number, OLD.created_at) THEN
                RETURN NEW;
            END IF;
            IF OLD.deleted_at IS NULL AND NEW.deleted_at IS NOT NULL
                AND (to_jsonb(NEW) - 'deleted_at')
                    IS NOT DISTINCT FROM (to_jsonb(OLD) - 'deleted_at') THEN
                RETURN NEW;
            END IF;
            IF OLD.deleted_at IS NOT NULL THEN
                RAISE EXCEPTION 'Deleted transcript segments are immutable';
            END IF;
            RAISE EXCEPTION 'Transcript segments are immutable';
        END;
        $$
        """
    )


def _install_sqlite_guards() -> None:
    op.execute("DROP TRIGGER IF EXISTS transcript_versions_immutability_guard")
    op.execute("DROP TRIGGER IF EXISTS transcript_segments_immutability_guard")
    op.execute(
        """
        CREATE TRIGGER transcript_versions_immutability_guard
        BEFORE UPDATE ON transcript_versions
        FOR EACH ROW WHEN NOT (
            (
                OLD.source = 'progressive' AND OLD.status = 'provisional'
                AND (
                    (
                        NEW.source = 'progressive' AND NEW.status = 'provisional'
                        AND NEW.id IS OLD.id AND NEW.organisation_id IS OLD.organisation_id
                        AND NEW.interaction_id IS OLD.interaction_id AND NEW.meeting_id IS OLD.meeting_id
                        AND NEW.transcript_id IS OLD.transcript_id
                        AND NEW.recording_session_id IS OLD.recording_session_id
                        AND NEW.evidence_id IS OLD.evidence_id AND NEW.version IS OLD.version
                        AND NEW.language IS OLD.language
                        AND NEW.provider_request_id IS OLD.provider_request_id
                        AND NEW.created_at IS OLD.created_at AND NEW.deleted_at IS OLD.deleted_at
                    )
                    OR (
                        NEW.source = 'progressive' AND NEW.status = 'deleted'
                        AND NEW.deleted_at IS NOT NULL
                        AND NEW.id IS OLD.id AND NEW.organisation_id IS OLD.organisation_id
                        AND NEW.interaction_id IS OLD.interaction_id AND NEW.meeting_id IS OLD.meeting_id
                        AND NEW.transcript_id IS OLD.transcript_id
                        AND NEW.recording_session_id IS OLD.recording_session_id
                        AND NEW.evidence_id IS OLD.evidence_id AND NEW.version IS OLD.version
                        AND NEW.raw_text IS OLD.raw_text AND NEW.language IS OLD.language
                        AND NEW.provider_name IS OLD.provider_name
                        AND NEW.provider_request_id IS OLD.provider_request_id
                        AND NEW.created_at IS OLD.created_at
                    )
                    OR (
                        NEW.status = 'final' AND NEW.source IN ('recorded_audio', 'uploaded_audio')
                        AND NEW.deleted_at IS NULL
                        AND NEW.id IS OLD.id AND NEW.organisation_id IS OLD.organisation_id
                        AND NEW.interaction_id IS OLD.interaction_id
                        AND NEW.recording_session_id IS OLD.recording_session_id
                        AND NEW.created_at IS OLD.created_at
                    )
                )
            )
            OR (
                OLD.status = 'final'
                AND NEW.id IS OLD.id AND NEW.organisation_id IS OLD.organisation_id
                AND NEW.interaction_id IS OLD.interaction_id AND NEW.meeting_id IS OLD.meeting_id
                AND NEW.transcript_id IS OLD.transcript_id
                AND NEW.recording_session_id IS OLD.recording_session_id
                AND NEW.evidence_id IS OLD.evidence_id AND NEW.version IS OLD.version
                AND NEW.raw_text IS OLD.raw_text AND NEW.language IS OLD.language
                AND NEW.source IS OLD.source AND NEW.provider_name IS OLD.provider_name
                AND NEW.provider_request_id IS OLD.provider_request_id
                AND NEW.created_at IS OLD.created_at
                AND (
                    (NEW.status = 'final' AND NEW.deleted_at IS OLD.deleted_at)
                    OR (NEW.status = 'deleted' AND NEW.deleted_at IS NOT NULL)
                )
            )
            OR (
                OLD.status = 'deleted'
                AND NEW.id IS OLD.id AND NEW.organisation_id IS OLD.organisation_id
                AND NEW.interaction_id IS OLD.interaction_id AND NEW.meeting_id IS OLD.meeting_id
                AND NEW.transcript_id IS OLD.transcript_id
                AND NEW.recording_session_id IS OLD.recording_session_id
                AND NEW.evidence_id IS OLD.evidence_id AND NEW.version IS OLD.version
                AND NEW.raw_text IS OLD.raw_text AND NEW.language IS OLD.language
                AND NEW.source IS OLD.source AND NEW.status IS OLD.status
                AND NEW.provider_name IS OLD.provider_name
                AND NEW.provider_request_id IS OLD.provider_request_id
                AND NEW.created_at IS OLD.created_at AND NEW.deleted_at IS OLD.deleted_at
            )
        )
        BEGIN
            SELECT RAISE(ABORT, 'Transcript version lifecycle is immutable');
        END
        """
    )
    op.execute(
        """
        CREATE TRIGGER transcript_segments_immutability_guard
        BEFORE UPDATE ON transcript_segments
        FOR EACH ROW WHEN NOT (
            (
                OLD.deleted_at IS NULL AND NEW.deleted_at IS NULL
                AND NEW.id IS OLD.id AND NEW.organisation_id IS OLD.organisation_id
                AND NEW.transcript_version_id IS OLD.transcript_version_id
                AND NEW.sequence_number IS OLD.sequence_number AND NEW.created_at IS OLD.created_at
                AND EXISTS (
                    SELECT 1 FROM transcript_versions
                    WHERE transcript_versions.id = OLD.transcript_version_id
                      AND transcript_versions.organisation_id = OLD.organisation_id
                      AND transcript_versions.source = 'progressive'
                      AND transcript_versions.status = 'provisional'
                )
            )
            OR (
                OLD.deleted_at IS NULL AND NEW.deleted_at IS NOT NULL
                AND NEW.id IS OLD.id AND NEW.organisation_id IS OLD.organisation_id
                AND NEW.transcript_version_id IS OLD.transcript_version_id
                AND NEW.sequence_number IS OLD.sequence_number AND NEW.start_ms IS OLD.start_ms
                AND NEW.end_ms IS OLD.end_ms AND NEW.speaker_label IS OLD.speaker_label
                AND NEW.speaker_role IS OLD.speaker_role AND NEW.text IS OLD.text
                AND NEW.source_confidence IS OLD.source_confidence AND NEW.created_at IS OLD.created_at
            )
            OR (
                NEW.id IS OLD.id AND NEW.organisation_id IS OLD.organisation_id
                AND NEW.transcript_version_id IS OLD.transcript_version_id
                AND NEW.sequence_number IS OLD.sequence_number AND NEW.start_ms IS OLD.start_ms
                AND NEW.end_ms IS OLD.end_ms AND NEW.speaker_label IS OLD.speaker_label
                AND NEW.speaker_role IS OLD.speaker_role AND NEW.text IS OLD.text
                AND NEW.source_confidence IS OLD.source_confidence AND NEW.created_at IS OLD.created_at
                AND NEW.deleted_at IS OLD.deleted_at
            )
        )
        BEGIN
            SELECT RAISE(ABORT, 'Transcript segments are immutable');
        END
        """
    )


def _restore_legacy_postgres_guards() -> None:
    op.execute(
        """
        CREATE OR REPLACE FUNCTION protect_transcript_version_history()
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
        """
        CREATE OR REPLACE FUNCTION protect_transcript_segment_history()
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


def _restore_legacy_sqlite_guards() -> None:
    op.execute("DROP TRIGGER IF EXISTS transcript_versions_immutability_guard")
    op.execute("DROP TRIGGER IF EXISTS transcript_segments_immutability_guard")
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
            OR NEW.speaker_role IS NOT OLD.speaker_role
            OR NEW.text IS NOT OLD.text OR NEW.source_confidence IS NOT OLD.source_confidence
            OR NEW.created_at IS NOT OLD.created_at
            OR (OLD.deleted_at IS NOT NULL AND NEW.deleted_at IS NOT OLD.deleted_at)
        BEGIN
            SELECT RAISE(ABORT, 'Transcript segments are immutable');
        END
        """
    )


def upgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        _install_postgres_guards()
    elif op.get_bind().dialect.name == "sqlite":
        _install_sqlite_guards()


def downgrade() -> None:
    provisional_exists = (
        op.get_bind()
        .execute(
            sa.text(
                "SELECT 1 FROM transcript_versions "
                "WHERE source = 'progressive' AND status = 'provisional' "
                "AND deleted_at IS NULL LIMIT 1"
            )
        )
        .first()
    )
    if provisional_exists is not None:
        raise RuntimeError("Cannot downgrade progressive transcript guards while provisional progressive data exists.")
    if op.get_bind().dialect.name == "postgresql":
        _restore_legacy_postgres_guards()
    elif op.get_bind().dialect.name == "sqlite":
        _restore_legacy_sqlite_guards()
