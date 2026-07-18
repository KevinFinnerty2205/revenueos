from pathlib import Path
from sqlite3 import IntegrityError, connect

import pytest
from alembic import command
from alembic.config import Config


def test_migrations_upgrade_downgrade_and_reupgrade_ai_database_foundation(
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
        assert connection.execute("SELECT version_num FROM alembic_version").fetchone() == (
            "0004_ai_database_foundation",
        )
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
        artifact_columns = {row[1]: row[3] for row in connection.execute("PRAGMA table_info(ai_artifacts)").fetchall()}
        assert artifact_columns["organisation_id"] == 1
        assert artifact_columns["job_id"] == 1
        assert artifact_columns["artifact_version"] == 1
        assert artifact_columns["content_json"] == 1
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
        assert connection.execute("SELECT version_num FROM alembic_version").fetchone() == (
            "0004_ai_database_foundation",
        )

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
