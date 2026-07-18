"""Add the tenant-owned AI database foundation.

Revision ID: 0004_ai_database_foundation
Revises: 0003_meeting_domain
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004_ai_database_foundation"
down_revision: str | None = "0003_meeting_domain"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _enable_tenant_rls(table_name: str) -> None:
    if op.get_bind().dialect.name != "postgresql":
        return
    policy_name = f"{table_name}_tenant_isolation"
    op.execute(f"ALTER TABLE {table_name} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {table_name} FORCE ROW LEVEL SECURITY")
    op.execute(
        f"""CREATE POLICY {policy_name} ON {table_name}
        USING (organisation_id = NULLIF(current_setting('app.organisation_id', true), '')::uuid)
        WITH CHECK (organisation_id = NULLIF(current_setting('app.organisation_id', true), '')::uuid)"""
    )


def _create_job_trace_guard() -> None:
    dialect = op.get_bind().dialect.name
    if dialect == "postgresql":
        op.execute(
            """
            CREATE FUNCTION enforce_ai_job_transcript_trace()
            RETURNS trigger
            LANGUAGE plpgsql
            AS $$
            BEGIN
                IF TG_OP = 'INSERT' THEN
                    PERFORM 1
                    FROM transcripts
                    WHERE organisation_id = NEW.organisation_id
                        AND id = NEW.transcript_id
                        AND meeting_id = NEW.meeting_id
                        AND version = NEW.transcript_version;
                    IF NOT FOUND THEN
                        RAISE EXCEPTION 'AI job transcript version must match the current transcript';
                    END IF;
                ELSIF ROW(
                    NEW.organisation_id,
                    NEW.meeting_id,
                    NEW.transcript_id,
                    NEW.transcript_version,
                    NEW.job_type
                ) IS DISTINCT FROM ROW(
                    OLD.organisation_id,
                    OLD.meeting_id,
                    OLD.transcript_id,
                    OLD.transcript_version,
                    OLD.job_type
                ) THEN
                    RAISE EXCEPTION 'AI job trace is immutable';
                END IF;
                RETURN NEW;
            END;
            $$
            """
        )
        op.execute(
            """
            CREATE TRIGGER ai_jobs_validate_transcript_trace
            BEFORE INSERT ON ai_jobs
            FOR EACH ROW
            EXECUTE FUNCTION enforce_ai_job_transcript_trace()
            """
        )
        op.execute(
            """
            CREATE TRIGGER ai_jobs_prevent_trace_change
            BEFORE UPDATE OF organisation_id, meeting_id, transcript_id,
                transcript_version, job_type ON ai_jobs
            FOR EACH ROW
            EXECUTE FUNCTION enforce_ai_job_transcript_trace()
            """
        )
    elif dialect == "sqlite":
        op.execute(
            """
            CREATE TRIGGER ai_jobs_validate_transcript_trace
            BEFORE INSERT ON ai_jobs
            FOR EACH ROW
            WHEN NOT EXISTS (
                SELECT 1
                FROM transcripts
                WHERE organisation_id = NEW.organisation_id
                    AND id = NEW.transcript_id
                    AND meeting_id = NEW.meeting_id
                    AND version = NEW.transcript_version
            )
            BEGIN
                SELECT RAISE(
                    ABORT,
                    'AI job transcript version must match the current transcript'
                );
            END
            """
        )
        op.execute(
            """
            CREATE TRIGGER ai_jobs_prevent_trace_change
            BEFORE UPDATE OF organisation_id, meeting_id, transcript_id,
                transcript_version, job_type ON ai_jobs
            FOR EACH ROW
            WHEN
                NEW.organisation_id IS NOT OLD.organisation_id
                OR NEW.meeting_id IS NOT OLD.meeting_id
                OR NEW.transcript_id IS NOT OLD.transcript_id
                OR NEW.transcript_version IS NOT OLD.transcript_version
                OR NEW.job_type IS NOT OLD.job_type
            BEGIN
                SELECT RAISE(ABORT, 'AI job trace is immutable');
            END
            """
        )


def _drop_job_trace_guard() -> None:
    dialect = op.get_bind().dialect.name
    if dialect == "postgresql":
        op.execute("DROP TRIGGER ai_jobs_prevent_trace_change ON ai_jobs")
        op.execute("DROP TRIGGER ai_jobs_validate_transcript_trace ON ai_jobs")
        op.execute("DROP FUNCTION enforce_ai_job_transcript_trace()")
    elif dialect == "sqlite":
        op.execute("DROP TRIGGER ai_jobs_prevent_trace_change")
        op.execute("DROP TRIGGER ai_jobs_validate_transcript_trace")


def _create_artifact_immutability_guard() -> None:
    dialect = op.get_bind().dialect.name
    if dialect == "postgresql":
        op.execute(
            """
            CREATE FUNCTION prevent_ai_artifact_overwrite()
            RETURNS trigger
            LANGUAGE plpgsql
            AS $$
            BEGIN
                IF (to_jsonb(NEW) - 'superseded_at')
                    IS DISTINCT FROM (to_jsonb(OLD) - 'superseded_at') THEN
                    RAISE EXCEPTION 'AI artefact rows are immutable';
                END IF;
                IF OLD.superseded_at IS NOT NULL
                    AND NEW.superseded_at IS DISTINCT FROM OLD.superseded_at THEN
                    RAISE EXCEPTION 'AI artefact supersession is immutable once set';
                END IF;
                RETURN NEW;
            END;
            $$
            """
        )
        op.execute(
            """
            CREATE TRIGGER ai_artifacts_prevent_overwrite
            BEFORE UPDATE ON ai_artifacts
            FOR EACH ROW
            EXECUTE FUNCTION prevent_ai_artifact_overwrite()
            """
        )
    elif dialect == "sqlite":
        op.execute(
            """
            CREATE TRIGGER ai_artifacts_prevent_overwrite
            BEFORE UPDATE ON ai_artifacts
            FOR EACH ROW
            WHEN
                NEW.id IS NOT OLD.id
                OR NEW.organisation_id IS NOT OLD.organisation_id
                OR NEW.meeting_id IS NOT OLD.meeting_id
                OR NEW.transcript_id IS NOT OLD.transcript_id
                OR NEW.transcript_version IS NOT OLD.transcript_version
                OR NEW.job_id IS NOT OLD.job_id
                OR NEW.artifact_type IS NOT OLD.artifact_type
                OR NEW.artifact_version IS NOT OLD.artifact_version
                OR NEW.schema_version IS NOT OLD.schema_version
                OR NEW.prompt_key IS NOT OLD.prompt_key
                OR NEW.prompt_version IS NOT OLD.prompt_version
                OR NEW.provider_key IS NOT OLD.provider_key
                OR NEW.model_name IS NOT OLD.model_name
                OR NEW.content_json IS NOT OLD.content_json
                OR NEW.confidence IS NOT OLD.confidence
                OR NEW.created_at IS NOT OLD.created_at
            BEGIN
                SELECT RAISE(ABORT, 'AI artefact rows are immutable');
            END
            """
        )
        op.execute(
            """
            CREATE TRIGGER ai_artifacts_prevent_resupersession
            BEFORE UPDATE OF superseded_at ON ai_artifacts
            FOR EACH ROW
            WHEN OLD.superseded_at IS NOT NULL
                AND NEW.superseded_at IS NOT OLD.superseded_at
            BEGIN
                SELECT RAISE(ABORT, 'AI artefact supersession is immutable once set');
            END
            """
        )


def _drop_artifact_immutability_guard() -> None:
    dialect = op.get_bind().dialect.name
    if dialect == "postgresql":
        op.execute("DROP TRIGGER ai_artifacts_prevent_overwrite ON ai_artifacts")
        op.execute("DROP FUNCTION prevent_ai_artifact_overwrite()")
    elif dialect == "sqlite":
        op.execute("DROP TRIGGER ai_artifacts_prevent_resupersession")
        op.execute("DROP TRIGGER ai_artifacts_prevent_overwrite")


def upgrade() -> None:
    uuid_type = sa.Uuid(as_uuid=True)

    with op.batch_alter_table("transcripts") as batch_op:
        batch_op.create_unique_constraint(
            "uq_transcripts_organisation_id_meeting",
            ["organisation_id", "id", "meeting_id"],
        )

    op.create_table(
        "ai_jobs",
        sa.Column("id", uuid_type, primary_key=True, nullable=False),
        sa.Column(
            "organisation_id",
            uuid_type,
            sa.ForeignKey("organisations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("meeting_id", uuid_type, nullable=False),
        sa.Column("transcript_id", uuid_type, nullable=False),
        sa.Column("transcript_version", sa.Integer(), nullable=False),
        sa.Column(
            "job_type",
            sa.String(length=64),
            server_default="infrastructure_test",
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.String(length=30),
            server_default="pending",
            nullable=False,
        ),
        sa.Column("provider_key", sa.String(length=100)),
        sa.Column("model_name", sa.String(length=200)),
        sa.Column("prompt_key", sa.String(length=100)),
        sa.Column("prompt_version", sa.Integer()),
        sa.Column("schema_version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("idempotency_key", sa.String(length=200)),
        sa.Column("attempt_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("max_attempts", sa.Integer(), server_default="3", nullable=False),
        sa.Column(
            "requested_by_user_id",
            uuid_type,
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("cancelled_at", sa.DateTime(timezone=True)),
        sa.Column("cancellation_requested_at", sa.DateTime(timezone=True)),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True)),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True)),
        sa.Column("last_error_code", sa.String(length=100)),
        sa.Column("last_error_message_safe", sa.String(length=1000)),
        sa.Column("provider_request_id", sa.String(length=255)),
        sa.Column("input_token_count", sa.Integer()),
        sa.Column("output_token_count", sa.Integer()),
        sa.Column("estimated_cost_minor_units", sa.BigInteger()),
        sa.Column("currency", sa.String(length=3)),
        sa.Column("processing_duration_ms", sa.BigInteger()),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "job_type IN ('infrastructure_test')",
            name="ck_ai_jobs_type",
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'running', 'completed', 'failed', 'cancelled')",
            name="ck_ai_jobs_status",
        ),
        sa.CheckConstraint("transcript_version > 0", name="ck_ai_jobs_transcript_version"),
        sa.CheckConstraint(
            "prompt_version IS NULL OR prompt_version > 0",
            name="ck_ai_jobs_prompt_version",
        ),
        sa.CheckConstraint("schema_version > 0", name="ck_ai_jobs_schema_version"),
        sa.CheckConstraint("attempt_count >= 0", name="ck_ai_jobs_attempt_count"),
        sa.CheckConstraint("max_attempts >= 1", name="ck_ai_jobs_max_attempts"),
        sa.CheckConstraint(
            "input_token_count IS NULL OR input_token_count >= 0",
            name="ck_ai_jobs_input_tokens",
        ),
        sa.CheckConstraint(
            "output_token_count IS NULL OR output_token_count >= 0",
            name="ck_ai_jobs_output_tokens",
        ),
        sa.CheckConstraint(
            "estimated_cost_minor_units IS NULL OR estimated_cost_minor_units >= 0",
            name="ck_ai_jobs_estimated_cost",
        ),
        sa.CheckConstraint(
            "processing_duration_ms IS NULL OR processing_duration_ms >= 0",
            name="ck_ai_jobs_processing_duration",
        ),
        sa.CheckConstraint(
            "last_error_message_safe IS NULL OR length(last_error_message_safe) <= 1000",
            name="ck_ai_jobs_safe_error_length",
        ),
        sa.CheckConstraint(
            "idempotency_key IS NULL OR length(idempotency_key) <= 200",
            name="ck_ai_jobs_idempotency_length",
        ),
        sa.CheckConstraint(
            "currency IS NULL OR (length(currency) = 3 AND currency = upper(currency))",
            name="ck_ai_jobs_currency",
        ),
        sa.ForeignKeyConstraint(
            ["organisation_id", "meeting_id"],
            ["meetings.organisation_id", "meetings.id"],
            name="fk_ai_jobs_meeting_tenant",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organisation_id", "transcript_id", "meeting_id"],
            [
                "transcripts.organisation_id",
                "transcripts.id",
                "transcripts.meeting_id",
            ],
            name="fk_ai_jobs_transcript_meeting_tenant",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organisation_id", "requested_by_user_id"],
            [
                "organisation_memberships.organisation_id",
                "organisation_memberships.user_id",
            ],
            name="fk_ai_jobs_requester_membership",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint("organisation_id", "id", name="uq_ai_jobs_organisation_id_id"),
        sa.UniqueConstraint(
            "organisation_id",
            "id",
            "meeting_id",
            "transcript_id",
            "transcript_version",
            name="uq_ai_jobs_artifact_trace",
        ),
        sa.UniqueConstraint(
            "organisation_id",
            "meeting_id",
            "transcript_version",
            "job_type",
            "idempotency_key",
            name="uq_ai_jobs_idempotency",
        ),
    )
    op.create_index(
        "ix_ai_jobs_organisation_meeting",
        "ai_jobs",
        ["organisation_id", "meeting_id"],
    )
    op.create_index(
        "ix_ai_jobs_organisation_status",
        "ai_jobs",
        ["organisation_id", "status"],
    )
    op.create_index(
        "ix_ai_jobs_status_next_attempt",
        "ai_jobs",
        ["status", "next_attempt_at"],
    )
    op.create_index(
        "ix_ai_jobs_status_lease_expires",
        "ai_jobs",
        ["status", "lease_expires_at"],
    )
    op.create_index(
        "ix_ai_jobs_transcript_version",
        "ai_jobs",
        ["organisation_id", "transcript_id", "transcript_version"],
    )
    op.create_index(
        "ix_ai_jobs_organisation_created",
        "ai_jobs",
        ["organisation_id", "created_at"],
    )

    op.create_table(
        "ai_artifacts",
        sa.Column("id", uuid_type, primary_key=True, nullable=False),
        sa.Column(
            "organisation_id",
            uuid_type,
            sa.ForeignKey("organisations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("meeting_id", uuid_type, nullable=False),
        sa.Column("transcript_id", uuid_type, nullable=False),
        sa.Column("transcript_version", sa.Integer(), nullable=False),
        sa.Column("job_id", uuid_type, nullable=False),
        sa.Column(
            "artifact_type",
            sa.String(length=64),
            server_default="infrastructure_test",
            nullable=False,
        ),
        sa.Column("artifact_version", sa.Integer(), nullable=False),
        sa.Column("schema_version", sa.Integer(), nullable=False),
        sa.Column("prompt_key", sa.String(length=100)),
        sa.Column("prompt_version", sa.Integer()),
        sa.Column("provider_key", sa.String(length=100)),
        sa.Column("model_name", sa.String(length=200)),
        sa.Column("content_json", sa.JSON(none_as_null=True), nullable=False),
        sa.Column("confidence", sa.Numeric(precision=5, scale=4)),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("superseded_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint(
            "artifact_type IN ('infrastructure_test')",
            name="ck_ai_artifacts_type",
        ),
        sa.CheckConstraint("artifact_version > 0", name="ck_ai_artifacts_version"),
        sa.CheckConstraint("schema_version > 0", name="ck_ai_artifacts_schema_version"),
        sa.CheckConstraint(
            "transcript_version > 0",
            name="ck_ai_artifacts_transcript_version",
        ),
        sa.CheckConstraint(
            "confidence IS NULL OR (confidence >= 0 AND confidence <= 1)",
            name="ck_ai_artifacts_confidence",
        ),
        sa.CheckConstraint(
            "prompt_version IS NULL OR prompt_version > 0",
            name="ck_ai_artifacts_prompt_version",
        ),
        sa.ForeignKeyConstraint(
            ["organisation_id", "meeting_id"],
            ["meetings.organisation_id", "meetings.id"],
            name="fk_ai_artifacts_meeting_tenant",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organisation_id", "transcript_id", "meeting_id"],
            [
                "transcripts.organisation_id",
                "transcripts.id",
                "transcripts.meeting_id",
            ],
            name="fk_ai_artifacts_transcript_meeting_tenant",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            [
                "organisation_id",
                "job_id",
                "meeting_id",
                "transcript_id",
                "transcript_version",
            ],
            [
                "ai_jobs.organisation_id",
                "ai_jobs.id",
                "ai_jobs.meeting_id",
                "ai_jobs.transcript_id",
                "ai_jobs.transcript_version",
            ],
            name="fk_ai_artifacts_job_trace",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint(
            "organisation_id",
            "id",
            name="uq_ai_artifacts_organisation_id_id",
        ),
        sa.UniqueConstraint(
            "organisation_id",
            "meeting_id",
            "transcript_id",
            "transcript_version",
            "artifact_type",
            "artifact_version",
            name="uq_ai_artifacts_logical_version",
        ),
    )
    op.create_index(
        "ix_ai_artifacts_organisation_meeting",
        "ai_artifacts",
        ["organisation_id", "meeting_id"],
    )
    op.create_index(
        "ix_ai_artifacts_organisation_meeting_type",
        "ai_artifacts",
        ["organisation_id", "meeting_id", "artifact_type"],
    )
    op.create_index(
        "ix_ai_artifacts_transcript_version",
        "ai_artifacts",
        ["organisation_id", "transcript_id", "transcript_version"],
    )
    op.create_index(
        "ix_ai_artifacts_job",
        "ai_artifacts",
        ["organisation_id", "job_id"],
    )
    op.create_index(
        "ix_ai_artifacts_latest_version",
        "ai_artifacts",
        [
            "organisation_id",
            "meeting_id",
            "transcript_version",
            "artifact_type",
            "artifact_version",
        ],
    )

    _create_job_trace_guard()
    _create_artifact_immutability_guard()
    _enable_tenant_rls("ai_jobs")
    _enable_tenant_rls("ai_artifacts")


def downgrade() -> None:
    _drop_artifact_immutability_guard()
    _drop_job_trace_guard()
    op.drop_table("ai_artifacts")
    op.drop_table("ai_jobs")
    with op.batch_alter_table("transcripts") as batch_op:
        batch_op.drop_constraint(
            "uq_transcripts_organisation_id_meeting",
            type_="unique",
        )
