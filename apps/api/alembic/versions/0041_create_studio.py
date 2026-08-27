"""Add tenant-isolated RevenueOS Create Sales Content Studio.

Revision ID: 0041_create_studio
Revises: 0040_event_intelligence

WO-032 adds approved PPTX template versions, reviewed reusable slide content,
customer-safe presentation plans, immutable generated versions and private files.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0041_create_studio"
down_revision: str | None = "0040_event_intelligence"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TENANT_TABLES = (
    "create_usage_counters",
    "create_templates",
    "create_template_versions",
    "create_template_slides",
    "create_approved_content_items",
    "create_presentations",
    "create_presentation_versions",
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


def _create_worker_discovery() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return
    op.execute(
        """
        CREATE FUNCTION public.revenueos_create_worker_eligible_organisations(
            eligible_at timestamptz,
            result_limit integer
        )
        RETURNS TABLE (organisation_id uuid)
        LANGUAGE sql
        SECURITY DEFINER
        SET search_path = pg_catalog, public
        AS $$
            SELECT DISTINCT work.organisation_id
            FROM (
                SELECT create_template_versions.organisation_id
                FROM public.create_template_versions
                WHERE create_template_versions.processing_state = 'processing'
                  AND create_template_versions.processing_attempts < 3
                  AND (
                    create_template_versions.lease_expires_at IS NULL
                    OR create_template_versions.lease_expires_at <= eligible_at
                  )
                UNION
                SELECT create_presentation_versions.organisation_id
                FROM public.create_presentation_versions
                WHERE create_presentation_versions.state = 'generating'
                  AND create_presentation_versions.processing_attempts < 3
                  AND (
                    create_presentation_versions.lease_expires_at IS NULL
                    OR create_presentation_versions.lease_expires_at <= eligible_at
                  )
            ) AS work
            ORDER BY work.organisation_id
            LIMIT LEAST(GREATEST(result_limit, 1), 1000)
        $$
        """
    )


def upgrade() -> None:
    uuid_type = sa.Uuid(as_uuid=True)
    with op.batch_alter_table("organisation_module_entitlements") as batch:
        batch.drop_constraint("ck_module_entitlements_key", type_="check")
        batch.create_check_constraint("ck_module_entitlements_key", "module_key IN ('prospect', 'engage', 'create')")

    op.create_table(
        "create_usage_counters",
        sa.Column("organisation_id", uuid_type, nullable=False),
        sa.Column("usage_date", sa.Date(), nullable=False),
        sa.Column("scope_key", sa.String(length=50), nullable=False),
        sa.Column("generation_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "scope_key = 'organisation' OR scope_key LIKE 'user:%'",
            name="ck_create_usage_scope",
        ),
        sa.CheckConstraint("generation_count >= 0", name="ck_create_usage_generations"),
        sa.ForeignKeyConstraint(["organisation_id"], ["organisations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("organisation_id", "usage_date", "scope_key"),
    )

    op.create_table(
        "create_templates",
        sa.Column("id", uuid_type, nullable=False),
        sa.Column("organisation_id", uuid_type, nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("state", sa.String(length=20), server_default="active", nullable=False),
        sa.Column("created_by_user_id", uuid_type, nullable=False),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("length(trim(name)) BETWEEN 1 AND 200", name="ck_create_templates_name"),
        sa.CheckConstraint("state IN ('active', 'archived')", name="ck_create_templates_state"),
        sa.ForeignKeyConstraint(["organisation_id"], ["organisations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["organisation_id", "created_by_user_id"],
            ["organisation_memberships.organisation_id", "organisation_memberships.user_id"],
            name="fk_create_templates_creator",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organisation_id", "id", name="uq_create_templates_org_id"),
        sa.UniqueConstraint("organisation_id", "name", name="uq_create_templates_org_name"),
    )
    op.create_index("ix_create_templates_org_state", "create_templates", ["organisation_id", "state", "updated_at"])

    op.create_table(
        "create_template_versions",
        sa.Column("id", uuid_type, nullable=False),
        sa.Column("organisation_id", uuid_type, nullable=False),
        sa.Column("template_id", uuid_type, nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("uploaded_by_user_id", uuid_type, nullable=False),
        sa.Column("processing_state", sa.String(length=20), server_default="processing", nullable=False),
        sa.Column("approval_state", sa.String(length=20), server_default="pending", nullable=False),
        sa.Column("display_filename", sa.String(length=255), nullable=False),
        sa.Column("storage_key", sa.String(length=255), nullable=False),
        sa.Column("storage_status", sa.String(length=24), server_default="available", nullable=False),
        sa.Column("mime_type", sa.String(length=120), nullable=False),
        sa.Column("byte_size", sa.BigInteger(), nullable=False),
        sa.Column("checksum_sha256", sa.String(length=64), nullable=False),
        sa.Column("processing_schema_version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("slide_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("width_emu", sa.BigInteger(), nullable=True),
        sa.Column("height_emu", sa.BigInteger(), nullable=True),
        sa.Column("warning_codes_json", sa.JSON(), server_default=sa.text("'[]'"), nullable=False),
        sa.Column("manifest_json", sa.JSON(), server_default=sa.text("'{}'"), nullable=False),
        sa.Column("safe_failure_code", sa.String(length=100), nullable=True),
        sa.Column("authority_attestation_version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("authority_attested_by_user_id", uuid_type, nullable=False),
        sa.Column("authority_attested_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("processing_attempts", sa.Integer(), server_default="0", nullable=False),
        sa.Column("worker_id", sa.String(length=200), nullable=True),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("approved_by_user_id", uuid_type, nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("version > 0", name="ck_create_template_versions_number"),
        sa.CheckConstraint(
            "processing_state IN ('processing', 'ready', 'partial', 'failed', 'archived')",
            name="ck_create_template_versions_processing",
        ),
        sa.CheckConstraint(
            "approval_state IN ('pending', 'approved', 'revoked')", name="ck_create_template_versions_approval"
        ),
        sa.CheckConstraint("byte_size BETWEEN 1 AND 52428800", name="ck_create_template_versions_bytes"),
        sa.CheckConstraint("length(checksum_sha256) = 64", name="ck_create_template_versions_checksum"),
        sa.CheckConstraint("slide_count BETWEEN 0 AND 100", name="ck_create_template_versions_slides"),
        sa.CheckConstraint("processing_schema_version = 1", name="ck_create_template_versions_schema"),
        sa.CheckConstraint("authority_attestation_version = 1", name="ck_create_template_versions_attestation"),
        sa.CheckConstraint("processing_attempts BETWEEN 0 AND 3", name="ck_create_template_versions_attempts"),
        sa.CheckConstraint(
            "storage_status IN ('available', 'deletion_pending', 'delete_failed', 'deleted')",
            name="ck_create_template_versions_storage",
        ),
        sa.ForeignKeyConstraint(["organisation_id"], ["organisations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["organisation_id", "template_id"],
            ["create_templates.organisation_id", "create_templates.id"],
            name="fk_create_template_versions_template",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["organisation_id", "uploaded_by_user_id"],
            ["organisation_memberships.organisation_id", "organisation_memberships.user_id"],
            name="fk_create_template_versions_uploader",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organisation_id", "authority_attested_by_user_id"],
            ["organisation_memberships.organisation_id", "organisation_memberships.user_id"],
            name="fk_create_template_versions_attester",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organisation_id", "approved_by_user_id"],
            ["organisation_memberships.organisation_id", "organisation_memberships.user_id"],
            name="fk_create_template_versions_approver",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organisation_id", "id", name="uq_create_template_versions_org_id"),
        sa.UniqueConstraint("organisation_id", "id", "template_id", name="uq_create_template_versions_org_id_template"),
        sa.UniqueConstraint("organisation_id", "template_id", "version", name="uq_create_template_versions_number"),
        sa.UniqueConstraint("organisation_id", "checksum_sha256", name="uq_create_template_versions_checksum"),
        sa.UniqueConstraint("organisation_id", "storage_key", name="uq_create_template_versions_storage"),
    )
    op.create_index(
        "ix_create_template_versions_org_template",
        "create_template_versions",
        ["organisation_id", "template_id", "version"],
    )
    op.create_index(
        "ix_create_template_versions_org_processing",
        "create_template_versions",
        ["organisation_id", "processing_state", "created_at"],
    )

    op.create_table(
        "create_template_slides",
        sa.Column("id", uuid_type, nullable=False),
        sa.Column("organisation_id", uuid_type, nullable=False),
        sa.Column("template_id", uuid_type, nullable=False),
        sa.Column("template_version_id", uuid_type, nullable=False),
        sa.Column("slide_number", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=240), nullable=False),
        sa.Column("category", sa.String(length=32), server_default="unknown", nullable=False),
        sa.Column("reuse_state", sa.String(length=20), server_default="pending", nullable=False),
        sa.Column("modification_policy", sa.String(length=32), server_default="reuse_as_is", nullable=False),
        sa.Column("customer_safe", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("required", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("exact_text_required", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("hidden", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("approved_description", sa.String(length=400), nullable=True),
        sa.Column("text_blocks_json", sa.JSON(), nullable=False),
        sa.Column("placeholder_mappings_json", sa.JSON(), server_default=sa.text("'{}'"), nullable=False),
        sa.Column("reviewed_by_user_id", uuid_type, nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("slide_number BETWEEN 1 AND 100", name="ck_create_template_slides_number"),
        sa.CheckConstraint(
            "category IN ('title', 'agenda', 'company_overview', 'problem', 'solution', 'product', "
            "'capability', 'architecture', 'case_study', 'proof_point', 'process', 'pricing_placeholder', "
            "'next_steps', 'appendix', 'unknown')",
            name="ck_create_template_slides_category",
        ),
        sa.CheckConstraint(
            "reuse_state IN ('pending', 'approved', 'excluded')", name="ck_create_template_slides_reuse"
        ),
        sa.CheckConstraint(
            "modification_policy IN ('locked', 'text_placeholders_only', 'editable_text', 'reuse_as_is')",
            name="ck_create_template_slides_modification",
        ),
        sa.CheckConstraint(
            "NOT required OR (reuse_state = 'approved' AND customer_safe)", name="ck_create_template_slides_required"
        ),
        sa.CheckConstraint(
            "NOT exact_text_required OR modification_policy IN ('locked', 'reuse_as_is')",
            name="ck_create_template_slides_exact",
        ),
        sa.ForeignKeyConstraint(["organisation_id"], ["organisations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["organisation_id", "template_version_id", "template_id"],
            [
                "create_template_versions.organisation_id",
                "create_template_versions.id",
                "create_template_versions.template_id",
            ],
            name="fk_create_template_slides_version",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["organisation_id", "reviewed_by_user_id"],
            ["organisation_memberships.organisation_id", "organisation_memberships.user_id"],
            name="fk_create_template_slides_reviewer",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organisation_id", "id", name="uq_create_template_slides_org_id"),
        sa.UniqueConstraint(
            "organisation_id", "template_version_id", "slide_number", name="uq_create_template_slides_number"
        ),
    )
    op.create_index(
        "ix_create_template_slides_org_version",
        "create_template_slides",
        ["organisation_id", "template_version_id", "slide_number"],
    )

    op.create_table(
        "create_approved_content_items",
        sa.Column("id", uuid_type, nullable=False),
        sa.Column("organisation_id", uuid_type, nullable=False),
        sa.Column("template_id", uuid_type, nullable=False),
        sa.Column("template_version_id", uuid_type, nullable=False),
        sa.Column("slide_id", uuid_type, nullable=False),
        sa.Column("content_type", sa.String(length=32), nullable=False),
        sa.Column("title", sa.String(length=240), nullable=False),
        sa.Column("approved_text", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=20), server_default="approved", nullable=False),
        sa.Column("modification_policy", sa.String(length=32), nullable=False),
        sa.Column("customer_safe", sa.Boolean(), nullable=False),
        sa.Column("exact_text_required", sa.Boolean(), nullable=False),
        sa.Column("approved_by_user_id", uuid_type, nullable=False),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("status IN ('approved', 'revoked')", name="ck_create_content_items_status"),
        sa.CheckConstraint("length(trim(title)) BETWEEN 1 AND 240", name="ck_create_content_items_title"),
        sa.CheckConstraint("length(trim(approved_text)) BETWEEN 1 AND 12000", name="ck_create_content_items_text"),
        sa.ForeignKeyConstraint(["organisation_id"], ["organisations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["organisation_id", "template_version_id", "template_id"],
            [
                "create_template_versions.organisation_id",
                "create_template_versions.id",
                "create_template_versions.template_id",
            ],
            name="fk_create_content_items_version",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["organisation_id", "slide_id"],
            ["create_template_slides.organisation_id", "create_template_slides.id"],
            name="fk_create_content_items_slide",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["organisation_id", "approved_by_user_id"],
            ["organisation_memberships.organisation_id", "organisation_memberships.user_id"],
            name="fk_create_content_items_approver",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organisation_id", "id", name="uq_create_content_items_org_id"),
        sa.UniqueConstraint("organisation_id", "slide_id", name="uq_create_content_items_slide"),
    )
    op.create_index(
        "ix_create_content_items_org_version",
        "create_approved_content_items",
        ["organisation_id", "template_version_id", "status"],
    )

    op.create_table(
        "create_presentations",
        sa.Column("id", uuid_type, nullable=False),
        sa.Column("organisation_id", uuid_type, nullable=False),
        sa.Column("account_id", uuid_type, nullable=False),
        sa.Column("opportunity_id", uuid_type, nullable=True),
        sa.Column("template_id", uuid_type, nullable=False),
        sa.Column("template_version_id", uuid_type, nullable=False),
        sa.Column("created_by_user_id", uuid_type, nullable=False),
        sa.Column("title", sa.String(length=240), nullable=False),
        sa.Column("objective", sa.String(length=40), nullable=False),
        sa.Column("audience_json", sa.JSON(), nullable=False),
        sa.Column("focus_instruction", sa.String(length=500), nullable=True),
        sa.Column("state", sa.String(length=24), server_default="draft_plan", nullable=False),
        sa.Column("review_state", sa.String(length=20), server_default="pending", nullable=False),
        sa.Column("plan_json", sa.JSON(), nullable=False),
        sa.Column("source_context_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("idempotency_key", sa.String(length=200), nullable=False),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("length(trim(title)) BETWEEN 1 AND 240", name="ck_create_presentations_title"),
        sa.CheckConstraint(
            "objective IN ('introductory_meeting', 'discovery_follow_up', 'solution_overview', "
            "'technical_workshop', 'executive_presentation', 'proposal_presentation', 'business_case', "
            "'event_follow_up')",
            name="ck_create_presentations_objective",
        ),
        sa.CheckConstraint(
            "state IN ('draft_plan', 'generating', 'needs_review', 'ready', 'failed', 'archived')",
            name="ck_create_presentations_state",
        ),
        sa.CheckConstraint("review_state IN ('pending', 'approved')", name="ck_create_presentations_review"),
        sa.ForeignKeyConstraint(["organisation_id"], ["organisations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["organisation_id", "account_id"],
            ["companies.organisation_id", "companies.id"],
            name="fk_create_presentations_account",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organisation_id", "opportunity_id"],
            ["opportunities.organisation_id", "opportunities.id"],
            name="fk_create_presentations_opportunity",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organisation_id", "template_version_id", "template_id"],
            [
                "create_template_versions.organisation_id",
                "create_template_versions.id",
                "create_template_versions.template_id",
            ],
            name="fk_create_presentations_template_version",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organisation_id", "created_by_user_id"],
            ["organisation_memberships.organisation_id", "organisation_memberships.user_id"],
            name="fk_create_presentations_creator",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organisation_id", "id", name="uq_create_presentations_org_id"),
        sa.UniqueConstraint(
            "organisation_id", "created_by_user_id", "idempotency_key", name="uq_create_presentations_idempotency"
        ),
    )
    op.create_index("ix_create_presentations_org_created", "create_presentations", ["organisation_id", "created_at"])
    op.create_index(
        "ix_create_presentations_org_account", "create_presentations", ["organisation_id", "account_id", "updated_at"]
    )
    op.create_index(
        "ix_create_presentations_org_opportunity",
        "create_presentations",
        ["organisation_id", "opportunity_id", "updated_at"],
    )

    op.create_table(
        "create_presentation_versions",
        sa.Column("id", uuid_type, nullable=False),
        sa.Column("organisation_id", uuid_type, nullable=False),
        sa.Column("presentation_id", uuid_type, nullable=False),
        sa.Column("template_id", uuid_type, nullable=False),
        sa.Column("template_version_id", uuid_type, nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_by_user_id", uuid_type, nullable=False),
        sa.Column("state", sa.String(length=20), server_default="generating", nullable=False),
        sa.Column("review_state", sa.String(length=20), server_default="pending", nullable=False),
        sa.Column("plan_snapshot_json", sa.JSON(), nullable=False),
        sa.Column("audience_snapshot_json", sa.JSON(), nullable=False),
        sa.Column("source_context_json", sa.JSON(), nullable=False),
        sa.Column("source_context_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("generated_content_json", sa.JSON(), nullable=False),
        sa.Column("claim_manifest_json", sa.JSON(), nullable=False),
        sa.Column("warning_codes_json", sa.JSON(), server_default=sa.text("'[]'"), nullable=False),
        sa.Column("renderer_version", sa.String(length=60), server_default="deterministic_pptx_v1", nullable=False),
        sa.Column("generation_schema_version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("idempotency_key", sa.String(length=200), nullable=False),
        sa.Column("processing_attempts", sa.Integer(), server_default="0", nullable=False),
        sa.Column("worker_id", sa.String(length=200), nullable=True),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("pptx_storage_key", sa.String(length=255), nullable=True),
        sa.Column("storage_status", sa.String(length=24), server_default="pending", nullable=False),
        sa.Column("byte_size", sa.BigInteger(), nullable=True),
        sa.Column("checksum_sha256", sa.String(length=64), nullable=True),
        sa.Column("safe_failure_code", sa.String(length=100), nullable=True),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("approved_by_user_id", uuid_type, nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("version > 0", name="ck_create_presentation_versions_number"),
        sa.CheckConstraint(
            "state IN ('generating', 'needs_review', 'ready', 'failed')", name="ck_create_presentation_versions_state"
        ),
        sa.CheckConstraint("review_state IN ('pending', 'approved')", name="ck_create_presentation_versions_review"),
        sa.CheckConstraint(
            "renderer_version = 'deterministic_pptx_v1'", name="ck_create_presentation_versions_renderer"
        ),
        sa.CheckConstraint("generation_schema_version = 1", name="ck_create_presentation_versions_schema"),
        sa.CheckConstraint("processing_attempts BETWEEN 0 AND 3", name="ck_create_presentation_versions_attempts"),
        sa.CheckConstraint(
            "storage_status IN ('pending', 'available', 'deletion_pending', 'delete_failed', 'deleted')",
            name="ck_create_presentation_versions_storage",
        ),
        sa.ForeignKeyConstraint(["organisation_id"], ["organisations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["organisation_id", "presentation_id"],
            ["create_presentations.organisation_id", "create_presentations.id"],
            name="fk_create_presentation_versions_presentation",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["organisation_id", "template_version_id", "template_id"],
            [
                "create_template_versions.organisation_id",
                "create_template_versions.id",
                "create_template_versions.template_id",
            ],
            name="fk_create_presentation_versions_template",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organisation_id", "created_by_user_id"],
            ["organisation_memberships.organisation_id", "organisation_memberships.user_id"],
            name="fk_create_presentation_versions_creator",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organisation_id", "approved_by_user_id"],
            ["organisation_memberships.organisation_id", "organisation_memberships.user_id"],
            name="fk_create_presentation_versions_approver",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organisation_id", "id", name="uq_create_presentation_versions_org_id"),
        sa.UniqueConstraint(
            "organisation_id", "presentation_id", "version", name="uq_create_presentation_versions_number"
        ),
        sa.UniqueConstraint(
            "organisation_id", "presentation_id", "idempotency_key", name="uq_create_presentation_versions_key"
        ),
        sa.UniqueConstraint("organisation_id", "pptx_storage_key", name="uq_create_presentation_versions_storage"),
    )
    op.create_index(
        "ix_create_presentation_versions_org_presentation",
        "create_presentation_versions",
        ["organisation_id", "presentation_id", "version"],
    )
    op.create_index(
        "ix_create_presentation_versions_org_state",
        "create_presentation_versions",
        ["organisation_id", "state", "created_at"],
    )

    _enable_tenant_rls()
    _create_worker_discovery()


def downgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        op.execute(
            "DROP FUNCTION IF EXISTS public.revenueos_create_worker_eligible_organisations(timestamptz, integer)"
        )
    for table_name in reversed(TENANT_TABLES):
        op.drop_table(table_name)
    op.execute("DELETE FROM organisation_module_entitlements WHERE module_key = 'create'")
    with op.batch_alter_table("organisation_module_entitlements") as batch:
        batch.drop_constraint("ck_module_entitlements_key", type_="check")
        batch.create_check_constraint("ck_module_entitlements_key", "module_key IN ('prospect', 'engage')")
