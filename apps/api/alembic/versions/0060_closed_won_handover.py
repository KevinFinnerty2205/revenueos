"""Add reviewed, source-aware Closed-Won Handovers.

Revision ID: 0060_closed_won_handover
Revises: 0059_opportunity_deal_room

Draft and review revisions remain editable under optimistic locks. Approved
content and its pinned source pack are immutable; only supersession or safe
retirement may change the lifecycle state. PostgreSQL RLS is forced for every
tenant table and canonical Opportunity status remains the approval authority.
The Opportunity correction trigger is a locked-search-path SECURITY DEFINER
function so restricted runtime roles do not need cross-domain handover grants;
its only scope is the trusted tenant and Opportunity keys from the trigger row.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0060_closed_won_handover"
down_revision: str | None = "0059_opportunity_deal_room"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

HANDOVER_TABLES = (
    "closed_won_handovers",
    "closed_won_handover_revisions",
    "closed_won_handover_sources",
    "closed_won_handover_audit_events",
)


def _membership_fk(column: str, name: str) -> sa.ForeignKeyConstraint:
    return sa.ForeignKeyConstraint(
        ["organisation_id", column],
        ["organisation_memberships.organisation_id", "organisation_memberships.user_id"],
        name=name,
        ondelete="RESTRICT",
    )


def _enable_tenant_rls() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return
    for table_name in HANDOVER_TABLES:
        op.execute(f"ALTER TABLE {table_name} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table_name} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"""CREATE POLICY {table_name}_tenant_isolation ON {table_name}
            USING (organisation_id = NULLIF(current_setting('app.organisation_id', true), '')::uuid)
            WITH CHECK (organisation_id = NULLIF(current_setting('app.organisation_id', true), '')::uuid)"""
        )


def _create_approval_guard() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return
    op.execute(
        """
        CREATE FUNCTION public.revenueos_closed_won_handover_approval_guard()
        RETURNS trigger
        LANGUAGE plpgsql
        SET search_path = pg_catalog, public
        AS $$
        BEGIN
            IF TG_OP = 'INSERT' AND NEW.status <> 'draft' THEN
                RAISE EXCEPTION 'Closed-Won Handover revisions must begin as drafts';
            END IF;
            IF TG_OP = 'UPDATE' THEN
                IF OLD.status = 'draft' AND NEW.status NOT IN ('draft', 'in_review') THEN
                    RAISE EXCEPTION 'Closed-Won Handover lifecycle transition is invalid';
                END IF;
                IF OLD.status = 'in_review' AND NEW.status NOT IN ('draft', 'in_review', 'approved') THEN
                    RAISE EXCEPTION 'Closed-Won Handover lifecycle transition is invalid';
                END IF;
            END IF;
            IF NEW.status = 'approved' AND (TG_OP = 'INSERT' OR OLD.status IS DISTINCT FROM NEW.status) THEN
                PERFORM 1
                  FROM public.closed_won_handovers AS handovers
                  JOIN public.opportunities AS opportunities
                    ON opportunities.organisation_id = handovers.organisation_id
                   AND opportunities.id = handovers.opportunity_id
                 WHERE handovers.organisation_id = NEW.organisation_id
                   AND handovers.id = NEW.handover_id
                   AND handovers.opportunity_id = NEW.opportunity_id
                   AND opportunities.status = 'won'
                   AND opportunities.archived_at IS NULL;
                IF NOT FOUND THEN
                    RAISE EXCEPTION 'Closed-Won Handover approval requires a canonical Closed-Won Opportunity';
                END IF;
            END IF;
            RETURN NEW;
        END;
        $$
        """
    )
    op.execute(
        """CREATE TRIGGER closed_won_handover_approval_guard
        BEFORE INSERT OR UPDATE OF status ON closed_won_handover_revisions
        FOR EACH ROW EXECUTE FUNCTION public.revenueos_closed_won_handover_approval_guard()"""
    )
    op.execute("REVOKE ALL ON FUNCTION public.revenueos_closed_won_handover_approval_guard() FROM PUBLIC")


def _create_immutability_guards() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return
    op.execute(
        """
        CREATE FUNCTION public.revenueos_closed_won_handover_revision_immutable()
        RETURNS trigger
        LANGUAGE plpgsql
        SET search_path = pg_catalog, public
        AS $$
        BEGIN
            IF TG_OP = 'DELETE' THEN
                IF current_setting('app.beta_maintenance', true) = 'approved' THEN
                    RETURN OLD;
                END IF;
                IF OLD.status IN ('approved', 'superseded', 'retired') THEN
                    RAISE EXCEPTION 'Approved Closed-Won Handover revisions are immutable';
                END IF;
                RETURN OLD;
            END IF;

            IF OLD.status IN ('approved', 'superseded', 'retired') THEN
                IF OLD.organisation_id IS DISTINCT FROM NEW.organisation_id
                   OR OLD.handover_id IS DISTINCT FROM NEW.handover_id
                   OR OLD.opportunity_id IS DISTINCT FROM NEW.opportunity_id
                   OR OLD.revision IS DISTINCT FROM NEW.revision
                   OR OLD.content_schema_version IS DISTINCT FROM NEW.content_schema_version
                   OR OLD.content_json::jsonb IS DISTINCT FROM NEW.content_json::jsonb
                   OR OLD.source_pack_fingerprint IS DISTINCT FROM NEW.source_pack_fingerprint
                   OR OLD.created_by_user_id IS DISTINCT FROM NEW.created_by_user_id
                   OR OLD.submitted_by_user_id IS DISTINCT FROM NEW.submitted_by_user_id
                   OR OLD.submitted_at IS DISTINCT FROM NEW.submitted_at
                   OR OLD.approved_by_user_id IS DISTINCT FROM NEW.approved_by_user_id
                   OR OLD.approved_at IS DISTINCT FROM NEW.approved_at
                   OR OLD.created_at IS DISTINCT FROM NEW.created_at THEN
                    RAISE EXCEPTION 'Approved Closed-Won Handover revision content is immutable';
                END IF;
                IF OLD.status = 'approved' AND NEW.status NOT IN ('approved', 'superseded', 'retired') THEN
                    RAISE EXCEPTION 'Approved Closed-Won Handover lifecycle transition is invalid';
                END IF;
                IF OLD.status = 'approved'
                   AND NEW.status = 'approved'
                   AND to_jsonb(OLD) IS DISTINCT FROM to_jsonb(NEW) THEN
                    RAISE EXCEPTION 'Approved Closed-Won Handover revision is immutable';
                END IF;
                IF OLD.status IN ('superseded', 'retired')
                   AND to_jsonb(OLD) IS DISTINCT FROM to_jsonb(NEW) THEN
                    RAISE EXCEPTION 'Final Closed-Won Handover lifecycle state is immutable';
                END IF;
            END IF;
            RETURN NEW;
        END;
        $$
        """
    )
    op.execute(
        """CREATE TRIGGER closed_won_handover_revisions_immutable
        BEFORE UPDATE OR DELETE ON closed_won_handover_revisions
        FOR EACH ROW EXECUTE FUNCTION public.revenueos_closed_won_handover_revision_immutable()"""
    )
    op.execute("REVOKE ALL ON FUNCTION public.revenueos_closed_won_handover_revision_immutable() FROM PUBLIC")

    op.execute(
        """
        CREATE FUNCTION public.revenueos_closed_won_handover_source_immutable()
        RETURNS trigger
        LANGUAGE plpgsql
        SET search_path = pg_catalog, public
        AS $$
        DECLARE
            old_revision_status text;
            new_revision_status text;
        BEGIN
            IF TG_OP = 'DELETE' AND current_setting('app.beta_maintenance', true) = 'approved' THEN
                RETURN OLD;
            END IF;
            IF TG_OP = 'INSERT' THEN
                SELECT status INTO new_revision_status
                  FROM public.closed_won_handover_revisions
                 WHERE organisation_id = NEW.organisation_id
                   AND id = NEW.revision_id;
            ELSE
                SELECT status INTO old_revision_status
                  FROM public.closed_won_handover_revisions
                 WHERE organisation_id = OLD.organisation_id
                   AND id = OLD.revision_id;
                IF TG_OP = 'UPDATE' THEN
                    SELECT status INTO new_revision_status
                      FROM public.closed_won_handover_revisions
                     WHERE organisation_id = NEW.organisation_id
                       AND id = NEW.revision_id;
                END IF;
            END IF;
            IF old_revision_status IN ('approved', 'superseded', 'retired')
               OR new_revision_status IN ('approved', 'superseded', 'retired') THEN
                RAISE EXCEPTION 'Approved Closed-Won Handover sources are immutable';
            END IF;
            IF TG_OP = 'DELETE' THEN
                RETURN OLD;
            END IF;
            RETURN NEW;
        END;
        $$
        """
    )
    op.execute(
        """CREATE TRIGGER closed_won_handover_sources_immutable
        BEFORE INSERT OR UPDATE OR DELETE ON closed_won_handover_sources
        FOR EACH ROW EXECUTE FUNCTION public.revenueos_closed_won_handover_source_immutable()"""
    )
    op.execute("REVOKE ALL ON FUNCTION public.revenueos_closed_won_handover_source_immutable() FROM PUBLIC")


def _create_opportunity_correction_guard() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return
    op.execute(
        """
        CREATE FUNCTION public.revenueos_retire_invalid_closed_won_handover()
        RETURNS trigger
        LANGUAGE plpgsql
        SECURITY DEFINER
        SET search_path = pg_catalog, public
        AS $$
        BEGIN
            IF (NEW.status <> 'won' OR NEW.archived_at IS NOT NULL)
               AND (OLD.status IS DISTINCT FROM NEW.status OR OLD.archived_at IS DISTINCT FROM NEW.archived_at) THEN
                WITH retired AS (
                    UPDATE public.closed_won_handover_revisions AS revisions
                       SET status = 'retired',
                           retired_at = CURRENT_TIMESTAMP,
                           retired_by_user_id = NULL,
                           retirement_reason = CASE
                               WHEN NEW.archived_at IS NOT NULL THEN 'opportunity_archived'
                               WHEN NEW.status = 'lost' THEN 'opportunity_corrected_lost'
                               ELSE 'opportunity_reopened'
                           END,
                           lock_version = revisions.lock_version + 1,
                           updated_at = CURRENT_TIMESTAMP
                      FROM public.closed_won_handovers AS handovers
                     WHERE revisions.organisation_id = NEW.organisation_id
                       AND revisions.handover_id = handovers.id
                       AND handovers.organisation_id = NEW.organisation_id
                       AND handovers.opportunity_id = NEW.id
                       AND revisions.status = 'approved'
                    RETURNING revisions.organisation_id, revisions.handover_id, revisions.id,
                              revisions.revision, revisions.retirement_reason
                ), bumped AS (
                    UPDATE public.closed_won_handovers AS handovers
                       SET lock_version = handovers.lock_version + 1,
                           updated_at = CURRENT_TIMESTAMP
                     WHERE handovers.organisation_id = NEW.organisation_id
                       AND handovers.opportunity_id = NEW.id
                       AND EXISTS (
                           SELECT 1
                             FROM retired
                            WHERE retired.organisation_id = handovers.organisation_id
                              AND retired.handover_id = handovers.id
                       )
                    RETURNING handovers.id
                )
                INSERT INTO public.closed_won_handover_audit_events
                    (id, organisation_id, handover_id, revision_id, actor_user_id,
                     action, metadata_json, created_at)
                SELECT md5(random()::text || clock_timestamp()::text || retired.id::text)::uuid,
                       retired.organisation_id, retired.handover_id, retired.id, NULL,
                       'retired',
                       jsonb_build_object('revision', retired.revision, 'reason', retired.retirement_reason)::json,
                       CURRENT_TIMESTAMP
                  FROM retired
                  JOIN bumped ON bumped.id = retired.handover_id;
            END IF;
            RETURN NEW;
        END;
        $$
        """
    )
    op.execute(
        """CREATE TRIGGER opportunities_retire_closed_won_handover
        AFTER UPDATE OF status, archived_at ON opportunities
        FOR EACH ROW EXECUTE FUNCTION public.revenueos_retire_invalid_closed_won_handover()"""
    )
    op.execute("REVOKE ALL ON FUNCTION public.revenueos_retire_invalid_closed_won_handover() FROM PUBLIC")


def upgrade() -> None:
    op.create_table(
        "closed_won_handovers",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organisation_id", sa.Uuid(), nullable=False),
        sa.Column("opportunity_id", sa.Uuid(), nullable=False),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("lock_version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("lock_version > 0", name="ck_closed_won_handovers_lock_version"),
        sa.ForeignKeyConstraint(["organisation_id"], ["organisations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["organisation_id", "opportunity_id"],
            ["opportunities.organisation_id", "opportunities.id"],
            name="fk_closed_won_handovers_opportunity",
            ondelete="CASCADE",
        ),
        _membership_fk("created_by_user_id", "fk_closed_won_handovers_creator"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organisation_id", "id", name="uq_closed_won_handovers_org_id"),
        sa.UniqueConstraint(
            "organisation_id", "id", "opportunity_id", name="uq_closed_won_handovers_org_id_opportunity"
        ),
        sa.UniqueConstraint("organisation_id", "opportunity_id", name="uq_closed_won_handovers_org_opportunity"),
    )
    op.create_index(
        "ix_closed_won_handovers_org_opportunity",
        "closed_won_handovers",
        ["organisation_id", "opportunity_id"],
    )

    op.create_table(
        "closed_won_handover_revisions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organisation_id", sa.Uuid(), nullable=False),
        sa.Column("handover_id", sa.Uuid(), nullable=False),
        sa.Column("opportunity_id", sa.Uuid(), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=20), server_default="draft", nullable=False),
        sa.Column("content_schema_version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("content_json", sa.JSON(), nullable=False),
        sa.Column("source_pack_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("lock_version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("submitted_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("approved_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("superseded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("retired_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("retired_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("retirement_reason", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("revision > 0", name="ck_closed_won_handover_revisions_number"),
        sa.CheckConstraint(
            "status IN ('draft', 'in_review', 'approved', 'superseded', 'retired')",
            name="ck_closed_won_handover_revisions_status",
        ),
        sa.CheckConstraint("content_schema_version = 1", name="ck_closed_won_handover_revisions_schema"),
        sa.CheckConstraint("lock_version > 0", name="ck_closed_won_handover_revisions_lock_version"),
        sa.CheckConstraint(
            "length(source_pack_fingerprint) = 64 AND source_pack_fingerprint = lower(source_pack_fingerprint)",
            name="ck_closed_won_handover_revisions_source_fingerprint",
        ),
        sa.CheckConstraint(
            "(status = 'draft' AND submitted_by_user_id IS NULL AND submitted_at IS NULL "
            "AND approved_by_user_id IS NULL AND approved_at IS NULL) OR "
            "(status = 'in_review' AND submitted_by_user_id IS NOT NULL AND submitted_at IS NOT NULL "
            "AND approved_by_user_id IS NULL AND approved_at IS NULL) OR "
            "(status IN ('approved', 'superseded', 'retired') AND submitted_by_user_id IS NOT NULL "
            "AND submitted_at IS NOT NULL AND approved_by_user_id IS NOT NULL AND approved_at IS NOT NULL)",
            name="ck_closed_won_handover_revisions_lifecycle",
        ),
        sa.CheckConstraint(
            "(status = 'superseded' AND superseded_at IS NOT NULL) OR "
            "(status <> 'superseded' AND superseded_at IS NULL)",
            name="ck_closed_won_handover_revisions_superseded",
        ),
        sa.CheckConstraint(
            "(status = 'retired' AND retired_at IS NOT NULL AND ("
            "(retirement_reason = 'authorised_user_retired' AND retired_by_user_id IS NOT NULL) OR "
            "retirement_reason IN ('opportunity_reopened', 'opportunity_corrected_lost'))) OR "
            "(status <> 'retired' AND retired_by_user_id IS NULL AND retired_at IS NULL AND retirement_reason IS NULL)",
            name="ck_closed_won_handover_revisions_retired",
        ),
        sa.ForeignKeyConstraint(["organisation_id"], ["organisations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["organisation_id", "handover_id", "opportunity_id"],
            [
                "closed_won_handovers.organisation_id",
                "closed_won_handovers.id",
                "closed_won_handovers.opportunity_id",
            ],
            name="fk_closed_won_handover_revisions_handover",
            ondelete="CASCADE",
        ),
        _membership_fk("created_by_user_id", "fk_closed_won_handover_revisions_creator"),
        _membership_fk("submitted_by_user_id", "fk_closed_won_handover_revisions_submitter"),
        _membership_fk("approved_by_user_id", "fk_closed_won_handover_revisions_approver"),
        _membership_fk("retired_by_user_id", "fk_closed_won_handover_revisions_retirer"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organisation_id", "id", name="uq_closed_won_handover_revisions_org_id"),
        sa.UniqueConstraint(
            "organisation_id", "id", "opportunity_id", name="uq_closed_won_handover_revisions_org_id_opportunity"
        ),
        sa.UniqueConstraint(
            "organisation_id", "handover_id", "revision", name="uq_closed_won_handover_revisions_number"
        ),
    )
    op.create_index(
        "ix_closed_won_handover_revisions_org_handover",
        "closed_won_handover_revisions",
        ["organisation_id", "handover_id", "revision"],
    )
    op.create_index(
        "uq_closed_won_handover_revisions_editable",
        "closed_won_handover_revisions",
        ["organisation_id", "handover_id"],
        unique=True,
        postgresql_where=sa.text("status IN ('draft', 'in_review')"),
        sqlite_where=sa.text("status IN ('draft', 'in_review')"),
    )
    op.create_index(
        "uq_closed_won_handover_revisions_current_approved",
        "closed_won_handover_revisions",
        ["organisation_id", "handover_id"],
        unique=True,
        postgresql_where=sa.text("status = 'approved'"),
        sqlite_where=sa.text("status = 'approved'"),
    )

    op.create_table(
        "closed_won_handover_sources",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organisation_id", sa.Uuid(), nullable=False),
        sa.Column("revision_id", sa.Uuid(), nullable=False),
        sa.Column("opportunity_id", sa.Uuid(), nullable=False),
        sa.Column("source_type", sa.String(length=24), nullable=False),
        sa.Column("source_id", sa.Uuid(), nullable=False),
        sa.Column("source_version_id", sa.Uuid(), nullable=True),
        sa.Column("source_version", sa.Integer(), nullable=True),
        sa.Column("authority_type", sa.String(length=32), nullable=False),
        sa.Column("label", sa.String(length=240), nullable=False),
        sa.Column("snapshot_json", sa.JSON(), nullable=False),
        sa.Column("source_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("pinned_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "source_type IN ('opportunity', 'evidence', 'business_case', 'deal_room', "
            "'contact', 'interaction', 'action', 'task')",
            name="ck_closed_won_handover_sources_type",
        ),
        sa.CheckConstraint(
            "authority_type IN ('customer_evidence', 'seller_confirmed', 'commercial_record', "
            "'customer_facing_approved', 'system_derived', 'inference', 'unknown')",
            name="ck_closed_won_handover_sources_authority",
        ),
        sa.CheckConstraint(
            "length(source_fingerprint) = 64 AND source_fingerprint = lower(source_fingerprint)",
            name="ck_closed_won_handover_sources_fingerprint",
        ),
        sa.CheckConstraint(
            "(source_type IN ('evidence', 'business_case', 'deal_room', 'action') "
            "AND source_version_id IS NOT NULL AND source_version IS NOT NULL AND source_version > 0) OR "
            "(source_type IN ('opportunity', 'contact', 'interaction', 'task') "
            "AND source_version_id IS NULL AND source_version IS NULL)",
            name="ck_closed_won_handover_sources_version",
        ),
        sa.CheckConstraint("length(trim(label)) BETWEEN 1 AND 240", name="ck_closed_won_handover_sources_label"),
        sa.ForeignKeyConstraint(["organisation_id"], ["organisations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["organisation_id", "revision_id", "opportunity_id"],
            [
                "closed_won_handover_revisions.organisation_id",
                "closed_won_handover_revisions.id",
                "closed_won_handover_revisions.opportunity_id",
            ],
            name="fk_closed_won_handover_sources_revision",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organisation_id", "id", name="uq_closed_won_handover_sources_org_id"),
        sa.UniqueConstraint(
            "organisation_id",
            "revision_id",
            "source_type",
            "source_id",
            "source_version_id",
            name="uq_closed_won_handover_sources_reference",
        ),
    )
    op.create_index(
        "ix_closed_won_handover_sources_org_revision",
        "closed_won_handover_sources",
        ["organisation_id", "revision_id", "source_type"],
    )
    op.create_index(
        "uq_closed_won_handover_sources_unversioned_reference",
        "closed_won_handover_sources",
        ["organisation_id", "revision_id", "source_type", "source_id"],
        unique=True,
        postgresql_where=sa.text("source_version_id IS NULL"),
        sqlite_where=sa.text("source_version_id IS NULL"),
    )

    op.create_table(
        "closed_won_handover_audit_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organisation_id", sa.Uuid(), nullable=False),
        sa.Column("handover_id", sa.Uuid(), nullable=False),
        sa.Column("revision_id", sa.Uuid(), nullable=True),
        sa.Column("actor_user_id", sa.Uuid(), nullable=True),
        sa.Column("action", sa.String(length=40), nullable=False),
        sa.Column("metadata_json", sa.JSON(), server_default="{}", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "action IN ('draft_created', 'draft_updated', 'submitted_for_review', 'claim_confirmed', "
            "'approved', 'superseded', 'retired')",
            name="ck_closed_won_handover_audit_action",
        ),
        sa.ForeignKeyConstraint(["organisation_id"], ["organisations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["organisation_id", "handover_id"],
            ["closed_won_handovers.organisation_id", "closed_won_handovers.id"],
            name="fk_closed_won_handover_audit_handover",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["organisation_id", "revision_id"],
            ["closed_won_handover_revisions.organisation_id", "closed_won_handover_revisions.id"],
            name="fk_closed_won_handover_audit_revision",
            ondelete="CASCADE",
        ),
        _membership_fk("actor_user_id", "fk_closed_won_handover_audit_actor"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_closed_won_handover_audit_org_handover",
        "closed_won_handover_audit_events",
        ["organisation_id", "handover_id", "created_at"],
    )

    _enable_tenant_rls()
    _create_approval_guard()
    _create_immutability_guards()
    _create_opportunity_correction_guard()


def downgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        op.execute("DROP TRIGGER IF EXISTS opportunities_retire_closed_won_handover ON opportunities")
        op.execute("DROP FUNCTION IF EXISTS public.revenueos_retire_invalid_closed_won_handover()")
        op.execute("DROP TRIGGER IF EXISTS closed_won_handover_sources_immutable ON closed_won_handover_sources")
        op.execute("DROP FUNCTION IF EXISTS public.revenueos_closed_won_handover_source_immutable()")
        op.execute("DROP TRIGGER IF EXISTS closed_won_handover_revisions_immutable ON closed_won_handover_revisions")
        op.execute("DROP FUNCTION IF EXISTS public.revenueos_closed_won_handover_revision_immutable()")
        op.execute("DROP TRIGGER IF EXISTS closed_won_handover_approval_guard ON closed_won_handover_revisions")
        op.execute("DROP FUNCTION IF EXISTS public.revenueos_closed_won_handover_approval_guard()")
    op.drop_index("ix_closed_won_handover_audit_org_handover", table_name="closed_won_handover_audit_events")
    op.drop_table("closed_won_handover_audit_events")
    op.drop_index(
        "uq_closed_won_handover_sources_unversioned_reference",
        table_name="closed_won_handover_sources",
    )
    op.drop_index("ix_closed_won_handover_sources_org_revision", table_name="closed_won_handover_sources")
    op.drop_table("closed_won_handover_sources")
    op.drop_index("uq_closed_won_handover_revisions_current_approved", table_name="closed_won_handover_revisions")
    op.drop_index("uq_closed_won_handover_revisions_editable", table_name="closed_won_handover_revisions")
    op.drop_index("ix_closed_won_handover_revisions_org_handover", table_name="closed_won_handover_revisions")
    op.drop_table("closed_won_handover_revisions")
    op.drop_index("ix_closed_won_handovers_org_opportunity", table_name="closed_won_handovers")
    op.drop_table("closed_won_handovers")
