"""Add company knowledge sources and the MEDDICC framework option.

Revision ID: 0066_conversation_core
Revises: 0065_campaign_trigger_guard

Knowledge sources are tenant-owned inputs for the organisation-approved company
profile. Website addresses are stored without fetching; manually supplied text
is bounded and retained for administrator review. No legacy product records are
removed by this refocus.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0066_conversation_core"
down_revision: str | None = "0065_campaign_trigger_guard"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLE_NAME = "company_knowledge_sources"


def _replace_methodology_selection_constraint(*, include_meddicc: bool) -> None:
    selections = "'none', 'meddic', 'meddpicc', 'bant', 'spiced', 'custom'"
    if include_meddicc:
        selections = "'none', 'meddic', 'meddicc', 'meddpicc', 'bant', 'spiced', 'custom'"
    with op.batch_alter_table("organisation_methodology_settings") as batch:
        batch.drop_constraint("ck_methodology_settings_selection", type_="check")
        batch.create_check_constraint(
            "ck_methodology_settings_selection",
            f"selection IN ({selections})",
        )


def upgrade() -> None:
    uuid_type = sa.Uuid(as_uuid=True)
    op.create_table(
        TABLE_NAME,
        sa.Column("id", uuid_type, nullable=False),
        sa.Column("organisation_id", uuid_type, nullable=False),
        sa.Column("source_kind", sa.String(length=24), nullable=False),
        sa.Column("label", sa.String(length=200), nullable=False),
        sa.Column("website_url", sa.String(length=2_000), nullable=True),
        sa.Column("source_text", sa.Text(), nullable=True),
        sa.Column("content_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("processing_status", sa.String(length=24), nullable=False),
        sa.Column("failure_code", sa.String(length=100), nullable=True),
        sa.Column("created_by_user_id", uuid_type, nullable=False),
        sa.Column("idempotency_key", sa.String(length=200), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "source_kind IN ('website', 'supporting_text', 'text_file')",
            name="ck_company_knowledge_sources_kind",
        ),
        sa.CheckConstraint(
            "processing_status IN ('saved_unprocessed', 'ready_for_review', 'failed')",
            name="ck_company_knowledge_sources_status",
        ),
        sa.CheckConstraint(
            "(source_kind = 'website' AND website_url IS NOT NULL AND source_text IS NULL) OR "
            "(source_kind IN ('supporting_text', 'text_file') AND website_url IS NULL "
            "AND source_text IS NOT NULL)",
            name="ck_company_knowledge_sources_content",
        ),
        sa.ForeignKeyConstraint(["organisation_id"], ["organisations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["organisation_id", "created_by_user_id"],
            ["organisation_memberships.organisation_id", "organisation_memberships.user_id"],
            name="fk_company_knowledge_sources_creator",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organisation_id", "id", name="uq_company_knowledge_sources_org_id"),
        sa.UniqueConstraint(
            "organisation_id",
            "created_by_user_id",
            "idempotency_key",
            name="uq_company_knowledge_sources_idempotency",
        ),
    )
    op.create_index(
        "ix_company_knowledge_sources_org_created",
        TABLE_NAME,
        ["organisation_id", "created_at"],
    )
    if op.get_bind().dialect.name == "postgresql":
        op.execute(f"ALTER TABLE {TABLE_NAME} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {TABLE_NAME} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"""CREATE POLICY {TABLE_NAME}_tenant_isolation ON {TABLE_NAME}
            USING (organisation_id = NULLIF(current_setting('app.organisation_id', true), '')::uuid)
            WITH CHECK (organisation_id = NULLIF(current_setting('app.organisation_id', true), '')::uuid)"""
        )
    _replace_methodology_selection_constraint(include_meddicc=True)


def downgrade() -> None:
    # MEDDICC is the closest reversible representation in the previous
    # catalogue. Normalise it before restoring the narrower check constraint
    # so a rollback cannot strand an otherwise valid organisation setting.
    op.execute("UPDATE organisation_methodology_settings SET selection = 'meddic' WHERE selection = 'meddicc'")
    _replace_methodology_selection_constraint(include_meddicc=False)
    op.drop_index("ix_company_knowledge_sources_org_created", table_name=TABLE_NAME)
    op.drop_table(TABLE_NAME)
