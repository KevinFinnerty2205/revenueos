"""Add versioned commercial plans, entitlements and trial authority.

Revision ID: 0052_commercial_plans_trial
Revises: 0051_selling_profile

WO-047 adds a global immutable V1 plan catalogue and tenant-owned commercial
projection/history. Existing private-beta module access is preserved through a
minimal inferred base plan plus add-ons. No payment/provider facts are stored.
The forward migration also reapplies the checked-in WO-046 PostgreSQL history
guard so databases that ran an earlier function body receive its JSON comparison
fix without rewriting the prior revision.
"""

import uuid
from collections.abc import Sequence
from datetime import UTC, datetime
from decimal import Decimal

import sqlalchemy as sa
from alembic import op

revision: str = "0052_commercial_plans_trial"
down_revision: str | None = "0051_selling_profile"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PLAN_IDS = {
    "core": uuid.UUID("ee299a7d-3f12-5845-847e-3425f78ed6f2"),
    "growth": uuid.UUID("2d8aa6a4-30aa-52e8-8273-3859210a8406"),
    "complete": uuid.UUID("43cb5fa7-1b0b-5ca7-b5a3-740bd3e063a0"),
    "enterprise": uuid.UUID("070bd960-04cf-58bf-8382-9428565f996c"),
}
PLAN_MODULES = {
    "core": ["core"],
    "growth": ["core", "prospect", "engage"],
    "complete": ["core", "prospect", "engage", "create", "crm"],
    "enterprise": ["core", "prospect", "engage", "create", "crm"],
}
ALL_MODULES = ("core", "prospect", "engage", "create", "crm")
TENANT_TABLES = ("organisation_commercial_states", "commercial_state_events")


def _repair_selling_profile_history_guard() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return
    op.execute(
        """CREATE OR REPLACE FUNCTION public.revenueos_protect_selling_profile_history()
        RETURNS trigger AS $$
        BEGIN
            IF OLD.state <> 'draft' AND (
                NEW.id IS DISTINCT FROM OLD.id OR
                NEW.organisation_id IS DISTINCT FROM OLD.organisation_id OR
                NEW.content_json::text IS DISTINCT FROM OLD.content_json::text OR
                NEW.content_fingerprint IS DISTINCT FROM OLD.content_fingerprint OR
                NEW.revision_number IS DISTINCT FROM OLD.revision_number OR
                NEW.schema_version IS DISTINCT FROM OLD.schema_version OR
                NEW.lock_version IS DISTINCT FROM OLD.lock_version OR
                NEW.profile_id IS DISTINCT FROM OLD.profile_id OR
                NEW.created_by_user_id IS DISTINCT FROM OLD.created_by_user_id OR
                NEW.approved_by_user_id IS DISTINCT FROM OLD.approved_by_user_id OR
                NEW.idempotency_key IS DISTINCT FROM OLD.idempotency_key OR
                NEW.approved_at IS DISTINCT FROM OLD.approved_at OR
                NEW.created_at IS DISTINCT FROM OLD.created_at OR
                (OLD.state IN ('superseded', 'retired') AND (
                    NEW.state IS DISTINCT FROM OLD.state OR
                    NEW.superseded_at IS DISTINCT FROM OLD.superseded_at OR
                    NEW.retired_at IS DISTINCT FROM OLD.retired_at
                ))
            ) THEN
                RAISE EXCEPTION 'approved selling-profile history is immutable';
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql"""
    )


