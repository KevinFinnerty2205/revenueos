"""Pin private personal-note sources for post-conversation drafts.

Revision ID: 0078_private_note_draft_sources
Revises: 0077_spin_methodology

Each automatic draft keeps the exact owner-private live-note snapshot used by
that generation. The transcript fingerprint remains independent so existing
supersession checks keep their original meaning; a separate input fingerprint
binds transcript, optional notes and the deterministic draft schema version.

Note-bearing active rows keep the legacy ``pending``/``processing`` statuses so
old API instances can still serialise them. A far-future ``next_attempt_at``
plus a database constraint fences old workers, whose literal claim query only
accepts due rows. The note-aware worker recognises the pinned source and keeps
that fence through pending, processing and released-poll states.

Downgrade refuses while snapshots exist: an application rollback must keep the
forward schema until any required export is complete and the private provenance
is explicitly erased.
"""

from __future__ import annotations

import hashlib
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0078_private_note_draft_sources"
down_revision: str | None = "0077_spin_methodology"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

DRAFT_SCHEMA_VERSION = 1


def _input_fingerprint(source_fingerprint: str) -> str:
    digest = hashlib.sha256()
    digest.update(source_fingerprint.encode("ascii"))
    digest.update(b"\0")
    digest.update(b"none")
    digest.update(b"\0")
    digest.update(str(DRAFT_SCHEMA_VERSION).encode("ascii"))
    return digest.hexdigest()


def upgrade() -> None:
    with op.batch_alter_table("conversation_draft_generations") as batch:
        batch.add_column(sa.Column("source_live_notes", sa.Text(), nullable=True))
        batch.add_column(sa.Column("source_live_notes_fingerprint", sa.String(length=64), nullable=True))
        batch.add_column(sa.Column("source_workspace_lock_version", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("input_fingerprint", sa.String(length=64), nullable=True))
        batch.add_column(
            sa.Column(
                "draft_schema_version",
                sa.Integer(),
                server_default=str(DRAFT_SCHEMA_VERSION),
                nullable=False,
            )
        )

    generations = sa.table(
        "conversation_draft_generations",
        sa.column("id", sa.Uuid(as_uuid=True)),
        sa.column("source_fingerprint", sa.String(length=64)),
        sa.column("input_fingerprint", sa.String(length=64)),
    )
    connection = op.get_bind()
    # Existing rows predate personal-note snapshots, so every legacy input uses
    # the explicit ``none`` sentinel. Compute the portable SHA-256 value here
    # rather than relying on database-specific digest functions.
    rows = connection.execute(sa.select(generations.c.id, generations.c.source_fingerprint)).all()
    if rows:
        connection.execute(
            generations.update()
            .where(generations.c.id == sa.bindparam("generation_id"))
            .values(input_fingerprint=sa.bindparam("generation_input_fingerprint")),
            [
                {
                    "generation_id": generation_id,
                    "generation_input_fingerprint": _input_fingerprint(str(source_fingerprint)),
                }
                for generation_id, source_fingerprint in rows
            ],
        )

    with op.batch_alter_table("conversation_draft_generations") as batch:
        # Keep the new trace nullable at the database boundary for rolling
        # deploys: a pre-0078 worker may insert while the forward schema is
        # already active. The 0078 worker always writes the value and refuses
        # to claim or materialise a row whose trace is absent or invalid.
        batch.create_check_constraint(
            "ck_conversation_draft_gen_source_notes",
            "(source_live_notes IS NULL AND source_live_notes_fingerprint IS NULL "
            "AND source_workspace_lock_version IS NULL) OR "
            "(source_live_notes IS NOT NULL AND source_live_notes_fingerprint IS NOT NULL "
            "AND source_workspace_lock_version IS NOT NULL)",
        )
        batch.create_check_constraint(
            "ck_conversation_draft_gen_source_lock",
            "source_workspace_lock_version IS NULL OR source_workspace_lock_version > 0",
        )
        batch.create_check_constraint(
            "ck_conversation_draft_gen_source_worker_fence",
            "source_live_notes IS NULL OR status NOT IN ('pending', 'processing') OR next_attempt_at IS NOT NULL",
        )
        batch.create_check_constraint(
            "ck_conversation_draft_gen_schema_version",
            "draft_schema_version > 0",
        )


def downgrade() -> None:
    pinned_notes_exist = (
        op.get_bind()
        .execute(sa.text("SELECT 1 FROM conversation_draft_generations WHERE source_live_notes IS NOT NULL LIMIT 1"))
        .first()
    )
    if pinned_notes_exist is not None:
        raise RuntimeError("Cannot downgrade private note draft sources while pinned personal-note snapshots exist.")
    with op.batch_alter_table("conversation_draft_generations") as batch:
        batch.drop_constraint("ck_conversation_draft_gen_schema_version", type_="check")
        batch.drop_constraint("ck_conversation_draft_gen_source_worker_fence", type_="check")
        batch.drop_constraint("ck_conversation_draft_gen_source_lock", type_="check")
        batch.drop_constraint("ck_conversation_draft_gen_source_notes", type_="check")
        batch.drop_column("draft_schema_version")
        batch.drop_column("input_fingerprint")
        batch.drop_column("source_workspace_lock_version")
        batch.drop_column("source_live_notes_fingerprint")
        batch.drop_column("source_live_notes")
