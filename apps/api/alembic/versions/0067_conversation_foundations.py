"""Persist private conversation work and bounded knowledge ingestion.

Revision ID: 0067_conversation_foundations
Revises: 0066_conversation_core

The migration is additive. It preserves the original interaction/debrief records,
adds optimistic-lock user-private workspaces and preferences, introduces a
local-only briefing outbox, and turns company knowledge references into a
reviewable queued-ingestion lifecycle.
"""

import hashlib
import uuid
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0067_conversation_foundations"
down_revision: str | None = "0066_conversation_core"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PRIVATE_TABLES = (
    "conversation_user_workspaces",
    "conversation_delivery_preferences",
    "conversation_briefing_outbox",
)
TENANT_TABLES = ("company_knowledge_ingestion_jobs",)


def _enable_rls() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return
    for table_name in TENANT_TABLES:
        op.execute(f"ALTER TABLE {table_name} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table_name} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"""CREATE POLICY {table_name}_tenant_isolation ON {table_name}
            USING (organisation_id = NULLIF(current_setting('app.organisation_id', true), '')::uuid)
            WITH CHECK (organisation_id = NULLIF(current_setting('app.organisation_id', true), '')::uuid)"""
        )
    for table_name in PRIVATE_TABLES:
        op.execute(f"ALTER TABLE {table_name} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table_name} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"""CREATE POLICY {table_name}_owner_isolation ON {table_name}
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
        CREATE FUNCTION public.revenueos_knowledge_worker_eligible_organisations(result_limit integer)
        RETURNS TABLE (organisation_id uuid)
        LANGUAGE sql
        SECURITY DEFINER
        SET search_path = pg_catalog, public
        AS $$
            SELECT DISTINCT jobs.organisation_id
            FROM public.company_knowledge_ingestion_jobs AS jobs
            WHERE (
                jobs.status = 'pending'
                AND jobs.cancellation_requested_at IS NULL
                AND jobs.attempt_count < jobs.max_attempts
                AND (jobs.next_attempt_at IS NULL OR jobs.next_attempt_at <= CURRENT_TIMESTAMP)
            ) OR (
                jobs.status = 'running'
                AND jobs.lease_expires_at < CURRENT_TIMESTAMP
            )
            ORDER BY jobs.organisation_id
            LIMIT LEAST(GREATEST(result_limit, 1), 1000)
        $$
        """
    )


def upgrade() -> None:
    uuid_type = sa.Uuid(as_uuid=True)
    with op.batch_alter_table("company_knowledge_sources") as batch:
        batch.add_column(sa.Column("source_document", sa.LargeBinary(), nullable=True))
        batch.add_column(sa.Column("source_filename", sa.String(length=255), nullable=True))
        batch.add_column(sa.Column("source_mime_type", sa.String(length=120), nullable=True))
        batch.add_column(sa.Column("extracted_text", sa.Text(), nullable=True))
        batch.add_column(sa.Column("summary_text", sa.Text(), nullable=True))
        batch.add_column(sa.Column("processing_attempts", sa.Integer(), server_default="0", nullable=False))
        batch.add_column(sa.Column("last_http_etag", sa.String(length=500), nullable=True))
        batch.add_column(sa.Column("last_http_modified", sa.String(length=500), nullable=True))
        batch.add_column(sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True))
        batch.add_column(sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True))
        batch.add_column(sa.Column("approved_by_user_id", uuid_type, nullable=True))
        batch.add_column(sa.Column("stale_at", sa.DateTime(timezone=True), nullable=True))
    op.execute(
        "UPDATE company_knowledge_sources SET extracted_text = source_text "
        "WHERE source_text IS NOT NULL AND extracted_text IS NULL"
    )
    op.execute(
        "UPDATE company_knowledge_sources SET summary_text = "
        "COALESCE(NULLIF(substr(trim(source_text), 1, 2000), ''), 'Legacy source retained for review.') "
        "WHERE source_text IS NOT NULL AND summary_text IS NULL"
    )
    with op.batch_alter_table("company_knowledge_sources") as batch:
        batch.drop_constraint("ck_company_knowledge_sources_status", type_="check")
        batch.create_check_constraint(
            "ck_company_knowledge_sources_status",
            "processing_status IN ('saved_unprocessed', 'queued', 'fetching', 'extracting', "
            "'ready_for_review', 'approved', 'stale', 'failed')",
        )
    op.execute(
        "UPDATE company_knowledge_sources SET processing_status = 'queued' "
        "WHERE processing_status = 'saved_unprocessed'"
    )
    with op.batch_alter_table("company_knowledge_sources") as batch:
        batch.drop_constraint("ck_company_knowledge_sources_kind", type_="check")
        batch.drop_constraint("ck_company_knowledge_sources_status", type_="check")
        batch.drop_constraint("ck_company_knowledge_sources_content", type_="check")
        batch.create_check_constraint(
            "ck_company_knowledge_sources_kind",
            "source_kind IN ('website', 'supporting_text', 'text_file', 'document')",
        )
        batch.create_check_constraint(
            "ck_company_knowledge_sources_status",
            "processing_status IN ('queued', 'fetching', 'extracting', 'ready_for_review', "
            "'approved', 'stale', 'failed')",
        )
        batch.create_check_constraint(
            "ck_company_knowledge_sources_content",
            "(source_kind = 'website' AND website_url IS NOT NULL AND source_text IS NULL "
            "AND source_document IS NULL AND source_filename IS NULL AND source_mime_type IS NULL) OR "
            "(source_kind IN ('supporting_text', 'text_file') AND website_url IS NULL "
            "AND source_text IS NOT NULL AND source_document IS NULL AND source_filename IS NULL "
            "AND source_mime_type IS NULL) OR "
            "(source_kind = 'document' AND website_url IS NULL AND source_text IS NULL "
            "AND source_document IS NOT NULL AND source_filename IS NOT NULL "
            "AND source_mime_type IS NOT NULL)",
        )
        batch.create_check_constraint(
            "ck_company_knowledge_sources_attempts",
            "processing_attempts >= 0",
        )
        batch.create_foreign_key(
            "fk_company_knowledge_sources_approver",
            "organisation_memberships",
            ["organisation_id", "approved_by_user_id"],
            ["organisation_id", "user_id"],
            ondelete="RESTRICT",
        )

    op.create_table(
        "company_knowledge_ingestion_jobs",
        sa.Column("id", uuid_type, nullable=False),
        sa.Column("organisation_id", uuid_type, nullable=False),
        sa.Column("source_id", uuid_type, nullable=False),
        sa.Column("requested_by_user_id", uuid_type, nullable=False),
        sa.Column("status", sa.String(length=20), server_default="pending", nullable=False),
        sa.Column("request_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("attempt_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("max_attempts", sa.Integer(), server_default="3", nullable=False),
        sa.Column("worker_id", sa.String(length=200), nullable=True),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failure_code", sa.String(length=100), nullable=True),
        sa.Column("cancellation_requested_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "status IN ('pending', 'running', 'completed', 'failed', 'cancelled')",
            name="ck_company_knowledge_jobs_status",
        ),
        sa.CheckConstraint("attempt_count >= 0", name="ck_company_knowledge_jobs_attempts"),
        sa.CheckConstraint("max_attempts BETWEEN 1 AND 5", name="ck_company_knowledge_jobs_max_attempts"),
        sa.ForeignKeyConstraint(["organisation_id"], ["organisations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["organisation_id", "source_id"],
            ["company_knowledge_sources.organisation_id", "company_knowledge_sources.id"],
            name="fk_company_knowledge_jobs_source",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["organisation_id", "requested_by_user_id"],
            ["organisation_memberships.organisation_id", "organisation_memberships.user_id"],
            name="fk_company_knowledge_jobs_requester",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organisation_id", "id", name="uq_company_knowledge_jobs_org_id"),
        sa.UniqueConstraint(
            "organisation_id",
            "source_id",
            "request_fingerprint",
            name="uq_company_knowledge_jobs_request",
        ),
    )
    op.create_index(
        "ix_company_knowledge_jobs_org_status",
        "company_knowledge_ingestion_jobs",
        ["organisation_id", "status", "next_attempt_at"],
    )
    backfill_uuid_type: sa.types.TypeEngine[object] = (
        sa.String() if op.get_bind().dialect.name == "sqlite" else uuid_type
    )
    sources = sa.table(
        "company_knowledge_sources",
        sa.column("id", backfill_uuid_type),
        sa.column("organisation_id", backfill_uuid_type),
        sa.column("created_by_user_id", backfill_uuid_type),
        sa.column("processing_status", sa.String()),
    )
    queued_sources = op.get_bind().execute(
        sa.select(sources.c.id, sources.c.organisation_id, sources.c.created_by_user_id).where(
            sources.c.processing_status == "queued"
        )
    )
    jobs = sa.table(
        "company_knowledge_ingestion_jobs",
        sa.column("id", backfill_uuid_type),
        sa.column("organisation_id", backfill_uuid_type),
        sa.column("source_id", backfill_uuid_type),
        sa.column("requested_by_user_id", backfill_uuid_type),
        sa.column("status", sa.String()),
        sa.column("request_fingerprint", sa.String()),
        sa.column("attempt_count", sa.Integer()),
        sa.column("max_attempts", sa.Integer()),
    )
    for source_id, organisation_id, requested_by_user_id in queued_sources:
        op.bulk_insert(
            jobs,
            [
                {
                    "id": str(uuid.uuid4()) if op.get_bind().dialect.name == "sqlite" else uuid.uuid4(),
                    "organisation_id": organisation_id,
                    "source_id": source_id,
                    "requested_by_user_id": requested_by_user_id,
                    "status": "pending",
                    "request_fingerprint": hashlib.sha256(f"legacy:{source_id}".encode()).hexdigest(),
                    "attempt_count": 0,
                    "max_attempts": 3,
                }
            ],
        )

    op.create_table(
        "conversation_user_workspaces",
        sa.Column("id", uuid_type, nullable=False),
        sa.Column("organisation_id", uuid_type, nullable=False),
        sa.Column("interaction_id", uuid_type, nullable=False),
        sa.Column("user_id", uuid_type, nullable=False),
        sa.Column("enhanced_notes", sa.Text(), nullable=True),
        sa.Column("follow_up_draft", sa.Text(), nullable=True),
        sa.Column("follow_up_reviewed", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("generation_fingerprint", sa.String(length=64), nullable=True),
        sa.Column("imported_from_browser_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("lock_version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("lock_version > 0", name="ck_conversation_user_workspaces_lock"),
        sa.ForeignKeyConstraint(["organisation_id"], ["organisations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["organisation_id", "interaction_id"],
            ["interactions.organisation_id", "interactions.id"],
            name="fk_conversation_user_workspaces_interaction",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["organisation_id", "user_id"],
            ["organisation_memberships.organisation_id", "organisation_memberships.user_id"],
            name="fk_conversation_user_workspaces_user",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organisation_id", "id", name="uq_conversation_user_workspaces_org_id"),
        sa.UniqueConstraint(
            "organisation_id", "interaction_id", "user_id", name="uq_conversation_user_workspaces_owner"
        ),
    )
    op.create_index(
        "ix_conversation_user_workspaces_owner_updated",
        "conversation_user_workspaces",
        ["organisation_id", "user_id", "updated_at"],
    )

    op.create_table(
        "conversation_delivery_preferences",
        sa.Column("id", uuid_type, nullable=False),
        sa.Column("organisation_id", uuid_type, nullable=False),
        sa.Column("user_id", uuid_type, nullable=False),
        sa.Column("timezone", sa.String(length=64), server_default="UTC", nullable=False),
        sa.Column("morning_digest_enabled", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("morning_digest_time", sa.String(length=5), server_default="07:30", nullable=False),
        sa.Column("pre_meeting_enabled", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("pre_meeting_minutes", sa.Integer(), server_default="30", nullable=False),
        sa.Column("imported_from_browser_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("lock_version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("lock_version > 0", name="ck_conversation_delivery_preferences_lock"),
        sa.CheckConstraint(
            "pre_meeting_minutes BETWEEN 5 AND 1440",
            name="ck_conversation_delivery_preferences_lead",
        ),
        sa.ForeignKeyConstraint(["organisation_id"], ["organisations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["organisation_id", "user_id"],
            ["organisation_memberships.organisation_id", "organisation_memberships.user_id"],
            name="fk_conversation_delivery_preferences_user",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organisation_id", "id", name="uq_conversation_delivery_preferences_org_id"),
        sa.UniqueConstraint("organisation_id", "user_id", name="uq_conversation_delivery_preferences_owner"),
    )

    op.create_table(
        "conversation_briefing_outbox",
        sa.Column("id", uuid_type, nullable=False),
        sa.Column("organisation_id", uuid_type, nullable=False),
        sa.Column("user_id", uuid_type, nullable=False),
        sa.Column("interaction_id", uuid_type, nullable=True),
        sa.Column("kind", sa.String(length=24), nullable=False),
        sa.Column("status", sa.String(length=20), server_default="prepared", nullable=False),
        sa.Column("deduplication_key", sa.String(length=200), nullable=False),
        sa.Column("source_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("subject", sa.String(length=500), nullable=False),
        sa.Column("body_text", sa.Text(), nullable=False),
        sa.Column("href", sa.String(length=500), nullable=False),
        sa.Column("prepared_for_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "kind IN ('morning_digest', 'pre_meeting')",
            name="ck_conversation_briefing_outbox_kind",
        ),
        sa.CheckConstraint(
            "status IN ('prepared', 'superseded', 'cancelled')",
            name="ck_conversation_briefing_outbox_status",
        ),
        sa.ForeignKeyConstraint(["organisation_id"], ["organisations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["organisation_id", "user_id"],
            ["organisation_memberships.organisation_id", "organisation_memberships.user_id"],
            name="fk_conversation_briefing_outbox_user",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["organisation_id", "interaction_id"],
            ["interactions.organisation_id", "interactions.id"],
            name="fk_conversation_briefing_outbox_interaction",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organisation_id", "id", name="uq_conversation_briefing_outbox_org_id"),
        sa.UniqueConstraint(
            "organisation_id",
            "user_id",
            "deduplication_key",
            name="uq_conversation_briefing_outbox_deduplication",
        ),
    )
    op.create_index(
        "ix_conversation_briefing_outbox_owner_created",
        "conversation_briefing_outbox",
        ["organisation_id", "user_id", "created_at"],
    )
    _enable_rls()
    _create_worker_discovery()


def downgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        op.execute("DROP FUNCTION IF EXISTS public.revenueos_knowledge_worker_eligible_organisations(integer)")
    op.drop_index(
        "ix_conversation_briefing_outbox_owner_created",
        table_name="conversation_briefing_outbox",
    )
    op.drop_table("conversation_briefing_outbox")
    op.drop_table("conversation_delivery_preferences")
    op.drop_index(
        "ix_conversation_user_workspaces_owner_updated",
        table_name="conversation_user_workspaces",
    )
    op.drop_table("conversation_user_workspaces")
    op.drop_index("ix_company_knowledge_jobs_org_status", table_name="company_knowledge_ingestion_jobs")
    op.drop_table("company_knowledge_ingestion_jobs")
    with op.batch_alter_table("company_knowledge_sources") as batch:
        batch.drop_constraint("fk_company_knowledge_sources_approver", type_="foreignkey")
        batch.drop_constraint("ck_company_knowledge_sources_attempts", type_="check")
        batch.drop_constraint("ck_company_knowledge_sources_content", type_="check")
        batch.drop_constraint("ck_company_knowledge_sources_status", type_="check")
        batch.drop_constraint("ck_company_knowledge_sources_kind", type_="check")
    op.execute(
        "UPDATE company_knowledge_sources SET source_kind = 'text_file', "
        "source_text = COALESCE(extracted_text, 'Document retained without extracted text'), "
        "source_document = NULL WHERE source_kind = 'document'"
    )
    op.execute(
        "UPDATE company_knowledge_sources SET processing_status = 'saved_unprocessed' WHERE source_kind = 'website'"
    )
    op.execute(
        "UPDATE company_knowledge_sources SET processing_status = 'ready_for_review' "
        "WHERE source_kind IN ('supporting_text', 'text_file')"
    )
    with op.batch_alter_table("company_knowledge_sources") as batch:
        batch.create_check_constraint(
            "ck_company_knowledge_sources_kind",
            "source_kind IN ('website', 'supporting_text', 'text_file')",
        )
        batch.create_check_constraint(
            "ck_company_knowledge_sources_status",
            "processing_status IN ('saved_unprocessed', 'ready_for_review', 'failed')",
        )
        batch.create_check_constraint(
            "ck_company_knowledge_sources_content",
            "(source_kind = 'website' AND website_url IS NOT NULL AND source_text IS NULL) OR "
            "(source_kind IN ('supporting_text', 'text_file') AND website_url IS NULL "
            "AND source_text IS NOT NULL)",
        )
    with op.batch_alter_table("company_knowledge_sources") as batch:
        batch.drop_column("stale_at")
        batch.drop_column("approved_by_user_id")
        batch.drop_column("approved_at")
        batch.drop_column("processed_at")
        batch.drop_column("last_http_modified")
        batch.drop_column("last_http_etag")
        batch.drop_column("processing_attempts")
        batch.drop_column("summary_text")
        batch.drop_column("extracted_text")
        batch.drop_column("source_mime_type")
        batch.drop_column("source_filename")
        batch.drop_column("source_document")