def _create_guards() -> None:
    dialect = op.get_bind().dialect.name
    if dialect == "postgresql":
        op.execute(
            """CREATE FUNCTION public.revenueos_reject_commercial_history_mutation()
            RETURNS trigger AS $$
            BEGIN
                IF TG_TABLE_NAME = 'commercial_state_events'
                   AND TG_OP = 'DELETE'
                   AND current_setting('app.beta_maintenance', true) = 'approved' THEN
                    RETURN OLD;
                END IF;
                RAISE EXCEPTION 'commercial catalogue and history are immutable';
            END;
            $$ LANGUAGE plpgsql"""
        )
        op.execute(
            """CREATE TRIGGER commercial_plan_versions_immutable_update
            BEFORE INSERT OR UPDATE OR DELETE ON commercial_plan_versions
            FOR EACH ROW EXECUTE FUNCTION public.revenueos_reject_commercial_history_mutation()"""
        )
        op.execute(
            """CREATE TRIGGER commercial_state_events_immutable_update
            BEFORE UPDATE OR DELETE ON commercial_state_events
            FOR EACH ROW EXECUTE FUNCTION public.revenueos_reject_commercial_history_mutation()"""
        )
        for table_name in TENANT_TABLES:
            op.execute(f"ALTER TABLE {table_name} ENABLE ROW LEVEL SECURITY")
            op.execute(f"ALTER TABLE {table_name} FORCE ROW LEVEL SECURITY")
            op.execute(
                f"""CREATE POLICY {table_name}_tenant_isolation
                ON {table_name}
                USING (organisation_id = NULLIF(current_setting('app.organisation_id', true), '')::uuid)
                WITH CHECK (organisation_id = NULLIF(current_setting('app.organisation_id', true), '')::uuid)"""
            )
    elif dialect == "sqlite":
        for table_name, operations in (
            ("commercial_plan_versions", ("INSERT", "UPDATE", "DELETE")),
            ("commercial_state_events", ("UPDATE", "DELETE")),
        ):
            for operation in operations:
                op.execute(
                    f"""CREATE TRIGGER {table_name}_immutable_{operation.lower()}
                    BEFORE {operation} ON {table_name}
                    BEGIN SELECT RAISE(ABORT, 'commercial catalogue and history are immutable'); END"""
                )


def _drop_guards() -> None:
    dialect = op.get_bind().dialect.name
    if dialect == "postgresql":
        for table_name in ("commercial_plan_versions", "commercial_state_events"):
            op.execute(f"DROP TRIGGER IF EXISTS {table_name}_immutable_update ON {table_name}")
        op.execute("DROP FUNCTION IF EXISTS public.revenueos_reject_commercial_history_mutation()")
    elif dialect == "sqlite":
        for table_name, operations in (
            ("commercial_plan_versions", ("insert", "update", "delete")),
            ("commercial_state_events", ("update", "delete")),
        ):
            for operation in operations:
                op.execute(f"DROP TRIGGER IF EXISTS {table_name}_immutable_{operation}")


def _seed_catalogue() -> None:
    table = sa.table(
        "commercial_plan_versions",
        sa.column("id", sa.Uuid(as_uuid=True)),
        sa.column("code", sa.String()),
        sa.column("version", sa.Integer()),
        sa.column("display_name", sa.String()),
        sa.column("monthly_price_amount", sa.Numeric()),
        sa.column("annual_price_amount", sa.Numeric()),
        sa.column("currency", sa.String()),
        sa.column("included_user_limit", sa.Integer()),
        sa.column("modules_json", sa.JSON()),
        sa.column("effective_from", sa.DateTime(timezone=True)),
        sa.column("effective_to", sa.DateTime(timezone=True)),
        sa.column("status", sa.String()),
    )
    effective_from = datetime(2026, 9, 4, tzinfo=UTC)
    op.bulk_insert(
        table,
        [
            {
                "id": PLAN_IDS["core"],
                "code": "core",
                "version": 1,
                "display_name": "Core",
                "monthly_price_amount": Decimal("200.00"),
                "annual_price_amount": Decimal("2000.00"),
                "currency": "AUD",
                "included_user_limit": 5,
                "modules_json": PLAN_MODULES["core"],
                "effective_from": effective_from,
                "effective_to": None,
                "status": "active",
            },
            {
                "id": PLAN_IDS["growth"],
                "code": "growth",
                "version": 1,
                "display_name": "Growth",
                "monthly_price_amount": Decimal("350.00"),
                "annual_price_amount": Decimal("3500.00"),
                "currency": "AUD",
                "included_user_limit": 10,
                "modules_json": PLAN_MODULES["growth"],
                "effective_from": effective_from,
                "effective_to": None,
                "status": "active",
            },
            {
                "id": PLAN_IDS["complete"],
                "code": "complete",
                "version": 1,
                "display_name": "Complete",
                "monthly_price_amount": Decimal("500.00"),
                "annual_price_amount": Decimal("5000.00"),
                "currency": "AUD",
                "included_user_limit": 15,
                "modules_json": PLAN_MODULES["complete"],
                "effective_from": effective_from,
                "effective_to": None,
                "status": "active",
            },
            {
                "id": PLAN_IDS["enterprise"],
                "code": "enterprise",
                "version": 1,
                "display_name": "Enterprise",
                "monthly_price_amount": None,
                "annual_price_amount": None,
                "currency": "AUD",
                "included_user_limit": None,
                "modules_json": PLAN_MODULES["enterprise"],
                "effective_from": effective_from,
                "effective_to": None,
                "status": "active",
            },
        ],
    )


