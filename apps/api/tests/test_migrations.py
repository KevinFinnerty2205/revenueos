import asyncio
import os
from pathlib import Path
from sqlite3 import IntegrityError, connect

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine


def test_migrations_upgrade_downgrade_and_reupgrade_ai_worker_queue(
    tmp_path: Path,
    monkeypatch: object,
) -> None:
    database_path = tmp_path / "migration.db"
    database_url = f"sqlite+aiosqlite:///{database_path}"
    monkeypatch.setenv("DATABASE_URL", database_url)  # type: ignore[attr-defined]
    configuration = Config("alembic.ini")

    command.upgrade(configuration, "head")

    with connect(database_path) as connection:
        tables = {
            row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'").fetchall()
        }
        assert {
            "companies",
            "contacts",
            "opportunities",
            "tasks",
            "meetings",
            "meeting_participants",
            "transcripts",
            "meeting_audit_events",
            "ai_jobs",
            "ai_artifacts",
        }.issubset(tables)
        assert connection.execute("SELECT version_num FROM alembic_version").fetchone() == ("0010_risks_blockers",)
        task_columns = {row[1]: row[3] for row in connection.execute("PRAGMA table_info(tasks)").fetchall()}
        assert task_columns["organisation_id"] == 1
        assert task_columns["title"] == 1
        assert task_columns["created_by_user_id"] == 1
        meeting_columns = {row[1]: row[3] for row in connection.execute("PRAGMA table_info(meetings)").fetchall()}
        assert meeting_columns["organisation_id"] == 1
        assert meeting_columns["meeting_date"] == 1
        assert meeting_columns["created_by"] == 1
        assert meeting_columns["updated_by"] == 1
        assert meeting_columns["deleted_at"] == 0
        participant_columns = {
            row[1]: row[3] for row in connection.execute("PRAGMA table_info(meeting_participants)").fetchall()
        }
        assert participant_columns["organisation_id"] == 1
        transcript_columns = {row[1]: row[3] for row in connection.execute("PRAGMA table_info(transcripts)").fetchall()}
        assert transcript_columns["organisation_id"] == 1
        assert transcript_columns["version"] == 1
        job_columns = {row[1]: row[3] for row in connection.execute("PRAGMA table_info(ai_jobs)").fetchall()}
        assert job_columns["organisation_id"] == 1
        assert job_columns["meeting_id"] == 1
        assert job_columns["transcript_id"] == 1
        assert job_columns["transcript_version"] == 1
        assert job_columns["requested_by_user_id"] == 1
        assert job_columns["worker_id"] == 0
        assert job_columns["heartbeat_at"] == 0
        artifact_columns = {row[1]: row[3] for row in connection.execute("PRAGMA table_info(ai_artifacts)").fetchall()}
        assert artifact_columns["organisation_id"] == 1
        assert artifact_columns["job_id"] == 1
        assert artifact_columns["artifact_version"] == 1
        assert artifact_columns["content_json"] == 1
        audit_columns = {
            row[1]: (row[2], row[3]) for row in connection.execute("PRAGMA table_info(meeting_audit_events)").fetchall()
        }
        assert audit_columns["action"] == ("VARCHAR(40)", 1)
        assert audit_columns["metadata_json"][1] == 1
        job_indexes = {row[1] for row in connection.execute("PRAGMA index_list(ai_jobs)").fetchall()}
        assert {
            "ix_ai_jobs_organisation_meeting",
            "ix_ai_jobs_organisation_status",
            "ix_ai_jobs_status_next_attempt",
            "ix_ai_jobs_status_lease_expires",
            "ix_ai_jobs_transcript_version",
            "ix_ai_jobs_organisation_created",
        }.issubset(job_indexes)
        artifact_indexes = {row[1] for row in connection.execute("PRAGMA index_list(ai_artifacts)").fetchall()}
        assert {
            "ix_ai_artifacts_organisation_meeting",
            "ix_ai_artifacts_organisation_meeting_type",
            "ix_ai_artifacts_transcript_version",
            "ix_ai_artifacts_job",
            "ix_ai_artifacts_latest_version",
        }.issubset(artifact_indexes)
        triggers = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'trigger' AND tbl_name = 'ai_artifacts'"
            ).fetchall()
        }
        assert triggers == {
            "ai_artifacts_prevent_overwrite",
            "ai_artifacts_prevent_resupersession",
        }
        job_triggers = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'trigger' AND tbl_name = 'ai_jobs'"
            ).fetchall()
        }
        assert job_triggers == {
            "ai_jobs_validate_transcript_trace",
            "ai_jobs_prevent_trace_change",
        }

        connection.execute(
            """
            INSERT INTO transcripts
                (id, organisation_id, meeting_id, raw_text, version)
            VALUES
                ('transcript-1', 'organisation-1', 'meeting-1',
                 'Migration trace text', 1)
            """
        )
        connection.execute(
            """
            INSERT INTO ai_jobs
                (id, organisation_id, meeting_id, transcript_id, transcript_version,
                 requested_by_user_id, idempotency_key)
            VALUES
                ('job-1', 'organisation-1', 'meeting-1', 'transcript-1', 1,
                 'user-1', 'migration-test')
            """
        )
        with pytest.raises(IntegrityError, match="must match the current transcript"):
            connection.execute(
                """
                INSERT INTO ai_jobs
                    (id, organisation_id, meeting_id, transcript_id,
                     transcript_version, requested_by_user_id, idempotency_key)
                VALUES
                    ('job-2', 'organisation-1', 'meeting-1', 'transcript-1',
                     2, 'user-1', 'wrong-transcript-version')
                """
            )
        with pytest.raises(IntegrityError, match="AI job trace is immutable"):
            connection.execute(
                """
                UPDATE ai_jobs
                SET transcript_version = 2
                WHERE id = 'job-1'
                """
            )
        connection.execute(
            """
            UPDATE ai_jobs
            SET status = 'running'
            WHERE id = 'job-1'
            """
        )
        connection.execute(
            """
            INSERT INTO ai_artifacts
                (id, organisation_id, meeting_id, transcript_id, transcript_version,
                 job_id, artifact_version, schema_version, content_json)
            VALUES
                ('artifact-1', 'organisation-1', 'meeting-1', 'transcript-1', 1,
                 'job-1', 1, 1, '{"status":"ok"}')
            """
        )
        with pytest.raises(IntegrityError, match="AI artefact rows are immutable"):
            connection.execute(
                """
                UPDATE ai_artifacts
                SET content_json = '{"status":"changed"}'
                WHERE id = 'artifact-1'
                """
            )
        connection.execute(
            """
            UPDATE ai_artifacts
            SET superseded_at = CURRENT_TIMESTAMP
            WHERE id = 'artifact-1'
            """
        )
        with pytest.raises(IntegrityError, match="supersession is immutable"):
            connection.execute(
                """
                UPDATE ai_artifacts
                SET superseded_at = NULL
                WHERE id = 'artifact-1'
                """
            )

    with connect(database_path) as connection:
        connection.execute(
            """
            INSERT INTO ai_jobs
                (id, organisation_id, meeting_id, transcript_id,
                 transcript_version, job_type, requested_by_user_id,
                 idempotency_key)
            VALUES
                ('decisions-job-1', 'organisation-1', 'meeting-1',
                 'transcript-1', 1, 'decisions', 'user-1',
                 'decisions-migration-test')
            """
        )
        connection.execute(
            """
            INSERT INTO ai_artifacts
                (id, organisation_id, meeting_id, transcript_id,
                 transcript_version, job_id, artifact_type, artifact_version,
                 schema_version, content_json)
            VALUES
                ('decisions-artifact-1', 'organisation-1', 'meeting-1',
                 'transcript-1', 1, 'decisions-job-1', 'decisions', 1, 1,
                '{"decisions":[]}')
            """
        )
        connection.execute(
            """
            INSERT INTO ai_jobs
                (id, organisation_id, meeting_id, transcript_id,
                 transcript_version, job_type, requested_by_user_id,
                 idempotency_key)
            VALUES
                ('action-items-job-1', 'organisation-1', 'meeting-1',
                 'transcript-1', 1, 'action_items', 'user-1',
                 'action-items-migration-test')
            """
        )
        connection.execute(
            """
            INSERT INTO ai_artifacts
                (id, organisation_id, meeting_id, transcript_id,
                 transcript_version, job_id, artifact_type, artifact_version,
                 schema_version, content_json)
            VALUES
                ('action-items-artifact-1', 'organisation-1', 'meeting-1',
                 'transcript-1', 1, 'action-items-job-1', 'action_items', 1, 1,
                 '{"action_items":[]}')
            """
        )
        connection.execute(
            """
            INSERT INTO ai_jobs
                (id, organisation_id, meeting_id, transcript_id,
                 transcript_version, job_type, requested_by_user_id,
                 idempotency_key)
            VALUES
                ('risks-blockers-job-1', 'organisation-1', 'meeting-1',
                 'transcript-1', 1, 'risks_blockers', 'user-1',
                 'risks-blockers-migration-test')
            """
        )
        connection.execute(
            """
            INSERT INTO ai_artifacts
                (id, organisation_id, meeting_id, transcript_id,
                 transcript_version, job_id, artifact_type, artifact_version,
                 schema_version, content_json)
            VALUES
                ('risks-blockers-artifact-1', 'organisation-1', 'meeting-1',
                 'transcript-1', 1, 'risks-blockers-job-1', 'risks_blockers',
                 1, 1, '{"risks":[]}')
            """
        )

    command.downgrade(configuration, "0008_decisions")
    with connect(database_path) as connection:
        assert connection.execute("SELECT version_num FROM alembic_version").fetchone() == ("0008_decisions",)
        assert connection.execute("SELECT count(*) FROM ai_jobs WHERE job_type = 'action_items'").fetchone() == (0,)
        assert connection.execute("SELECT count(*) FROM ai_jobs WHERE job_type = 'risks_blockers'").fetchone() == (0,)
        with pytest.raises(IntegrityError, match="ck_ai_jobs_type"):
            connection.execute(
                """
                INSERT INTO ai_jobs
                    (id, organisation_id, meeting_id, transcript_id,
                     transcript_version, job_type, requested_by_user_id,
                     idempotency_key)
                VALUES
                    ('action-items-job-after-downgrade', 'organisation-1',
                     'meeting-1', 'transcript-1', 1, 'action_items',
                     'user-1', 'action-items-after-downgrade')
                """
            )

    command.upgrade(configuration, "head")
    with connect(database_path) as connection:
        assert connection.execute("SELECT version_num FROM alembic_version").fetchone() == ("0010_risks_blockers",)
        connection.execute(
            """
            INSERT INTO ai_jobs
                (id, organisation_id, meeting_id, transcript_id,
                 transcript_version, job_type, requested_by_user_id,
                 idempotency_key)
            VALUES
                ('action-items-job-after-reupgrade', 'organisation-1',
                 'meeting-1', 'transcript-1', 1, 'action_items',
                 'user-1', 'action-items-after-reupgrade')
            """
        )

    command.downgrade(configuration, "0007_executive_summary")
    with connect(database_path) as connection:
        assert connection.execute("SELECT version_num FROM alembic_version").fetchone() == ("0007_executive_summary",)
        assert connection.execute("SELECT count(*) FROM ai_jobs WHERE job_type = 'decisions'").fetchone() == (0,)
        with pytest.raises(IntegrityError, match="ck_ai_jobs_type"):
            connection.execute(
                """
                INSERT INTO ai_jobs
                    (id, organisation_id, meeting_id, transcript_id,
                     transcript_version, job_type, requested_by_user_id,
                     idempotency_key)
                VALUES
                    ('decisions-job-after-downgrade', 'organisation-1',
                     'meeting-1', 'transcript-1', 1, 'decisions',
                     'user-1', 'decisions-after-downgrade')
                """
            )

    command.upgrade(configuration, "head")
    command.downgrade(configuration, "0006_ai_worker_queue")
    with connect(database_path) as connection:
        assert connection.execute("SELECT version_num FROM alembic_version").fetchone() == ("0006_ai_worker_queue",)
        with pytest.raises(IntegrityError, match="ck_ai_jobs_type"):
            connection.execute(
                """
                INSERT INTO ai_jobs
                    (id, organisation_id, meeting_id, transcript_id,
                     transcript_version, job_type, requested_by_user_id,
                     idempotency_key)
                VALUES
                    ('executive-job-after-downgrade', 'organisation-1',
                     'meeting-1', 'transcript-1', 1, 'executive_summary',
                     'user-1', 'executive-after-downgrade')
                """
            )

    command.upgrade(configuration, "head")
    with connect(database_path) as connection:
        assert connection.execute("SELECT version_num FROM alembic_version").fetchone() == ("0010_risks_blockers",)
        connection.execute(
            """
            INSERT INTO ai_jobs
                (id, organisation_id, meeting_id, transcript_id,
                 transcript_version, job_type, requested_by_user_id,
                 idempotency_key)
            VALUES
                ('executive-job-1', 'organisation-1', 'meeting-1',
                 'transcript-1', 1, 'executive_summary', 'user-1',
                 'executive-migration-test')
            """
        )
        connection.execute(
            """
            INSERT INTO ai_artifacts
                (id, organisation_id, meeting_id, transcript_id,
                 transcript_version, job_id, artifact_type, artifact_version,
                 schema_version, content_json)
            VALUES
                ('executive-artifact-1', 'organisation-1', 'meeting-1',
                 'transcript-1', 1, 'executive-job-1',
                 'executive_summary', 1, 1,
                 '{"executive_summary":"Validated migration summary.",
                   "meeting_type":"other","sentiment":"neutral",
                   "confidence":0.8}')
            """
        )

    command.downgrade(configuration, "0005_ai_domain_services")
    with connect(database_path) as connection:
        job_columns_after_worker_downgrade = {
            row[1] for row in connection.execute("PRAGMA table_info(ai_jobs)").fetchall()
        }
        assert "worker_id" not in job_columns_after_worker_downgrade
        assert "heartbeat_at" not in job_columns_after_worker_downgrade
        assert connection.execute("SELECT version_num FROM alembic_version").fetchone() == ("0005_ai_domain_services",)

    command.upgrade(configuration, "head")
    with connect(database_path) as connection:
        job_columns_after_worker_reupgrade = {
            row[1] for row in connection.execute("PRAGMA table_info(ai_jobs)").fetchall()
        }
        assert {"worker_id", "heartbeat_at"}.issubset(job_columns_after_worker_reupgrade)
        assert connection.execute("SELECT version_num FROM alembic_version").fetchone() == ("0010_risks_blockers",)

    command.downgrade(configuration, "0004_ai_database_foundation")
    with connect(database_path) as connection:
        audit_columns_after_domain_downgrade = {
            row[1] for row in connection.execute("PRAGMA table_info(meeting_audit_events)").fetchall()
        }
        assert "metadata_json" not in audit_columns_after_domain_downgrade
        assert connection.execute("SELECT version_num FROM alembic_version").fetchone() == (
            "0004_ai_database_foundation",
        )

    command.upgrade(configuration, "head")
    with connect(database_path) as connection:
        assert connection.execute("SELECT version_num FROM alembic_version").fetchone() == ("0010_risks_blockers",)

    command.downgrade(configuration, "0003_meeting_domain")
    with connect(database_path) as connection:
        tables_after_downgrade = {
            row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'").fetchall()
        }
        assert {
            "meetings",
            "meeting_participants",
            "transcripts",
            "meeting_audit_events",
        }.issubset(tables_after_downgrade)
        assert not {"ai_jobs", "ai_artifacts"} & tables_after_downgrade
        assert connection.execute("SELECT version_num FROM alembic_version").fetchone() == ("0003_meeting_domain",)

    command.upgrade(configuration, "head")
    with connect(database_path) as connection:
        tables_after_reupgrade = {
            row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'").fetchall()
        }
        assert {"ai_jobs", "ai_artifacts"}.issubset(tables_after_reupgrade)
        assert connection.execute("SELECT version_num FROM alembic_version").fetchone() == ("0010_risks_blockers",)

    command.downgrade(configuration, "0002_core_business_entities")
    with connect(database_path) as connection:
        tables_after_meeting_downgrade = {
            row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'").fetchall()
        }
        assert {"companies", "contacts", "opportunities", "tasks"}.issubset(tables_after_meeting_downgrade)
    assert (
        not {
            "meetings",
            "meeting_participants",
            "transcripts",
            "meeting_audit_events",
        }
        & tables_after_meeting_downgrade
    )

    command.downgrade(configuration, "0001_initial_schema")
    with connect(database_path) as connection:
        tables_after_business_downgrade = {
            row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'").fetchall()
        }
    assert (
        not {
            "companies",
            "contacts",
            "opportunities",
            "tasks",
        }
        & tables_after_business_downgrade
    )


