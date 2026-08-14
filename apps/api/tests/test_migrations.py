import asyncio
import os
import uuid
from pathlib import Path
from sqlite3 import IntegrityError, connect

import pytest
from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine


def test_migration_revision_identifiers_fit_alembic_version_column() -> None:
    configuration = Config("alembic.ini")
    script = ScriptDirectory.from_config(configuration)

    revision_ids = [revision.revision for revision in script.walk_revisions()]

    assert revision_ids
    assert all(len(revision_id) <= 32 for revision_id in revision_ids)


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
            "revenue_brain_snapshots",
            "revenue_brain_insights",
            "opportunity_audit_events",
            "organisation_beta_settings",
            "data_notice_acknowledgements",
            "onboarding_progress",
            "ai_usage_counters",
            "beta_feedback",
            "beta_data_requests",
            "beta_system_events",
            "interactions",
            "capture_sessions",
            "evidence",
            "interaction_audit_events",
            "pre_interaction_briefs",
            "debrief_sessions",
            "debrief_turns",
            "evidence_fragments",
            "candidate_evidence",
            "interaction_intelligence_snapshots",
            "revenue_brain_interaction_snapshots",
            "visual_assets",
            "visual_candidate_evidence",
        }.issubset(tables)
        assert connection.execute("SELECT version_num FROM alembic_version").fetchone() == ("0024_visual_evidence",)
        opportunity_columns = {
            row[1]: row[3] for row in connection.execute("PRAGMA table_info(opportunities)").fetchall()
        }
        assert opportunity_columns["status"] == 1
        assert opportunity_columns["estimated_value"] == 0
        assert opportunity_columns["currency"] == 0
        assert "probability" not in opportunity_columns
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
        assert meeting_columns["opportunity_id"] == 0
        assert meeting_columns["interaction_id"] == 1
        interaction_columns = {
            row[1]: row[3] for row in connection.execute("PRAGMA table_info(interactions)").fetchall()
        }
        assert interaction_columns["organisation_id"] == 1
        assert interaction_columns["interaction_type"] == 1
        assert interaction_columns["lifecycle_status"] == 1
        assert interaction_columns["created_by_user_id"] == 1
        brief_columns = {
            row[1]: row[3] for row in connection.execute("PRAGMA table_info(pre_interaction_briefs)").fetchall()
        }
        assert brief_columns["organisation_id"] == 1
        assert brief_columns["interaction_id"] == 1
        assert brief_columns["source_context_fingerprint"] == 1
        assert brief_columns["content_json"] == 1
        assert brief_columns["source_references_json"] == 1
        assert brief_columns["reviewed_at"] == 0
        evidence_columns = {row[1]: row[3] for row in connection.execute("PRAGMA table_info(evidence)").fetchall()}
        assert evidence_columns["organisation_id"] == 1
        assert evidence_columns["origin_class"] == 1
        assert evidence_columns["support_class"] == 1
        assert evidence_columns["validation_state"] == 1
        assert not {"raw_text", "content", "body", "blob"} & set(evidence_columns)
        debrief_columns = {
            row[1]: row[3] for row in connection.execute("PRAGMA table_info(debrief_sessions)").fetchall()
        }
        assert debrief_columns["organisation_id"] == 1
        assert debrief_columns["interaction_id"] == 1
        assert debrief_columns["safety_confirmed_at"] == 1
        assert debrief_columns["voice_processing_acknowledged_at"] == 0
        turn_columns = {row[1]: row[3] for row in connection.execute("PRAGMA table_info(debrief_turns)").fetchall()}
        assert turn_columns["answer_text"] == 1
        assert not {"audio", "audio_bytes", "audio_blob", "recording"} & set(turn_columns)
        candidate_columns = {
            row[1]: row[3] for row in connection.execute("PRAGMA table_info(candidate_evidence)").fetchall()
        }
        assert candidate_columns["origin_class"] == 1
        assert candidate_columns["support_class"] == 1
        assert candidate_columns["validation_state"] == 1
        visual_columns = {row[1]: row[3] for row in connection.execute("PRAGMA table_info(visual_assets)").fetchall()}
        assert visual_columns["organisation_id"] == 1
        assert visual_columns["interaction_id"] == 1
        assert visual_columns["source_ownership"] == 1
        assert visual_columns["storage_key"] == 1
        assert visual_columns["processing_status"] == 1
        assert not {"image", "image_bytes", "blob", "content"} & set(visual_columns)
        visual_candidate_columns = {
            row[1]: row[3] for row in connection.execute("PRAGMA table_info(visual_candidate_evidence)").fetchall()
        }
        assert visual_candidate_columns["source_visual_id"] == 1
        assert visual_candidate_columns["source_ownership"] == 1
        assert visual_candidate_columns["origin_class"] == 1
        assert visual_candidate_columns["support_classification"] == 1
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
        assert job_columns["composition_tone"] == 0
        artifact_columns = {row[1]: row[3] for row in connection.execute("PRAGMA table_info(ai_artifacts)").fetchall()}
        assert artifact_columns["organisation_id"] == 1
        assert artifact_columns["job_id"] == 1
        assert artifact_columns["artifact_version"] == 1
        assert artifact_columns["content_json"] == 1
        snapshot_columns = {
            row[1]: row[3] for row in connection.execute("PRAGMA table_info(revenue_brain_snapshots)").fetchall()
        }
        assert snapshot_columns == {
            "id": 1,
            "organisation_id": 1,
            "company_id": 1,
            "opportunity_id": 0,
            "meeting_id": 1,
            "transcript_version_id": 1,
            "created_at": 1,
            "summary_reference": 1,
            "buying_signals_reference": 1,
            "objections_reference": 1,
            "stakeholders_reference": 1,
            "decisions_reference": 1,
            "actions_reference": 1,
            "risks_reference": 1,
            "questions_reference": 1,
            "next_best_action_reference": 1,
            "version": 1,
        }
        insight_columns = {
            row[1]: row[3] for row in connection.execute("PRAGMA table_info(revenue_brain_insights)").fetchall()
        }
        assert insight_columns == {
            "id": 1,
            "organisation_id": 1,
            "company_id": 1,
            "opportunity_id": 0,
            "scope": 1,
            "scope_target_id": 1,
            "from_snapshot_id": 1,
            "to_snapshot_id": 1,
            "reasoning_version": 1,
            "status": 1,
            "content_json": 1,
            "created_at": 1,
        }
        membership_columns = {
            row[1]: row[3] for row in connection.execute("PRAGMA table_info(organisation_memberships)").fetchall()
        }
        assert membership_columns["status"] == 1
        assert membership_columns["updated_at"] == 1
        user_columns = {row[1]: row[3] for row in connection.execute("PRAGMA table_info(users)").fetchall()}
        assert user_columns["status"] == 1
        organisation_columns = {
            row[1]: row[3] for row in connection.execute("PRAGMA table_info(organisations)").fetchall()
        }
        assert organisation_columns["external_auth_id"] == 0
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
        snapshot_indexes = {
            row[1] for row in connection.execute("PRAGMA index_list(revenue_brain_snapshots)").fetchall()
        }
        assert {
            "ix_revenue_brain_snapshots_organisation_company_created",
            "ix_revenue_brain_snapshots_organisation_meeting",
        }.issubset(snapshot_indexes)
        snapshot_triggers = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'trigger' AND tbl_name = 'revenue_brain_snapshots'"
            ).fetchall()
        }
        assert snapshot_triggers == {
            "revenue_brain_snapshots_prevent_update",
            "revenue_brain_snapshots_prevent_delete",
        }
        insight_indexes = {row[1] for row in connection.execute("PRAGMA index_list(revenue_brain_insights)").fetchall()}
        assert {
            "ix_revenue_brain_insights_organisation_company_created",
            "ix_revenue_brain_insights_organisation_opportunity_created",
        }.issubset(insight_indexes)
        insight_triggers = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'trigger' AND tbl_name = 'revenue_brain_insights'"
            ).fetchall()
        }
        assert insight_triggers == {
            "revenue_brain_insights_prevent_update",
            "revenue_brain_insights_prevent_delete",
        }
        interaction_intelligence_triggers = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master "
                "WHERE type = 'trigger' AND tbl_name = 'interaction_intelligence_snapshots'"
            ).fetchall()
        }
        assert interaction_intelligence_triggers == {
            "interaction_intelligence_snapshots_prevent_update",
        }
        debrief_snapshot_triggers = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master "
                "WHERE type = 'trigger' AND tbl_name = 'revenue_brain_interaction_snapshots'"
            ).fetchall()
        }
        assert debrief_snapshot_triggers == {
            "revenue_brain_interaction_snapshots_prevent_update",
        }
        visual_review_triggers = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'trigger' AND tbl_name = 'visual_candidate_evidence'"
            ).fetchall()
        }
        assert visual_review_triggers == {"visual_candidate_evidence_review_guard"}

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
        connection.execute(
            """
            INSERT INTO ai_jobs
                (id, organisation_id, meeting_id, transcript_id,
                 transcript_version, job_type, requested_by_user_id,
                 idempotency_key)
            VALUES
                ('next-best-action-job-1', 'organisation-1', 'meeting-1',
                 'transcript-1', 1, 'next_best_action', 'user-1',
                 'next-best-action-migration-test')
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
        connection.execute(
            """
            INSERT INTO revenue_brain_snapshots
                (id, organisation_id, company_id, meeting_id,
                 transcript_version_id, summary_reference,
                 buying_signals_reference, objections_reference,
                 stakeholders_reference, decisions_reference,
                 actions_reference, risks_reference, questions_reference,
                 next_best_action_reference)
            VALUES
                ('snapshot-1', 'organisation-1', 'company-1', 'meeting-1',
                 'transcript-version-1', 'artifact-1', 'artifact-1',
                 'artifact-1', 'artifact-1', 'artifact-1', 'artifact-1',
                 'artifact-1', 'artifact-1', 'artifact-1')
            """
        )
        with pytest.raises(IntegrityError, match="append only"):
            connection.execute(
                """
                UPDATE revenue_brain_snapshots
                SET version = 2
                WHERE id = 'snapshot-1'
                """
            )
        with pytest.raises(IntegrityError, match="append only"):
            connection.execute(
                """
                DELETE FROM revenue_brain_snapshots
                WHERE id = 'snapshot-1'
                """
            )
        with pytest.raises(IntegrityError, match="UNIQUE constraint failed"):
            connection.execute(
                """
                INSERT INTO revenue_brain_snapshots
                    (id, organisation_id, company_id, meeting_id,
                     transcript_version_id, summary_reference,
                     buying_signals_reference, objections_reference,
                     stakeholders_reference, decisions_reference,
                     actions_reference, risks_reference, questions_reference,
                     next_best_action_reference)
                VALUES
                    ('snapshot-duplicate', 'organisation-1', 'company-1',
                     'meeting-1', 'transcript-version-1', 'artifact-1',
                     'artifact-1', 'artifact-1', 'artifact-1', 'artifact-1',
                     'artifact-1', 'artifact-1', 'artifact-1', 'artifact-1')
                """
            )
        connection.execute(
            """
            INSERT INTO revenue_brain_snapshots
                (id, organisation_id, company_id, meeting_id,
                 transcript_version_id, summary_reference,
                 buying_signals_reference, objections_reference,
                 stakeholders_reference, decisions_reference,
                 actions_reference, risks_reference, questions_reference,
                 next_best_action_reference)
            VALUES
                ('snapshot-2', 'organisation-1', 'company-1', 'meeting-1',
                 'transcript-version-2', 'artifact-1', 'artifact-1',
                 'artifact-1', 'artifact-1', 'artifact-1', 'artifact-1',
                 'artifact-1', 'artifact-1', 'artifact-1')
            """
        )
        connection.execute(
            """
            INSERT INTO revenue_brain_insights
                (id, organisation_id, company_id, scope, scope_target_id,
                 from_snapshot_id, to_snapshot_id, content_json)
            VALUES
                ('insight-1', 'organisation-1', 'company-1', 'account',
                 'company-1', 'snapshot-1', 'snapshot-2',
                 '{"scope":"account","changes":[]}')
            """
        )
        with pytest.raises(IntegrityError, match="append only"):
            connection.execute(
                """
                UPDATE revenue_brain_insights
                SET reasoning_version = 2
                WHERE id = 'insight-1'
                """
            )
        with pytest.raises(IntegrityError, match="append only"):
            connection.execute(
                """
                DELETE FROM revenue_brain_insights
                WHERE id = 'insight-1'
                """
            )
        with pytest.raises(IntegrityError, match="UNIQUE constraint failed"):
            connection.execute(
                """
                INSERT INTO revenue_brain_insights
                    (id, organisation_id, company_id, scope, scope_target_id,
                     from_snapshot_id, to_snapshot_id, content_json)
                VALUES
                    ('insight-duplicate', 'organisation-1', 'company-1',
                     'account', 'company-1', 'snapshot-1', 'snapshot-2',
                     '{"scope":"account","changes":[]}')
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
        connection.execute(
            """
            INSERT INTO ai_jobs
                (id, organisation_id, meeting_id, transcript_id,
                 transcript_version, job_type, requested_by_user_id,
                 idempotency_key)
            VALUES
                ('open-questions-job-1', 'organisation-1', 'meeting-1',
                 'transcript-1', 1, 'open_questions', 'user-1',
                 'open-questions-migration-test')
            """
        )
        connection.execute(
            """
            INSERT INTO ai_artifacts
                (id, organisation_id, meeting_id, transcript_id,
                 transcript_version, job_id, artifact_type, artifact_version,
                 schema_version, content_json)
            VALUES
                ('open-questions-artifact-1', 'organisation-1', 'meeting-1',
                 'transcript-1', 1, 'open-questions-job-1', 'open_questions',
                 1, 1, '{"open_questions":[]}')
            """
        )
        connection.execute(
            """
            INSERT INTO ai_jobs
                (id, organisation_id, meeting_id, transcript_id,
                 transcript_version, job_type, requested_by_user_id,
                 idempotency_key, composition_tone)
            VALUES
                ('follow-up-email-job-1', 'organisation-1', 'meeting-1',
                 'transcript-1', 1, 'follow_up_email', 'user-1',
                 'follow-up-email-migration-test', 'professional')
            """
        )
        connection.execute(
            """
            INSERT INTO ai_jobs
                (id, organisation_id, meeting_id, transcript_id,
                 transcript_version, job_type, requested_by_user_id,
                 idempotency_key)
            VALUES
                ('buying-signals-job-1', 'organisation-1', 'meeting-1',
                 'transcript-1', 1, 'buying_signals', 'user-1',
                 'buying-signals-migration-test')
            """
        )
        connection.execute(
            """
            INSERT INTO ai_artifacts
                (id, organisation_id, meeting_id, transcript_id,
                 transcript_version, job_id, artifact_type, artifact_version,
                 schema_version, content_json)
            VALUES
                ('buying-signals-artifact-1', 'organisation-1', 'meeting-1',
                 'transcript-1', 1, 'buying-signals-job-1',
                 'buying_signals', 1, 1,
                 '{"signals":[],"overall_momentum":"insufficient_evidence",' ||
                 '"momentum_summary":"There was not enough transcript evidence.",' ||
                 '"confidence":0.2}')
            """
        )
        connection.execute(
            """
            INSERT INTO ai_jobs
                (id, organisation_id, meeting_id, transcript_id,
                 transcript_version, job_type, requested_by_user_id,
                 idempotency_key)
            VALUES
                ('objections-job-1', 'organisation-1', 'meeting-1',
                 'transcript-1', 1, 'objections_competitive_signals', 'user-1',
                 'objections-migration-test')
            """
        )
        connection.execute(
            """
            INSERT INTO ai_artifacts
                (id, organisation_id, meeting_id, transcript_id,
                 transcript_version, job_id, artifact_type, artifact_version,
                 schema_version, content_json)
            VALUES
                ('objections-artifact-1', 'organisation-1', 'meeting-1',
                 'transcript-1', 1, 'objections-job-1',
                 'objections_competitive_signals', 1, 1,
                 '{"objections":[],"competitors":[],' ||
                 '"overall_objection_pressure":"none",' ||
                 '"summary":"No objections or competitive signals were identified."}')
            """
        )
        connection.execute(
            """
            INSERT INTO ai_jobs
                (id, organisation_id, meeting_id, transcript_id,
                 transcript_version, job_type, requested_by_user_id,
                 idempotency_key)
            VALUES
                ('stakeholder-job-1', 'organisation-1', 'meeting-1',
                 'transcript-1', 1, 'stakeholder_intelligence', 'user-1',
                 'stakeholder-migration-test')
            """
        )
        connection.execute(
            """
            INSERT INTO ai_artifacts
                (id, organisation_id, meeting_id, transcript_id,
                 transcript_version, job_id, artifact_type, artifact_version,
                 schema_version, content_json)
            VALUES
                ('stakeholder-artifact-1', 'organisation-1', 'meeting-1',
                 'transcript-1', 1, 'stakeholder-job-1',
                 'stakeholder_intelligence', 1, 1,
                 '{"stakeholders":[],"role_coverage":{' ||
                 '"economic_buyer":"not_discussed",' ||
                 '"decision_maker":"not_discussed",' ||
                 '"champion":"not_discussed",' ||
                 '"technical_buyer":"not_discussed",' ||
                 '"procurement":"not_discussed",' ||
                 '"legal_security":"not_discussed"},' ||
                 '"stakeholder_summary":"There was not enough evidence to identify stakeholder roles reliably.",' ||
                 '"confidence":0.3}')
            """
        )
        connection.execute(
            """
            INSERT INTO ai_artifacts
                (id, organisation_id, meeting_id, transcript_id,
                 transcript_version, job_id, artifact_type, artifact_version,
                 schema_version, content_json)
            VALUES
                ('follow-up-email-artifact-1', 'organisation-1', 'meeting-1',
                 'transcript-1', 1, 'follow-up-email-job-1',
                 'follow_up_email', 1, 1,
                 '{"subject":"Meeting follow-up","greeting":"Hello,",' ||
                 '"summary":"Validated migration follow-up summary.",' ||
                 '"decisions":[],"action_items":[],"open_questions":[],' ||
                 '"closing":"Kind regards,","tone":"professional",' ||
                 '"confidence":0.95}')
            """
        )
        with pytest.raises(IntegrityError, match="ck_ai_jobs_composition_tone"):
            connection.execute(
                """
                INSERT INTO ai_jobs
                    (id, organisation_id, meeting_id, transcript_id,
                     transcript_version, job_type, requested_by_user_id,
                     idempotency_key)
                VALUES
                    ('follow-up-email-without-tone', 'organisation-1',
                     'meeting-1', 'transcript-1', 1, 'follow_up_email',
                     'user-1', 'follow-up-email-without-tone')
                """
            )

    command.downgrade(configuration, "0008_decisions")
    with connect(database_path) as connection:
        assert connection.execute("SELECT version_num FROM alembic_version").fetchone() == ("0008_decisions",)
        assert connection.execute("SELECT count(*) FROM ai_jobs WHERE job_type = 'action_items'").fetchone() == (0,)
        assert connection.execute("SELECT count(*) FROM ai_jobs WHERE job_type = 'risks_blockers'").fetchone() == (0,)
        assert connection.execute("SELECT count(*) FROM ai_jobs WHERE job_type = 'open_questions'").fetchone() == (0,)
        assert connection.execute("SELECT count(*) FROM ai_jobs WHERE job_type = 'follow_up_email'").fetchone() == (0,)
        assert connection.execute("SELECT count(*) FROM ai_jobs WHERE job_type = 'buying_signals'").fetchone() == (0,)
        assert connection.execute(
            "SELECT count(*) FROM ai_jobs WHERE job_type = 'objections_competitive_signals'"
        ).fetchone() == (0,)
        assert connection.execute(
            "SELECT count(*) FROM ai_jobs WHERE job_type = 'stakeholder_intelligence'"
        ).fetchone() == (0,)
        assert connection.execute("SELECT count(*) FROM ai_jobs WHERE job_type = 'next_best_action'").fetchone() == (0,)
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
        assert connection.execute("SELECT version_num FROM alembic_version").fetchone() == ("0024_visual_evidence",)
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
        assert connection.execute("SELECT version_num FROM alembic_version").fetchone() == ("0024_visual_evidence",)
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
        assert connection.execute("SELECT version_num FROM alembic_version").fetchone() == ("0024_visual_evidence",)

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
        assert connection.execute("SELECT version_num FROM alembic_version").fetchone() == ("0024_visual_evidence",)

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
        assert (
            not {
                "ai_jobs",
                "ai_artifacts",
                "revenue_brain_snapshots",
                "revenue_brain_insights",
            }
            & tables_after_downgrade
        )
        assert connection.execute("SELECT version_num FROM alembic_version").fetchone() == ("0003_meeting_domain",)

    command.upgrade(configuration, "head")
    with connect(database_path) as connection:
        tables_after_reupgrade = {
            row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'").fetchall()
        }
        assert {
            "ai_jobs",
            "ai_artifacts",
            "revenue_brain_snapshots",
            "revenue_brain_insights",
            "opportunity_audit_events",
        }.issubset(tables_after_reupgrade)
        assert connection.execute("SELECT version_num FROM alembic_version").fetchone() == ("0024_visual_evidence",)

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


def test_revenue_brain_reasoning_is_the_single_head_after_snapshots(
    tmp_path: Path,
    monkeypatch: object,
) -> None:
    database_path = tmp_path / "migration-ordering.db"
    monkeypatch.setenv(  # type: ignore[attr-defined]
        "DATABASE_URL",
        f"sqlite+aiosqlite:///{database_path}",
    )
    configuration = Config("alembic.ini")

    command.upgrade(configuration, "0018_revenue_brain")
    with connect(database_path) as connection:
        tables = {
            row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'").fetchall()
        }
        assert "opportunity_audit_events" in tables
        assert "revenue_brain_snapshots" in tables
        assert "revenue_brain_insights" not in tables
        assert connection.execute("SELECT version_num FROM alembic_version").fetchone() == ("0018_revenue_brain",)

    command.upgrade(configuration, "head")
    with connect(database_path) as connection:
        tables = {
            row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'").fetchall()
        }
        assert {
            "opportunity_audit_events",
            "revenue_brain_snapshots",
            "revenue_brain_insights",
        }.issubset(tables)
        assert connection.execute("SELECT version_num FROM alembic_version").fetchone() == ("0024_visual_evidence",)

    command.downgrade(configuration, "0018_revenue_brain")
    with connect(database_path) as connection:
        tables = {
            row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'").fetchall()
        }
        meeting_columns = {row[1] for row in connection.execute("PRAGMA table_info(meetings)").fetchall()}
        assert "opportunity_audit_events" in tables
        assert "revenue_brain_snapshots" in tables
        assert "revenue_brain_insights" not in tables
        assert "opportunity_id" in meeting_columns

    command.upgrade(configuration, "head")
    with connect(database_path) as connection:
        assert "revenue_brain_insights" in {
            row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'").fetchall()
        }
        assert connection.execute("SELECT version_num FROM alembic_version").fetchone() == ("0024_visual_evidence",)


def test_interaction_migration_backfills_multiple_tenants_and_reupgrades_deterministically(
    tmp_path: Path,
    monkeypatch: object,
) -> None:
    database_path = tmp_path / "interaction-migration.db"
    database_url = f"sqlite+aiosqlite:///{database_path}"
    monkeypatch.setenv("DATABASE_URL", database_url)  # type: ignore[attr-defined]
    configuration = Config("alembic.ini")
    script = ScriptDirectory.from_config(configuration)
    assert [revision.revision for revision in script.walk_revisions()][:3] == [
        "0024_visual_evidence",
        "0023_ai_debrief_voice_journal",
        "0022_pre_interaction_brief",
    ]
    assert script.get_heads() == ["0024_visual_evidence"]
    command.upgrade(configuration, "0020_private_beta_readiness")

    organisation_a = uuid.uuid4()
    organisation_b = uuid.uuid4()
    user_a = uuid.uuid4()
    user_b = uuid.uuid4()
    meeting_a_one = uuid.uuid4()
    meeting_a_two = uuid.uuid4()
    meeting_b = uuid.uuid4()
    meetings = (
        (meeting_a_one, organisation_a, user_a, "remote", "completed", "Tenant A completed"),
        (meeting_a_two, organisation_a, user_a, "in_person", "scheduled", "Tenant A planned"),
        (meeting_b, organisation_b, user_b, "phone", "cancelled", "Tenant B cancelled"),
    )
    with connect(database_path) as connection:
        connection.execute("PRAGMA foreign_keys=ON")
        for organisation_id, user_id, label in (
            (organisation_a, user_a, "a"),
            (organisation_b, user_b, "b"),
        ):
            connection.execute(
                "INSERT INTO organisations (id, name, slug) VALUES (?, ?, ?)",
                (organisation_id.hex, f"Tenant {label.upper()}", f"tenant-{label}"),
            )
            connection.execute(
                """
                INSERT INTO users (id, external_auth_id, email, display_name)
                VALUES (?, ?, ?, ?)
                """,
                (
                    user_id.hex,
                    f"user-{label}",
                    f"user-{label}@example.test",
                    f"User {label.upper()}",
                ),
            )
            connection.execute(
                """
                INSERT INTO organisation_memberships (organisation_id, user_id, role)
                VALUES (?, ?, 'admin')
                """,
                (organisation_id.hex, user_id.hex),
            )
        for meeting_id, organisation_id, user_id, meeting_type, meeting_status, title in meetings:
            connection.execute(
                """
                INSERT INTO meetings
                    (id, organisation_id, title, meeting_date, meeting_type, status,
                     owner_user_id, created_by, updated_by)
                VALUES (?, ?, ?, '2026-07-20 10:00:00', ?, ?, ?, ?, ?)
                """,
                (
                    meeting_id.hex,
                    organisation_id.hex,
                    title,
                    meeting_type,
                    meeting_status,
                    user_id.hex,
                    user_id.hex,
                    user_id.hex,
                ),
            )

    command.upgrade(configuration, "head")
    expected = {
        meeting_id.hex: uuid.uuid5(
            uuid.UUID("cf709ef5-e59d-4ce2-9c93-547a4a5e5990"),
            f"{organisation_id}:{meeting_id}",
        ).hex
        for meeting_id, organisation_id, *_ in meetings
    }
    with connect(database_path) as connection:
        rows = connection.execute("SELECT id, organisation_id, interaction_id FROM meetings ORDER BY id").fetchall()
        assert len(rows) == 3
        assert {row[0]: row[2] for row in rows} == expected
        interaction_rows = connection.execute(
            """
            SELECT id, organisation_id, interaction_type, lifecycle_status,
                   title, creation_origin
            FROM interactions
            ORDER BY id
            """
        ).fetchall()
        assert len(interaction_rows) == 3
        assert {row[1] for row in interaction_rows} == {organisation_a.hex, organisation_b.hex}
        assert {row[2] for row in interaction_rows} == {
            "online_meeting",
            "face_to_face_meeting",
            "phone_call",
        }
        assert {row[3] for row in interaction_rows} == {"planned", "completed", "cancelled"}
        assert {row[5] for row in interaction_rows} == {"meeting_compatibility"}
        with pytest.raises(IntegrityError):
            connection.execute(
                "UPDATE meetings SET interaction_id = ? WHERE id = ?",
                (expected[meeting_a_one.hex], meeting_a_two.hex),
            )

    command.downgrade(configuration, "0020_private_beta_readiness")
    with connect(database_path) as connection:
        tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        assert not {"interactions", "capture_sessions", "evidence", "interaction_audit_events"} & tables
        meeting_columns = {row[1] for row in connection.execute("PRAGMA table_info(meetings)")}
        assert "interaction_id" not in meeting_columns
        assert {row[0] for row in connection.execute("SELECT id FROM meetings")} == set(expected)

    command.upgrade(configuration, "head")
    with connect(database_path) as connection:
        assert connection.execute("SELECT version_num FROM alembic_version").fetchone() == ("0024_visual_evidence",)
        assert {row[0]: row[1] for row in connection.execute("SELECT id, interaction_id FROM meetings")} == expected
        assert connection.execute("SELECT count(*) FROM interactions").fetchone() == (3,)


def test_pre_interaction_brief_migration_is_immutable_and_reupgrades_cleanly(
    tmp_path: Path,
    monkeypatch: object,
) -> None:
    database_path = tmp_path / "pre-interaction-brief-migration.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite+aiosqlite:///{database_path}")  # type: ignore[attr-defined]
    configuration = Config("alembic.ini")
    command.upgrade(configuration, "0021_interaction_foundation")
    organisation_id = uuid.uuid4().hex
    user_id = uuid.uuid4().hex
    company_id = uuid.uuid4().hex
    opportunity_id = uuid.uuid4().hex
    interaction_id = uuid.uuid4().hex
    brief_id = uuid.uuid4().hex

    with connect(database_path) as connection:
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute(
            "INSERT INTO organisations (id, name, slug) VALUES (?, 'Brief tenant', ?)",
            (organisation_id, f"brief-{organisation_id}"),
        )
        connection.execute(
            "INSERT INTO users (id, external_auth_id, email, display_name) VALUES (?, ?, ?, 'Brief user')",
            (user_id, f"brief-user-{user_id}", f"{user_id}@example.test"),
        )
        connection.execute(
            "INSERT INTO organisation_memberships (organisation_id, user_id, role) VALUES (?, ?, 'admin')",
            (organisation_id, user_id),
        )
        connection.execute(
            "INSERT INTO companies (id, organisation_id, name, owner_user_id) VALUES (?, ?, 'Brief company', ?)",
            (company_id, organisation_id, user_id),
        )
        connection.execute(
            """
            INSERT INTO opportunities
                (id, organisation_id, company_id, name, stage, status, owner_user_id)
            VALUES (?, ?, ?, 'Brief opportunity', 'discovery', 'open', ?)
            """,
            (opportunity_id, organisation_id, company_id, user_id),
        )
        connection.execute(
            """
            INSERT INTO interactions
                (id, organisation_id, company_id, opportunity_id, interaction_type,
                 lifecycle_status, title, creation_origin, created_by_user_id)
            VALUES (?, ?, ?, ?, 'phone_call', 'planned', 'Brief call', 'manual', ?)
            """,
            (interaction_id, organisation_id, company_id, opportunity_id, user_id),
        )
        connection.commit()

    command.upgrade(configuration, "head")
    with connect(database_path) as connection:
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute(
            """
            INSERT INTO pre_interaction_briefs
                (id, organisation_id, interaction_id, company_id, opportunity_id,
                 source_context_fingerprint, brief_version, schema_version,
                 status, content_json, source_references_json, created_by_user_id)
            VALUES (?, ?, ?, ?, ?, ?, 1, 1, 'completed', ?, ?, ?)
            """,
            (
                brief_id,
                organisation_id,
                interaction_id,
                company_id,
                opportunity_id,
                "a" * 64,
                '{"headline":"Migration brief"}',
                '[{"capability":"interaction_metadata"}]',
                user_id,
            ),
        )
        with pytest.raises(IntegrityError, match="immutable"):
            connection.execute(
                'UPDATE pre_interaction_briefs SET content_json = \'{"headline":"Changed"}\' WHERE id = ?',
                (brief_id,),
            )
        connection.execute(
            "UPDATE pre_interaction_briefs SET reviewed_at = CURRENT_TIMESTAMP, reviewed_by_user_id = ? WHERE id = ?",
            (user_id, brief_id),
        )
        with pytest.raises(IntegrityError, match="append only"):
            connection.execute(
                "UPDATE pre_interaction_briefs SET reviewed_at = '2099-01-01 00:00:00' WHERE id = ?",
                (brief_id,),
            )
        with pytest.raises(IntegrityError):
            connection.execute(
                """
                INSERT INTO pre_interaction_briefs
                    (id, organisation_id, interaction_id, source_context_fingerprint,
                     brief_version, schema_version, status, content_json,
                     source_references_json, created_by_user_id)
                VALUES (?, ?, ?, ?, 2, 1, 'completed', '{}', '[]', ?)
                """,
                (uuid.uuid4().hex, organisation_id, interaction_id, "a" * 64, user_id),
            )

    command.downgrade(configuration, "0021_interaction_foundation")
    with connect(database_path) as connection:
        tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        assert "pre_interaction_briefs" not in tables

    command.upgrade(configuration, "head")
    with connect(database_path) as connection:
        assert connection.execute("SELECT count(*) FROM pre_interaction_briefs").fetchone() == (0,)
        assert connection.execute("SELECT version_num FROM alembic_version").fetchone() == ("0024_visual_evidence",)


