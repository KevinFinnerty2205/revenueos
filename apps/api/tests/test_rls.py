from __future__ import annotations

import asyncio
import os
import uuid
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from revenueos.ai_repositories import AIJobRepository
from revenueos.ai_services import AIArtifactService, AIJobService
from revenueos.ai_worker_repositories import AIWorkerRepository
from revenueos.auth import VerifiedIdentity, _resolve_identity
from revenueos.beta_services import BetaService
from revenueos.config import Settings
from revenueos.database import set_tenant_database_context
from revenueos.domain import AIJobStatus
from revenueos.errors import PublicAPIError
from revenueos.tenant import TenantContext


def test_postgresql_clerk_identity_reconciliation_uses_deterministic_rls_context() -> None:
    database_url = os.getenv("DATABASE_URL", "")
    if not database_url.startswith(("postgresql", "postgres")):
        pytest.skip("A PostgreSQL DATABASE_URL is required for the identity RLS integration test.")

    suffix = uuid.uuid4().hex
    identity = VerifiedIdentity(
        external_auth_id=f"user_clerk_rls_{suffix}",
        external_organisation_id=f"org_clerk_rls_{suffix}",
        display_name="Synthetic Clerk RLS user",
        email=f"clerk-rls-{suffix}@example.test",
        organisation_name="Synthetic Clerk RLS organisation",
        role="admin",
        auth_mode="clerk",
    )

    async def scenario() -> None:
        engine = create_async_engine(database_url)
        organisation_id: uuid.UUID | None = None
        user_id: uuid.UUID | None = None
        try:
            async with AsyncSession(engine, expire_on_commit=False) as session:
                first = await _resolve_identity(session, identity)
                second = await _resolve_identity(session, identity)
                assert first.organisation_id == second.organisation_id
                assert first.user_id == second.user_id
                assert second.role == "admin"
                organisation_id = first.organisation_id
                user_id = first.user_id
        finally:
            if organisation_id is not None and user_id is not None:
                async with engine.begin() as connection:
                    await connection.execute(
                        text("SELECT set_config('app.organisation_id', :organisation_id, true)"),
                        {"organisation_id": str(organisation_id)},
                    )
                    await connection.execute(
                        text(
                            """
                            DELETE FROM organisation_memberships
                            WHERE organisation_id = :organisation_id
                              AND user_id = :user_id
                            """
                        ),
                        {"organisation_id": organisation_id, "user_id": user_id},
                    )
                    await connection.execute(
                        text("DELETE FROM organisations WHERE id = :organisation_id"),
                        {"organisation_id": organisation_id},
                    )
                    await connection.execute(
                        text("DELETE FROM users WHERE id = :user_id"),
                        {"user_id": user_id},
                    )
            await engine.dispose()

    asyncio.run(scenario())


