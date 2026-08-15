"""Add provisional live interaction intelligence.

Revision ID: 0030_live_interaction_intel
Revises: 0029_doc_email_evidence

Downgrade warning: live sessions, provisional signals, reconciliation metadata and
progressive transcript segments are permanently removed.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0030_live_interaction_intel"
down_revision: str | None = "0029_doc_email_evidence"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TENANT_TABLES = (
    "live_interaction_sessions",
    "live_processing_windows",
    "provisional_signals",
    "live_brief_progress",
)


def _restore_sqlite_transcript_immutability_guards(*, include_speaker_role: bool) -> None:
    """Restore triggers that SQLite drops while Alembic rebuilds constrained tables."""
    if op.get_bind().dialect.name != "sqlite":
        return
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
    speaker_role_guard = "OR NEW.speaker_role IS NOT OLD.speaker_role" if include_speaker_role else ""
    op.execute(
        f"""
        CREATE TRIGGER transcript_segments_immutability_guard
        BEFORE UPDATE ON transcript_segments
        FOR EACH ROW WHEN
            NEW.id IS NOT OLD.id OR NEW.organisation_id IS NOT OLD.organisation_id
            OR NEW.transcript_version_id IS NOT OLD.transcript_version_id
            OR NEW.sequence_number IS NOT OLD.sequence_number OR NEW.start_ms IS NOT OLD.start_ms
            OR NEW.end_ms IS NOT OLD.end_ms OR NEW.speaker_label IS NOT OLD.speaker_label
            {speaker_role_guard}
            OR NEW.text IS NOT OLD.text OR NEW.source_confidence IS NOT OLD.source_confidence
            OR NEW.created_at IS NOT OLD.created_at
            OR (OLD.deleted_at IS NOT NULL AND NEW.deleted_at IS NOT OLD.deleted_at)
        BEGIN
            SELECT RAISE(ABORT, 'Transcript segments are immutable');
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


def _widen_transcript_contract() -> None:
    with op.batch_alter_table("transcript_versions") as batch:
        batch.drop_constraint("ck_transcript_versions_source", type_="check")
        batch.drop_constraint("ck_transcript_versions_status", type_="check")
        batch.create_check_constraint(
            "ck_transcript_versions_source",
            "source IN ('manual', 'upload', 'recorded_audio', 'uploaded_audio', 'imported_audio', "
            "'platform_generated', 'user_uploaded', 'externally_generated', 'manually_pasted', 'progressive')",
        )
        batch.create_check_constraint(
            "ck_transcript_versions_status",
            "status IN ('provisional', 'final', 'deleted')",
        )
    with op.batch_alter_table("transcript_segments") as batch:
        batch.add_column(
            sa.Column(
                "speaker_role",
                sa.String(length=20),
                server_default="unknown",
                nullable=True,
            )
        )
        batch.create_check_constraint(
            "ck_transcript_segments_speaker_role",
            "speaker_role IS NULL OR speaker_role IN ('customer', 'salesperson', 'unknown')",
        )
    _restore_sqlite_transcript_immutability_guards(include_speaker_role=True)


def _narrow_transcript_contract() -> None:
    op.execute("DELETE FROM transcript_versions WHERE source = 'progressive' OR status = 'provisional'")
    with op.batch_alter_table("transcript_segments") as batch:
        batch.drop_constraint("ck_transcript_segments_speaker_role", type_="check")
        batch.drop_column("speaker_role")
    with op.batch_alter_table("transcript_versions") as batch:
        batch.drop_constraint("ck_transcript_versions_source", type_="check")
        batch.drop_constraint("ck_transcript_versions_status", type_="check")
        batch.create_check_constraint(
            "ck_transcript_versions_source",
            "source IN ('manual', 'upload', 'recorded_audio', 'uploaded_audio', 'imported_audio', "
            "'platform_generated', 'user_uploaded', 'externally_generated', 'manually_pasted')",
        )
        batch.create_check_constraint(
            "ck_transcript_versions_status",
            "status IN ('final', 'deleted')",
        )
    _restore_sqlite_transcript_immutability_guards(include_speaker_role=False)