def test_visual_evidence_migration_review_guard_and_downgrade_reupgrade(
    tmp_path: Path,
    monkeypatch: object,
) -> None:
    database_path = tmp_path / "visual-evidence-migration.db"
    monkeypatch.setenv(  # type: ignore[attr-defined]
        "DATABASE_URL",
        f"sqlite+aiosqlite:///{database_path}",
    )
    configuration = Config("alembic.ini")
    command.upgrade(configuration, "head")
    organisation_id = uuid.uuid4().hex
    user_id = uuid.uuid4().hex
    interaction_id = uuid.uuid4().hex
    visual_id = uuid.uuid4().hex
    evidence_id = uuid.uuid4().hex
    candidate_id = uuid.uuid4().hex

    with connect(database_path) as connection:
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute(
            "INSERT INTO organisations (id, name, slug) VALUES (?, 'Visual tenant', ?)",
            (organisation_id, f"visual-{organisation_id}"),
        )
        connection.execute(
            "INSERT INTO users (id, external_auth_id, email, display_name) VALUES (?, ?, ?, 'Visual user')",
            (user_id, f"visual-user-{user_id}", f"{user_id}@example.test"),
        )
        connection.execute(
            "INSERT INTO organisation_memberships (organisation_id, user_id, role) VALUES (?, ?, 'admin')",
            (organisation_id, user_id),
        )
        connection.execute(
            """
            INSERT INTO interactions
                (id, organisation_id, interaction_type, lifecycle_status, title,
                 creation_origin, created_by_user_id)
            VALUES (?, ?, 'workshop', 'completed', 'Visual workshop', 'manual', ?)
            """,
            (interaction_id, organisation_id, user_id),
        )
        connection.execute(
            """
            INSERT INTO capture_sessions
                (id, organisation_id, interaction_id, capture_type, status,
                 started_by_user_id, started_at)
            VALUES (?, ?, ?, 'visual_capture', 'capturing', ?, '2026-08-14 01:00:00')
            """,
            (visual_id, organisation_id, interaction_id, user_id),
        )
        connection.execute(
            """
            INSERT INTO evidence
                (id, organisation_id, interaction_id, capture_session_id, evidence_type,
                 origin_class, support_class, validation_state, captured_by_user_id,
                 lifecycle_status, retention_class)
            VALUES (?, ?, ?, ?, 'visual', 'customer_direct', 'direct', 'unreviewed',
                    ?, 'available', 'inherited')
            """,
            (evidence_id, organisation_id, interaction_id, visual_id, user_id),
        )
        connection.execute(
            """
            INSERT INTO visual_assets
                (id, organisation_id, interaction_id, capture_session_id, source_evidence_id,
                 captured_by_user_id, visual_type, source_ownership, display_filename,
                 storage_key, mime_type, byte_size, upload_byte_size, checksum_sha256,
                 upload_checksum_sha256, captured_at, upload_idempotency_key,
                 processing_status, storage_status, processing_attempts, upload_expires_at)
            VALUES (?, ?, ?, ?, ?, ?, 'whiteboard', 'customer_created', 'board.png', ?,
                    'image/png', 68, 68, ?, ?, '2026-08-14 01:00:00', 'migration-upload',
                    'review', 'available', 1, '2026-08-14 01:05:00')
            """,
            (
                visual_id,
                organisation_id,
                interaction_id,
                visual_id,
                evidence_id,
                user_id,
                f"{organisation_id}/{interaction_id}/visual.png",
                "a" * 64,
                "a" * 64,
            ),
        )
        connection.execute(
            """
            INSERT INTO visual_candidate_evidence
                (id, organisation_id, interaction_id, source_visual_id, evidence_category,
                 statement, original_statement, statement_fingerprint, source_ownership,
                 origin_class, support_classification, validation_state, review_state,
                 conflict_state)
            VALUES (?, ?, ?, ?, 'customer_request', 'Requested a pilot.',
                    'Requested a pilot.', ?, 'customer_created', 'ai_inferred', 'direct',
                    'unreviewed', 'pending', 'not_assessed')
            """,
            (candidate_id, organisation_id, interaction_id, visual_id, "b" * 64),
        )
        connection.execute(
            """
            UPDATE visual_candidate_evidence
            SET review_state = 'rejected', validation_state = 'rejected',
                reviewed_by_user_id = ?, reviewed_at = '2026-08-14 01:02:00'
            WHERE id = ?
            """,
            (user_id, candidate_id),
        )
        with pytest.raises(IntegrityError, match="Reviewed visual candidate evidence is immutable"):
            connection.execute(
                "UPDATE visual_candidate_evidence SET statement = 'Changed.' WHERE id = ?",
                (candidate_id,),
            )

    command.downgrade(configuration, "0023_ai_debrief_voice_journal")
    with connect(database_path) as connection:
        tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        assert "visual_assets" not in tables
        assert "visual_candidate_evidence" not in tables
        assert connection.execute("SELECT version_num FROM alembic_version").fetchone() == (
            "0023_ai_debrief_voice_journal",
        )

    command.upgrade(configuration, "head")
    with connect(database_path) as connection:
        assert connection.execute("SELECT count(*) FROM visual_assets").fetchone() == (0,)
        assert connection.execute("SELECT version_num FROM alembic_version").fetchone() == ("0024_visual_evidence",)


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
                    assert version == "0024_visual_evidence"
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
