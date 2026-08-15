"""Add bounded phone-call metadata and recording provenance.

Revision ID: 0027_phone_call_intelligence
Revises: 0026_face_to_face_companion

Downgrade warning: phone associations, call state, recording-source labels and
debrief reconciliation states are permanently removed.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0027_phone_call_intelligence"
down_revision: str | None = "0026_face_to_face_companion"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _restore_sqlite_candidate_review_guard() -> None:
    if op.get_bind().dialect.name != "sqlite":
        return
    op.execute("DROP TRIGGER IF EXISTS candidate_evidence_review_guard")
    op.execute(
        """
        CREATE TRIGGER candidate_evidence_review_guard
        BEFORE UPDATE ON candidate_evidence
        FOR EACH ROW WHEN OLD.review_state <> 'pending'
        BEGIN
            SELECT RAISE(ABORT, 'Reviewed candidate evidence is immutable');
        END
        """
    )


def upgrade() -> None:
    with op.batch_alter_table("interactions") as batch:
        batch.add_column(sa.Column("contact_id", sa.Uuid(), nullable=True))
        batch.add_column(sa.Column("call_direction", sa.String(length=20), nullable=True))
        batch.add_column(sa.Column("call_outcome", sa.String(length=20), nullable=True))
        batch.create_foreign_key(
            "fk_interactions_contact_tenant",
            "contacts",
            ["organisation_id", "contact_id"],
            ["organisation_id", "id"],
            ondelete="RESTRICT",
        )
        batch.create_check_constraint(
            "ck_interactions_call_direction",
            "call_direction IS NULL OR call_direction IN ('inbound', 'outbound', 'unknown')",
        )
        batch.create_check_constraint(
            "ck_interactions_call_outcome",
            "call_outcome IS NULL OR call_outcome IN ('connected', 'no_answer', 'voicemail', 'cancelled')",
        )
    op.create_index(
        "ix_interactions_organisation_contact",
        "interactions",
        ["organisation_id", "contact_id"],
    )
    op.execute("UPDATE interactions SET call_direction = 'unknown' WHERE interaction_type = 'phone_call'")
    with op.batch_alter_table("interactions") as batch:
        batch.create_check_constraint(
            "ck_interactions_phone_metadata_scope",
            "(interaction_type = 'phone_call' AND call_direction IS NOT NULL) OR "
            "(interaction_type <> 'phone_call' AND contact_id IS NULL AND "
            "call_direction IS NULL AND call_outcome IS NULL)",
        )

    with op.batch_alter_table("recording_sessions") as batch:
        batch.add_column(sa.Column("recording_source", sa.String(length=40), nullable=True))
    op.execute(
        "UPDATE recording_sessions SET recording_source = 'user_uploaded_recording' "
        "WHERE recording_type IN ('uploaded_audio_recording', 'imported_audio_recording')"
    )
    with op.batch_alter_table("recording_sessions") as batch:
        batch.create_check_constraint(
            "ck_recording_sessions_source",
            "recording_source IS NULL OR recording_source IN ("
            "'customer_call_recording', 'business_phone_recording', 'user_uploaded_recording', "
            "'external_provider_recording')",
        )
        batch.create_check_constraint(
            "ck_recording_sessions_import_source",
            "(recording_type = 'live_audio_recording' AND recording_source IS NULL) OR "
            "(recording_type <> 'live_audio_recording' AND recording_source IS NOT NULL)",
        )

    with op.batch_alter_table("candidate_evidence") as batch:
        batch.add_column(
            sa.Column(
                "conflict_state",
                sa.String(length=20),
                server_default="not_assessed",
                nullable=False,
            )
        )
        batch.create_check_constraint(
            "ck_candidate_evidence_conflict_state",
            "conflict_state IN ('not_assessed', 'conflicting', 'unresolved', 'corroborated')",
        )
    _restore_sqlite_candidate_review_guard()


def downgrade() -> None:
    with op.batch_alter_table("candidate_evidence") as batch:
        batch.drop_constraint("ck_candidate_evidence_conflict_state", type_="check")
        batch.drop_column("conflict_state")
    _restore_sqlite_candidate_review_guard()

    with op.batch_alter_table("recording_sessions") as batch:
        batch.drop_constraint("ck_recording_sessions_import_source", type_="check")
        batch.drop_constraint("ck_recording_sessions_source", type_="check")
        batch.drop_column("recording_source")

    op.drop_index("ix_interactions_organisation_contact", table_name="interactions")
    with op.batch_alter_table("interactions") as batch:
        batch.drop_constraint("ck_interactions_phone_metadata_scope", type_="check")
        batch.drop_constraint("ck_interactions_call_outcome", type_="check")
        batch.drop_constraint("ck_interactions_call_direction", type_="check")
        batch.drop_constraint("fk_interactions_contact_tenant", type_="foreignkey")
        batch.drop_column("call_outcome")
        batch.drop_column("call_direction")
        batch.drop_column("contact_id")
