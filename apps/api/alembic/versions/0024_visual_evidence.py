"""Add provenance-aware visual evidence and presentation capture support.

Revision ID: 0024_visual_evidence
Revises: 0023_ai_debrief_voice_journal

Downgrade warning: downgrading permanently removes visual asset metadata,
candidate review decisions and their storage lineage. Export and delete private
objects before downgrade.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0024_visual_evidence"
down_revision: str | None = "0023_ai_debrief_voice_journal"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TENANT_TABLES = ("visual_assets", "visual_candidate_evidence")


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


def _create_review_guard() -> None:
    dialect = op.get_bind().dialect.name
    if dialect == "postgresql":
        op.execute(
            """
            CREATE FUNCTION protect_visual_candidate_review()
            RETURNS trigger LANGUAGE plpgsql AS $$
            BEGIN
                IF OLD.review_state <> 'pending' THEN
                    RAISE EXCEPTION 'Reviewed visual candidate evidence is immutable';
                END IF;
                IF NEW.organisation_id <> OLD.organisation_id
                   OR NEW.id <> OLD.id
                   OR NEW.interaction_id <> OLD.interaction_id
                   OR NEW.source_visual_id <> OLD.source_visual_id
                   OR NEW.original_statement <> OLD.original_statement
                   OR NEW.statement_fingerprint <> OLD.statement_fingerprint
                   OR NEW.source_ownership <> OLD.source_ownership
                   OR NEW.origin_class <> OLD.origin_class
                   OR NEW.support_classification <> OLD.support_classification
                   OR NEW.conflict_state <> OLD.conflict_state THEN
                    RAISE EXCEPTION 'Visual candidate provenance is immutable';
                END IF;
                RETURN NEW;
            END;
            $$
            """
        )
        op.execute(
            """CREATE TRIGGER visual_candidate_evidence_review_guard
            BEFORE UPDATE ON visual_candidate_evidence
            FOR EACH ROW EXECUTE FUNCTION protect_visual_candidate_review()"""
        )
    elif dialect == "sqlite":
        op.execute(
            """
            CREATE TRIGGER visual_candidate_evidence_review_guard
            BEFORE UPDATE ON visual_candidate_evidence
            FOR EACH ROW WHEN OLD.review_state <> 'pending'
            BEGIN
                SELECT RAISE(ABORT, 'Reviewed visual candidate evidence is immutable');
            END
            """
        )


def _drop_review_guard() -> None:
    dialect = op.get_bind().dialect.name
    if dialect == "postgresql":
        op.execute("DROP TRIGGER visual_candidate_evidence_review_guard ON visual_candidate_evidence")
        op.execute("DROP FUNCTION protect_visual_candidate_review()")
    elif dialect == "sqlite":
        op.execute("DROP TRIGGER visual_candidate_evidence_review_guard")


def _widen_evidence_support() -> None:
    with op.batch_alter_table("evidence") as batch:
        batch.drop_constraint("ck_evidence_support_class", type_="check")
        batch.create_check_constraint(
            "ck_evidence_support_class",
            "support_class IN ('direct', 'reported', 'inferred', 'corroborated', "
            "'verified', 'disputed', 'stale', 'superseded', 'observed')",
        )


def _narrow_evidence_support() -> None:
    with op.batch_alter_table("evidence") as batch:
        batch.drop_constraint("ck_evidence_support_class", type_="check")
        batch.create_check_constraint(
            "ck_evidence_support_class",
            "support_class IN ('direct', 'reported', 'inferred', 'corroborated', "
            "'verified', 'disputed', 'stale', 'superseded')",
        )


def _point_intelligence_to_capture_sessions() -> None:
    dialect = op.get_bind().dialect.name
    if dialect == "sqlite":
        op.execute("DROP TRIGGER interaction_intelligence_snapshots_prevent_update")
    with op.batch_alter_table("interaction_intelligence_snapshots") as batch:
        batch.drop_constraint("fk_interaction_intelligence_session_tenant", type_="foreignkey")
        batch.create_foreign_key(
            "fk_interaction_intelligence_session_tenant",
            "capture_sessions",
            ["organisation_id", "session_id"],
            ["organisation_id", "id"],
            ondelete="RESTRICT",
        )
    if dialect == "sqlite":
        op.execute(
            """
            CREATE TRIGGER interaction_intelligence_snapshots_prevent_update
            BEFORE UPDATE ON interaction_intelligence_snapshots
            BEGIN
                SELECT RAISE(ABORT, 'WO-013 validated rows are immutable');
            END
            """
        )


def _point_intelligence_to_debrief_sessions() -> None:
    dialect = op.get_bind().dialect.name
    if dialect == "sqlite":
        op.execute("DROP TRIGGER interaction_intelligence_snapshots_prevent_update")
    with op.batch_alter_table("interaction_intelligence_snapshots") as batch:
        batch.drop_constraint("fk_interaction_intelligence_session_tenant", type_="foreignkey")
        batch.create_foreign_key(
            "fk_interaction_intelligence_session_tenant",
            "debrief_sessions",
            ["organisation_id", "session_id"],
            ["organisation_id", "id"],
            ondelete="RESTRICT",
        )
    if dialect == "sqlite":
        op.execute(
            """
            CREATE TRIGGER interaction_intelligence_snapshots_prevent_update
            BEFORE UPDATE ON interaction_intelligence_snapshots
            BEGIN
                SELECT RAISE(ABORT, 'WO-013 validated rows are immutable');
            END
            """
        )


def upgrade() -> None:
    _widen_evidence_support()
    _point_intelligence_to_capture_sessions()
    op.create_table(
        "visual_assets",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organisation_id", sa.Uuid(), nullable=False),
        sa.Column("interaction_id", sa.Uuid(), nullable=False),
        sa.Column("capture_session_id", sa.Uuid(), nullable=False),
        sa.Column("source_evidence_id", sa.Uuid(), nullable=False),
        sa.Column("captured_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("visual_type", sa.String(length=40), nullable=False),
        sa.Column("source_ownership", sa.String(length=30), nullable=False),
        sa.Column("context_label", sa.String(length=200), nullable=True),
        sa.Column("display_filename", sa.String(length=160), nullable=False),
        sa.Column("storage_key", sa.String(length=300), nullable=False),
        sa.Column("mime_type", sa.String(length=30), nullable=False),
        sa.Column("byte_size", sa.BigInteger(), nullable=False),
        sa.Column("upload_byte_size", sa.BigInteger(), nullable=False),
        sa.Column("width", sa.Integer(), nullable=True),
        sa.Column("height", sa.Integer(), nullable=True),
        sa.Column("checksum_sha256", sa.String(length=64), nullable=False),
        sa.Column("upload_checksum_sha256", sa.String(length=64), nullable=False),
        sa.Column("captured_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("upload_idempotency_key", sa.String(length=200), nullable=False),
        sa.Column("completion_idempotency_key", sa.String(length=200), nullable=True),
        sa.Column("processing_status", sa.String(length=24), server_default="uploading", nullable=False),
        sa.Column("storage_status", sa.String(length=24), server_default="pending", nullable=False),
        sa.Column("processing_attempts", sa.Integer(), server_default="0", nullable=False),
        sa.Column("provider_name", sa.String(length=40), nullable=True),
        sa.Column("provider_request_id", sa.String(length=255), nullable=True),
        sa.Column("failure_code", sa.String(length=100), nullable=True),
        sa.Column("upload_expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("upload_completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "visual_type IN ('whiteboard', 'workshop_output', 'architecture_diagram', "
            "'handwritten_notes', 'agenda', 'business_card', 'presentation_slide', "
            "'presentation_deck_page', 'customer_document_photo', 'site_photo', "
            "'product_photo', 'screenshot', 'other')",
            name="ck_visual_assets_type",
        ),
        sa.CheckConstraint(
            "source_ownership IN ('customer_created', 'salesperson_created', 'jointly_created', 'unknown_origin')",
            name="ck_visual_assets_source_ownership",
        ),
        sa.CheckConstraint("mime_type IN ('image/jpeg', 'image/png')", name="ck_visual_assets_mime_type"),
        sa.CheckConstraint("byte_size BETWEEN 1 AND 25000000", name="ck_visual_assets_byte_size"),
        sa.CheckConstraint(
            "upload_byte_size BETWEEN 1 AND 25000000",
            name="ck_visual_assets_upload_byte_size",
        ),
        sa.CheckConstraint(
            "(width IS NULL AND height IS NULL) OR (width BETWEEN 1 AND 30000 AND height BETWEEN 1 AND 30000)",
            name="ck_visual_assets_dimensions",
        ),
        sa.CheckConstraint(
            "length(checksum_sha256) = 64 AND checksum_sha256 = lower(checksum_sha256)",
            name="ck_visual_assets_checksum",
        ),
        sa.CheckConstraint(
            "length(upload_checksum_sha256) = 64 AND upload_checksum_sha256 = lower(upload_checksum_sha256)",
            name="ck_visual_assets_upload_checksum",
        ),
        sa.CheckConstraint(
            "processing_status IN ('uploading', 'uploaded', 'processing', 'review', "
            "'completed', 'failed', 'cancelled', 'deletion_pending', 'deleted')",
            name="ck_visual_assets_processing_status",
        ),
        sa.CheckConstraint(
            "storage_status IN ('pending', 'available', 'missing', 'deletion_pending', 'delete_failed', 'deleted')",
            name="ck_visual_assets_storage_status",
        ),
        sa.CheckConstraint("processing_attempts BETWEEN 0 AND 5", name="ck_visual_assets_processing_attempts"),
        sa.CheckConstraint(
            "length(trim(upload_idempotency_key)) BETWEEN 1 AND 200",
            name="ck_visual_assets_idempotency_key",
        ),
        sa.ForeignKeyConstraint(["organisation_id"], ["organisations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["organisation_id", "interaction_id"],
            ["interactions.organisation_id", "interactions.id"],
            name="fk_visual_assets_interaction_tenant",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["organisation_id", "capture_session_id"],
            ["capture_sessions.organisation_id", "capture_sessions.id"],
            name="fk_visual_assets_capture_session_tenant",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["organisation_id", "source_evidence_id"],
            ["evidence.organisation_id", "evidence.id"],
            name="fk_visual_assets_source_evidence_tenant",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organisation_id", "captured_by_user_id"],
            ["organisation_memberships.organisation_id", "organisation_memberships.user_id"],
            name="fk_visual_assets_captured_by_membership",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organisation_id", "id", name="uq_visual_assets_organisation_id_id"),
        sa.UniqueConstraint("organisation_id", "capture_session_id", name="uq_visual_assets_capture_session"),
        sa.UniqueConstraint(
            "organisation_id",
            "interaction_id",
            "captured_by_user_id",
            "upload_idempotency_key",
            name="uq_visual_assets_upload_idempotency",
        ),
        sa.UniqueConstraint("storage_key", name="uq_visual_assets_storage_key"),
    )
    op.create_index(
        "ix_visual_assets_organisation_interaction_created",
        "visual_assets",
        ["organisation_id", "interaction_id", "created_at"],
    )
    op.create_index(
        "ix_visual_assets_organisation_processing",
        "visual_assets",
        ["organisation_id", "processing_status"],
    )
    op.create_index(
        "ix_visual_assets_organisation_storage",
        "visual_assets",
        ["organisation_id", "storage_status"],
    )

    op.create_table(
        "visual_candidate_evidence",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organisation_id", sa.Uuid(), nullable=False),
        sa.Column("interaction_id", sa.Uuid(), nullable=False),
        sa.Column("source_visual_id", sa.Uuid(), nullable=False),
        sa.Column("accepted_evidence_id", sa.Uuid(), nullable=True),
        sa.Column("evidence_category", sa.String(length=40), nullable=False),
        sa.Column("statement", sa.String(length=1000), nullable=False),
        sa.Column("original_statement", sa.String(length=1000), nullable=False),
        sa.Column("statement_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("source_ownership", sa.String(length=30), nullable=False),
        sa.Column("origin_class", sa.String(length=30), server_default="ai_inferred", nullable=False),
        sa.Column("support_classification", sa.String(length=20), nullable=False),
        sa.Column("validation_state", sa.String(length=20), server_default="unreviewed", nullable=False),
        sa.Column("review_state", sa.String(length=20), server_default="pending", nullable=False),
        sa.Column("conflict_state", sa.String(length=20), server_default="not_assessed", nullable=False),
        sa.Column("confidence_class", sa.String(length=10), nullable=True),
        sa.Column("evidence_region_json", sa.JSON(), nullable=True),
        sa.Column("entity_reference", sa.String(length=200), nullable=True),
        sa.Column("extracted_text_snippet", sa.String(length=500), nullable=True),
        sa.Column("reviewed_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "evidence_category IN ('stakeholder', 'customer_request', 'decision', 'action_item', "
            "'risk', 'technical_constraint', 'implementation_requirement', 'timeline', "
            "'procurement', 'security_legal', 'budget', 'objection', 'commercial_intent', "
            "'contact_detail', 'other')",
            name="ck_visual_candidate_category",
        ),
        sa.CheckConstraint("origin_class = 'ai_inferred'", name="ck_visual_candidate_origin"),
        sa.CheckConstraint(
            "source_ownership IN ('customer_created', 'salesperson_created', 'jointly_created', 'unknown_origin')",
            name="ck_visual_candidate_source_ownership",
        ),
        sa.CheckConstraint(
            "support_classification IN ('direct', 'observed', 'context')",
            name="ck_visual_candidate_support",
        ),
        sa.CheckConstraint(
            "validation_state IN ('unreviewed', 'verified', 'rejected')",
            name="ck_visual_candidate_validation",
        ),
        sa.CheckConstraint(
            "review_state IN ('pending', 'accepted', 'rejected')",
            name="ck_visual_candidate_review",
        ),
        sa.CheckConstraint(
            "conflict_state IN ('not_assessed', 'conflicting')",
            name="ck_visual_candidate_conflict",
        ),
        sa.CheckConstraint(
            "confidence_class IS NULL OR confidence_class IN ('low', 'medium', 'high')",
            name="ck_visual_candidate_confidence",
        ),
        sa.CheckConstraint(
            "length(trim(statement)) BETWEEN 1 AND 1000 AND length(trim(original_statement)) BETWEEN 1 AND 1000",
            name="ck_visual_candidate_statements",
        ),
        sa.CheckConstraint(
            "(review_state = 'pending' AND reviewed_at IS NULL AND reviewed_by_user_id IS NULL "
            "AND accepted_evidence_id IS NULL AND validation_state = 'unreviewed') OR "
            "(review_state = 'accepted' AND reviewed_at IS NOT NULL AND reviewed_by_user_id IS NOT NULL "
            "AND accepted_evidence_id IS NOT NULL AND validation_state = 'verified') OR "
            "(review_state = 'rejected' AND reviewed_at IS NOT NULL AND reviewed_by_user_id IS NOT NULL "
            "AND accepted_evidence_id IS NULL AND validation_state = 'rejected')",
            name="ck_visual_candidate_review_consistency",
        ),
        sa.ForeignKeyConstraint(["organisation_id"], ["organisations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["organisation_id", "interaction_id"],
            ["interactions.organisation_id", "interactions.id"],
            name="fk_visual_candidate_interaction_tenant",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["organisation_id", "source_visual_id"],
            ["visual_assets.organisation_id", "visual_assets.id"],
            name="fk_visual_candidate_visual_tenant",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["organisation_id", "accepted_evidence_id"],
            ["evidence.organisation_id", "evidence.id"],
            name="fk_visual_candidate_accepted_evidence_tenant",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organisation_id", "reviewed_by_user_id"],
            ["organisation_memberships.organisation_id", "organisation_memberships.user_id"],
            name="fk_visual_candidate_reviewer_membership",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organisation_id", "id", name="uq_visual_candidate_organisation_id_id"),
        sa.UniqueConstraint(
            "organisation_id",
            "source_visual_id",
            "evidence_category",
            "statement_fingerprint",
            name="uq_visual_candidate_statement",
        ),
    )
    op.create_index(
        "ix_visual_candidate_organisation_visual_review",
        "visual_candidate_evidence",
        ["organisation_id", "source_visual_id", "review_state"],
    )
    _enable_tenant_rls()
    _create_review_guard()


def downgrade() -> None:
    _drop_review_guard()
    op.drop_table("visual_candidate_evidence")
    op.drop_table("visual_assets")
    _point_intelligence_to_debrief_sessions()
    _narrow_evidence_support()
