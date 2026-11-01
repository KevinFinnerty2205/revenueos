"""Persist and protect automatic private-draft AI job origins.

Revision ID: 0075_automatic_draft_job_origin
Revises: 0074_progressive_transcript

The internal nullable origin distinguishes automatic private-draft work from
independently requested tenant AI work. It is written with the job, never
changed afterwards, and remains absent from public API contracts.
"""

from collections.abc import Sequence
from uuid import UUID

import sqlalchemy as sa
from alembic import op

revision: str = "0075_automatic_draft_job_origin"
down_revision: str | None = "0074_progressive_transcript"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ORIGIN_METADATA_KEY = "automatic_draft_generation_id"
ORIGIN_INDEX = "ix_ai_jobs_organisation_automatic_draft_generation"
SQLITE_ORIGIN_TRIGGER = "ai_jobs_automatic_draft_origin_immutable"
POSTGRES_ORIGIN_FUNCTION = "enforce_ai_job_automatic_draft_origin"
POSTGRES_ORIGIN_TRIGGER = "ai_jobs_automatic_draft_origin_immutable"


def _backfill_origins() -> None:
    """Backfill PR-local audit origins and reject any ambiguous tagged trace."""

    uuid_type = sa.Uuid(as_uuid=True)
    audits = sa.table(
        "meeting_audit_events",
        sa.column("id", uuid_type),
        sa.column("organisation_id", uuid_type),
        sa.column("meeting_id", uuid_type),
        sa.column("actor_user_id", uuid_type),
        sa.column("action", sa.String()),
        sa.column("entity_type", sa.String()),
        sa.column("entity_id", uuid_type),
        sa.column("metadata_json", sa.JSON()),
        sa.column("version", sa.Integer()),
    )
    jobs = sa.table(
        "ai_jobs",
        sa.column("id", uuid_type),
        sa.column("organisation_id", uuid_type),
        sa.column("meeting_id", uuid_type),
        sa.column("transcript_version", sa.Integer()),
        sa.column("requested_by_user_id", uuid_type),
        sa.column("automatic_draft_generation_id", uuid_type),
    )
    generations = sa.table(
        "conversation_draft_generations",
        sa.column("id", uuid_type),
        sa.column("organisation_id", uuid_type),
        sa.column("meeting_id", uuid_type),
        sa.column("transcript_version", sa.Integer()),
        sa.column("user_id", uuid_type),
    )
    bind = op.get_bind()
    rows = list(
        bind.execute(
            sa.select(
                audits.c.id,
                audits.c.organisation_id,
                audits.c.meeting_id,
                audits.c.actor_user_id,
                audits.c.entity_id,
                audits.c.metadata_json,
                audits.c.version,
                jobs.c.requested_by_user_id,
                jobs.c.meeting_id.label("job_meeting_id"),
                jobs.c.transcript_version,
            )
            .select_from(
                audits.join(
                    jobs,
                    (jobs.c.organisation_id == audits.c.organisation_id) & (jobs.c.id == audits.c.entity_id),
                )
            )
            .where(
                audits.c.action == "ai_job_created",
                audits.c.entity_type == "ai_job",
            )
        ).mappings()
    )

    seen_jobs: set[tuple[UUID, UUID]] = set()
    for row in rows:
        metadata = row["metadata_json"]
        if not isinstance(metadata, dict) or ORIGIN_METADATA_KEY not in metadata:
            continue
        job_key = (row["organisation_id"], row["entity_id"])
        if job_key in seen_jobs:
            raise RuntimeError("Automatic draft AI job origin audit is duplicated.")
        seen_jobs.add(job_key)
        try:
            generation_id = UUID(str(metadata[ORIGIN_METADATA_KEY]))
            metadata_job_id = UUID(str(metadata.get("job_id")))
        except (TypeError, ValueError, AttributeError) as exc:
            raise RuntimeError("Automatic draft AI job origin audit is malformed.") from exc
        if (
            metadata_job_id != row["entity_id"]
            or row["actor_user_id"] != row["requested_by_user_id"]
            or row["meeting_id"] != row["job_meeting_id"]
            or row["version"] != row["transcript_version"]
        ):
            raise RuntimeError("Automatic draft AI job origin audit does not match its job trace.")
        generation_exists = bind.scalar(
            sa.select(sa.literal(1)).where(
                sa.exists(
                    sa.select(generations.c.id).where(
                        generations.c.organisation_id == row["organisation_id"],
                        generations.c.id == generation_id,
                        generations.c.meeting_id == row["job_meeting_id"],
                        generations.c.transcript_version == row["transcript_version"],
                        generations.c.user_id == row["requested_by_user_id"],
                    )
                )
            )
        )
        if generation_exists is None:
            raise RuntimeError("Automatic draft AI job origin generation is unavailable.")
        bind.execute(
            jobs.update()
            .where(
                jobs.c.organisation_id == row["organisation_id"],
                jobs.c.id == row["entity_id"],
            )
            .values(automatic_draft_generation_id=generation_id)
        )


