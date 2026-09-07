"""Add the opportunity-scoped Deal Room publication boundary.

Revision ID: 0059_opportunity_deal_room
Revises: 0058_production_crm_connectors

Draft configuration remains tenant-private. Publication creates an immutable,
allow-listed JSON snapshot. Public resolution is available only through two
bounded SECURITY DEFINER functions keyed by a SHA-256 share-token digest; the
runtime role never receives general unauthenticated tenant authority.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0059_opportunity_deal_room"
down_revision: str | None = "0058_production_crm_connectors"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

DEAL_ROOM_TABLES = (
    "deal_rooms",
    "deal_room_revisions",
    "deal_room_access_links",
    "deal_room_audit_events",
)


def _membership_fk(column: str, name: str, *, ondelete: str = "RESTRICT") -> sa.ForeignKeyConstraint:
    return sa.ForeignKeyConstraint(
        ["organisation_id", column],
        ["organisation_memberships.organisation_id", "organisation_memberships.user_id"],
        name=name,
        ondelete=ondelete,
    )


def _enable_tenant_rls() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return
    for table_name in DEAL_ROOM_TABLES:
        op.execute(f"ALTER TABLE {table_name} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table_name} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"""CREATE POLICY {table_name}_tenant_isolation ON {table_name}
            USING (organisation_id = NULLIF(current_setting('app.organisation_id', true), '')::uuid)
            WITH CHECK (organisation_id = NULLIF(current_setting('app.organisation_id', true), '')::uuid)"""
        )


def _create_public_projection_functions() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return
    op.execute(
        """
        CREATE FUNCTION public.revenueos_public_deal_room(
            requested_token_hash text
        )
        RETURNS TABLE (snapshot_json json, revision integer, published_at timestamptz, expires_at timestamptz)
        LANGUAGE sql
        STABLE
        SECURITY DEFINER
        SET search_path = pg_catalog, public
        AS $$
            SELECT revisions.snapshot_json,
                   revisions.revision,
                   revisions.published_at,
                   links.expires_at
            FROM public.deal_room_access_links AS links
            JOIN public.deal_rooms AS rooms
              ON rooms.organisation_id = links.organisation_id
             AND rooms.id = links.room_id
            JOIN public.deal_room_revisions AS revisions
              ON revisions.organisation_id = rooms.organisation_id
             AND revisions.id = rooms.published_revision_id
            JOIN public.opportunities AS opportunities
              ON opportunities.organisation_id = rooms.organisation_id
             AND opportunities.id = rooms.opportunity_id
            JOIN public.organisations AS organisations
              ON organisations.id = rooms.organisation_id
            WHERE requested_token_hash ~ '^[0-9a-f]{64}$'
              AND links.token_hash = requested_token_hash
              AND links.revoked_at IS NULL
              AND (links.expires_at IS NULL OR links.expires_at > CURRENT_TIMESTAMP)
              AND rooms.status = 'published'
              AND opportunities.status = 'open'
              AND opportunities.archived_at IS NULL
            LIMIT 1
        $$
        """
    )
    op.execute(
        """
        CREATE FUNCTION public.revenueos_public_deal_room_resource(
            requested_token_hash text,
            requested_resource_id text
        )
        RETURNS TABLE (
            storage_key text,
            checksum_sha256 text,
            byte_size bigint,
            resource_title text
        )
        LANGUAGE sql
        STABLE
        SECURITY DEFINER
        SET search_path = pg_catalog, public
        AS $$
            SELECT versions.pptx_storage_key,
                   versions.checksum_sha256,
                   versions.byte_size,
                   resource.value ->> 'title'
            FROM public.deal_room_access_links AS links
            JOIN public.deal_rooms AS rooms
              ON rooms.organisation_id = links.organisation_id
             AND rooms.id = links.room_id
            JOIN public.deal_room_revisions AS revisions
              ON revisions.organisation_id = rooms.organisation_id
             AND revisions.id = rooms.published_revision_id
            JOIN public.opportunities AS opportunities
              ON opportunities.organisation_id = rooms.organisation_id
             AND opportunities.id = rooms.opportunity_id
            CROSS JOIN LATERAL jsonb_array_elements(
                COALESCE(revisions.snapshot_json::jsonb -> 'resources', '[]'::jsonb)
            ) AS resource(value)
            JOIN public.create_presentation_versions AS versions
              ON versions.organisation_id = rooms.organisation_id
             AND versions.id::text = resource.value ->> 'presentationVersionId'
            JOIN public.create_presentations AS presentations
              ON presentations.organisation_id = versions.organisation_id
             AND presentations.id = versions.presentation_id
            WHERE requested_token_hash ~ '^[0-9a-f]{64}$'
              AND links.token_hash = requested_token_hash
              AND links.revoked_at IS NULL
              AND (links.expires_at IS NULL OR links.expires_at > CURRENT_TIMESTAMP)
              AND rooms.status = 'published'
              AND opportunities.status = 'open'
              AND opportunities.archived_at IS NULL
              AND resource.value ->> 'id' = requested_resource_id
              AND resource.value ->> 'kind' = 'presentation'
              AND versions.state = 'ready'
              AND versions.review_state = 'approved'
              AND versions.storage_status = 'available'
              AND versions.pptx_storage_key IS NOT NULL
              AND versions.checksum_sha256 IS NOT NULL
              AND presentations.opportunity_id = rooms.opportunity_id
              AND presentations.archived_at IS NULL
            LIMIT 1
        $$
        """
    )
    op.execute("GRANT EXECUTE ON FUNCTION public.revenueos_public_deal_room(text) TO PUBLIC")
    op.execute("GRANT EXECUTE ON FUNCTION public.revenueos_public_deal_room_resource(text, text) TO PUBLIC")


def _create_immutable_guard() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return
    op.execute(
        """
        CREATE FUNCTION public.revenueos_deal_room_revision_immutable()
        RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            IF TG_OP = 'DELETE'
               AND current_setting('app.beta_maintenance', true) = 'approved' THEN
                RETURN OLD;
            END IF;
            RAISE EXCEPTION 'Deal Room revisions are immutable';
        END;
        $$
        """
    )
    op.execute(
        """CREATE TRIGGER deal_room_revisions_immutable
        BEFORE UPDATE OR DELETE ON deal_room_revisions
        FOR EACH ROW EXECUTE FUNCTION public.revenueos_deal_room_revision_immutable()"""
    )


def _create_closed_opportunity_guard() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return
    op.execute(
        """
        CREATE FUNCTION public.revenueos_pause_closed_deal_room()
        RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            IF (NEW.status IN ('won', 'lost') OR NEW.archived_at IS NOT NULL)
               AND (OLD.status IS DISTINCT FROM NEW.status OR OLD.archived_at IS DISTINCT FROM NEW.archived_at) THEN
                UPDATE public.deal_rooms
                   SET status = 'paused', paused_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP,
                       lock_version = lock_version + 1
                 WHERE organisation_id = NEW.organisation_id
                   AND opportunity_id = NEW.id
                   AND status = 'published';
            END IF;
            RETURN NEW;
        END;
        $$
        """
    )
    op.execute(
        """CREATE TRIGGER opportunities_pause_deal_room
        AFTER UPDATE OF status, archived_at ON opportunities
        FOR EACH ROW EXECUTE FUNCTION public.revenueos_pause_closed_deal_room()"""
    )


def upgrade() -> None:
    op.create_table(
        "deal_rooms",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organisation_id", sa.Uuid(), nullable=False),
        sa.Column("opportunity_id", sa.Uuid(), nullable=False),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(length=20), server_default="draft", nullable=False),
        sa.Column("draft_version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("draft_content_json", sa.JSON(), server_default="{}", nullable=False),
        sa.Column("published_revision_id", sa.Uuid(), nullable=True),
        sa.Column("lock_version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("last_published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("paused_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("status IN ('draft', 'published', 'paused', 'revoked')", name="ck_deal_rooms_status"),
        sa.CheckConstraint("draft_version > 0", name="ck_deal_rooms_draft_version"),
        sa.CheckConstraint("lock_version > 0", name="ck_deal_rooms_lock_version"),
        sa.CheckConstraint(
            "(status = 'draft' AND published_revision_id IS NULL) OR "
            "(status IN ('published', 'paused', 'revoked') AND published_revision_id IS NOT NULL)",
            name="ck_deal_rooms_publication_state",
        ),
        sa.ForeignKeyConstraint(["organisation_id"], ["organisations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["organisation_id", "opportunity_id"],
            ["opportunities.organisation_id", "opportunities.id"],
            name="fk_deal_rooms_opportunity",
            ondelete="CASCADE",
        ),
        _membership_fk("created_by_user_id", "fk_deal_rooms_creator"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organisation_id", "id", name="uq_deal_rooms_org_id"),
        sa.UniqueConstraint("organisation_id", "opportunity_id", name="uq_deal_rooms_org_opportunity"),
    )
    op.create_index("ix_deal_rooms_org_status", "deal_rooms", ["organisation_id", "status", "updated_at"])

    op.create_table(
        "deal_room_revisions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organisation_id", sa.Uuid(), nullable=False),
        sa.Column("room_id", sa.Uuid(), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("snapshot_schema_version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("snapshot_json", sa.JSON(), nullable=False),
        sa.Column("content_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("published_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("revision > 0", name="ck_deal_room_revisions_number"),
        sa.CheckConstraint("snapshot_schema_version = 1", name="ck_deal_room_revisions_schema"),
        sa.CheckConstraint(
            "length(content_fingerprint) = 64 AND content_fingerprint = lower(content_fingerprint)",
            name="ck_deal_room_revisions_fingerprint",
        ),
        sa.ForeignKeyConstraint(["organisation_id"], ["organisations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["organisation_id", "room_id"],
            ["deal_rooms.organisation_id", "deal_rooms.id"],
            name="fk_deal_room_revisions_room",
            ondelete="CASCADE",
        ),
        _membership_fk("published_by_user_id", "fk_deal_room_revisions_publisher"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organisation_id", "id", name="uq_deal_room_revisions_org_id"),
        sa.UniqueConstraint("organisation_id", "room_id", "revision", name="uq_deal_room_revisions_number"),
    )
    op.create_index(
        "ix_deal_room_revisions_org_room",
        "deal_room_revisions",
        ["organisation_id", "room_id", "revision"],
    )
    op.create_table(
        "deal_room_access_links",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organisation_id", sa.Uuid(), nullable=False),
        sa.Column("room_id", sa.Uuid(), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("revoked_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "length(token_hash) = 64 AND token_hash = lower(token_hash)", name="ck_deal_room_links_token_hash"
        ),
        sa.CheckConstraint("expires_at IS NULL OR expires_at > created_at", name="ck_deal_room_links_expiry"),
        sa.CheckConstraint("revoked_at IS NULL OR revoked_at >= created_at", name="ck_deal_room_links_revoked"),
        sa.ForeignKeyConstraint(["organisation_id"], ["organisations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["organisation_id", "room_id"],
            ["deal_rooms.organisation_id", "deal_rooms.id"],
            name="fk_deal_room_links_room",
            ondelete="CASCADE",
        ),
        _membership_fk("created_by_user_id", "fk_deal_room_links_creator"),
        _membership_fk("revoked_by_user_id", "fk_deal_room_links_revoker"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organisation_id", "id", name="uq_deal_room_links_org_id"),
        sa.UniqueConstraint("token_hash", name="uq_deal_room_links_token_hash"),
    )
    op.create_index(
        "ix_deal_room_links_org_room",
        "deal_room_access_links",
        ["organisation_id", "room_id", "created_at"],
    )
    op.create_index(
        "uq_deal_room_links_current",
        "deal_room_access_links",
        ["organisation_id", "room_id"],
        unique=True,
        postgresql_where=sa.text("revoked_at IS NULL"),
        sqlite_where=sa.text("revoked_at IS NULL"),
    )

    op.create_table(
        "deal_room_audit_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organisation_id", sa.Uuid(), nullable=False),
        sa.Column("room_id", sa.Uuid(), nullable=False),
        sa.Column("actor_user_id", sa.Uuid(), nullable=False),
        sa.Column("action", sa.String(length=40), nullable=False),
        sa.Column("metadata_json", sa.JSON(), server_default="{}", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "action IN ('created', 'draft_updated', 'published', 'republished', 'paused', 'revoked', "
            "'link_rotated', 'resource_changed', 'publication_source_changed')",
            name="ck_deal_room_audit_action",
        ),
        sa.ForeignKeyConstraint(["organisation_id"], ["organisations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["organisation_id", "room_id"],
            ["deal_rooms.organisation_id", "deal_rooms.id"],
            name="fk_deal_room_audit_room",
            ondelete="CASCADE",
        ),
        _membership_fk("actor_user_id", "fk_deal_room_audit_actor"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_deal_room_audit_org_room",
        "deal_room_audit_events",
        ["organisation_id", "room_id", "created_at"],
    )

    _enable_tenant_rls()
    _create_immutable_guard()
    _create_public_projection_functions()
    _create_closed_opportunity_guard()


def downgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        op.execute("DROP TRIGGER IF EXISTS opportunities_pause_deal_room ON opportunities")
        op.execute("DROP FUNCTION IF EXISTS public.revenueos_pause_closed_deal_room()")
        op.execute("DROP FUNCTION IF EXISTS public.revenueos_public_deal_room_resource(text, text, timestamptz)")
        op.execute("DROP FUNCTION IF EXISTS public.revenueos_public_deal_room_resource(text, text)")
        op.execute("DROP FUNCTION IF EXISTS public.revenueos_public_deal_room(text, timestamptz)")
        op.execute("DROP FUNCTION IF EXISTS public.revenueos_public_deal_room(text)")
        op.execute("DROP TRIGGER IF EXISTS deal_room_revisions_immutable ON deal_room_revisions")
        op.execute("DROP FUNCTION IF EXISTS public.revenueos_deal_room_revision_immutable()")
    op.drop_index("ix_deal_room_audit_org_room", table_name="deal_room_audit_events")
    op.drop_table("deal_room_audit_events")
    op.drop_index("uq_deal_room_links_current", table_name="deal_room_access_links")
    op.drop_index("ix_deal_room_links_org_room", table_name="deal_room_access_links")
    op.drop_table("deal_room_access_links")
    op.drop_index("ix_deal_room_revisions_org_room", table_name="deal_room_revisions")
    op.drop_table("deal_room_revisions")
    op.drop_index("ix_deal_rooms_org_status", table_name="deal_rooms")
    op.drop_table("deal_rooms")
