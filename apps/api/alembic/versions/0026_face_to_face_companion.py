"""Add tenant-scoped face-to-face Companion quick markers.

Revision ID: 0026_face_to_face_companion
Revises: 0025_recording_transcription

Downgrade warning: quick-marker metadata is permanently removed.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0026_face_to_face_companion"
down_revision: str | None = "0025_recording_transcription"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _enable_tenant_rls() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return
    op.execute("ALTER TABLE interaction_markers ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE interaction_markers FORCE ROW LEVEL SECURITY")
    op.execute(
        """CREATE POLICY interaction_markers_tenant_isolation
        ON interaction_markers
        USING (organisation_id = NULLIF(current_setting('app.organisation_id', true), '')::uuid)
        WITH CHECK (organisation_id = NULLIF(current_setting('app.organisation_id', true), '')::uuid)"""
    )


def _create_immutability_guard() -> None:
    dialect = op.get_bind().dialect.name
    if dialect == "postgresql":
        op.execute(
            """
            CREATE FUNCTION protect_interaction_marker_metadata()
            RETURNS trigger LANGUAGE plpgsql AS $$
            BEGIN
                IF NEW.organisation_id <> OLD.organisation_id
                   OR NEW.id <> OLD.id
                   OR NEW.interaction_id <> OLD.interaction_id
                   OR NEW.created_by_user_id <> OLD.created_by_user_id
                   OR NEW.marker_type <> OLD.marker_type
                   OR NEW.recording_offset_ms IS DISTINCT FROM OLD.recording_offset_ms
                   OR NEW.idempotency_key <> OLD.idempotency_key
                   OR NEW.created_at <> OLD.created_at THEN
                    RAISE EXCEPTION 'Interaction marker metadata is immutable';
                END IF;
                IF OLD.deleted_at IS NOT NULL AND NEW.deleted_at IS DISTINCT FROM OLD.deleted_at THEN
                    RAISE EXCEPTION 'Deleted interaction markers are immutable';
                END IF;
                RETURN NEW;
            END;
            $$
            """
        )
        op.execute(
            """CREATE TRIGGER interaction_markers_immutability_guard
            BEFORE UPDATE ON interaction_markers
            FOR EACH ROW EXECUTE FUNCTION protect_interaction_marker_metadata()"""
        )
    elif dialect == "sqlite":
        op.execute(
            """
            CREATE TRIGGER interaction_markers_immutability_guard
            BEFORE UPDATE ON interaction_markers
            FOR EACH ROW
            WHEN NEW.organisation_id IS NOT OLD.organisation_id
              OR NEW.id IS NOT OLD.id
              OR NEW.interaction_id IS NOT OLD.interaction_id
              OR NEW.created_by_user_id IS NOT OLD.created_by_user_id
              OR NEW.marker_type IS NOT OLD.marker_type
              OR NEW.recording_offset_ms IS NOT OLD.recording_offset_ms
              OR NEW.idempotency_key IS NOT OLD.idempotency_key
              OR NEW.created_at IS NOT OLD.created_at
              OR (OLD.deleted_at IS NOT NULL AND NEW.deleted_at IS NOT OLD.deleted_at)
            BEGIN
                SELECT RAISE(ABORT, 'Interaction marker metadata is immutable');
            END
            """
        )


def _drop_immutability_guard() -> None:
    dialect = op.get_bind().dialect.name
    if dialect == "postgresql":
        op.execute("DROP TRIGGER interaction_markers_immutability_guard ON interaction_markers")
        op.execute("DROP FUNCTION protect_interaction_marker_metadata()")
    elif dialect == "sqlite":
        op.execute("DROP TRIGGER interaction_markers_immutability_guard")


def upgrade() -> None:
    op.create_table(
        "interaction_markers",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organisation_id", sa.Uuid(), nullable=False),
        sa.Column("interaction_id", sa.Uuid(), nullable=False),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("marker_type", sa.String(length=40), nullable=False),
        sa.Column("recording_offset_ms", sa.Integer(), nullable=True),
        sa.Column("idempotency_key", sa.String(length=200), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "marker_type IN ('buying_signal', 'objection', 'decision', 'action_item', "
            "'risk', 'stakeholder', 'timeline', 'budget', 'procurement', 'follow_up', "
            "'important_moment', 'customer_question', 'requested_material', 'strong_engagement')",
            name="ck_interaction_markers_type",
        ),
        sa.CheckConstraint(
            "recording_offset_ms IS NULL OR recording_offset_ms BETWEEN 0 AND 14400000",
            name="ck_interaction_markers_offset",
        ),
        sa.CheckConstraint(
            "length(trim(idempotency_key)) BETWEEN 1 AND 200",
            name="ck_interaction_markers_idempotency",
        ),
        sa.ForeignKeyConstraint(["organisation_id"], ["organisations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["organisation_id", "interaction_id"],
            ["interactions.organisation_id", "interactions.id"],
            name="fk_interaction_markers_interaction_tenant",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["organisation_id", "created_by_user_id"],
            ["organisation_memberships.organisation_id", "organisation_memberships.user_id"],
            name="fk_interaction_markers_creator_membership",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organisation_id", "id", name="uq_interaction_markers_organisation_id_id"),
        sa.UniqueConstraint(
            "organisation_id",
            "interaction_id",
            "created_by_user_id",
            "idempotency_key",
            name="uq_interaction_markers_idempotency",
        ),
    )
    op.create_index(
        "ix_interaction_markers_organisation_interaction_created",
        "interaction_markers",
        ["organisation_id", "interaction_id", "created_at"],
    )
    _enable_tenant_rls()
    _create_immutability_guard()


def downgrade() -> None:
    _drop_immutability_guard()
    op.drop_table("interaction_markers")