def _create_origin_guard() -> None:
    if op.get_bind().dialect.name == "postgresql":
        op.execute(
            f"""
            CREATE FUNCTION {POSTGRES_ORIGIN_FUNCTION}()
            RETURNS trigger
            LANGUAGE plpgsql
            AS $$
            BEGIN
                IF NEW.automatic_draft_generation_id IS DISTINCT FROM OLD.automatic_draft_generation_id THEN
                    RAISE EXCEPTION 'Automatic draft AI job origin is immutable';
                END IF;
                RETURN NEW;
            END;
            $$
            """
        )
        op.execute(
            f"""
            CREATE TRIGGER {POSTGRES_ORIGIN_TRIGGER}
            BEFORE UPDATE OF automatic_draft_generation_id ON ai_jobs
            FOR EACH ROW
            EXECUTE FUNCTION {POSTGRES_ORIGIN_FUNCTION}()
            """
        )
        return
    op.execute(
        f"""
        CREATE TRIGGER {SQLITE_ORIGIN_TRIGGER}
        BEFORE UPDATE OF automatic_draft_generation_id ON ai_jobs
        FOR EACH ROW
        WHEN NEW.automatic_draft_generation_id IS NOT OLD.automatic_draft_generation_id
        BEGIN
            SELECT RAISE(ABORT, 'Automatic draft AI job origin is immutable');
        END
        """
    )


def _drop_origin_guard() -> None:
    if op.get_bind().dialect.name == "postgresql":
        op.execute(f"DROP TRIGGER IF EXISTS {POSTGRES_ORIGIN_TRIGGER} ON ai_jobs")
        op.execute(f"DROP FUNCTION IF EXISTS {POSTGRES_ORIGIN_FUNCTION}()")
        return
    op.execute(f"DROP TRIGGER IF EXISTS {SQLITE_ORIGIN_TRIGGER}")


def upgrade() -> None:
    uuid_type = sa.Uuid(as_uuid=True)
    op.add_column(
        "ai_jobs",
        sa.Column("automatic_draft_generation_id", uuid_type, nullable=True),
    )
    _backfill_origins()
    op.create_index(
        ORIGIN_INDEX,
        "ai_jobs",
        ["organisation_id", "automatic_draft_generation_id"],
    )
    _create_origin_guard()


def downgrade() -> None:
    durable_origins_exist = (
        op.get_bind()
        .execute(sa.text("SELECT 1 FROM ai_jobs WHERE automatic_draft_generation_id IS NOT NULL LIMIT 1"))
        .first()
    )
    if durable_origins_exist is not None:
        raise RuntimeError("Cannot downgrade automatic draft origin guards while tagged AI jobs exist.")
    _drop_origin_guard()
    op.drop_index(ORIGIN_INDEX, table_name="ai_jobs")
    op.drop_column("ai_jobs", "automatic_draft_generation_id")
