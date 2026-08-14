"""Add AI Debrief and Voice Journal evidence, review and snapshot models.

Revision ID: 0023_ai_debrief_voice_journal
Revises: 0022_pre_interaction_brief

Downgrade warning: downgrading permanently removes debrief answers, evidence
fragments, review decisions and source-aware Interaction/Revenue Brain snapshots.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0023_ai_debrief_voice_journal"
down_revision: str | None = "0022_pre_interaction_brief"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TENANT_TABLES = (
    "debrief_sessions",
    "debrief_turns",
    "evidence_fragments",
    "candidate_evidence",
    "interaction_intelligence_snapshots",
    "revenue_brain_interaction_snapshots",
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


def _create_immutability_guards() -> None:
    dialect = op.get_bind().dialect.name
    immutable_tables = (
        "interaction_intelligence_snapshots",
        "revenue_brain_interaction_snapshots",
    )
    if dialect == "postgresql":
        op.execute(
            """
            CREATE FUNCTION protect_wo013_immutable_row()
            RETURNS trigger LANGUAGE plpgsql AS $$
            BEGIN
                IF TG_OP = 'DELETE'
                   AND current_setting('app.beta_maintenance', true) = 'approved'
                   AND OLD.organisation_id = NULLIF(current_setting('app.organisation_id', true), '')::uuid THEN
                    RETURN OLD;
                END IF;
                RAISE EXCEPTION 'WO-013 validated rows are immutable';
            END;
            $$
            """
        )
        for table_name in immutable_tables:
            op.execute(
                f"""CREATE TRIGGER {table_name}_immutable
                BEFORE UPDATE OR DELETE ON {table_name}
                FOR EACH ROW EXECUTE FUNCTION protect_wo013_immutable_row()"""
            )
        op.execute(
            """
            CREATE FUNCTION protect_reviewed_candidate_evidence()
            RETURNS trigger LANGUAGE plpgsql AS $$
            BEGIN
                IF OLD.review_state <> 'pending' THEN
                    RAISE EXCEPTION 'Reviewed candidate evidence is immutable';
                END IF;
                IF NEW.organisation_id <> OLD.organisation_id
                   OR NEW.id <> OLD.id
                   OR NEW.interaction_id <> OLD.interaction_id
                   OR NEW.session_id <> OLD.session_id
                   OR NEW.source_fragment_id <> OLD.source_fragment_id
                   OR NEW.original_statement <> OLD.original_statement
                   OR NEW.statement_fingerprint <> OLD.statement_fingerprint
                   OR NEW.origin_class <> OLD.origin_class
                   OR NEW.support_class <> OLD.support_class THEN
                    RAISE EXCEPTION 'Candidate evidence provenance is immutable';
                END IF;
                RETURN NEW;
            END;
            $$
            """
        )
        op.execute(
            """CREATE TRIGGER candidate_evidence_review_guard
            BEFORE UPDATE ON candidate_evidence
            FOR EACH ROW EXECUTE FUNCTION protect_reviewed_candidate_evidence()"""
        )
    elif dialect == "sqlite":
        for table_name in immutable_tables:
            op.execute(
                f"""CREATE TRIGGER {table_name}_prevent_update
                BEFORE UPDATE ON {table_name}
                BEGIN
                    SELECT RAISE(ABORT, 'WO-013 validated rows are immutable');
                END"""
            )
        op.execute(
            """
            CREATE TRIGGER candidate_evidence_review_guard
            BEFORE UPDATE ON candidate_evidence
            FOR EACH ROW WHEN OLD.review_state <> 'pending'
            BEGIN
                SELECT RAISE(ABORT, 'Reviewed candidate evidence is immutable');
            END
            """
        )


def _drop_immutability_guards() -> None:
    dialect = op.get_bind().dialect.name
    if dialect == "postgresql":
        op.execute("DROP TRIGGER candidate_evidence_review_guard ON candidate_evidence")
        op.execute("DROP FUNCTION protect_reviewed_candidate_evidence()")
        for table_name in (
            "revenue_brain_interaction_snapshots",
            "interaction_intelligence_snapshots",
        ):
            op.execute(f"DROP TRIGGER {table_name}_immutable ON {table_name}")
        op.execute("DROP FUNCTION protect_wo013_immutable_row()")
    elif dialect == "sqlite":
        op.execute("DROP TRIGGER candidate_evidence_review_guard")
        op.execute("DROP TRIGGER revenue_brain_interaction_snapshots_prevent_update")
        op.execute("DROP TRIGGER interaction_intelligence_snapshots_prevent_update")


def upgrade() -> None:
    op.create_table(
        "debrief_sessions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organisation_id", sa.Uuid(), nullable=False),
        sa.Column("interaction_id", sa.Uuid(), nullable=False),
        sa.Column("started_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("lifecycle_status", sa.String(length=20), server_default="created", nullable=False),
        sa.Column("idempotency_key", sa.String(length=200), nullable=False),
        sa.Column("question_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("max_questions", sa.Integer(), server_default="6", nullable=False),
        sa.Column("current_question_json", sa.JSON(), nullable=True),
        sa.Column("safety_confirmed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("voice_processing_acknowledged_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_early", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("failure_code", sa.String(length=100), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "lifecycle_status IN ('created', 'collecting', 'processing', 'review', 'completed', 'cancelled', 'failed')",
            name="ck_debrief_sessions_lifecycle_status",
        ),
        sa.CheckConstraint("question_count >= 0", name="ck_debrief_sessions_question_count"),
        sa.CheckConstraint("max_questions BETWEEN 1 AND 10", name="ck_debrief_sessions_max_questions"),
        sa.CheckConstraint("question_count <= max_questions", name="ck_debrief_sessions_question_cap"),
        sa.CheckConstraint(
            "failure_code IS NULL OR length(failure_code) <= 100",
            name="ck_debrief_sessions_failure_code",
        ),
        sa.CheckConstraint(
            "length(trim(idempotency_key)) BETWEEN 1 AND 200",
            name="ck_debrief_sessions_idempotency_key",
        ),
        sa.ForeignKeyConstraint(["organisation_id"], ["organisations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["organisation_id", "id"],
            ["capture_sessions.organisation_id", "capture_sessions.id"],
            name="fk_debrief_sessions_capture_session_tenant",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["organisation_id", "interaction_id"],
            ["interactions.organisation_id", "interactions.id"],
            name="fk_debrief_sessions_interaction_tenant",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["organisation_id", "started_by_user_id"],
            ["organisation_memberships.organisation_id", "organisation_memberships.user_id"],
            name="fk_debrief_sessions_starter_membership",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organisation_id", "id", name="uq_debrief_sessions_organisation_id_id"),
        sa.UniqueConstraint(
            "organisation_id",
            "interaction_id",
            "started_by_user_id",
            "idempotency_key",
            name="uq_debrief_sessions_idempotency",
        ),
    )
    op.create_index(
        "ix_debrief_sessions_organisation_interaction_created",
        "debrief_sessions",
        ["organisation_id", "interaction_id", "created_at"],
    )
    op.create_index(
        "ix_debrief_sessions_organisation_status",
        "debrief_sessions",
        ["organisation_id", "lifecycle_status"],
    )

    op.create_table(
        "debrief_turns",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organisation_id", sa.Uuid(), nullable=False),
        sa.Column("interaction_id", sa.Uuid(), nullable=False),
        sa.Column("session_id", sa.Uuid(), nullable=False),
        sa.Column("evidence_id", sa.Uuid(), nullable=False),
        sa.Column("turn_number", sa.Integer(), nullable=False),
        sa.Column("question_json", sa.JSON(), nullable=False),
        sa.Column("answer_text", sa.Text(), nullable=False),
        sa.Column("input_mode", sa.String(length=10), nullable=False),
        sa.Column("idempotency_key", sa.String(length=200), nullable=False),
        sa.Column("audio_duration_seconds", sa.Integer(), nullable=True),
        sa.Column("transcription_provider", sa.String(length=40), nullable=True),
        sa.Column("transcription_request_id", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("turn_number > 0", name="ck_debrief_turns_number"),
        sa.CheckConstraint("input_mode IN ('text', 'voice')", name="ck_debrief_turns_input_mode"),
        sa.CheckConstraint(
            "length(trim(answer_text)) BETWEEN 1 AND 12000",
            name="ck_debrief_turns_answer_text",
        ),
        sa.CheckConstraint(
            "audio_duration_seconds IS NULL OR audio_duration_seconds BETWEEN 0 AND 180",
            name="ck_debrief_turns_audio_duration",
        ),
        sa.CheckConstraint(
            "length(trim(idempotency_key)) BETWEEN 1 AND 200",
            name="ck_debrief_turns_idempotency_key",
        ),
        sa.ForeignKeyConstraint(["organisation_id"], ["organisations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["organisation_id", "interaction_id"],
            ["interactions.organisation_id", "interactions.id"],
            name="fk_debrief_turns_interaction_tenant",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["organisation_id", "session_id"],
            ["debrief_sessions.organisation_id", "debrief_sessions.id"],
            name="fk_debrief_turns_session_tenant",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["organisation_id", "evidence_id"],
            ["evidence.organisation_id", "evidence.id"],
            name="fk_debrief_turns_evidence_tenant",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organisation_id", "id", name="uq_debrief_turns_organisation_id_id"),
        sa.UniqueConstraint("organisation_id", "session_id", "turn_number", name="uq_debrief_turns_session_number"),
        sa.UniqueConstraint("organisation_id", "session_id", "idempotency_key", name="uq_debrief_turns_idempotency"),
    )
    op.create_index(
        "ix_debrief_turns_organisation_session_number",
        "debrief_turns",
        ["organisation_id", "session_id", "turn_number"],
    )

    op.create_table(
        "evidence_fragments",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organisation_id", sa.Uuid(), nullable=False),
        sa.Column("evidence_id", sa.Uuid(), nullable=False),
        sa.Column("session_id", sa.Uuid(), nullable=False),
        sa.Column("turn_id", sa.Uuid(), nullable=False),
        sa.Column("locator_type", sa.String(length=30), server_default="debrief_turn", nullable=False),
        sa.Column("content_text", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("locator_type = 'debrief_turn'", name="ck_evidence_fragments_locator_type"),
        sa.CheckConstraint(
            "length(trim(content_text)) BETWEEN 1 AND 12000",
            name="ck_evidence_fragments_content_text",
        ),
        sa.ForeignKeyConstraint(["organisation_id"], ["organisations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["organisation_id", "evidence_id"],
            ["evidence.organisation_id", "evidence.id"],
            name="fk_evidence_fragments_evidence_tenant",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["organisation_id", "session_id"],
            ["debrief_sessions.organisation_id", "debrief_sessions.id"],
            name="fk_evidence_fragments_session_tenant",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["organisation_id", "turn_id"],
            ["debrief_turns.organisation_id", "debrief_turns.id"],
            name="fk_evidence_fragments_turn_tenant",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organisation_id", "id", name="uq_evidence_fragments_organisation_id_id"),
        sa.UniqueConstraint("organisation_id", "turn_id", name="uq_evidence_fragments_turn"),
    )
    op.create_index(
        "ix_evidence_fragments_organisation_evidence",
        "evidence_fragments",
        ["organisation_id", "evidence_id"],
    )

    op.create_table(
        "candidate_evidence",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organisation_id", sa.Uuid(), nullable=False),
        sa.Column("interaction_id", sa.Uuid(), nullable=False),
        sa.Column("session_id", sa.Uuid(), nullable=False),
        sa.Column("source_fragment_id", sa.Uuid(), nullable=False),
        sa.Column("accepted_evidence_id", sa.Uuid(), nullable=True),
        sa.Column("evidence_category", sa.String(length=30), nullable=False),
        sa.Column("statement", sa.String(length=1000), nullable=False),
        sa.Column("original_statement", sa.String(length=1000), nullable=False),
        sa.Column("statement_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("origin_class", sa.String(length=30), server_default="salesperson_reported", nullable=False),
        sa.Column("support_class", sa.String(length=20), server_default="reported", nullable=False),
        sa.Column("validation_state", sa.String(length=20), server_default="unreviewed", nullable=False),
        sa.Column("entity_reference", sa.String(length=200), nullable=True),
        sa.Column("explicitly_reported_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("review_state", sa.String(length=20), server_default="pending", nullable=False),
        sa.Column("reviewed_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "evidence_category IN ('stakeholder', 'buying_signal', 'objection', 'competitor', "
            "'risk', 'decision', 'action_item', 'open_question', 'commitment', 'timeline', "
            "'procurement', 'budget', 'security_legal', 'implementation', 'commercial_intent', "
            "'customer_request', 'other')",
            name="ck_candidate_evidence_category",
        ),
        sa.CheckConstraint("origin_class = 'salesperson_reported'", name="ck_candidate_evidence_origin"),
        sa.CheckConstraint("support_class = 'reported'", name="ck_candidate_evidence_support"),
        sa.CheckConstraint(
            "validation_state IN ('unreviewed', 'verified', 'rejected')",
            name="ck_candidate_evidence_validation_state",
        ),
        sa.CheckConstraint(
            "review_state IN ('pending', 'accepted', 'rejected')",
            name="ck_candidate_evidence_review_state",
        ),
        sa.CheckConstraint(
            "length(trim(statement)) BETWEEN 1 AND 1000 AND length(trim(original_statement)) BETWEEN 1 AND 1000",
            name="ck_candidate_evidence_statements",
        ),
        sa.CheckConstraint(
            "(review_state = 'pending' AND reviewed_at IS NULL AND reviewed_by_user_id IS NULL "
            "AND accepted_evidence_id IS NULL AND validation_state = 'unreviewed') OR "
            "(review_state = 'accepted' AND reviewed_at IS NOT NULL AND reviewed_by_user_id IS NOT NULL "
            "AND accepted_evidence_id IS NOT NULL AND validation_state = 'verified') OR "
            "(review_state = 'rejected' AND reviewed_at IS NOT NULL AND reviewed_by_user_id IS NOT NULL "
            "AND accepted_evidence_id IS NULL AND validation_state = 'rejected')",
            name="ck_candidate_evidence_review_consistency",
        ),
        sa.ForeignKeyConstraint(["organisation_id"], ["organisations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["organisation_id", "interaction_id"],
            ["interactions.organisation_id", "interactions.id"],
            name="fk_candidate_evidence_interaction_tenant",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["organisation_id", "session_id"],
            ["debrief_sessions.organisation_id", "debrief_sessions.id"],
            name="fk_candidate_evidence_session_tenant",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["organisation_id", "source_fragment_id"],
            ["evidence_fragments.organisation_id", "evidence_fragments.id"],
            name="fk_candidate_evidence_fragment_tenant",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organisation_id", "accepted_evidence_id"],
            ["evidence.organisation_id", "evidence.id"],
            name="fk_candidate_evidence_accepted_evidence_tenant",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organisation_id", "reviewed_by_user_id"],
            ["organisation_memberships.organisation_id", "organisation_memberships.user_id"],
            name="fk_candidate_evidence_reviewer_membership",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organisation_id", "id", name="uq_candidate_evidence_organisation_id_id"),
        sa.UniqueConstraint(
            "organisation_id",
            "session_id",
            "evidence_category",
            "statement_fingerprint",
            name="uq_candidate_evidence_session_statement",
        ),
    )
    op.create_index(
        "ix_candidate_evidence_organisation_session_review",
        "candidate_evidence",
        ["organisation_id", "session_id", "review_state"],
    )

    op.create_table(
        "interaction_intelligence_snapshots",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organisation_id", sa.Uuid(), nullable=False),
        sa.Column("interaction_id", sa.Uuid(), nullable=False),
        sa.Column("opportunity_id", sa.Uuid(), nullable=True),
        sa.Column("session_id", sa.Uuid(), nullable=False),
        sa.Column("schema_version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("validation_state", sa.String(length=20), server_default="validated", nullable=False),
        sa.Column("content_json", sa.JSON(), nullable=False),
        sa.Column("source_evidence_ids", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("schema_version > 0", name="ck_interaction_intelligence_schema_version"),
        sa.CheckConstraint("version > 0", name="ck_interaction_intelligence_version"),
        sa.CheckConstraint("validation_state = 'validated'", name="ck_interaction_intelligence_validation"),
        sa.ForeignKeyConstraint(["organisation_id"], ["organisations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["organisation_id", "interaction_id"],
            ["interactions.organisation_id", "interactions.id"],
            name="fk_interaction_intelligence_interaction_tenant",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["organisation_id", "opportunity_id"],
            ["opportunities.organisation_id", "opportunities.id"],
            name="fk_interaction_intelligence_opportunity_tenant",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organisation_id", "session_id"],
            ["debrief_sessions.organisation_id", "debrief_sessions.id"],
            name="fk_interaction_intelligence_session_tenant",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organisation_id", "id", name="uq_interaction_intelligence_organisation_id_id"),
        sa.UniqueConstraint(
            "organisation_id",
            "interaction_id",
            "version",
            name="uq_interaction_intelligence_logical_version",
        ),
        sa.UniqueConstraint("organisation_id", "session_id", name="uq_interaction_intelligence_session"),
    )
    op.create_index(
        "ix_interaction_intelligence_organisation_opportunity_created",
        "interaction_intelligence_snapshots",
        ["organisation_id", "opportunity_id", "created_at"],
    )

    op.create_table(
        "revenue_brain_interaction_snapshots",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organisation_id", sa.Uuid(), nullable=False),
        sa.Column("company_id", sa.Uuid(), nullable=False),
        sa.Column("opportunity_id", sa.Uuid(), nullable=True),
        sa.Column("interaction_id", sa.Uuid(), nullable=False),
        sa.Column("interaction_intelligence_id", sa.Uuid(), nullable=False),
        sa.Column("schema_version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("content_json", sa.JSON(), nullable=False),
        sa.Column("source_evidence_ids", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("schema_version > 0", name="ck_revenue_brain_interaction_schema_version"),
        sa.CheckConstraint("version > 0", name="ck_revenue_brain_interaction_version"),
        sa.ForeignKeyConstraint(["organisation_id"], ["organisations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["organisation_id", "company_id"],
            ["companies.organisation_id", "companies.id"],
            name="fk_revenue_brain_interaction_company_tenant",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organisation_id", "opportunity_id"],
            ["opportunities.organisation_id", "opportunities.id"],
            name="fk_revenue_brain_interaction_opportunity_tenant",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organisation_id", "interaction_id"],
            ["interactions.organisation_id", "interactions.id"],
            name="fk_revenue_brain_interaction_interaction_tenant",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organisation_id", "interaction_intelligence_id"],
            ["interaction_intelligence_snapshots.organisation_id", "interaction_intelligence_snapshots.id"],
            name="fk_revenue_brain_interaction_intelligence_tenant",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organisation_id", "id", name="uq_revenue_brain_interaction_organisation_id_id"),
        sa.UniqueConstraint(
            "organisation_id",
            "interaction_id",
            "interaction_intelligence_id",
            name="uq_revenue_brain_interaction_source",
        ),
    )
    op.create_index(
        "ix_revenue_brain_interaction_organisation_opportunity_created",
        "revenue_brain_interaction_snapshots",
        ["organisation_id", "opportunity_id", "created_at"],
    )
    op.create_index(
        "ix_revenue_brain_interaction_organisation_company_created",
        "revenue_brain_interaction_snapshots",
        ["organisation_id", "company_id", "created_at"],
    )

    _enable_tenant_rls()
    _create_immutability_guards()


def downgrade() -> None:
    _drop_immutability_guards()
    op.drop_table("revenue_brain_interaction_snapshots")
    op.drop_table("interaction_intelligence_snapshots")
    op.drop_table("candidate_evidence")
    op.drop_table("evidence_fragments")
    op.drop_table("debrief_turns")
    op.drop_table("debrief_sessions")