def _backfill_existing_organisations() -> None:
    bind = op.get_bind()
    now = datetime.now(UTC)
    organisations = bind.execute(sa.text("SELECT id FROM organisations ORDER BY id")).mappings()
    for organisation in organisations:
        organisation_id = organisation["id"]
        legacy_enabled = {
            row["module_key"]
            for row in bind.execute(
                sa.text(
                    "SELECT module_key FROM organisation_module_entitlements "
                    "WHERE organisation_id = :organisation_id AND enabled = true"
                ),
                {"organisation_id": organisation_id},
            ).mappings()
        }
        external_crm = bool(
            bind.execute(
                sa.text(
                    "SELECT EXISTS (SELECT 1 FROM organisation_crm_settings "
                    "WHERE organisation_id = :organisation_id AND mode = 'external') "
                    "OR EXISTS (SELECT 1 FROM integration_connections "
                    "WHERE organisation_id = :organisation_id AND connector_key = 'hubspot' "
                    "AND connection_status IN ('active', 'reauthorisation_required'))"
                ),
                {"organisation_id": organisation_id},
            ).scalar_one()
        )
        enabled = legacy_enabled - {"crm"}
        if external_crm:
            enabled.add("crm")
        if {"prospect", "engage", "create", "crm"}.issubset(enabled):
            plan_code = "complete"
        elif {"prospect", "engage"}.issubset(enabled):
            plan_code = "growth"
        else:
            plan_code = "core"
        plan_modules = set(PLAN_MODULES[plan_code])
        add_ons = sorted(enabled - plan_modules)
        active_count = int(
            bind.execute(
                sa.text(
                    "SELECT count(*) FROM organisation_memberships membership "
                    "JOIN users user_account ON user_account.id = membership.user_id "
                    "WHERE membership.organisation_id = :organisation_id "
                    "AND membership.status = 'active' AND user_account.status = 'active'"
                ),
                {"organisation_id": organisation_id},
            ).scalar_one()
        )
        limit = {"core": 5, "growth": 10, "complete": 15}[plan_code]
        seat_status = "requires_resolution" if active_count > limit else "within_limit"
        plan_id = PLAN_IDS[plan_code].hex if bind.dialect.name == "sqlite" else str(PLAN_IDS[plan_code])
        bind.execute(
            sa.text(
                """INSERT INTO organisation_commercial_states
                (organisation_id, plan_version_id, status, billing_interval,
                 trial_started_at, trial_ends_at, grace_ends_at, trial_used_at,
                 custom_user_limit, add_on_modules_json, seat_limit_status,
                 effective_at, source, actor_reference, reason, lock_version,
                 created_at, updated_at)
                VALUES (:organisation_id, :plan_version_id, 'active', NULL,
                        NULL, NULL, NULL, NULL, NULL, :add_ons,
                        :seat_status, :effective_at, 'migration',
                        'wo-047-migration', 'Preserve pre-WO-047 private-beta access.',
                        1, :effective_at, :effective_at)"""
            ).bindparams(sa.bindparam("add_ons", type_=sa.JSON())),
            {
                "organisation_id": organisation_id,
                "plan_version_id": plan_id,
                "add_ons": add_ons,
                "seat_status": seat_status,
                "effective_at": now,
            },
        )
        for module in ALL_MODULES:
            target_write = module in plan_modules or module in add_ons
            existing = bind.execute(
                sa.text(
                    "SELECT enabled FROM organisation_module_entitlements "
                    "WHERE organisation_id = :organisation_id AND module_key = :module"
                ),
                {"organisation_id": organisation_id, "module": module},
            ).first()
            source = "add_on" if module in add_ons else "commercial_plan"
            if existing is None:
                if not target_write:
                    continue
                bind.execute(
                    sa.text(
                        """INSERT INTO organisation_module_entitlements
                        (organisation_id, module_key, enabled, access_level, source,
                         configured_by_user_id, configured_by_actor, enabled_at,
                         disabled_at, created_at, updated_at)
                        VALUES (:organisation_id, :module, :enabled, :access_level,
                                :source, NULL, 'wo-047-migration', :enabled_at,
                                :disabled_at, :now, :now)"""
                    ),
                    {
                        "organisation_id": organisation_id,
                        "module": module,
                        "enabled": target_write,
                        "access_level": "write" if target_write else "none",
                        "source": source,
                        "enabled_at": now if target_write else None,
                        "disabled_at": None if target_write else now,
                        "now": now,
                    },
                )
            else:
                bind.execute(
                    sa.text(
                        """UPDATE organisation_module_entitlements
                        SET enabled = :enabled, access_level = :access_level,
                            source = :source, configured_by_actor = :configured_by_actor,
                            enabled_at = CASE WHEN :enabled THEN COALESCE(enabled_at, :now) ELSE enabled_at END,
                            disabled_at = CASE WHEN :enabled THEN NULL ELSE :now END,
                            updated_at = :now
                        WHERE organisation_id = :organisation_id AND module_key = :module"""
                    ),
                    {
                        "organisation_id": organisation_id,
                        "module": module,
                        "enabled": target_write,
                        "access_level": "write" if target_write else "none",
                        "source": source,
                        "configured_by_actor": (
                            "wo-047-migration-enabled" if bool(existing[0]) else "wo-047-migration-disabled"
                        ),
                        "now": now,
                    },
                )
        entitled = sorted(plan_modules | set(add_ons))
        bind.execute(
            sa.text(
                """INSERT INTO commercial_state_events
                (id, organisation_id, plan_version_id, event_type,
                 effective_status, billing_interval, entitled_modules_json,
                 readable_modules_json, included_user_limit, active_user_count,
                 seat_limit_status, trial_started_at, trial_ends_at, grace_ends_at,
                 effective_at, source, actor_reference, reason, state_version, created_at)
                VALUES (:id, :organisation_id, :plan_version_id, 'plan_assigned',
                        'active', NULL, :entitled, :readable, :included_user_limit,
                        :active_user_count, :seat_limit_status, NULL, NULL, NULL,
                        :effective_at, 'migration', 'wo-047-migration',
                        'Preserve pre-WO-047 private-beta access.', 1, :effective_at)"""
            ).bindparams(
                sa.bindparam("entitled", type_=sa.JSON()),
                sa.bindparam("readable", type_=sa.JSON()),
            ),
            {
                "id": uuid.uuid4().hex if bind.dialect.name == "sqlite" else str(uuid.uuid4()),
                "organisation_id": organisation_id,
                "plan_version_id": plan_id,
                "entitled": entitled,
                "readable": entitled,
                "included_user_limit": limit,
                "active_user_count": active_count,
                "seat_limit_status": seat_status,
                "effective_at": now,
            },
        )


