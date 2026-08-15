"""Add provenance-aware document and email evidence.

Revision ID: 0029_doc_email_evidence
Revises: 0028_online_meeting_capture

Downgrade warning: source files, parsed document text, email bodies, review
decisions and source-aware Revenue Brain projections are permanently removed.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0029_doc_email_evidence"
down_revision: str | None = "0028_online_meeting_capture"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TENANT_TABLES = (
    "document_sources",
    "document_fragments",
    "email_sources",
    "source_candidate_evidence",
    "revenue_brain_source_snapshots",
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
    if dialect == "postgresql":
        op.execute(
            """
            CREATE FUNCTION protect_wo019_immutable_rows()
            RETURNS trigger
            LANGUAGE plpgsql
            AS $$
            BEGIN
                RAISE EXCEPTION 'Accepted document and email evidence lineage is immutable';
            END;
            $$
            """
        )
        op.execute(
            """
            CREATE TRIGGER revenue_brain_source_snapshots_immutable
            BEFORE UPDATE ON revenue_brain_source_snapshots
            FOR EACH ROW EXECUTE FUNCTION protect_wo019_immutable_rows()
            """
        )
    elif dialect == "sqlite":
        op.execute(
            """
            CREATE TRIGGER revenue_brain_source_snapshots_immutable
            BEFORE UPDATE ON revenue_brain_source_snapshots
            FOR EACH ROW
            BEGIN
                SELECT RAISE(ABORT, 'Accepted document and email evidence lineage is immutable');
            END
            """
        )


def _drop_immutability_guards() -> None:
    dialect = op.get_bind().dialect.name
    if dialect == "postgresql":
        op.execute("DROP TRIGGER revenue_brain_source_snapshots_immutable ON revenue_brain_source_snapshots")
        op.execute("DROP FUNCTION protect_wo019_immutable_rows()")
    elif dialect == "sqlite":
        op.execute("DROP TRIGGER revenue_brain_source_snapshots_immutable")


def _widen_capture_sessions() -> None:
    with op.batch_alter_table("capture_sessions") as batch:
        batch.drop_constraint("ck_capture_sessions_type", type_="check")
        batch.alter_column("interaction_id", existing_type=sa.Uuid(), nullable=True)
        batch.create_check_constraint(
            "ck_capture_sessions_type",
            "capture_type IN ('ai_debrief', 'voice_journal', 'live_recording', 'live_audio_recording', "
            "'visual_capture', 'uploaded_transcript', 'uploaded_recording', 'uploaded_audio_recording', "
            "'imported_audio_recording', 'document_import', 'email_import', 'manual_notes')",
        )
    with op.batch_alter_table("evidence") as batch:
        batch.alter_column("interaction_id", existing_type=sa.Uuid(), nullable=True)
        batch.drop_constraint("ck_evidence_support_class", type_="check")
        batch.create_check_constraint(
            "ck_evidence_support_class",
            "support_class IN ('direct', 'reported', 'context', 'inferred', 'corroborated', "
            "'verified', 'disputed', 'stale', 'superseded', 'observed')",
        )


def _narrow_capture_sessions() -> None:
    op.execute("DELETE FROM evidence WHERE evidence_type IN ('document', 'email')")
    op.execute("DELETE FROM capture_sessions WHERE capture_type IN ('document_import', 'email_import')")
    with op.batch_alter_table("evidence") as batch:
        batch.drop_constraint("ck_evidence_support_class", type_="check")
        batch.create_check_constraint(
            "ck_evidence_support_class",
            "support_class IN ('direct', 'reported', 'inferred', 'corroborated', "
            "'verified', 'disputed', 'stale', 'superseded', 'observed')",
        )
        batch.alter_column("interaction_id", existing_type=sa.Uuid(), nullable=False)
    with op.batch_alter_table("capture_sessions") as batch:
        batch.drop_constraint("ck_capture_sessions_type", type_="check")
        batch.alter_column("interaction_id", existing_type=sa.Uuid(), nullable=False)
        batch.create_check_constraint(
            "ck_capture_sessions_type",
            "capture_type IN ('ai_debrief', 'voice_journal', 'live_recording', 'live_audio_recording', "
            "'visual_capture', 'uploaded_transcript', 'uploaded_recording', 'uploaded_audio_recording', "
            "'imported_audio_recording', 'manual_notes')",
        )


def upgrade() -> None:
    _widen_capture_sessions()
    op.create_table(
        "document_sources",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organisation_id", sa.Uuid(), nullable=False),
        sa.Column("company_id", sa.Uuid(), nullable=True),
        sa.Column("opportunity_id", sa.Uuid(), nullable=True),
        sa.Column("interaction_id", sa.Uuid(), nullable=True),
        sa.Column("capture_session_id", sa.Uuid(), nullable=False),
        sa.Column("source_evidence_id", sa.Uuid(), nullable=False),
        sa.Column("uploaded_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("document_type", sa.String(length=40), nullable=False),
        sa.Column("source_ownership", sa.String(length=30), nullable=False),
        sa.Column("display_filename", sa.String(length=160), nullable=False),
        sa.Column("storage_key", sa.String(length=360), nullable=False),
        sa.Column("mime_type", sa.String(length=40), nullable=False),
        sa.Column("byte_size", sa.BigInteger(), nullable=False),
        sa.Column("checksum_sha256", sa.String(length=64), nullable=False),
        sa.Column("document_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("idempotency_key", sa.String(length=200), nullable=False),
        sa.Column("processing_status", sa.String(length=24), server_default="received", nullable=False),
        sa.Column("storage_status", sa.String(length=24), server_default="available", nullable=False),
        sa.Column("processing_attempts", sa.Integer(), server_default="0", nullable=False),
        sa.Column("page_count", sa.Integer(), nullable=True),
        sa.Column("extracted_character_count", sa.Integer(), nullable=True),
        sa.Column("provider_name", sa.String(length=40), nullable=True),
        sa.Column("provider_request_id", sa.String(length=255), nullable=True),
        sa.Column("failure_code", sa.String(length=100), nullable=True),
        sa.Column("authority_confirmed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("external_processing_acknowledged_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "document_type IN ('proposal', 'rfp', 'rfq', 'requirements', 'contract', 'sow', 'pricing', "
            "'procurement', 'security_questionnaire', 'implementation_plan', 'technical_specification', "
            "'customer_presentation', 'sales_material', 'other')",
            name="ck_document_sources_type",
        ),
        sa.CheckConstraint(
            "source_ownership IN ('customer_provided', 'salesperson_provided', 'jointly_created', "
            "'externally_generated', 'system_imported', 'unknown')",
            name="ck_document_sources_ownership",
        ),
        sa.CheckConstraint("mime_type IN ('application/pdf', 'text/plain')", name="ck_document_sources_mime"),
        sa.CheckConstraint("byte_size BETWEEN 1 AND 50000000", name="ck_document_sources_size"),
        sa.CheckConstraint(
            "length(checksum_sha256) = 64 AND checksum_sha256 = lower(checksum_sha256)",
            name="ck_document_sources_checksum",
        ),
        sa.CheckConstraint(
            "processing_status IN ('received', 'processing', 'review', 'completed', 'failed', "
            "'deletion_pending', 'deleted')",
            name="ck_document_sources_processing",
        ),
        sa.CheckConstraint(
            "storage_status IN ('available', 'missing', 'deletion_pending', 'delete_failed', 'deleted')",
            name="ck_document_sources_storage",
        ),
        sa.CheckConstraint("processing_attempts BETWEEN 0 AND 5", name="ck_document_sources_attempts"),
        sa.CheckConstraint("page_count IS NULL OR page_count BETWEEN 1 AND 500", name="ck_document_sources_pages"),
        sa.CheckConstraint(
            "extracted_character_count IS NULL OR extracted_character_count BETWEEN 1 AND 2000000",
            name="ck_document_sources_characters",
        ),
        sa.CheckConstraint(
            "company_id IS NOT NULL OR opportunity_id IS NOT NULL OR interaction_id IS NOT NULL",
            name="ck_document_sources_association",
        ),
        sa.ForeignKeyConstraint(["organisation_id"], ["organisations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["organisation_id", "company_id"],
            ["companies.organisation_id", "companies.id"],
            name="fk_document_sources_company_tenant",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organisation_id", "opportunity_id"],
            ["opportunities.organisation_id", "opportunities.id"],
            name="fk_document_sources_opportunity_tenant",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organisation_id", "interaction_id"],
            ["interactions.organisation_id", "interactions.id"],
            name="fk_document_sources_interaction_tenant",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organisation_id", "capture_session_id"],
            ["capture_sessions.organisation_id", "capture_sessions.id"],
            name="fk_document_sources_capture_tenant",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organisation_id", "source_evidence_id"],
            ["evidence.organisation_id", "evidence.id"],
            name="fk_document_sources_evidence_tenant",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organisation_id", "uploaded_by_user_id"],
            ["organisation_memberships.organisation_id", "organisation_memberships.user_id"],
            name="fk_document_sources_user_tenant",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organisation_id", "id", name="uq_document_sources_org_id"),
        sa.UniqueConstraint("organisation_id", "source_evidence_id", name="uq_document_sources_evidence"),
        sa.UniqueConstraint("organisation_id", "checksum_sha256", name="uq_document_sources_content"),
        sa.UniqueConstraint(
            "organisation_id", "uploaded_by_user_id", "idempotency_key", name="uq_document_sources_idempotency"
        ),
        sa.UniqueConstraint("storage_key", name="uq_document_sources_storage_key"),
    )
    op.create_index(
        "ix_document_sources_org_opportunity", "document_sources", ["organisation_id", "opportunity_id", "created_at"]
    )
    op.create_index(
        "ix_document_sources_org_company", "document_sources", ["organisation_id", "company_id", "created_at"]
    )
    op.create_index("ix_document_sources_org_status", "document_sources", ["organisation_id", "processing_status"])

    op.create_table(
        "document_fragments",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organisation_id", sa.Uuid(), nullable=False),
        sa.Column("document_source_id", sa.Uuid(), nullable=False),
        sa.Column("source_evidence_id", sa.Uuid(), nullable=False),
        sa.Column("page_number", sa.Integer(), nullable=True),
        sa.Column("section", sa.String(length=200), nullable=True),
        sa.Column("paragraph_index", sa.Integer(), nullable=False),
        sa.Column("content_text", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("page_number IS NULL OR page_number BETWEEN 1 AND 500", name="ck_document_fragments_page"),
        sa.CheckConstraint("paragraph_index BETWEEN 0 AND 100000", name="ck_document_fragments_paragraph"),
        sa.CheckConstraint("length(trim(content_text)) BETWEEN 1 AND 12000", name="ck_document_fragments_content"),
        sa.ForeignKeyConstraint(["organisation_id"], ["organisations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["organisation_id", "document_source_id"],
            ["document_sources.organisation_id", "document_sources.id"],
            name="fk_document_fragments_source_tenant",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["organisation_id", "source_evidence_id"],
            ["evidence.organisation_id", "evidence.id"],
            name="fk_document_fragments_evidence_tenant",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organisation_id", "id", name="uq_document_fragments_org_id"),
        sa.UniqueConstraint(
            "organisation_id",
            "document_source_id",
            "page_number",
            "paragraph_index",
            name="uq_document_fragments_locator",
        ),
    )
    op.create_index("ix_document_fragments_org_source", "document_fragments", ["organisation_id", "document_source_id"])

    op.create_table(
        "email_sources",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organisation_id", sa.Uuid(), nullable=False),
        sa.Column("company_id", sa.Uuid(), nullable=True),
        sa.Column("opportunity_id", sa.Uuid(), nullable=True),
        sa.Column("interaction_id", sa.Uuid(), nullable=True),
        sa.Column("capture_session_id", sa.Uuid(), nullable=False),
        sa.Column("source_evidence_id", sa.Uuid(), nullable=False),
        sa.Column("submitted_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("sender_contact_id", sa.Uuid(), nullable=True),
        sa.Column("source_type", sa.String(length=32), nullable=False),
        sa.Column("direction", sa.String(length=16), nullable=False),
        sa.Column("sender_identity_state", sa.String(length=24), nullable=False),
        sa.Column("origin_class", sa.String(length=30), nullable=False),
        sa.Column("support_class", sa.String(length=20), nullable=False),
        sa.Column("subject", sa.String(length=500), nullable=True),
        sa.Column("body_text", sa.Text(), nullable=False),
        sa.Column("normalized_body_text", sa.Text(), nullable=False),
        sa.Column("quote_handling", sa.String(length=16), nullable=False),
        sa.Column("message_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("content_sha256", sa.String(length=64), nullable=False),
        sa.Column("idempotency_key", sa.String(length=200), nullable=False),
        sa.Column("processing_status", sa.String(length=24), server_default="received", nullable=False),
        sa.Column("processing_attempts", sa.Integer(), server_default="0", nullable=False),
        sa.Column("provider_name", sa.String(length=40), nullable=True),
        sa.Column("provider_request_id", sa.String(length=255), nullable=True),
        sa.Column("failure_code", sa.String(length=100), nullable=True),
        sa.Column("authority_confirmed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("external_processing_acknowledged_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "source_type IN ('customer_sent', 'salesperson_sent', 'internal_forward', 'manually_pasted', "
            "'external_provider_import')",
            name="ck_email_sources_type",
        ),
        sa.CheckConstraint(
            "direction IN ('inbound', 'outbound', 'internal', 'unknown')", name="ck_email_sources_direction"
        ),
        sa.CheckConstraint(
            "sender_identity_state IN ('verified_contact', 'unknown')", name="ck_email_sources_sender_identity"
        ),
        sa.CheckConstraint(
            "origin_class IN ('customer_direct', 'salesperson_reported', 'imported_external')",
            name="ck_email_sources_origin",
        ),
        sa.CheckConstraint("support_class IN ('direct', 'reported', 'context')", name="ck_email_sources_support"),
        sa.CheckConstraint(
            "quote_handling IN ('none', 'stripped', 'ambiguous')", name="ck_email_sources_quote_handling"
        ),
        sa.CheckConstraint(
            "processing_status IN ('received', 'processing', 'review', 'completed', 'failed', 'deleted')",
            name="ck_email_sources_processing",
        ),
        sa.CheckConstraint("processing_attempts BETWEEN 0 AND 5", name="ck_email_sources_attempts"),
        sa.CheckConstraint("length(trim(body_text)) BETWEEN 1 AND 200000", name="ck_email_sources_body"),
        sa.CheckConstraint(
            "length(trim(normalized_body_text)) BETWEEN 1 AND 200000", name="ck_email_sources_normalized_body"
        ),
        sa.CheckConstraint(
            "length(content_sha256) = 64 AND content_sha256 = lower(content_sha256)",
            name="ck_email_sources_checksum",
        ),
        sa.CheckConstraint(
            "company_id IS NOT NULL OR opportunity_id IS NOT NULL OR interaction_id IS NOT NULL",
            name="ck_email_sources_association",
        ),
        sa.ForeignKeyConstraint(["organisation_id"], ["organisations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["organisation_id", "company_id"],
            ["companies.organisation_id", "companies.id"],
            name="fk_email_sources_company_tenant",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organisation_id", "opportunity_id"],
            ["opportunities.organisation_id", "opportunities.id"],
            name="fk_email_sources_opportunity_tenant",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organisation_id", "interaction_id"],
            ["interactions.organisation_id", "interactions.id"],
            name="fk_email_sources_interaction_tenant",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organisation_id", "capture_session_id"],
            ["capture_sessions.organisation_id", "capture_sessions.id"],
            name="fk_email_sources_capture_tenant",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organisation_id", "source_evidence_id"],
            ["evidence.organisation_id", "evidence.id"],
            name="fk_email_sources_evidence_tenant",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organisation_id", "sender_contact_id"],
            ["contacts.organisation_id", "contacts.id"],
            name="fk_email_sources_contact_tenant",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organisation_id", "submitted_by_user_id"],
            ["organisation_memberships.organisation_id", "organisation_memberships.user_id"],
            name="fk_email_sources_user_tenant",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organisation_id", "id", name="uq_email_sources_org_id"),
        sa.UniqueConstraint("organisation_id", "source_evidence_id", name="uq_email_sources_evidence"),
        sa.UniqueConstraint("organisation_id", "content_sha256", name="uq_email_sources_content"),
        sa.UniqueConstraint(
            "organisation_id", "submitted_by_user_id", "idempotency_key", name="uq_email_sources_idempotency"
        ),
    )
    op.create_index(
        "ix_email_sources_org_opportunity", "email_sources", ["organisation_id", "opportunity_id", "message_at"]
    )
    op.create_index("ix_email_sources_org_company", "email_sources", ["organisation_id", "company_id", "message_at"])
    op.create_index("ix_email_sources_org_status", "email_sources", ["organisation_id", "processing_status"])

    op.create_table(
        "source_candidate_evidence",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organisation_id", sa.Uuid(), nullable=False),
        sa.Column("source_kind", sa.String(length=16), nullable=False),
        sa.Column("document_source_id", sa.Uuid(), nullable=True),
        sa.Column("email_source_id", sa.Uuid(), nullable=True),
        sa.Column("source_evidence_id", sa.Uuid(), nullable=False),
        sa.Column("document_fragment_id", sa.Uuid(), nullable=True),
        sa.Column("accepted_evidence_id", sa.Uuid(), nullable=True),
        sa.Column("evidence_category", sa.String(length=40), nullable=False),
        sa.Column("statement", sa.String(length=1000), nullable=False),
        sa.Column("original_statement", sa.String(length=1000), nullable=False),
        sa.Column("statement_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("interpretation_origin", sa.String(length=24), server_default="ai_inferred", nullable=False),
        sa.Column("origin_class", sa.String(length=30), nullable=False),
        sa.Column("support_class", sa.String(length=20), nullable=False),
        sa.Column("source_location_json", sa.JSON(), nullable=False),
        sa.Column("validation_state", sa.String(length=20), server_default="unreviewed", nullable=False),
        sa.Column("review_state", sa.String(length=20), server_default="pending", nullable=False),
        sa.Column("conflict_state", sa.String(length=20), server_default="not_assessed", nullable=False),
        sa.Column("supersedes_candidate_id", sa.Uuid(), nullable=True),
        sa.Column("reviewed_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("source_kind IN ('document', 'email')", name="ck_source_candidates_kind"),
        sa.CheckConstraint(
            "(source_kind = 'document' AND document_source_id IS NOT NULL AND email_source_id IS NULL) OR "
            "(source_kind = 'email' AND email_source_id IS NOT NULL AND document_source_id IS NULL)",
            name="ck_source_candidates_source",
        ),
        sa.CheckConstraint(
            "evidence_category IN ('buying_signal', 'objection', 'competitor', 'stakeholder', 'decision', "
            "'action_item', 'risk', 'open_question', 'commitment', 'timeline', 'budget', 'procurement', "
            "'security_legal', 'implementation', 'commercial_intent', 'customer_request', "
            "'technical_requirement', 'contractual_requirement', 'pricing_requirement', 'renewal_signal', "
            "'expansion_signal', 'other')",
            name="ck_source_candidates_category",
        ),
        sa.CheckConstraint("interpretation_origin = 'ai_inferred'", name="ck_source_candidates_interpretation"),
        sa.CheckConstraint(
            "origin_class IN ('customer_direct', 'seller_prepared', 'salesperson_reported', 'imported_external')",
            name="ck_source_candidates_origin",
        ),
        sa.CheckConstraint("support_class IN ('direct', 'reported', 'context')", name="ck_source_candidates_support"),
        sa.CheckConstraint(
            "validation_state IN ('unreviewed', 'verified', 'rejected')", name="ck_source_candidates_validation"
        ),
        sa.CheckConstraint("review_state IN ('pending', 'accepted', 'rejected')", name="ck_source_candidates_review"),
        sa.CheckConstraint(
            "conflict_state IN ('not_assessed', 'conflicting', 'supersedes', 'superseded')",
            name="ck_source_candidates_conflict",
        ),
        sa.CheckConstraint(
            "length(trim(statement)) BETWEEN 1 AND 1000 AND length(trim(original_statement)) BETWEEN 1 AND 1000",
            name="ck_source_candidates_statements",
        ),
        sa.CheckConstraint(
            "(review_state = 'pending' AND reviewed_at IS NULL AND reviewed_by_user_id IS NULL "
            "AND accepted_evidence_id IS NULL AND validation_state = 'unreviewed') OR "
            "(review_state = 'accepted' AND reviewed_at IS NOT NULL AND reviewed_by_user_id IS NOT NULL "
            "AND accepted_evidence_id IS NOT NULL AND validation_state = 'verified') OR "
            "(review_state = 'rejected' AND reviewed_at IS NOT NULL AND reviewed_by_user_id IS NOT NULL "
            "AND accepted_evidence_id IS NULL AND validation_state = 'rejected')",
            name="ck_source_candidates_review_consistency",
        ),
        sa.ForeignKeyConstraint(["organisation_id"], ["organisations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["organisation_id", "document_source_id"],
            ["document_sources.organisation_id", "document_sources.id"],
            name="fk_source_candidates_document_tenant",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["organisation_id", "email_source_id"],
            ["email_sources.organisation_id", "email_sources.id"],
            name="fk_source_candidates_email_tenant",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["organisation_id", "source_evidence_id"],
            ["evidence.organisation_id", "evidence.id"],
            name="fk_source_candidates_source_evidence_tenant",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organisation_id", "accepted_evidence_id"],
            ["evidence.organisation_id", "evidence.id"],
            name="fk_source_candidates_accepted_evidence_tenant",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organisation_id", "document_fragment_id"],
            ["document_fragments.organisation_id", "document_fragments.id"],
            name="fk_source_candidates_fragment_tenant",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organisation_id", "reviewed_by_user_id"],
            ["organisation_memberships.organisation_id", "organisation_memberships.user_id"],
            name="fk_source_candidates_reviewer_tenant",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organisation_id", "supersedes_candidate_id"],
            ["source_candidate_evidence.organisation_id", "source_candidate_evidence.id"],
            name="fk_source_candidates_supersedes_tenant",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organisation_id", "id", name="uq_source_candidates_org_id"),
        sa.UniqueConstraint(
            "organisation_id",
            "source_evidence_id",
            "evidence_category",
            "statement_fingerprint",
            name="uq_source_candidates_statement",
        ),
    )
    op.create_index(
        "ix_source_candidates_org_document",
        "source_candidate_evidence",
        ["organisation_id", "document_source_id", "review_state"],
    )
    op.create_index(
        "ix_source_candidates_org_email",
        "source_candidate_evidence",
        ["organisation_id", "email_source_id", "review_state"],
    )

    op.create_table(
        "revenue_brain_source_snapshots",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organisation_id", sa.Uuid(), nullable=False),
        sa.Column("company_id", sa.Uuid(), nullable=True),
        sa.Column("opportunity_id", sa.Uuid(), nullable=True),
        sa.Column("interaction_id", sa.Uuid(), nullable=True),
        sa.Column("source_kind", sa.String(length=16), nullable=False),
        sa.Column("document_source_id", sa.Uuid(), nullable=True),
        sa.Column("email_source_id", sa.Uuid(), nullable=True),
        sa.Column("source_evidence_id", sa.Uuid(), nullable=False),
        sa.Column("source_evidence_ids", sa.JSON(), nullable=False),
        sa.Column("content_json", sa.JSON(), nullable=False),
        sa.Column("schema_version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("source_kind IN ('document', 'email')", name="ck_brain_source_snapshots_kind"),
        sa.CheckConstraint(
            "(source_kind = 'document' AND document_source_id IS NOT NULL AND email_source_id IS NULL) OR "
            "(source_kind = 'email' AND email_source_id IS NOT NULL AND document_source_id IS NULL)",
            name="ck_brain_source_snapshots_source",
        ),
        sa.CheckConstraint("schema_version = 1", name="ck_brain_source_snapshots_schema"),
        sa.CheckConstraint("version > 0", name="ck_brain_source_snapshots_version"),
        sa.ForeignKeyConstraint(["organisation_id"], ["organisations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["organisation_id", "company_id"],
            ["companies.organisation_id", "companies.id"],
            name="fk_brain_source_snapshots_company_tenant",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organisation_id", "opportunity_id"],
            ["opportunities.organisation_id", "opportunities.id"],
            name="fk_brain_source_snapshots_opportunity_tenant",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organisation_id", "interaction_id"],
            ["interactions.organisation_id", "interactions.id"],
            name="fk_brain_source_snapshots_interaction_tenant",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organisation_id", "source_evidence_id"],
            ["evidence.organisation_id", "evidence.id"],
            name="fk_brain_source_snapshots_evidence_tenant",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organisation_id", "document_source_id"],
            ["document_sources.organisation_id", "document_sources.id"],
            name="fk_brain_source_snapshots_document_tenant",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organisation_id", "email_source_id"],
            ["email_sources.organisation_id", "email_sources.id"],
            name="fk_brain_source_snapshots_email_tenant",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organisation_id", "id", name="uq_brain_source_snapshots_org_id"),
        sa.UniqueConstraint(
            "organisation_id", "source_evidence_id", "version", name="uq_brain_source_snapshots_version"
        ),
    )
    op.create_index(
        "ix_brain_source_snapshots_org_company",
        "revenue_brain_source_snapshots",
        ["organisation_id", "company_id", "created_at"],
    )
    op.create_index(
        "ix_brain_source_snapshots_org_opportunity",
        "revenue_brain_source_snapshots",
        ["organisation_id", "opportunity_id", "created_at"],
    )
    _enable_tenant_rls()
    _create_immutability_guards()


def downgrade() -> None:
    _drop_immutability_guards()
    op.drop_table("revenue_brain_source_snapshots")
    op.drop_table("source_candidate_evidence")
    op.drop_table("email_sources")
    op.drop_table("document_fragments")
    op.drop_table("document_sources")
    _narrow_capture_sessions()