def upgrade() -> None:
    _widen_transcript_contract()
    op.create_table(
        "live_interaction_sessions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organisation_id", sa.Uuid(), nullable=False),
        sa.Column("interaction_id", sa.Uuid(), nullable=False),
        sa.Column("transcript_version_id", sa.Uuid(), nullable=False),
        sa.Column("brief_id", sa.Uuid(), nullable=True),
        sa.Column("final_intelligence_id", sa.Uuid(), nullable=True),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(length=20), server_default="active", nullable=False),
        sa.Column("source_kind", sa.String(length=32), server_default="progressive_transcript", nullable=False),
        sa.Column("last_processed_sequence", sa.Integer(), server_default="-1", nullable=False),
        sa.Column("last_processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("current_window_fingerprint", sa.String(length=64), nullable=True),
        sa.Column("processed_character_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("processing_request_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("failure_code", sa.String(length=100), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("stopped_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reconciled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("retention_expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "status IN ('active', 'processing', 'stopped', 'completed', 'failed', 'expired')",
            name="ck_live_interaction_sessions_status",
        ),
        sa.CheckConstraint("source_kind = 'progressive_transcript'", name="ck_live_interaction_sessions_source"),
        sa.CheckConstraint("last_processed_sequence >= -1", name="ck_live_interaction_sessions_cursor"),
        sa.CheckConstraint("processed_character_count >= 0", name="ck_live_interaction_sessions_characters"),
        sa.CheckConstraint("processing_request_count >= 0", name="ck_live_interaction_sessions_requests"),
        sa.CheckConstraint(
            "failure_code IS NULL OR length(trim(failure_code)) BETWEEN 1 AND 100",
            name="ck_live_interaction_sessions_failure_code",
        ),
        sa.CheckConstraint(
            "stopped_at IS NULL OR stopped_at >= started_at",
            name="ck_live_interaction_sessions_time_range",
        ),
        sa.ForeignKeyConstraint(["organisation_id"], ["organisations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["organisation_id", "interaction_id"],
            ["interactions.organisation_id", "interactions.id"],
            name="fk_live_interaction_sessions_interaction_tenant",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["organisation_id", "transcript_version_id"],
            ["transcript_versions.organisation_id", "transcript_versions.id"],
            name="fk_live_interaction_sessions_transcript_tenant",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organisation_id", "brief_id"],
            ["pre_interaction_briefs.organisation_id", "pre_interaction_briefs.id"],
            name="fk_live_interaction_sessions_brief_tenant",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organisation_id", "created_by_user_id"],
            ["organisation_memberships.organisation_id", "organisation_memberships.user_id"],
            name="fk_live_interaction_sessions_creator_tenant",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organisation_id", "final_intelligence_id"],
            ["interaction_intelligence_snapshots.organisation_id", "interaction_intelligence_snapshots.id"],
            name="fk_live_interaction_sessions_final_intelligence_tenant",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organisation_id", "id", name="uq_live_interaction_sessions_org_id"),
        sa.UniqueConstraint(
            "organisation_id",
            "interaction_id",
            name="uq_live_interaction_sessions_interaction",
        ),
    )
    op.create_index(
        "ix_live_sessions_org_status_updated",
        "live_interaction_sessions",
        ["organisation_id", "status", "updated_at"],
    )
    op.create_index(
        "ix_live_sessions_org_retention",
        "live_interaction_sessions",
        ["organisation_id", "retention_expires_at"],
    )

    op.create_table(
        "live_processing_windows",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organisation_id", sa.Uuid(), nullable=False),
        sa.Column("live_session_id", sa.Uuid(), nullable=False),
        sa.Column("trigger_idempotency_key", sa.String(length=200), nullable=False),
        sa.Column("window_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("first_sequence", sa.Integer(), nullable=False),
        sa.Column("last_sequence", sa.Integer(), nullable=False),
        sa.Column("segment_count", sa.Integer(), nullable=False),
        sa.Column("character_count", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=20), server_default="processing", nullable=False),
        sa.Column("signal_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("failure_code", sa.String(length=100), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("first_sequence >= 0", name="ck_live_processing_windows_first_sequence"),
        sa.CheckConstraint(
            "last_sequence >= first_sequence",
            name="ck_live_processing_windows_last_sequence",
        ),
        sa.CheckConstraint(
            "segment_count BETWEEN 1 AND 50",
            name="ck_live_processing_windows_segment_count",
        ),
        sa.CheckConstraint(
            "character_count BETWEEN 1 AND 50000",
            name="ck_live_processing_windows_character_count",
        ),
        sa.CheckConstraint(
            "status IN ('processing', 'completed', 'no_signal', 'failed')",
            name="ck_live_processing_windows_status",
        ),
        sa.CheckConstraint("signal_count >= 0", name="ck_live_processing_windows_signals"),
        sa.CheckConstraint(
            "length(window_fingerprint) = 64",
            name="ck_live_processing_windows_fingerprint",
        ),
        sa.ForeignKeyConstraint(["organisation_id"], ["organisations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["organisation_id", "live_session_id"],
            ["live_interaction_sessions.organisation_id", "live_interaction_sessions.id"],
            name="fk_live_processing_windows_session_tenant",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organisation_id", "id", name="uq_live_processing_windows_org_id"),
        sa.UniqueConstraint(
            "organisation_id",
            "live_session_id",
            "window_fingerprint",
            name="uq_live_processing_windows_fingerprint",
        ),
        sa.UniqueConstraint(
            "organisation_id",
            "live_session_id",
            "trigger_idempotency_key",
            name="uq_live_processing_windows_trigger",
        ),
    )
    op.create_index(
        "ix_live_windows_org_created",
        "live_processing_windows",
        ["organisation_id", "created_at"],
    )

    op.create_table(
        "provisional_signals",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organisation_id", sa.Uuid(), nullable=False),
        sa.Column("interaction_id", sa.Uuid(), nullable=False),
        sa.Column("live_session_id", sa.Uuid(), nullable=False),
        sa.Column("transcript_version_id", sa.Uuid(), nullable=False),
        sa.Column("superseded_by_id", sa.Uuid(), nullable=True),
        sa.Column("signal_type", sa.String(length=32), nullable=False),
        sa.Column("statement", sa.String(length=500), nullable=False),
        sa.Column("lifecycle_status", sa.String(length=24), server_default="detected", nullable=False),
        sa.Column("is_provisional", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("priority", sa.String(length=12), server_default="normal", nullable=False),
        sa.Column("evidence_strength", sa.String(length=24), nullable=False),
        sa.Column("resolution_status", sa.String(length=16), server_default="pending", nullable=False),
        sa.Column("signal_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("subject_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("source_sequence_start", sa.Integer(), nullable=False),
        sa.Column("source_sequence_end", sa.Integer(), nullable=False),
        sa.Column("detected_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "signal_type IN ('buying_signal', 'objection', 'stakeholder', 'decision', 'action_item', "
            "'risk', 'timeline', 'procurement', 'security_legal', 'customer_request', 'commercial_intent', "
            "'objective_progress', 'open_question_progress', 'other')",
            name="ck_provisional_signals_type",
        ),
        sa.CheckConstraint(
            "lifecycle_status IN ('detected', 'updated', 'superseded', 'dismissed', 'promoted_candidate', 'expired')",
            name="ck_provisional_signals_lifecycle",
        ),
        sa.CheckConstraint("is_provisional = true", name="ck_provisional_signals_provisional"),
        sa.CheckConstraint("priority IN ('high', 'normal')", name="ck_provisional_signals_priority"),
        sa.CheckConstraint(
            "evidence_strength IN ('customer_attributed', 'speaker_uncertain', 'context_only')",
            name="ck_provisional_signals_strength",
        ),
        sa.CheckConstraint(
            "resolution_status IN ('pending', 'confirmed', 'revised', 'unsupported', 'unresolved')",
            name="ck_provisional_signals_resolution",
        ),
        sa.CheckConstraint(
            "length(trim(statement)) BETWEEN 1 AND 500",
            name="ck_provisional_signals_statement",
        ),
        sa.CheckConstraint("source_sequence_start >= 0", name="ck_provisional_signals_source_start"),
        sa.CheckConstraint(
            "source_sequence_end >= source_sequence_start",
            name="ck_provisional_signals_source_end",
        ),
        sa.CheckConstraint("length(signal_fingerprint) = 64", name="ck_provisional_signals_fingerprint"),
        sa.CheckConstraint("length(subject_fingerprint) = 64", name="ck_provisional_signals_subject"),
        sa.ForeignKeyConstraint(["organisation_id"], ["organisations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["organisation_id", "interaction_id"],
            ["interactions.organisation_id", "interactions.id"],
            name="fk_provisional_signals_interaction_tenant",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["organisation_id", "live_session_id"],
            ["live_interaction_sessions.organisation_id", "live_interaction_sessions.id"],
            name="fk_provisional_signals_session_tenant",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["organisation_id", "transcript_version_id"],
            ["transcript_versions.organisation_id", "transcript_versions.id"],
            name="fk_provisional_signals_transcript_tenant",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organisation_id", "superseded_by_id"],
            ["provisional_signals.organisation_id", "provisional_signals.id"],
            name="fk_provisional_signals_superseded_tenant",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organisation_id", "id", name="uq_provisional_signals_org_id"),
        sa.UniqueConstraint(
            "organisation_id",
            "live_session_id",
            "signal_fingerprint",
            name="uq_provisional_signals_fingerprint",
        ),
    )
    op.create_index(
        "ix_provisional_signals_org_interaction_status",
        "provisional_signals",
        ["organisation_id", "interaction_id", "lifecycle_status"],
    )

    op.create_table(
        "live_brief_progress",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organisation_id", sa.Uuid(), nullable=False),
        sa.Column("live_session_id", sa.Uuid(), nullable=False),
        sa.Column("item_type", sa.String(length=20), nullable=False),
        sa.Column("item_index", sa.Integer(), nullable=False),
        sa.Column("item_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("progress_status", sa.String(length=24), server_default="unresolved", nullable=False),
        sa.Column("source_sequence_end", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("item_type IN ('objective', 'open_question')", name="ck_live_brief_progress_type"),
        sa.CheckConstraint("item_index BETWEEN 0 AND 20", name="ck_live_brief_progress_index"),
        sa.CheckConstraint("length(item_fingerprint) = 64", name="ck_live_brief_progress_fingerprint"),
        sa.CheckConstraint(
            "progress_status IN ('unresolved', 'possibly_addressed', 'possibly_answered')",
            name="ck_live_brief_progress_status",
        ),
        sa.CheckConstraint(
            "source_sequence_end IS NULL OR source_sequence_end >= 0",
            name="ck_live_brief_progress_source",
        ),
        sa.ForeignKeyConstraint(["organisation_id"], ["organisations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["organisation_id", "live_session_id"],
            ["live_interaction_sessions.organisation_id", "live_interaction_sessions.id"],
            name="fk_live_brief_progress_session_tenant",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organisation_id", "id", name="uq_live_brief_progress_org_id"),
        sa.UniqueConstraint(
            "organisation_id",
            "live_session_id",
            "item_type",
            "item_index",
            name="uq_live_brief_progress_item",
        ),
    )
    op.create_index(
        "ix_live_brief_progress_org_session",
        "live_brief_progress",
        ["organisation_id", "live_session_id"],
    )
    _enable_tenant_rls()


def downgrade() -> None:
    op.drop_table("live_brief_progress")
    op.drop_table("provisional_signals")
    op.drop_table("live_processing_windows")
    op.drop_table("live_interaction_sessions")
    _narrow_transcript_contract()
