"""Add bounded real-data operations and Native CRM onboarding metadata.

Revision ID: 0050_real_data_operations
Revises: 0049_create_trust

WO-039C stores only content-free CSV import metadata, immutable merge
tombstones and immutable operator-provisioning events. Raw CSV rows are never
persisted. Imported open opportunities receive an explicit baseline event; no
earlier stage timing is inferred.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0050_real_data_operations"
down_revision: str | None = "0049_create_trust"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TENANT_TABLES = (
    "operator_provisioning_events",
    "crm_import_batches",
    "crm_import_rows",
    "crm_record_merges",
)
IMMUTABLE_TABLES = ("operator_provisioning_events", "crm_record_merges")


def _enable_tenant_rls_and_history_guards() -> None:
    dialect = op.get_bind().dialect.name
    if dialect == "postgresql":
        for table_name in TENANT_TABLES:
            op.execute(f"ALTER TABLE {table_name} ENABLE ROW LEVEL SECURITY")
            op.execute(f"ALTER TABLE {table_name} FORCE ROW LEVEL SECURITY")
            op.execute(
                f"""CREATE POLICY {table_name}_tenant_isolation
                ON {table_name}
                USING (organisation_id = NULLIF(current_setting('app.organisation_id', true), '')::uuid)
                WITH CHECK (organisation_id = NULLIF(current_setting('app.organisation_id', true), '')::uuid)"""
            )
        op.execute(
            """CREATE FUNCTION public.revenueos_reject_real_data_history_update()
            RETURNS trigger AS $$
            BEGIN
                RAISE EXCEPTION 'real-data history rows are immutable';
            END;
            $$ LANGUAGE plpgsql"""
        )
        for table_name in IMMUTABLE_TABLES:
            op.execute(
                f"""CREATE TRIGGER {table_name}_immutable
                BEFORE UPDATE ON {table_name}
                FOR EACH ROW EXECUTE FUNCTION public.revenueos_reject_real_data_history_update()"""
            )
    elif dialect == "sqlite":
        for table_name in IMMUTABLE_TABLES:
            op.execute(
                f"""CREATE TRIGGER {table_name}_immutable_update
                BEFORE UPDATE ON {table_name}
                BEGIN SELECT RAISE(ABORT, 'real-data history rows are immutable'); END"""
            )


def upgrade() -> None:
    uuid_type = sa.Uuid(as_uuid=True)

    with op.batch_alter_table("crm_custom_field_values") as batch:
        batch.drop_constraint("ck_crm_custom_values_source", type_="check")
        batch.create_check_constraint(
            "ck_crm_custom_values_source",
            "source IN ('manual_user_entry', 'crm_import', 'prospect_promotion', "
            "'event_promotion', 'external_crm', 'reviewed_action', 'record_merge', 'system')",
        )
    with op.batch_alter_table("crm_record_changes") as batch:
        batch.drop_constraint("ck_crm_record_changes_source", type_="check")
        batch.create_check_constraint(
            "ck_crm_record_changes_source",
            "source IN ('manual_user_entry', 'crm_import', 'prospect_promotion', "
            "'event_promotion', 'external_crm', 'reviewed_action', 'record_merge', 'system')",
        )
    with op.batch_alter_table("opportunity_stage_events") as batch:
        batch.drop_constraint("ck_opportunity_stage_events_source", type_="check")
        batch.create_check_constraint(
            "ck_opportunity_stage_events_source",
            "source IN ('system_initial', 'migration_baseline', 'import_baseline', 'manual', 'external_crm')",
        )

    op.create_table(
        "operator_provisioning_events",
        sa.Column("id", uuid_type, nullable=False),
        sa.Column("organisation_id", uuid_type, nullable=False),
        sa.Column("action", sa.String(length=40), nullable=False),
        sa.Column("idempotency_key_hash", sa.String(length=64), nullable=False),
        sa.Column("subject_user_id", uuid_type, nullable=False),
        sa.Column("operator_reference", sa.String(length=200), nullable=False),
        sa.Column("metadata_json", sa.JSON(), server_default="{}", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "action IN ('organisation_provisioned', 'member_provisioned')",
            name="ck_operator_provisioning_events_action",
        ),
        sa.CheckConstraint(
            "length(idempotency_key_hash) = 64 AND idempotency_key_hash = lower(idempotency_key_hash)",
            name="ck_operator_provisioning_events_key",
        ),
        sa.CheckConstraint(
            "length(trim(operator_reference)) BETWEEN 1 AND 200",
            name="ck_operator_provisioning_events_operator",
        ),
        sa.ForeignKeyConstraint(["organisation_id"], ["organisations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organisation_id", "id", name="uq_operator_provisioning_events_org_id"),
        sa.UniqueConstraint(
            "organisation_id",
            "action",
            "idempotency_key_hash",
            name="uq_operator_provisioning_events_key",
        ),
    )
    op.create_index(
        "ix_operator_provisioning_events_org_time",
        "operator_provisioning_events",
        ["organisation_id", "created_at"],
    )

    op.create_table(
        "crm_import_batches",
        sa.Column("id", uuid_type, nullable=False),
        sa.Column("organisation_id", uuid_type, nullable=False),
        sa.Column("entity_type", sa.String(length=24), nullable=False),
        sa.Column("requested_by_user_id", uuid_type, nullable=False),
        sa.Column("state", sa.String(length=20), server_default="previewed", nullable=False),
        sa.Column("file_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("mapping_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("file_size_bytes", sa.Integer(), nullable=False),
        sa.Column("row_count", sa.Integer(), nullable=False),
        sa.Column("actionable_row_count", sa.Integer(), nullable=False),
        sa.Column("imported_row_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "entity_type IN ('account', 'contact', 'opportunity')",
            name="ck_crm_import_batches_entity_type",
        ),
        sa.CheckConstraint(
            "state IN ('previewed', 'confirmed', 'expired', 'failed')",
            name="ck_crm_import_batches_state",
        ),
        sa.CheckConstraint(
            "length(file_fingerprint) = 64 AND file_fingerprint = lower(file_fingerprint)",
            name="ck_crm_import_batches_file_hash",
        ),
        sa.CheckConstraint(
            "length(mapping_fingerprint) = 64 AND mapping_fingerprint = lower(mapping_fingerprint)",
            name="ck_crm_import_batches_mapping_hash",
        ),
        sa.CheckConstraint(
            "row_count BETWEEN 0 AND 5000 AND actionable_row_count BETWEEN 0 AND row_count "
            "AND imported_row_count BETWEEN 0 AND actionable_row_count",
            name="ck_crm_import_batches_counts",
        ),
        sa.ForeignKeyConstraint(["organisation_id"], ["organisations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["organisation_id", "requested_by_user_id"],
            ["organisation_memberships.organisation_id", "organisation_memberships.user_id"],
            name="fk_crm_import_batches_requester",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organisation_id", "id", name="uq_crm_import_batches_org_id"),
        sa.UniqueConstraint(
            "organisation_id",
            "entity_type",
            "file_fingerprint",
            "mapping_fingerprint",
            name="uq_crm_import_batches_fingerprint",
        ),
    )
    op.create_index(
        "ix_crm_import_batches_org_state",
        "crm_import_batches",
        ["organisation_id", "state", "created_at"],
    )

    op.create_table(
        "crm_import_rows",
        sa.Column("id", uuid_type, nullable=False),
        sa.Column("organisation_id", uuid_type, nullable=False),
        sa.Column("batch_id", uuid_type, nullable=False),
        sa.Column("source_row", sa.Integer(), nullable=False),
        sa.Column("disposition", sa.String(length=24), nullable=False),
        sa.Column("issue_code", sa.String(length=80), nullable=True),
        sa.Column("canonical_entity_id", uuid_type, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("source_row BETWEEN 2 AND 5001", name="ck_crm_import_rows_source_row"),
        sa.CheckConstraint(
            "disposition IN ('new', 'matches_existing', 'possible_duplicate', 'invalid', 'imported', 'skipped')",
            name="ck_crm_import_rows_disposition",
        ),
        sa.CheckConstraint(
            "issue_code IS NULL OR length(trim(issue_code)) BETWEEN 1 AND 80",
            name="ck_crm_import_rows_issue",
        ),
        sa.ForeignKeyConstraint(["organisation_id"], ["organisations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["organisation_id", "batch_id"],
            ["crm_import_batches.organisation_id", "crm_import_batches.id"],
            name="fk_crm_import_rows_batch",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organisation_id", "id", name="uq_crm_import_rows_org_id"),
        sa.UniqueConstraint("organisation_id", "batch_id", "source_row", name="uq_crm_import_rows_source"),
    )
    op.create_index(
        "ix_crm_import_rows_org_batch",
        "crm_import_rows",
        ["organisation_id", "batch_id", "source_row"],
    )

    op.create_table(
        "crm_record_merges",
        sa.Column("id", uuid_type, nullable=False),
        sa.Column("organisation_id", uuid_type, nullable=False),
        sa.Column("entity_type", sa.String(length=24), nullable=False),
        sa.Column("source_entity_id", uuid_type, nullable=False),
        sa.Column("survivor_entity_id", uuid_type, nullable=False),
        sa.Column("preview_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("idempotency_key_hash", sa.String(length=64), nullable=False),
        sa.Column("field_selection_json", sa.JSON(), server_default="{}", nullable=False),
        sa.Column("merged_by_user_id", uuid_type, nullable=False),
        sa.Column("merged_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("entity_type IN ('account', 'contact')", name="ck_crm_record_merges_entity_type"),
        sa.CheckConstraint("source_entity_id <> survivor_entity_id", name="ck_crm_record_merges_distinct"),
        sa.CheckConstraint(
            "length(preview_fingerprint) = 64 AND preview_fingerprint = lower(preview_fingerprint)",
            name="ck_crm_record_merges_preview_hash",
        ),
        sa.CheckConstraint(
            "length(idempotency_key_hash) = 64 AND idempotency_key_hash = lower(idempotency_key_hash)",
            name="ck_crm_record_merges_key_hash",
        ),
        sa.ForeignKeyConstraint(["organisation_id"], ["organisations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["organisation_id", "merged_by_user_id"],
            ["organisation_memberships.organisation_id", "organisation_memberships.user_id"],
            name="fk_crm_record_merges_actor",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organisation_id", "id", name="uq_crm_record_merges_org_id"),
        sa.UniqueConstraint(
            "organisation_id",
            "entity_type",
            "source_entity_id",
            name="uq_crm_record_merges_source",
        ),
        sa.UniqueConstraint(
            "organisation_id",
            "entity_type",
            "idempotency_key_hash",
            name="uq_crm_record_merges_key",
        ),
    )
    op.create_index(
        "ix_crm_record_merges_org_survivor",
        "crm_record_merges",
        ["organisation_id", "entity_type", "survivor_entity_id"],
    )

    _enable_tenant_rls_and_history_guards()


def downgrade() -> None:
    dialect = op.get_bind().dialect.name
    if dialect == "postgresql":
        for table_name in IMMUTABLE_TABLES:
            op.execute(f"DROP TRIGGER {table_name}_immutable ON {table_name}")
        op.execute("DROP FUNCTION public.revenueos_reject_real_data_history_update()")
    elif dialect == "sqlite":
        for table_name in IMMUTABLE_TABLES:
            op.execute(f"DROP TRIGGER {table_name}_immutable_update")

    op.drop_index("ix_crm_record_merges_org_survivor", table_name="crm_record_merges")
    op.drop_table("crm_record_merges")
    op.drop_index("ix_crm_import_rows_org_batch", table_name="crm_import_rows")
    op.drop_table("crm_import_rows")
    op.drop_index("ix_crm_import_batches_org_state", table_name="crm_import_batches")
    op.drop_table("crm_import_batches")
    op.drop_index("ix_operator_provisioning_events_org_time", table_name="operator_provisioning_events")
    op.drop_table("operator_provisioning_events")

    with op.batch_alter_table("opportunity_stage_events") as batch:
        batch.drop_constraint("ck_opportunity_stage_events_source", type_="check")
        batch.create_check_constraint(
            "ck_opportunity_stage_events_source",
            "source IN ('system_initial', 'migration_baseline', 'manual', 'external_crm')",
        )
    with op.batch_alter_table("crm_record_changes") as batch:
        batch.drop_constraint("ck_crm_record_changes_source", type_="check")
        batch.create_check_constraint(
            "ck_crm_record_changes_source",
            "source IN ('manual_user_entry', 'crm_import', 'prospect_promotion', "
            "'event_promotion', 'external_crm', 'reviewed_action', 'system')",
        )
    with op.batch_alter_table("crm_custom_field_values") as batch:
        batch.drop_constraint("ck_crm_custom_values_source", type_="check")
        batch.create_check_constraint(
            "ck_crm_custom_values_source",
            "source IN ('manual_user_entry', 'crm_import', 'prospect_promotion', "
            "'event_promotion', 'external_crm', 'reviewed_action', 'system')",
        )