def upgrade() -> None:
    _repair_selling_profile_history_guard()
    uuid_type = sa.Uuid(as_uuid=True)
    op.create_table(
        "commercial_plan_versions",
        sa.Column("id", uuid_type, nullable=False),
        sa.Column("code", sa.String(length=20), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("display_name", sa.String(length=80), nullable=False),
        sa.Column("monthly_price_amount", sa.Numeric(12, 2), nullable=True),
        sa.Column("annual_price_amount", sa.Numeric(12, 2), nullable=True),
        sa.Column("currency", sa.String(length=3), server_default="AUD", nullable=False),
        sa.Column("included_user_limit", sa.Integer(), nullable=True),
        sa.Column("modules_json", sa.JSON(), nullable=False),
        sa.Column("effective_from", sa.DateTime(timezone=True), nullable=False),
        sa.Column("effective_to", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(length=16), server_default="active", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("code IN ('core', 'growth', 'complete', 'enterprise')", name="ck_plan_versions_code"),
        sa.CheckConstraint("version > 0", name="ck_plan_versions_version"),
        sa.CheckConstraint("currency = 'AUD'", name="ck_plan_versions_currency"),
        sa.CheckConstraint("status IN ('active', 'retired')", name="ck_plan_versions_status"),
        sa.CheckConstraint(
            "(code = 'enterprise' AND monthly_price_amount IS NULL AND annual_price_amount IS NULL "
            "AND included_user_limit IS NULL) OR "
            "(code <> 'enterprise' AND monthly_price_amount IS NOT NULL AND annual_price_amount IS NOT NULL "
            "AND included_user_limit IS NOT NULL)",
            name="ck_plan_versions_commercial_values",
        ),
        sa.CheckConstraint(
            "monthly_price_amount IS NULL OR monthly_price_amount >= 0", name="ck_plan_versions_monthly_price"
        ),
        sa.CheckConstraint(
            "annual_price_amount IS NULL OR annual_price_amount >= 0", name="ck_plan_versions_annual_price"
        ),
        sa.CheckConstraint(
            "included_user_limit IS NULL OR included_user_limit > 0", name="ck_plan_versions_user_limit"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code", "version", name="uq_plan_versions_code_version"),
    )
    _seed_catalogue()

    with op.batch_alter_table("organisation_module_entitlements") as batch:
        batch.drop_constraint("ck_module_entitlements_key", type_="check")
        batch.drop_constraint("ck_module_entitlements_source", type_="check")
        batch.add_column(sa.Column("access_level", sa.String(length=12), server_default="none", nullable=False))
        batch.add_column(sa.Column("configured_by_actor", sa.String(length=200), nullable=True))
        batch.alter_column("configured_by_user_id", existing_type=uuid_type, nullable=True)
        batch.create_check_constraint(
            "ck_module_entitlements_key",
            "module_key IN ('core', 'prospect', 'engage', 'create', 'crm')",
        )
        batch.create_check_constraint(
            "ck_module_entitlements_source",
            "source IN ('manual_private_beta', 'commercial_plan', 'trial', 'add_on')",
        )
    op.execute(
        "UPDATE organisation_module_entitlements SET access_level = CASE WHEN enabled THEN 'write' ELSE 'none' END"
    )
    with op.batch_alter_table("organisation_module_entitlements") as batch:
        batch.create_check_constraint(
            "ck_module_entitlements_access_level", "access_level IN ('none', 'read', 'write')"
        )
        batch.create_check_constraint(
            "ck_module_entitlements_enabled_access",
            "(enabled AND access_level = 'write') OR (NOT enabled AND access_level IN ('none', 'read'))",
        )

    op.create_table(
        "organisation_commercial_states",
        sa.Column("organisation_id", uuid_type, nullable=False),
        sa.Column("plan_version_id", uuid_type, nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("billing_interval", sa.String(length=12), nullable=True),
        sa.Column("trial_started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("trial_ends_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("grace_ends_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("trial_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("custom_user_limit", sa.Integer(), nullable=True),
        sa.Column("add_on_modules_json", sa.JSON(), server_default="[]", nullable=False),
        sa.Column("seat_limit_status", sa.String(length=24), server_default="within_limit", nullable=False),
        sa.Column("effective_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source", sa.String(length=24), nullable=False),
        sa.Column("actor_reference", sa.String(length=200), nullable=False),
        sa.Column("reason", sa.String(length=500), nullable=False),
        sa.Column("lock_version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "status IN ('trial', 'active', 'inactive', 'suspended')", name="ck_commercial_states_status"
        ),
        sa.CheckConstraint(
            "billing_interval IS NULL OR billing_interval IN ('monthly', 'annual')",
            name="ck_commercial_states_interval",
        ),
        sa.CheckConstraint(
            "seat_limit_status IN ('within_limit', 'requires_resolution')",
            name="ck_commercial_states_seat_limit_status",
        ),
        sa.CheckConstraint("lock_version > 0", name="ck_commercial_states_lock_version"),
        sa.CheckConstraint(
            "custom_user_limit IS NULL OR custom_user_limit > 0", name="ck_commercial_states_custom_user_limit"
        ),
        sa.CheckConstraint(
            "(status <> 'trial' AND trial_started_at IS NULL AND trial_ends_at IS NULL "
            "AND grace_ends_at IS NULL AND trial_used_at IS NULL) OR "
            "(trial_started_at IS NOT NULL AND trial_ends_at > trial_started_at "
            "AND grace_ends_at > trial_ends_at AND trial_used_at = trial_started_at)",
            name="ck_commercial_states_trial_dates",
        ),
        sa.CheckConstraint(
            "status <> 'trial' OR billing_interval IS NULL",
            name="ck_commercial_states_trial_interval",
        ),
        sa.CheckConstraint("source IN ('manual_support', 'migration')", name="ck_commercial_states_source"),
        sa.ForeignKeyConstraint(["organisation_id"], ["organisations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["plan_version_id"], ["commercial_plan_versions.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("organisation_id"),
    )
    op.create_table(
        "commercial_state_events",
        sa.Column("id", uuid_type, nullable=False),
        sa.Column("organisation_id", uuid_type, nullable=False),
        sa.Column("plan_version_id", uuid_type, nullable=False),
        sa.Column("event_type", sa.String(length=24), nullable=False),
        sa.Column("effective_status", sa.String(length=20), nullable=False),
        sa.Column("billing_interval", sa.String(length=12), nullable=True),
        sa.Column("entitled_modules_json", sa.JSON(), nullable=False),
        sa.Column("readable_modules_json", sa.JSON(), nullable=False),
        sa.Column("included_user_limit", sa.Integer(), nullable=True),
        sa.Column("active_user_count", sa.Integer(), nullable=False),
        sa.Column("seat_limit_status", sa.String(length=24), nullable=False),
        sa.Column("trial_started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("trial_ends_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("grace_ends_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("effective_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source", sa.String(length=24), nullable=False),
        sa.Column("actor_reference", sa.String(length=200), nullable=False),
        sa.Column("reason", sa.String(length=500), nullable=False),
        sa.Column("state_version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "event_type IN ('trial_started', 'plan_assigned', 'plan_changed', 'state_changed')",
            name="ck_commercial_events_type",
        ),
        sa.CheckConstraint(
            "effective_status IN ('trial_active', 'active', 'grace', 'expired', 'inactive', 'suspended')",
            name="ck_commercial_events_status",
        ),
        sa.CheckConstraint("state_version > 0", name="ck_commercial_events_state_version"),
        sa.ForeignKeyConstraint(["organisation_id"], ["organisations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["plan_version_id"], ["commercial_plan_versions.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organisation_id",
            "state_version",
            name="uq_commercial_events_org_state_version",
        ),
    )
    op.create_index(
        "ix_commercial_events_org_effective",
        "commercial_state_events",
        ["organisation_id", "effective_at", "id"],
    )
    _backfill_existing_organisations()
    _create_guards()


def downgrade() -> None:
    _drop_guards()
    op.drop_index("ix_commercial_events_org_effective", table_name="commercial_state_events")
    op.drop_table("commercial_state_events")
    op.drop_table("organisation_commercial_states")
    op.execute("DELETE FROM organisation_module_entitlements WHERE module_key = 'core'")
    op.execute(
        """UPDATE organisation_module_entitlements
        SET enabled = CASE
                WHEN configured_by_actor = 'wo-047-migration-enabled' THEN true
                WHEN configured_by_actor = 'wo-047-migration-disabled' THEN false
                ELSE enabled
            END,
            access_level = CASE
                WHEN configured_by_actor = 'wo-047-migration-enabled' THEN 'write'
                WHEN configured_by_actor = 'wo-047-migration-disabled' THEN 'none'
                ELSE access_level
            END,
            source = 'manual_private_beta',
            configured_by_user_id = COALESCE(
                configured_by_user_id,
                (SELECT user_id FROM organisation_memberships
                 WHERE organisation_memberships.organisation_id = organisation_module_entitlements.organisation_id
                   AND role = 'admin' AND status = 'active'
                 ORDER BY created_at, user_id LIMIT 1)
            )"""
    )
    with op.batch_alter_table("organisation_module_entitlements") as batch:
        batch.drop_constraint("ck_module_entitlements_enabled_access", type_="check")
        batch.drop_constraint("ck_module_entitlements_access_level", type_="check")
        batch.drop_constraint("ck_module_entitlements_source", type_="check")
        batch.drop_constraint("ck_module_entitlements_key", type_="check")
        batch.alter_column("configured_by_user_id", existing_type=sa.Uuid(as_uuid=True), nullable=False)
        batch.drop_column("configured_by_actor")
        batch.drop_column("access_level")
        batch.create_check_constraint(
            "ck_module_entitlements_key", "module_key IN ('prospect', 'engage', 'create', 'crm')"
        )
        batch.create_check_constraint("ck_module_entitlements_source", "source = 'manual_private_beta'")
    op.drop_table("commercial_plan_versions")
