"""Add canonical native pipeline definitions and stage history.

Revision ID: 0044_native_pipeline
Revises: 0043_native_crm

Existing Opportunity stage/status values are preserved. Each organisation receives
one default definition matching the canonical stage taxonomy, while every existing
Opportunity receives only a migration-baseline event. No earlier transition or
duration is inferred.
"""

from collections.abc import Sequence
from datetime import UTC, datetime
from uuid import uuid4

import sqlalchemy as sa
from alembic import op

revision: str = "0044_native_pipeline"
down_revision: str | None = "0043_native_crm"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TENANT_TABLES = ("sales_pipelines", "sales_pipeline_stages", "opportunity_stage_events")
DEFAULT_STAGES = (
    ("discovery", "Discovery", "open"),
    ("qualification", "Qualification", "open"),
    ("evaluation", "Evaluation", "open"),
    ("proposal", "Proposal", "open"),
    ("negotiation", "Negotiation", "open"),
    ("procurement", "Procurement", "open"),
    ("other", "Other", "open"),
    ("closed_won", "Closed Won", "won"),
    ("closed_lost", "Closed Lost", "lost"),
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
    op.execute(
        """CREATE FUNCTION reject_opportunity_stage_event_update() RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION 'opportunity stage events are immutable';
        END;
        $$ LANGUAGE plpgsql"""
    )
    op.execute(
        """CREATE TRIGGER opportunity_stage_events_immutable_update
        BEFORE UPDATE ON opportunity_stage_events
        FOR EACH ROW EXECUTE FUNCTION reject_opportunity_stage_event_update()"""
    )


def _seed_default_pipelines() -> None:
    bind = op.get_bind()
    identifier_type: sa.types.TypeEngine[object]
    if bind.dialect.name == "postgresql":
        identifier_type = sa.Uuid(as_uuid=True)

        def new_identifier() -> object:
            return uuid4()

    else:
        identifier_type = sa.String(36)

        def new_identifier() -> object:
            return str(uuid4())

    metadata = sa.MetaData()
    organisations = sa.Table("organisations", metadata, sa.Column("id", identifier_type))
    opportunities = sa.Table(
        "opportunities",
        metadata,
        sa.Column("id", identifier_type),
        sa.Column("organisation_id", identifier_type),
        sa.Column("stage", sa.String()),
        sa.Column("status", sa.String()),
        sa.Column("pipeline_id", identifier_type),
        sa.Column("pipeline_stage_id", identifier_type),
        sa.Column("stage_tracking_started_at", sa.DateTime(timezone=True)),
    )
    pipelines = sa.Table(
        "sales_pipelines",
        metadata,
        sa.Column("id", identifier_type),
        sa.Column("organisation_id", identifier_type),
        sa.Column("name", sa.String()),
        sa.Column("is_default", sa.Boolean()),
        sa.Column("active", sa.Boolean()),
        sa.Column("created_at", sa.DateTime(timezone=True)),
        sa.Column("updated_at", sa.DateTime(timezone=True)),
    )
    stages = sa.Table(
        "sales_pipeline_stages",
        metadata,
        sa.Column("id", identifier_type),
        sa.Column("organisation_id", identifier_type),
        sa.Column("pipeline_id", identifier_type),
        sa.Column("stage_key", sa.String()),
        sa.Column("name", sa.String()),
        sa.Column("position", sa.Integer()),
        sa.Column("stage_type", sa.String()),
        sa.Column("active", sa.Boolean()),
        sa.Column("created_at", sa.DateTime(timezone=True)),
        sa.Column("updated_at", sa.DateTime(timezone=True)),
    )
    events = sa.Table(
        "opportunity_stage_events",
        metadata,
        sa.Column("id", identifier_type),
        sa.Column("organisation_id", identifier_type),
        sa.Column("opportunity_id", identifier_type),
        sa.Column("to_pipeline_id", identifier_type),
        sa.Column("to_stage_id", identifier_type),
        sa.Column("to_stage_name", sa.String()),
        sa.Column("to_stage_type", sa.String()),
        sa.Column("changed_at", sa.DateTime(timezone=True)),
        sa.Column("source", sa.String()),
        sa.Column("is_baseline", sa.Boolean()),
    )
    tracking_started_at = datetime.now(UTC)
    for organisation_id in bind.execute(sa.select(organisations.c.id)).scalars():
        pipeline_id = new_identifier()
        bind.execute(
            pipelines.insert().values(
                id=pipeline_id,
                organisation_id=organisation_id,
                name="RevenueOS Sales Pipeline",
                is_default=True,
                active=True,
                created_at=tracking_started_at,
                updated_at=tracking_started_at,
            )
        )
        stage_ids: dict[str, object] = {}
        stage_types: dict[str, str] = {}
        stage_names: dict[str, str] = {}
        for position, (stage_key, stage_name, stage_type) in enumerate(DEFAULT_STAGES):
            stage_id = new_identifier()
            stage_ids[stage_key] = stage_id
            stage_types[stage_key] = stage_type
            stage_names[stage_key] = stage_name
            bind.execute(
                stages.insert().values(
                    id=stage_id,
                    organisation_id=organisation_id,
                    pipeline_id=pipeline_id,
                    stage_key=stage_key,
                    name=stage_name,
                    position=position,
                    stage_type=stage_type,
                    active=True,
                    created_at=tracking_started_at,
                    updated_at=tracking_started_at,
                )
            )
        rows = bind.execute(
            sa.select(opportunities.c.id, opportunities.c.stage, opportunities.c.status).where(
                opportunities.c.organisation_id == organisation_id
            )
        ).all()
        for opportunity_id, legacy_stage, status in rows:
            stage_key = "closed_won" if status == "won" else "closed_lost" if status == "lost" else legacy_stage
            if stage_key not in stage_ids:
                stage_key = "other"
            stage_id = stage_ids[stage_key]
            bind.execute(
                opportunities.update()
                .where(
                    opportunities.c.organisation_id == organisation_id,
                    opportunities.c.id == opportunity_id,
                )
                .values(
                    pipeline_id=pipeline_id,
                    pipeline_stage_id=stage_id,
                    stage_tracking_started_at=tracking_started_at,
                )
            )
            bind.execute(
                events.insert().values(
                    id=new_identifier(),
                    organisation_id=organisation_id,
                    opportunity_id=opportunity_id,
                    to_pipeline_id=pipeline_id,
                    to_stage_id=stage_id,
                    to_stage_name=stage_names[stage_key],
                    to_stage_type=stage_types[stage_key],
                    changed_at=tracking_started_at,
                    source="migration_baseline",
                    is_baseline=True,
                )
            )


def upgrade() -> None:
    uuid_type = sa.Uuid(as_uuid=True)
    op.create_table(
        "sales_pipelines",
        sa.Column("id", uuid_type, nullable=False),
        sa.Column("organisation_id", uuid_type, nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("is_default", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("length(trim(name)) BETWEEN 1 AND 100", name="ck_sales_pipelines_name"),
        sa.CheckConstraint(
            "(active AND archived_at IS NULL) OR (NOT active AND archived_at IS NOT NULL)",
            name="ck_sales_pipelines_archive",
        ),
        sa.ForeignKeyConstraint(["organisation_id"], ["organisations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organisation_id", "id", name="uq_sales_pipelines_org_id"),
    )
    op.create_index("ix_sales_pipelines_org_active", "sales_pipelines", ["organisation_id", "active", "created_at"])
    op.create_index(
        "uq_sales_pipelines_org_default",
        "sales_pipelines",
        ["organisation_id"],
        unique=True,
        postgresql_where=sa.text("is_default AND active"),
        sqlite_where=sa.text("is_default = 1 AND active = 1"),
    )
    op.create_table(
        "sales_pipeline_stages",
        sa.Column("id", uuid_type, nullable=False),
        sa.Column("organisation_id", uuid_type, nullable=False),
        sa.Column("pipeline_id", uuid_type, nullable=False),
        sa.Column("stage_key", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("stage_type", sa.String(length=12), nullable=False),
        sa.Column("guidance", sa.String(length=300), nullable=True),
        sa.Column("active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("length(trim(stage_key)) BETWEEN 1 AND 64", name="ck_pipeline_stages_key"),
        sa.CheckConstraint("length(trim(name)) BETWEEN 1 AND 100", name="ck_pipeline_stages_name"),
        sa.CheckConstraint("position BETWEEN 0 AND 11", name="ck_pipeline_stages_position"),
        sa.CheckConstraint("stage_type IN ('open', 'won', 'lost')", name="ck_pipeline_stages_type"),
        sa.CheckConstraint(
            "guidance IS NULL OR length(guidance) BETWEEN 1 AND 300",
            name="ck_pipeline_stages_guidance",
        ),
        sa.CheckConstraint(
            "(active AND archived_at IS NULL) OR (NOT active AND archived_at IS NOT NULL)",
            name="ck_pipeline_stages_archive",
        ),
        sa.ForeignKeyConstraint(["organisation_id"], ["organisations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["organisation_id", "pipeline_id"],
            ["sales_pipelines.organisation_id", "sales_pipelines.id"],
            name="fk_pipeline_stages_pipeline",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organisation_id", "id", name="uq_pipeline_stages_org_id"),
        sa.UniqueConstraint("organisation_id", "pipeline_id", "id", name="uq_pipeline_stages_org_pipeline_id"),
        sa.UniqueConstraint("organisation_id", "pipeline_id", "stage_key", name="uq_pipeline_stages_org_pipeline_key"),
    )
    op.create_index(
        "ix_pipeline_stages_org_pipeline",
        "sales_pipeline_stages",
        ["organisation_id", "pipeline_id", "active", "position"],
    )
    with op.batch_alter_table("opportunities") as batch:
        batch.add_column(sa.Column("pipeline_id", uuid_type, nullable=True))
        batch.add_column(sa.Column("pipeline_stage_id", uuid_type, nullable=True))
        batch.add_column(sa.Column("stage_entered_at", sa.DateTime(timezone=True), nullable=True))
        batch.add_column(sa.Column("stage_tracking_started_at", sa.DateTime(timezone=True), nullable=True))
        batch.add_column(sa.Column("actual_close_date", sa.Date(), nullable=True))
        batch.add_column(sa.Column("outcome_reason", sa.String(length=40), nullable=True))
        batch.add_column(sa.Column("outcome_note", sa.String(length=500), nullable=True))
        batch.add_column(sa.Column("outcome_provenance", sa.String(length=32), nullable=True))
        batch.create_check_constraint(
            "ck_opportunities_outcome_provenance",
            "outcome_provenance IS NULL OR outcome_provenance = 'seller_reported'",
        )
        batch.create_check_constraint(
            "ck_opportunities_outcome_note",
            "outcome_note IS NULL OR length(outcome_note) BETWEEN 1 AND 500",
        )
        batch.create_foreign_key(
            "fk_opportunities_pipeline",
            "sales_pipelines",
            ["organisation_id", "pipeline_id"],
            ["organisation_id", "id"],
            ondelete="RESTRICT",
        )
        batch.create_foreign_key(
            "fk_opportunities_pipeline_stage",
            "sales_pipeline_stages",
            ["organisation_id", "pipeline_id", "pipeline_stage_id"],
            ["organisation_id", "pipeline_id", "id"],
            ondelete="RESTRICT",
        )
    op.create_index(
        "ix_opportunities_org_pipeline_stage",
        "opportunities",
        ["organisation_id", "pipeline_id", "pipeline_stage_id", "status"],
    )
    op.create_index("ix_opportunities_org_stage_entered", "opportunities", ["organisation_id", "stage_entered_at"])
    op.create_table(
        "opportunity_stage_events",
        sa.Column("id", uuid_type, nullable=False),
        sa.Column("organisation_id", uuid_type, nullable=False),
        sa.Column("opportunity_id", uuid_type, nullable=False),
        sa.Column("from_pipeline_id", uuid_type, nullable=True),
        sa.Column("to_pipeline_id", uuid_type, nullable=False),
        sa.Column("from_stage_id", uuid_type, nullable=True),
        sa.Column("to_stage_id", uuid_type, nullable=False),
        sa.Column("from_stage_name", sa.String(length=100), nullable=True),
        sa.Column("to_stage_name", sa.String(length=100), nullable=False),
        sa.Column("from_stage_type", sa.String(length=12), nullable=True),
        sa.Column("to_stage_type", sa.String(length=12), nullable=False),
        sa.Column("changed_by_user_id", uuid_type, nullable=True),
        sa.Column("changed_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("source", sa.String(length=24), nullable=False),
        sa.Column("is_baseline", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("previous_stage_entered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("outcome_reason", sa.String(length=40), nullable=True),
        sa.Column("outcome_note", sa.String(length=500), nullable=True),
        sa.Column("outcome_provenance", sa.String(length=32), nullable=True),
        sa.Column("actual_close_date", sa.Date(), nullable=True),
        sa.Column("final_amount", sa.Numeric(precision=18, scale=2), nullable=True),
        sa.Column("final_currency", sa.String(length=3), nullable=True),
        sa.Column("idempotency_key", sa.String(length=100), nullable=True),
        sa.CheckConstraint(
            "source IN ('system_initial', 'migration_baseline', 'manual', 'external_crm')",
            name="ck_opportunity_stage_events_source",
        ),
        sa.CheckConstraint(
            "from_stage_type IS NULL OR from_stage_type IN ('open', 'won', 'lost')",
            name="ck_opportunity_stage_events_from_type",
        ),
        sa.CheckConstraint("to_stage_type IN ('open', 'won', 'lost')", name="ck_opportunity_stage_events_to_type"),
        sa.CheckConstraint(
            "outcome_provenance IS NULL OR outcome_provenance = 'seller_reported'",
            name="ck_opportunity_stage_events_provenance",
        ),
        sa.CheckConstraint(
            "outcome_note IS NULL OR length(outcome_note) BETWEEN 1 AND 500",
            name="ck_opportunity_stage_events_note",
        ),
        sa.CheckConstraint(
            "(final_amount IS NULL AND final_currency IS NULL) OR "
            "(final_amount IS NOT NULL AND final_amount >= 0 AND final_currency IS NOT NULL)",
            name="ck_opportunity_stage_events_value_currency",
        ),
        sa.CheckConstraint(
            "final_currency IS NULL OR (length(final_currency) = 3 AND final_currency = upper(final_currency))",
            name="ck_opportunity_stage_events_currency",
        ),
        sa.ForeignKeyConstraint(["organisation_id"], ["organisations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["organisation_id", "opportunity_id"],
            ["opportunities.organisation_id", "opportunities.id"],
            name="fk_opportunity_stage_events_opportunity",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["organisation_id", "from_pipeline_id"],
            ["sales_pipelines.organisation_id", "sales_pipelines.id"],
            name="fk_opportunity_stage_events_from_pipeline",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organisation_id", "to_pipeline_id"],
            ["sales_pipelines.organisation_id", "sales_pipelines.id"],
            name="fk_opportunity_stage_events_to_pipeline",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organisation_id", "from_pipeline_id", "from_stage_id"],
            ["sales_pipeline_stages.organisation_id", "sales_pipeline_stages.pipeline_id", "sales_pipeline_stages.id"],
            name="fk_opportunity_stage_events_from_stage",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organisation_id", "to_pipeline_id", "to_stage_id"],
            ["sales_pipeline_stages.organisation_id", "sales_pipeline_stages.pipeline_id", "sales_pipeline_stages.id"],
            name="fk_opportunity_stage_events_to_stage",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organisation_id", "changed_by_user_id"],
            ["organisation_memberships.organisation_id", "organisation_memberships.user_id"],
            name="fk_opportunity_stage_events_actor",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organisation_id", "id", name="uq_opportunity_stage_events_org_id"),
        sa.UniqueConstraint(
            "organisation_id",
            "opportunity_id",
            "idempotency_key",
            name="uq_opportunity_stage_events_idempotency",
        ),
    )
    op.create_index(
        "ix_opportunity_stage_events_org_opportunity",
        "opportunity_stage_events",
        ["organisation_id", "opportunity_id", "changed_at"],
    )
    with op.batch_alter_table("opportunity_audit_events") as batch:
        batch.drop_constraint("ck_opportunity_audit_events_action", type_="check")
        batch.create_check_constraint(
            "ck_opportunity_audit_events_action",
            "action IN ('created', 'updated', 'deleted', 'meeting_associated', "
            "'meeting_disassociated', 'stage_changed', 'closed_won', 'closed_lost', 'reopened')",
        )
    _seed_default_pipelines()
    _enable_tenant_rls()


def downgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        op.execute("DROP TRIGGER opportunity_stage_events_immutable_update ON opportunity_stage_events")
        op.execute("DROP FUNCTION reject_opportunity_stage_event_update()")
    with op.batch_alter_table("opportunity_audit_events") as batch:
        batch.drop_constraint("ck_opportunity_audit_events_action", type_="check")
        batch.create_check_constraint(
            "ck_opportunity_audit_events_action",
            "action IN ('created', 'updated', 'deleted', 'meeting_associated', 'meeting_disassociated')",
        )
    op.drop_table("opportunity_stage_events")
    op.drop_index("ix_opportunities_org_stage_entered", table_name="opportunities")
    op.drop_index("ix_opportunities_org_pipeline_stage", table_name="opportunities")
    with op.batch_alter_table("opportunities") as batch:
        batch.drop_constraint("fk_opportunities_pipeline_stage", type_="foreignkey")
        batch.drop_constraint("fk_opportunities_pipeline", type_="foreignkey")
        batch.drop_constraint("ck_opportunities_outcome_note", type_="check")
        batch.drop_constraint("ck_opportunities_outcome_provenance", type_="check")
        batch.drop_column("outcome_provenance")
        batch.drop_column("outcome_note")
        batch.drop_column("outcome_reason")
        batch.drop_column("actual_close_date")
        batch.drop_column("stage_tracking_started_at")
        batch.drop_column("stage_entered_at")
        batch.drop_column("pipeline_stage_id")
        batch.drop_column("pipeline_id")
    op.drop_table("sales_pipeline_stages")
    op.drop_table("sales_pipelines")