def test_postgresql_rls_isolates_every_tenant_table() -> None:
    database_url = os.getenv("DATABASE_URL", "")
    if not database_url.startswith(("postgresql", "postgres")):
        pytest.skip("A PostgreSQL DATABASE_URL is required for the RLS integration test.")

    role_name = f"revenueos_rls_test_{uuid.uuid4().hex[:12]}"
    tenant_tables = (
        "companies",
        "contacts",
        "opportunities",
        "opportunity_audit_events",
        "tasks",
        "interactions",
        "pre_interaction_briefs",
        "capture_sessions",
        "evidence",
        "visual_assets",
        "visual_candidate_evidence",
        "debrief_sessions",
        "debrief_turns",
        "evidence_fragments",
        "candidate_evidence",
        "interaction_intelligence_snapshots",
        "revenue_brain_interaction_snapshots",
        "interaction_audit_events",
        "meetings",
        "meeting_participants",
        "transcripts",
        "meeting_audit_events",
        "ai_jobs",
        "ai_artifacts",
        "revenue_brain_snapshots",
        "revenue_brain_insights",
        "organisation_beta_settings",
        "data_notice_acknowledgements",
        "onboarding_progress",
        "ai_usage_counters",
        "beta_feedback",
        "beta_data_requests",
        "beta_system_events",
    )
    tenant_a = {
        "suffix": "A",
        "organisation_id": uuid.uuid4(),
        "user_id": uuid.uuid4(),
        "company_id": uuid.uuid4(),
        "contact_id": uuid.uuid4(),
        "opportunity_id": uuid.uuid4(),
        "opportunity_audit_id": uuid.uuid4(),
        "task_id": uuid.uuid4(),
        "interaction_id": uuid.uuid4(),
        "brief_id": uuid.uuid4(),
        "capture_session_id": uuid.uuid4(),
        "evidence_id": uuid.uuid4(),
        "visual_id": uuid.uuid4(),
        "visual_candidate_id": uuid.uuid4(),
        "debrief_turn_id": uuid.uuid4(),
        "evidence_fragment_id": uuid.uuid4(),
        "candidate_evidence_id": uuid.uuid4(),
        "interaction_intelligence_id": uuid.uuid4(),
        "revenue_brain_interaction_id": uuid.uuid4(),
        "interaction_audit_id": uuid.uuid4(),
        "meeting_id": uuid.uuid4(),
        "participant_id": uuid.uuid4(),
        "transcript_id": uuid.uuid4(),
        "audit_id": uuid.uuid4(),
        "ai_job_id": uuid.uuid4(),
        "ai_artifact_id": uuid.uuid4(),
        "snapshot_id": uuid.uuid4(),
        "previous_snapshot_id": uuid.uuid4(),
        "insight_id": uuid.uuid4(),
        "transcript_version_id": uuid.uuid4(),
        "previous_transcript_version_id": uuid.uuid4(),
        "acknowledgement_id": uuid.uuid4(),
        "feedback_id": uuid.uuid4(),
        "data_request_id": uuid.uuid4(),
        "system_event_id": uuid.uuid4(),
    }
    tenant_b = {
        "suffix": "B",
        "organisation_id": uuid.uuid4(),
        "user_id": uuid.uuid4(),
        "company_id": uuid.uuid4(),
        "contact_id": uuid.uuid4(),
        "opportunity_id": uuid.uuid4(),
        "opportunity_audit_id": uuid.uuid4(),
        "task_id": uuid.uuid4(),
        "interaction_id": uuid.uuid4(),
        "brief_id": uuid.uuid4(),
        "capture_session_id": uuid.uuid4(),
        "evidence_id": uuid.uuid4(),
        "visual_id": uuid.uuid4(),
        "visual_candidate_id": uuid.uuid4(),
        "debrief_turn_id": uuid.uuid4(),
        "evidence_fragment_id": uuid.uuid4(),
        "candidate_evidence_id": uuid.uuid4(),
        "interaction_intelligence_id": uuid.uuid4(),
        "revenue_brain_interaction_id": uuid.uuid4(),
        "interaction_audit_id": uuid.uuid4(),
        "meeting_id": uuid.uuid4(),
        "participant_id": uuid.uuid4(),
        "transcript_id": uuid.uuid4(),
        "audit_id": uuid.uuid4(),
        "ai_job_id": uuid.uuid4(),
        "ai_artifact_id": uuid.uuid4(),
        "snapshot_id": uuid.uuid4(),
        "previous_snapshot_id": uuid.uuid4(),
        "insight_id": uuid.uuid4(),
        "transcript_version_id": uuid.uuid4(),
        "previous_transcript_version_id": uuid.uuid4(),
        "acknowledgement_id": uuid.uuid4(),
        "feedback_id": uuid.uuid4(),
        "data_request_id": uuid.uuid4(),
        "system_event_id": uuid.uuid4(),
    }

    async def scenario() -> None:
        engine = create_async_engine(database_url)
        try:
            async with engine.begin() as connection:
                await connection.exec_driver_sql(f'CREATE ROLE "{role_name}" NOLOGIN')
                await connection.exec_driver_sql(f'GRANT USAGE ON SCHEMA public TO "{role_name}"')
                for table in tenant_tables:
                    await connection.exec_driver_sql(
                        f'GRANT SELECT, INSERT, UPDATE, DELETE ON {table} TO "{role_name}"'
                    )

                for tenant in (tenant_a, tenant_b):
                    suffix = str(tenant["suffix"])
                    identity_parameters = {
                        **tenant,
                        "slug": f"rls-{suffix.lower()}-{tenant['organisation_id']}",
                        "external_auth_id": f"rls_{suffix.lower()}_{tenant['user_id']}",
                        "email": f"rls-{suffix.lower()}-{tenant['user_id']}@example.test",
                    }
                    await connection.execute(
                        text(
                            """
                            INSERT INTO organisations (id, name, slug)
                            VALUES (:organisation_id, :name, :slug)
                            """
                        ),
                        {
                            **identity_parameters,
                            "name": f"RLS Organisation {suffix}",
                        },
                    )
                    await connection.execute(
                        text(
                            """
                            INSERT INTO users
                                (id, external_auth_id, email, display_name)
                            VALUES
                                (:user_id, :external_auth_id, :email, :display_name)
                            """
                        ),
                        {
                            **identity_parameters,
                            "display_name": f"RLS User {suffix}",
                        },
                    )
                    await connection.execute(
                        text(
                            """
                            INSERT INTO organisation_memberships
                                (organisation_id, user_id, role)
                            VALUES (:organisation_id, :user_id, 'admin')
                            """
                        ),
                        identity_parameters,
                    )
                    await connection.execute(
                        text(
                            """
                            INSERT INTO companies
                                (id, organisation_id, name, status, owner_user_id)
                            VALUES
                                (:company_id, :organisation_id, :company_name,
                                 'prospect', :user_id)
                            """
                        ),
                        {
                            **identity_parameters,
                            "company_name": f"RLS Company {suffix}",
                        },
                    )
                    await connection.execute(
                        text(
                            """
                            INSERT INTO contacts
                                (id, organisation_id, company_id, first_name, last_name,
                                 email, owner_user_id)
                            VALUES
                                (:contact_id, :organisation_id, :company_id, 'RLS',
                                 :suffix, :contact_email, :user_id)
                            """
                        ),
                        {
                            **identity_parameters,
                            "contact_email": f"rls-contact-{suffix.lower()}-{tenant['contact_id']}@example.test",
                        },
                    )
                    await connection.execute(
                        text(
                            """
                            INSERT INTO opportunities
                                (id, organisation_id, company_id, name, stage, status,
                                 estimated_value, currency, owner_user_id)
                            VALUES
                                (:opportunity_id, :organisation_id, :company_id,
                                 :opportunity_name, 'discovery', 'open', :value, 'AUD', :user_id)
                            """
                        ),
                        {
                            **identity_parameters,
                            "opportunity_name": f"RLS Opportunity {suffix}",
                            "value": Decimal("1000.00"),
                        },
                    )
                    await connection.execute(
                        text(
                            """
                            INSERT INTO opportunity_audit_events
                                (id, organisation_id, opportunity_id, actor_user_id,
                                 action, changed_fields)
                            VALUES
                                (:opportunity_audit_id, :organisation_id,
                                 :opportunity_id, :user_id, 'created', '[]'::json)
                            """
                        ),
                        identity_parameters,
                    )
                    await connection.execute(
                        text(
                            """
                            INSERT INTO tasks
                                (id, organisation_id, company_id, contact_id, opportunity_id,
                                 title, status, priority, assigned_user_id, created_by_user_id)
                            VALUES
                                (:task_id, :organisation_id, :company_id, :contact_id,
                                 :opportunity_id, :task_title, 'open', 'medium',
                                 :user_id, :user_id)
                            """
                        ),
                        {
                            **identity_parameters,
                            "task_title": f"RLS Task {suffix}",
                        },
                    )
                    await connection.execute(
                        text(
                            """
                            INSERT INTO interactions
                                (id, organisation_id, company_id, opportunity_id,
                                 interaction_type, lifecycle_status, title,
                                 scheduled_start_at, creation_origin, created_by_user_id)
                            VALUES
                                (:interaction_id, :organisation_id, :company_id,
                                 :opportunity_id, 'online_meeting', 'completed',
                                 :interaction_title, now(), 'meeting_compatibility',
                                 :user_id)
                            """
                        ),
                        {
                            **identity_parameters,
                            "interaction_title": f"RLS Interaction {suffix}",
                        },
                    )
                    await connection.execute(
                        text(
                            """
                            INSERT INTO pre_interaction_briefs
                                (id, organisation_id, interaction_id, company_id,
                                 opportunity_id, source_context_fingerprint,
                                 brief_version, schema_version, status,
                                 content_json, source_references_json,
                                 created_by_user_id)
                            VALUES
                                (:brief_id, :organisation_id, :interaction_id,
                                 :company_id, :opportunity_id,
                                 :source_context_fingerprint, 1, 1, 'completed',
                                 '{"headline":"RLS brief"}'::json, '[]'::json,
                                 :user_id)
                            """
                        ),
                        {
                            **identity_parameters,
                            "source_context_fingerprint": suffix.lower() * 64,
                        },
                    )
                    await connection.execute(
                        text(
                            """
                            INSERT INTO capture_sessions
                                (id, organisation_id, interaction_id, capture_type,
                                 status, started_by_user_id)
                            VALUES
                                (:capture_session_id, :organisation_id,
                                 :interaction_id, 'ai_debrief', 'completed',
                                 :user_id)
                            """
                        ),
                        identity_parameters,
                    )
                    await connection.execute(
                        text(
                            """
                            INSERT INTO debrief_sessions
                                (id, organisation_id, interaction_id,
                                 started_by_user_id, lifecycle_status,
                                 idempotency_key, question_count, max_questions,
                                 safety_confirmed_at, completed_at)
                            VALUES
                                (:capture_session_id, :organisation_id,
                                 :interaction_id, :user_id, 'completed',
                                 :debrief_idempotency_key, 1, 6, now(), now())
                            """
                        ),
                        {
                            **identity_parameters,
                            "debrief_idempotency_key": f"rls-debrief-{suffix.lower()}",
                        },
                    )
                    await connection.execute(
                        text(
                            """
                            INSERT INTO evidence
                                (id, organisation_id, interaction_id,
                                 capture_session_id, evidence_type, origin_class,
                                 support_class, validation_state, lifecycle_status)
                            VALUES
                                (:evidence_id, :organisation_id, :interaction_id,
                                 :capture_session_id, 'system_metadata',
                                 'system_metadata', 'direct', 'not_applicable',
                                 'available')
                            """
                        ),
                        identity_parameters,
                    )
                    await connection.execute(
                        text(
                            """
                            INSERT INTO debrief_turns
                                (id, organisation_id, interaction_id, session_id,
                                 evidence_id, turn_number, question_json,
                                 answer_text, input_mode, idempotency_key)
                            VALUES
                                (:debrief_turn_id, :organisation_id,
                                 :interaction_id, :capture_session_id,
                                 :evidence_id, 1,
                                 '{"status":"ask","question":"How did it go?","reason":"RLS","target":"other","priority":"high"}'::json,
                                 :debrief_answer, 'text', :turn_idempotency_key)
                            """
                        ),
                        {
                            **identity_parameters,
                            "debrief_answer": f"RLS debrief answer {suffix}",
                            "turn_idempotency_key": f"rls-turn-{suffix.lower()}",
                        },
                    )
                    await connection.execute(
                        text(
                            """
                            INSERT INTO visual_assets
                                (id, organisation_id, interaction_id,
                                 capture_session_id, source_evidence_id,
                                 captured_by_user_id, visual_type,
                                 source_ownership, display_filename, storage_key,
                                 mime_type, byte_size, upload_byte_size, width,
                                 height, checksum_sha256,
                                 upload_checksum_sha256, captured_at,
                                 upload_idempotency_key, processing_status,
                                 storage_status, upload_expires_at)
                            VALUES
                                (:visual_id, :organisation_id, :interaction_id,
                                 :capture_session_id, :evidence_id, :user_id,
                                 'whiteboard', 'customer_created',
                                 'rls-whiteboard.png', :visual_storage_key,
                                 'image/png', 68, 68, 1, 1,
                                 :visual_checksum, :visual_checksum, now(),
                                 :visual_idempotency_key, 'review', 'available',
                                 now() + interval '5 minutes')
                            """
                        ),
                        {
                            **identity_parameters,
                            "visual_storage_key": (f"{tenant['organisation_id']}/{tenant['interaction_id']}/rls.png"),
                            "visual_checksum": suffix.lower() * 64,
                            "visual_idempotency_key": f"rls-visual-{suffix.lower()}",
                        },
                    )
                    await connection.execute(
                        text(
                            """
                            INSERT INTO visual_candidate_evidence
                                (id, organisation_id, interaction_id,
                                 source_visual_id, evidence_category, statement,
                                 original_statement, statement_fingerprint,
                                 source_ownership, origin_class,
                                 support_classification, validation_state,
                                 review_state, conflict_state)
                            VALUES
                                (:visual_candidate_id, :organisation_id,
                                 :interaction_id, :visual_id, 'other',
                                 :visual_statement, :visual_statement,
                                 :visual_candidate_fingerprint,
                                 'customer_created', 'ai_inferred', 'direct',
                                 'unreviewed', 'pending', 'not_assessed')
                            """
                        ),
                        {
                            **identity_parameters,
                            "visual_statement": f"RLS visual statement {suffix}.",
                            "visual_candidate_fingerprint": suffix.upper() * 64,
                        },
                    )
                    await connection.execute(
                        text(
                            """
                            INSERT INTO evidence_fragments
                                (id, organisation_id, evidence_id, session_id,
                                 turn_id, content_text)
                            VALUES
                                (:evidence_fragment_id, :organisation_id,
                                 :evidence_id, :capture_session_id,
                                 :debrief_turn_id, :debrief_answer)
                            """
                        ),
                        {
                            **identity_parameters,
                            "debrief_answer": f"RLS debrief answer {suffix}",
                        },
                    )
                    await connection.execute(
                        text(
                            """
                            INSERT INTO candidate_evidence
                                (id, organisation_id, interaction_id, session_id,
                                 source_fragment_id, evidence_category,
                                 statement, original_statement,
                                 statement_fingerprint)
                            VALUES
                                (:candidate_evidence_id, :organisation_id,
                                 :interaction_id, :capture_session_id,
                                 :evidence_fragment_id, 'other',
                                 :candidate_statement, :candidate_statement,
                                 :candidate_fingerprint)
                            """
                        ),
                        {
                            **identity_parameters,
                            "candidate_statement": f"RLS reported statement {suffix}.",
                            "candidate_fingerprint": suffix.lower() * 64,
                        },
                    )
                    await connection.execute(
                        text(
                            """
                            INSERT INTO interaction_intelligence_snapshots
                                (id, organisation_id, interaction_id,
                                 opportunity_id, session_id, content_json,
                                 source_evidence_ids)
                            VALUES
                                (:interaction_intelligence_id, :organisation_id,
                                 :interaction_id, :opportunity_id,
                                 :capture_session_id,
                                 '{"origin":"salesperson_reported","items":[]}'::json,
                                 '[]'::json)
                            """
                        ),
                        identity_parameters,
                    )
                    await connection.execute(
                        text(
                            """
                            INSERT INTO revenue_brain_interaction_snapshots
                                (id, organisation_id, company_id, opportunity_id,
                                 interaction_id, interaction_intelligence_id,
                                 content_json, source_evidence_ids)
                            VALUES
                                (:revenue_brain_interaction_id, :organisation_id,
                                 :company_id, :opportunity_id, :interaction_id,
                                 :interaction_intelligence_id,
                                 '{"origin":"salesperson_reported","items":[]}'::json,
                                 '[]'::json)
                            """
                        ),
                        identity_parameters,
                    )
                    await connection.execute(
                        text(
                            """
                            INSERT INTO interaction_audit_events
                                (id, organisation_id, interaction_id, actor_user_id,
                                 action, changed_fields)
                            VALUES
                                (:interaction_audit_id, :organisation_id,
                                 :interaction_id, :user_id, 'created',
                                 '["title"]'::json)
                            """
                        ),
                        identity_parameters,
                    )
                    await connection.execute(
                        text(
                            """
                            INSERT INTO meetings
                                (id, organisation_id, interaction_id, title,
                                 meeting_date, meeting_type, status, company_id,
                                 owner_user_id, created_by, updated_by)
                            VALUES
                                (:meeting_id, :organisation_id, :interaction_id,
                                 :meeting_title, now(), 'remote', 'completed',
                                 :company_id, :user_id, :user_id, :user_id)
                            """
                        ),
                        {
                            **identity_parameters,
                            "meeting_title": f"RLS Meeting {suffix}",
                        },
                    )
                    await connection.execute(
                        text(
                            """
                            INSERT INTO meeting_participants
                                (id, organisation_id, meeting_id, contact_id, display_name,
                                 email, attendance_status, role)
                            VALUES
                                (:participant_id, :organisation_id, :meeting_id, :contact_id,
                                 :participant_name, :contact_email, 'attended', 'attendee')
                            """
                        ),
                        {
                            **identity_parameters,
                            "participant_name": f"RLS Participant {suffix}",
                            "contact_email": f"rls-participant-{suffix.lower()}-{tenant['participant_id']}@example.test",
                        },
                    )
                    await connection.execute(
                        text(
                            """
                            INSERT INTO transcripts
                                (id, organisation_id, meeting_id, raw_text, language,
                                 version, source)
                            VALUES
                                (:transcript_id, :organisation_id, :meeting_id,
                                 :raw_text, 'en', 1, 'manual')
                            """
                        ),
                        {
                            **identity_parameters,
                            "raw_text": f"RLS transcript {suffix}",
                        },
                    )
                    await connection.execute(
                        text(
                            """
                            INSERT INTO meeting_audit_events
                                (id, organisation_id, meeting_id, actor_user_id, action,
                                 entity_type, entity_id, changed_fields)
                            VALUES
                                (:audit_id, :organisation_id, :meeting_id, :user_id,
                                 'created', 'meeting', :meeting_id, '["title"]'::json)
                            """
                        ),
                        identity_parameters,
                    )
                    await connection.execute(
                        text(
                            """
                            INSERT INTO ai_jobs
                                (id, organisation_id, meeting_id, transcript_id,
                                 transcript_version, job_type, status, schema_version,
                                 idempotency_key, requested_by_user_id)
                            VALUES
                                (:ai_job_id, :organisation_id, :meeting_id, :transcript_id,
                                 1, 'action_items', 'pending', 1,
                                 :idempotency_key, :user_id)
                            """
                        ),
                        {
                            **identity_parameters,
                            "idempotency_key": f"rls-job-{suffix.lower()}",
                        },
                    )
                    await connection.execute(
                        text(
                            """
                            INSERT INTO ai_artifacts
                                (id, organisation_id, meeting_id, transcript_id,
                                 transcript_version, job_id, artifact_type,
                                 artifact_version, schema_version, content_json)
                            VALUES
                                (:ai_artifact_id, :organisation_id, :meeting_id,
                                 :transcript_id, 1, :ai_job_id, 'action_items',
                                 1, 1, '{"action_items":[]}'::json)
                            """
                        ),
                        identity_parameters,
                    )
                    await connection.execute(
                        text(
                            """
                            INSERT INTO revenue_brain_snapshots
                                (id, organisation_id, company_id, opportunity_id,
                                 meeting_id, transcript_version_id,
                                 summary_reference, buying_signals_reference,
                                 objections_reference, stakeholders_reference,
                                 decisions_reference, actions_reference,
                                 risks_reference, questions_reference,
                                 next_best_action_reference)
                            VALUES
                                (:snapshot_id, :organisation_id, :company_id,
                                 :opportunity_id, :meeting_id,
                                 :transcript_version_id, :ai_artifact_id,
                                 :ai_artifact_id, :ai_artifact_id,
                                 :ai_artifact_id, :ai_artifact_id,
                                 :ai_artifact_id, :ai_artifact_id,
                                 :ai_artifact_id, :ai_artifact_id)
                            """
                        ),
                        identity_parameters,
                    )
                    await connection.execute(
                        text(
                            """
                            INSERT INTO revenue_brain_snapshots
                                (id, organisation_id, company_id, opportunity_id,
                                 meeting_id, transcript_version_id,
                                 summary_reference, buying_signals_reference,
                                 objections_reference, stakeholders_reference,
                                 decisions_reference, actions_reference,
                                 risks_reference, questions_reference,
                                 next_best_action_reference)
                            VALUES
                                (:previous_snapshot_id, :organisation_id,
                                 :company_id, :opportunity_id, :meeting_id,
                                 :previous_transcript_version_id,
                                 :ai_artifact_id, :ai_artifact_id,
                                 :ai_artifact_id, :ai_artifact_id,
                                 :ai_artifact_id, :ai_artifact_id,
                                 :ai_artifact_id, :ai_artifact_id,
                                 :ai_artifact_id)
                            """
                        ),
                        identity_parameters,
                    )
                    await connection.execute(
                        text(
                            """
                            INSERT INTO revenue_brain_insights
                                (id, organisation_id, company_id, opportunity_id,
                                 scope, scope_target_id, from_snapshot_id,
                                 to_snapshot_id, content_json)
                            VALUES
                                (:insight_id, :organisation_id, :company_id,
                                 :opportunity_id, 'opportunity', :opportunity_id,
                                 :previous_snapshot_id, :snapshot_id,
                                 '{"scope":"opportunity","changes":[]}'::json)
                            """
                        ),
                        identity_parameters,
                    )
                    await connection.execute(
                        text(
                            """
                            INSERT INTO organisation_beta_settings
                                (organisation_id, retention_days)
                            VALUES (:organisation_id, 90)
                            """
                        ),
                        identity_parameters,
                    )
                    await connection.execute(
                        text(
                            """
                            INSERT INTO data_notice_acknowledgements
                                (id, organisation_id, user_id, notice_version)
                            VALUES
                                (:acknowledgement_id, :organisation_id, :user_id, 1)
                            """
                        ),
                        identity_parameters,
                    )
                    await connection.execute(
                        text(
                            """
                            INSERT INTO onboarding_progress
                                (organisation_id, user_id, current_step)
                            VALUES (:organisation_id, :user_id, 2)
                            """
                        ),
                        identity_parameters,
                    )
                    await connection.execute(
                        text(
                            """
                            INSERT INTO ai_usage_counters
                                (organisation_id, usage_date, generation_count,
                                 provider_request_count)
                            VALUES (:organisation_id, CURRENT_DATE, 1, 0)
                            """
                        ),
                        identity_parameters,
                    )
                    await connection.execute(
                        text(
                            """
                            INSERT INTO beta_feedback
                                (id, organisation_id, user_id, category, rating,
                                 message, current_route)
                            VALUES
                                (:feedback_id, :organisation_id, :user_id,
                                 'confusing', 4, 'Synthetic RLS feedback.', '/feedback')
                            """
                        ),
                        identity_parameters,
                    )
                    await connection.execute(
                        text(
                            """
                            INSERT INTO beta_data_requests
                                (id, organisation_id, requested_by_user_id,
                                 request_type, status, confirmed_at)
                            VALUES
                                (:data_request_id, :organisation_id, :user_id,
                                 'export', 'pending', now())
                            """
                        ),
                        identity_parameters,
                    )
                    await connection.execute(
                        text(
                            """
                            INSERT INTO beta_system_events
                                (id, organisation_id, actor_user_id, event_type,
                                 subject_id, metadata_json)
                            VALUES
                                (:system_event_id, :organisation_id, :user_id,
                                 'rls_test_event', :data_request_id, '{}'::json)
                            """
                        ),
                        identity_parameters,
                    )

                savepoint = await connection.begin_nested()
                with pytest.raises(DBAPIError):
                    await connection.execute(
                        text(
                            """
                            INSERT INTO ai_jobs
                                (id, organisation_id, meeting_id, transcript_id,
                                 transcript_version, requested_by_user_id)
                            VALUES
                                (:id, :organisation_id, :meeting_id, :transcript_id,
                                 1, :requested_by_user_id)
                            """
                        ),
                        {
                            "id": uuid.uuid4(),
                            "organisation_id": tenant_a["organisation_id"],
                            "meeting_id": tenant_b["meeting_id"],
                            "transcript_id": tenant_b["transcript_id"],
                            "requested_by_user_id": tenant_a["user_id"],
                        },
                    )
                await savepoint.rollback()

                savepoint = await connection.begin_nested()
                with pytest.raises(DBAPIError):
                    await connection.execute(
                        text(
                            """
                            INSERT INTO ai_artifacts
                                (id, organisation_id, meeting_id, transcript_id,
                                 transcript_version, job_id, artifact_version,
                                 schema_version, content_json)
                            VALUES
                                (:id, :organisation_id, :meeting_id, :transcript_id,
                                 1, :job_id, 99, 1, '{"status":"ok"}'::json)
                            """
                        ),
                        {
                            "id": uuid.uuid4(),
                            "organisation_id": tenant_a["organisation_id"],
                            "meeting_id": tenant_a["meeting_id"],
                            "transcript_id": tenant_a["transcript_id"],
                            "job_id": tenant_b["ai_job_id"],
                        },
                    )
                await savepoint.rollback()

                rls_state = {
                    row.relname: (row.relrowsecurity, row.relforcerowsecurity)
                    for row in (
                        await connection.execute(
                            text(
                                """
                                SELECT relname, relrowsecurity, relforcerowsecurity
                                FROM pg_class
                                WHERE relname IN (
                                    'companies',
                                    'contacts',
                                    'opportunities',
                                    'opportunity_audit_events',
                                    'tasks',
                                    'interactions',
                                    'pre_interaction_briefs',
                                    'capture_sessions',
                                    'evidence',
                                    'visual_assets',
                                    'visual_candidate_evidence',
                                    'debrief_sessions',
                                    'debrief_turns',
                                    'evidence_fragments',
                                    'candidate_evidence',
                                    'interaction_intelligence_snapshots',
                                    'revenue_brain_interaction_snapshots',
                                    'interaction_audit_events',
                                    'meetings',
                                    'meeting_participants',
                                    'transcripts',
                                    'meeting_audit_events',
                                    'ai_jobs',
                                    'ai_artifacts',
                                    'revenue_brain_snapshots',
                                    'revenue_brain_insights',
                                    'organisation_beta_settings',
                                    'data_notice_acknowledgements',
                                    'onboarding_progress',
                                    'ai_usage_counters',
                                    'beta_feedback',
                                    'beta_data_requests',
                                    'beta_system_events'
                                )
                                """
                            )
                        )
                    )
                }
                assert rls_state == {table: (True, True) for table in tenant_tables}

            async with engine.connect() as connection:
                transaction = await connection.begin()
                await connection.exec_driver_sql(f'SET LOCAL ROLE "{role_name}"')
                await connection.execute(
                    text("SELECT set_config('app.organisation_id', :organisation_id, true)"),
                    {"organisation_id": str(tenant_a["organisation_id"])},
                )
                tenant_a_counts = {
                    table: await connection.scalar(text(f"SELECT count(*) FROM {table}")) for table in tenant_tables
                }
                expected_tenant_a_counts = {
                    table: 2 if table == "revenue_brain_snapshots" else 1 for table in tenant_tables
                }
                assert tenant_a_counts == expected_tenant_a_counts
                company_update = await connection.execute(
                    text("UPDATE companies SET name = 'Blocked' WHERE id = :id"),
                    {"id": tenant_b["company_id"]},
                )
                assert company_update.rowcount == 0
                job_update = await connection.execute(
                    text("UPDATE ai_jobs SET status = 'cancelled' WHERE id = :id"),
                    {"id": tenant_b["ai_job_id"]},
                )
                assert job_update.rowcount == 0
                artifact_update = await connection.execute(
                    text("UPDATE ai_artifacts SET superseded_at = now() WHERE id = :id"),
                    {"id": tenant_b["ai_artifact_id"]},
                )
                assert artifact_update.rowcount == 0
                brief_update = await connection.execute(
                    text("UPDATE pre_interaction_briefs SET status = 'failed' WHERE id = :id"),
                    {"id": tenant_b["brief_id"]},
                )
                assert brief_update.rowcount == 0
                snapshot_update = await connection.execute(
                    text("UPDATE revenue_brain_snapshots SET version = 2 WHERE id = :id"),
                    {"id": tenant_b["snapshot_id"]},
                )
                assert snapshot_update.rowcount == 0
                insight_update = await connection.execute(
                    text("UPDATE revenue_brain_insights SET reasoning_version = 2 WHERE id = :id"),
                    {"id": tenant_b["insight_id"]},
                )
                assert insight_update.rowcount == 0

                tenant_context = TenantContext(
                    organisation_id=tenant_a["organisation_id"],
                    user_id=tenant_a["user_id"],
                    role="admin",
                )
                async with AsyncSession(
                    bind=connection,
                    expire_on_commit=False,
                ) as session:
                    repository = AIJobRepository(session)
                    worker_repository = AIWorkerRepository(session)
                    assert (
                        await worker_repository.claim_next(
                            tenant_b["organisation_id"],
                            eligible_at=datetime.now(UTC),
                        )
                        is None
                    )
                    own_queue_job = await worker_repository.claim_next(
                        tenant_a["organisation_id"],
                        eligible_at=datetime.now(UTC),
                    )
                    assert own_queue_job is not None
                    assert own_queue_job.organisation_id == tenant_a["organisation_id"]
                    assert (
                        await repository.get_job(
                            tenant_a["organisation_id"],
                            tenant_b["ai_job_id"],
                        )
                        is None
                    )
                    job_service = AIJobService(
                        session,
                        tenant_context,
                        job_repository=repository,
                    )
                    with pytest.raises(PublicAPIError) as cross_tenant_job:
                        await job_service.transition_job(
                            tenant_b["ai_job_id"],
                            AIJobStatus.RUNNING,
                        )
                    assert cross_tenant_job.value.code == "ai_job_not_found"

                    service_job = await job_service.create_infrastructure_test_job(
                        meeting_id=tenant_a["meeting_id"],
                        transcript_id=tenant_a["transcript_id"],
                        transcript_version=1,
                        idempotency_key="rls-service-job-a",
                    )
                    service_artifact = await AIArtifactService(
                        session,
                        tenant_context,
                        job_repository=repository,
                    ).create_infrastructure_test_artifact(
                        job_id=service_job.id,
                        meeting_id=tenant_a["meeting_id"],
                        transcript_id=tenant_a["transcript_id"],
                        transcript_version=1,
                        schema_version=1,
                        content={
                            "status": "ok",
                            "message": "AI processing infrastructure is operational.",
                        },
                    )
                    assert service_job.organisation_id == tenant_a["organisation_id"]
                    assert service_artifact.organisation_id == tenant_a["organisation_id"]
                    assert service_artifact.artifact_version == 1
                await transaction.commit()

                quota_settings = Settings(
                    environment="test",
                    auth_mode="mock",
                    mock_auth_enabled=True,
                    database_url=database_url,
                    private_beta_max_generations_per_day=2,
                )
                quota_tenant = TenantContext(
                    organisation_id=tenant_a["organisation_id"],
                    user_id=tenant_a["user_id"],
                    role="admin",
                )

                async def reserve_concurrently() -> str:
                    async with AsyncSession(engine, expire_on_commit=False) as session, session.begin():
                        await set_tenant_database_context(session, tenant_a["organisation_id"])
                        try:
                            await BetaService(session, quota_tenant, quota_settings).reserve_generation()
                        except PublicAPIError as error:
                            return error.code
                    return "reserved"

                quota_results = await asyncio.gather(reserve_concurrently(), reserve_concurrently())
                assert sorted(quota_results) == ["daily_generation_limit_exceeded", "reserved"]
                async with AsyncSession(engine, expire_on_commit=False) as session, session.begin():
                    await set_tenant_database_context(session, tenant_a["organisation_id"])
                    generation_count = await session.scalar(
                        text(
                            """
                            SELECT generation_count
                            FROM ai_usage_counters
                            WHERE organisation_id = :organisation_id
                              AND usage_date = CURRENT_DATE
                            """
                        ),
                        {"organisation_id": tenant_a["organisation_id"]},
                    )
                assert generation_count == 2

                cross_tenant_inserts = (
                    (
                        """
                        INSERT INTO meetings
                            (id, organisation_id, title, meeting_date, meeting_type,
                             status, owner_user_id, created_by, updated_by)
                        VALUES
                            (:id, :organisation_id, 'Cross tenant', now(), 'remote',
                             'scheduled', :user_id, :user_id, :user_id)
                        """,
                        {
                            "id": uuid.uuid4(),
                            "organisation_id": tenant_b["organisation_id"],
                            "user_id": tenant_b["user_id"],
                        },
                    ),
                    (
                        """
                        INSERT INTO ai_jobs
                            (id, organisation_id, meeting_id, transcript_id,
                             transcript_version, requested_by_user_id)
                        VALUES
                            (:id, :organisation_id, :meeting_id, :transcript_id,
                             1, :requested_by_user_id)
                        """,
                        {
                            "id": uuid.uuid4(),
                            "organisation_id": tenant_b["organisation_id"],
                            "meeting_id": tenant_b["meeting_id"],
                            "transcript_id": tenant_b["transcript_id"],
                            "requested_by_user_id": tenant_b["user_id"],
                        },
                    ),
                    (
                        """
                        INSERT INTO revenue_brain_insights
                            (id, organisation_id, company_id, opportunity_id,
                             scope, scope_target_id, from_snapshot_id,
                             to_snapshot_id, content_json)
                        VALUES
                            (:id, :organisation_id, :company_id, :opportunity_id,
                             'opportunity', :opportunity_id, :from_snapshot_id,
                             :to_snapshot_id,
                             '{"scope":"opportunity","changes":[]}'::json)
                        """,
                        {
                            "id": uuid.uuid4(),
                            "organisation_id": tenant_b["organisation_id"],
                            "company_id": tenant_b["company_id"],
                            "opportunity_id": tenant_b["opportunity_id"],
                            "from_snapshot_id": tenant_b["previous_snapshot_id"],
                            "to_snapshot_id": tenant_b["snapshot_id"],
                        },
                    ),
                    (
                        """
                        INSERT INTO ai_artifacts
                            (id, organisation_id, meeting_id, transcript_id,
                             transcript_version, job_id, artifact_version,
                             schema_version, content_json)
                        VALUES
                            (:id, :organisation_id, :meeting_id, :transcript_id,
                             1, :job_id, 2, 1, '{"status":"ok"}'::json)
                        """,
                        {
                            "id": uuid.uuid4(),
                            "organisation_id": tenant_b["organisation_id"],
                            "meeting_id": tenant_b["meeting_id"],
                            "transcript_id": tenant_b["transcript_id"],
                            "job_id": tenant_b["ai_job_id"],
                        },
                    ),
                    (
                        """
                        INSERT INTO pre_interaction_briefs
                            (id, organisation_id, interaction_id, company_id,
                             opportunity_id, source_context_fingerprint,
                             brief_version, schema_version, status,
                             content_json, source_references_json,
                             created_by_user_id)
                        VALUES
                            (:id, :organisation_id, :interaction_id,
                             :company_id, :opportunity_id,
                             :source_context_fingerprint, 2, 1, 'completed',
                             '{"headline":"Cross tenant"}'::json, '[]'::json,
                             :user_id)
                        """,
                        {
                            "id": uuid.uuid4(),
                            "organisation_id": tenant_b["organisation_id"],
                            "interaction_id": tenant_b["interaction_id"],
                            "company_id": tenant_b["company_id"],
                            "opportunity_id": tenant_b["opportunity_id"],
                            "source_context_fingerprint": "c" * 64,
                            "user_id": tenant_b["user_id"],
                        },
                    ),
                    (
                        """
                        INSERT INTO evidence
                            (id, organisation_id, interaction_id, evidence_type,
                             origin_class, support_class, validation_state,
                             lifecycle_status)
                        VALUES
                            (:id, :organisation_id, :interaction_id,
                             'system_metadata', 'system_metadata', 'direct',
                             'not_applicable', 'available')
                        """,
                        {
                            "id": uuid.uuid4(),
                            "organisation_id": tenant_a["organisation_id"],
                            "interaction_id": tenant_b["interaction_id"],
                        },
                    ),
                    (
                        """
                        INSERT INTO debrief_sessions
                            (id, organisation_id, interaction_id,
                             started_by_user_id, lifecycle_status,
                             idempotency_key, max_questions,
                             safety_confirmed_at)
                        VALUES
                            (:id, :organisation_id, :interaction_id,
                             :user_id, 'collecting', 'cross-tenant', 6, now())
                        """,
                        {
                            "id": tenant_b["capture_session_id"],
                            "organisation_id": tenant_b["organisation_id"],
                            "interaction_id": tenant_b["interaction_id"],
                            "user_id": tenant_b["user_id"],
                        },
                    ),
                    (
                        """
                        INSERT INTO organisation_beta_settings
                            (organisation_id, retention_days)
                        VALUES (:organisation_id, 30)
                        ON CONFLICT (organisation_id)
                        DO UPDATE SET retention_days = EXCLUDED.retention_days
                        """,
                        {
                            "organisation_id": tenant_b["organisation_id"],
                        },
                    ),
                )
                for statement, parameters in cross_tenant_inserts:
                    transaction = await connection.begin()
                    await connection.exec_driver_sql(f'SET LOCAL ROLE "{role_name}"')
                    await connection.execute(
                        text("SELECT set_config('app.organisation_id', :organisation_id, true)"),
                        {"organisation_id": str(tenant_a["organisation_id"])},
                    )
                    with pytest.raises(DBAPIError):
                        await connection.execute(text(statement), parameters)
                    await transaction.rollback()
        finally:
            async with engine.begin() as connection:
                await connection.execute(
                    text("ALTER TABLE pre_interaction_briefs DISABLE TRIGGER pre_interaction_briefs_immutable")
                )
                await connection.execute(
                    text("ALTER TABLE revenue_brain_insights DISABLE TRIGGER revenue_brain_insights_append_only")
                )
                await connection.execute(
                    text("ALTER TABLE revenue_brain_snapshots DISABLE TRIGGER revenue_brain_snapshots_append_only")
                )
                await connection.execute(
                    text(
                        "ALTER TABLE interaction_intelligence_snapshots "
                        "DISABLE TRIGGER interaction_intelligence_snapshots_immutable"
                    )
                )
                await connection.execute(
                    text(
                        "ALTER TABLE revenue_brain_interaction_snapshots "
                        "DISABLE TRIGGER revenue_brain_interaction_snapshots_immutable"
                    )
                )
                for table in (
                    "beta_system_events",
                    "beta_data_requests",
                    "beta_feedback",
                    "ai_usage_counters",
                    "onboarding_progress",
                    "data_notice_acknowledgements",
                    "organisation_beta_settings",
                    "revenue_brain_insights",
                    "revenue_brain_interaction_snapshots",
                    "interaction_intelligence_snapshots",
                    "revenue_brain_snapshots",
                    "ai_artifacts",
                    "ai_jobs",
                    "opportunity_audit_events",
                    "pre_interaction_briefs",
                    "candidate_evidence",
                    "visual_candidate_evidence",
                    "visual_assets",
                    "evidence_fragments",
                    "debrief_turns",
                    "debrief_sessions",
                    "evidence",
                    "capture_sessions",
                    "interaction_audit_events",
                    "meeting_audit_events",
                    "transcripts",
                    "meeting_participants",
                    "meetings",
                    "interactions",
                    "tasks",
                    "contacts",
                    "opportunities",
                    "companies",
                ):
                    await connection.execute(
                        text(f"DELETE FROM {table} WHERE organisation_id IN (:organisation_a, :organisation_b)"),
                        {
                            "organisation_a": tenant_a["organisation_id"],
                            "organisation_b": tenant_b["organisation_id"],
                        },
                    )
                await connection.execute(
                    text("ALTER TABLE revenue_brain_snapshots ENABLE TRIGGER revenue_brain_snapshots_append_only")
                )
                await connection.execute(
                    text(
                        "ALTER TABLE interaction_intelligence_snapshots "
                        "ENABLE TRIGGER interaction_intelligence_snapshots_immutable"
                    )
                )
                await connection.execute(
                    text(
                        "ALTER TABLE revenue_brain_interaction_snapshots "
                        "ENABLE TRIGGER revenue_brain_interaction_snapshots_immutable"
                    )
                )
                await connection.execute(
                    text("ALTER TABLE revenue_brain_insights ENABLE TRIGGER revenue_brain_insights_append_only")
                )
                await connection.execute(
                    text("ALTER TABLE pre_interaction_briefs ENABLE TRIGGER pre_interaction_briefs_immutable")
                )
                cleanup_parameters = {
                    "organisation_a": tenant_a["organisation_id"],
                    "organisation_b": tenant_b["organisation_id"],
                    "user_a": tenant_a["user_id"],
                    "user_b": tenant_b["user_id"],
                }
                await connection.execute(
                    text(
                        """
                        DELETE FROM organisation_memberships
                        WHERE organisation_id IN (:organisation_a, :organisation_b)
                        """
                    ),
                    cleanup_parameters,
                )
                await connection.execute(
                    text("DELETE FROM users WHERE id IN (:user_a, :user_b)"),
                    cleanup_parameters,
                )
                await connection.execute(
                    text("DELETE FROM organisations WHERE id IN (:organisation_a, :organisation_b)"),
                    cleanup_parameters,
                )
                await connection.exec_driver_sql(f'DROP OWNED BY "{role_name}"')
                await connection.exec_driver_sql(f'DROP ROLE IF EXISTS "{role_name}"')
            await engine.dispose()

    asyncio.run(scenario())
