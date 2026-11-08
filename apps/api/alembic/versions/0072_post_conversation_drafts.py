"""Add transcript-versioned private post-conversation drafts.

Revision ID: 0072_post_conversation_drafts
Revises: 0071_assignment_tombstones

The additive table records one owner-private generation per final transcript
version. Generated content remains distinct from the editable private workspace
so late corrections and retries cannot silently replace user edits.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0072_post_conversation_drafts"
down_revision: str | None = "0071_assignment_tombstones"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _enable_private_rls() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return
    op.execute("ALTER TABLE conversation_draft_generations ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE conversation_draft_generations FORCE ROW LEVEL SECURITY")
    op.execute(
        """CREATE POLICY conversation_draft_generations_owner_isolation
        ON conversation_draft_generations
        USING (
            organisation_id = NULLIF(current_setting('app.organisation_id', true), '')::uuid
            AND user_id = NULLIF(current_setting('app.user_id', true), '')::uuid
        )
        WITH CHECK (
            organisation_id = NULLIF(current_setting('app.organisation_id', true), '')::uuid
            AND user_id = NULLIF(current_setting('app.user_id', true), '')::uuid
        )"""
    )


def _create_worker_discovery() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return
    op.execute(
        """
        CREATE FUNCTION public.revenueos_post_conversation_draft_worker_scopes(result_limit integer)
        RETURNS TABLE (organisation_id uuid, user_id uuid)
        LANGUAGE sql
        SECURITY DEFINER
        SET search_path = pg_catalog, public
        AS $$
            WITH final_sources AS (
                SELECT
                    versions.organisation_id,
                    COALESCE(
                        recordings.created_by_user_id,
                        evidence.captured_by_user_id,
                        interactions.created_by_user_id
                    ) AS user_id,
                    versions.id AS transcript_version_id
                FROM public.transcript_versions AS versions
                JOIN public.transcripts AS transcripts
                  ON transcripts.organisation_id = versions.organisation_id
                 AND transcripts.id = versions.transcript_id
                 AND transcripts.version = versions.version
                 AND transcripts.deleted_at IS NULL
                JOIN public.interactions AS interactions
                  ON interactions.organisation_id = versions.organisation_id
                 AND interactions.id = versions.interaction_id
                 AND interactions.lifecycle_status = 'completed'
                 AND interactions.deleted_at IS NULL
                LEFT JOIN public.recording_sessions AS recordings
                  ON recordings.organisation_id = versions.organisation_id
                 AND recordings.id = COALESCE(
                     versions.recording_session_id,
                     (
                         SELECT lineage.recording_session_id
                         FROM public.transcript_versions AS lineage
                         WHERE lineage.organisation_id = versions.organisation_id
                           AND lineage.transcript_id = versions.transcript_id
                           AND lineage.version <= versions.version
                           AND lineage.recording_session_id IS NOT NULL
                         ORDER BY lineage.version DESC, lineage.id DESC
                         LIMIT 1
                     )
                 )
                LEFT JOIN public.evidence AS evidence
                  ON evidence.organisation_id = versions.organisation_id
                 AND evidence.id = COALESCE(
                     versions.evidence_id,
                     (
                         SELECT lineage.evidence_id
                         FROM public.transcript_versions AS lineage
                         WHERE lineage.organisation_id = versions.organisation_id
                           AND lineage.transcript_id = versions.transcript_id
                           AND lineage.version <= versions.version
                           AND lineage.evidence_id IS NOT NULL
                         ORDER BY lineage.version DESC, lineage.id DESC
                         LIMIT 1
                     )
                 )
                WHERE versions.status = 'final'
                  AND versions.deleted_at IS NULL
                  AND versions.meeting_id IS NOT NULL
            ), eligible_sources AS (
                SELECT sources.organisation_id, sources.user_id
                FROM final_sources AS sources
                JOIN public.organisation_memberships AS memberships
                  ON memberships.organisation_id = sources.organisation_id
                 AND memberships.user_id = sources.user_id
                 AND memberships.status = 'active'
                JOIN public.users AS users
                  ON users.id = sources.user_id
                 AND users.status = 'active'
                WHERE NOT EXISTS (
                    SELECT 1
                    FROM public.conversation_draft_generations AS generations
                    WHERE generations.organisation_id = sources.organisation_id
                      AND generations.user_id = sources.user_id
                      AND generations.transcript_version_id = sources.transcript_version_id
                )
            ), active_generations AS (
                SELECT generations.organisation_id, generations.user_id
                FROM public.conversation_draft_generations AS generations
                WHERE generations.status IN ('pending', 'processing')
            )
            SELECT scopes.organisation_id, scopes.user_id
            FROM (
                SELECT * FROM eligible_sources
                UNION
                SELECT * FROM active_generations
            ) AS scopes
            ORDER BY scopes.organisation_id, scopes.user_id
            LIMIT LEAST(GREATEST(COALESCE(result_limit, 1), 1), 1000)
        $$
        """
    )
    # Cross-tenant worker discovery is an explicit privileged capability. The
    # migration owner retains execution; activation must grant this exact
    # function to the deployment's least-privilege runtime role.
    op.execute("REVOKE ALL ON FUNCTION public.revenueos_post_conversation_draft_worker_scopes(integer) FROM PUBLIC")


def upgrade() -> None:
    uuid_type = sa.Uuid(as_uuid=True)
    with op.batch_alter_table("conversation_user_workspaces") as batch:
        batch.add_column(sa.Column("user_edited_at", sa.DateTime(timezone=True), nullable=True))
    op.create_table(
        "conversation_draft_generations",
        sa.Column("id", uuid_type, nullable=False),
        sa.Column("organisation_id", uuid_type, nullable=False),
        sa.Column("interaction_id", uuid_type, nullable=False),
        sa.Column("meeting_id", uuid_type, nullable=False),
        sa.Column("transcript_version_id", uuid_type, nullable=False),
        sa.Column("transcript_version", sa.Integer(), nullable=False),
        sa.Column("source_recording_session_id", uuid_type, nullable=True),
        sa.Column("source_evidence_id", uuid_type, nullable=True),
        sa.Column("user_id", uuid_type, nullable=False),
        sa.Column("status", sa.String(length=20), server_default="pending", nullable=False),
        sa.Column("source_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("content_fingerprint", sa.String(length=64), nullable=True),
        sa.Column("enhanced_notes", sa.Text(), nullable=True),
        sa.Column("follow_up_draft", sa.Text(), nullable=True),
        sa.Column("framework_included", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("attempt_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("orchestration_attempt_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("max_attempts", sa.Integer(), server_default="3", nullable=False),
        sa.Column("worker_id", sa.String(length=200), nullable=True),
        sa.Column("lease_mode", sa.String(length=20), nullable=True),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failure_code", sa.String(length=100), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("workspace_applied_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "status IN ('pending', 'processing', 'ready', 'failed', 'cancelled')",
            name="ck_conversation_draft_generations_status",
        ),
        sa.CheckConstraint("transcript_version > 0", name="ck_conversation_draft_generations_version"),
        sa.CheckConstraint(
            "attempt_count BETWEEN 0 AND max_attempts AND max_attempts BETWEEN 1 AND 20",
            name="ck_conversation_draft_generations_attempts",
        ),
        sa.CheckConstraint(
            "orchestration_attempt_count BETWEEN 0 AND attempt_count",
            name="ck_conversation_draft_gen_orchestration",
        ),
        sa.CheckConstraint(
            "lease_mode IS NULL OR lease_mode IN ('orchestrate', 'poll')",
            name="ck_conversation_draft_gen_lease_mode",
        ),
        sa.CheckConstraint(
            "(status = 'ready' AND enhanced_notes IS NOT NULL AND follow_up_draft IS NOT NULL "
            "AND content_fingerprint IS NOT NULL AND completed_at IS NOT NULL) OR status <> 'ready'",
            name="ck_conversation_draft_generations_ready",
        ),
        sa.ForeignKeyConstraint(["organisation_id"], ["organisations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["organisation_id", "interaction_id"],
            ["interactions.organisation_id", "interactions.id"],
            name="fk_conversation_draft_generations_interaction",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["organisation_id", "meeting_id"],
            ["meetings.organisation_id", "meetings.id"],
            name="fk_conversation_draft_generations_meeting",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["organisation_id", "transcript_version_id"],
            ["transcript_versions.organisation_id", "transcript_versions.id"],
            name="fk_conversation_draft_generations_transcript_version",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["organisation_id", "source_recording_session_id"],
            ["recording_sessions.organisation_id", "recording_sessions.id"],
            name="fk_conversation_draft_generations_source_recording",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organisation_id", "source_evidence_id"],
            ["evidence.organisation_id", "evidence.id"],
            name="fk_conversation_draft_generations_source_evidence",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organisation_id", "user_id"],
            ["organisation_memberships.organisation_id", "organisation_memberships.user_id"],
            name="fk_conversation_draft_generations_user",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organisation_id", "id", name="uq_conversation_draft_generations_org_id"),
        sa.UniqueConstraint(
            "organisation_id",
            "transcript_version_id",
            "user_id",
            name="uq_conversation_draft_generations_source_owner",
        ),
    )
    op.create_index(
        "ix_conversation_draft_generations_owner_status",
        "conversation_draft_generations",
        ["organisation_id", "user_id", "status", "created_at"],
    )
    _enable_private_rls()
    _create_worker_discovery()


def downgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        op.execute("DROP FUNCTION IF EXISTS public.revenueos_post_conversation_draft_worker_scopes(integer)")
    op.drop_index(
        "ix_conversation_draft_generations_owner_status",
        table_name="conversation_draft_generations",
    )
    op.drop_table("conversation_draft_generations")
    with op.batch_alter_table("conversation_user_workspaces") as batch:
        batch.drop_column("user_edited_at")