def test_postgresql_worker_migration_downgrade_and_reupgrade() -> None:
    database_url = os.getenv("DATABASE_URL", "")
    if not database_url.startswith(("postgresql", "postgres")):
        pytest.skip("A PostgreSQL DATABASE_URL is required for migration integration tests.")

    configuration = Config("alembic.ini")

    async def inspect_worker_schema(expected_present: bool) -> None:
        engine = create_async_engine(database_url)
        try:
            async with engine.connect() as connection:
                columns = set(
                    await connection.scalars(
                        text(
                            """
                            SELECT column_name
                            FROM information_schema.columns
                            WHERE table_schema = 'public'
                                AND table_name = 'ai_jobs'
                            """
                        )
                    )
                )
                function_present = bool(
                    await connection.scalar(
                        text(
                            """
                            SELECT count(*)
                            FROM pg_proc
                            WHERE proname =
                                'revenueos_ai_worker_eligible_organisations'
                            """
                        )
                    )
                )
                version = await connection.scalar(text("SELECT version_num FROM alembic_version"))
                if expected_present:
                    assert {"worker_id", "heartbeat_at"}.issubset(columns)
                    assert function_present is True
                    assert version == "0010_risks_blockers"
                else:
                    assert not {"worker_id", "heartbeat_at"} & columns
                    assert function_present is False
                    assert version == "0005_ai_domain_services"
        finally:
            await engine.dispose()

    try:
        command.downgrade(configuration, "0005_ai_domain_services")
        asyncio.run(inspect_worker_schema(False))
    finally:
        command.upgrade(configuration, "head")

    asyncio.run(inspect_worker_schema(True))
    command.check(configuration)
