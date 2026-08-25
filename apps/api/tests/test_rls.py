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
from revenueos.daily_repositories import DailyRepository
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
        "action_proposals",
        "action_proposal_versions",
        "action_audit_events",
        "integration_connections",
        "execution_previews",
        "action_executions",
        "action_execution_attempts",
        "integration_audit_events",
        "mock_connector_objects",
        "oauth_connection_states",
        "encrypted_connector_credentials",
        "crm_entity_mappings",
        "crm_field_mappings",
        "crm_stage_mappings",
        "tasks",
        "interactions",
        "online_meeting_metadata",
        "online_meeting_transcript_imports",
        "interaction_markers",
        "pre_interaction_briefs",
        "capture_sessions",
        "evidence",
        "visual_assets",
        "visual_candidate_evidence",
        "document_sources",
        "document_fragments",
        "email_sources",
        "source_candidate_evidence",
        "revenue_brain_source_snapshots",
        "recording_usage_counters",
        "recording_sessions",
        "recording_consents",
        "recording_chunks",
        "transcript_versions",
        "transcript_segments",
        "live_interaction_sessions",
        "live_processing_windows",
        "provisional_signals",
        "live_brief_progress",
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
        "methodology_definitions",
        "methodology_definition_versions",
        "organisation_methodology_settings",
        "methodology_projections",
        "methodology_reviews",
        "organisation_module_entitlements",
        "prospect_usage_counters",
        "prospect_research_targets",
        "prospect_research_runs",
        "prospect_research_sources",
        "prospect_research_observations",
        "prospect_research_observation_sources",
    )
    tenant_a = {
        "suffix": "A",
        "organisation_id": uuid.uuid4(),
        "user_id": uuid.uuid4(),
        "company_id": uuid.uuid4(),
        "contact_id": uuid.uuid4(),
        "opportunity_id": uuid.uuid4(),
        "opportunity_audit_id": uuid.uuid4(),
        "action_id": uuid.uuid4(),
        "action_version_id": uuid.uuid4(),
        "action_audit_event_id": uuid.uuid4(),
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
        "recording_id": uuid.uuid4(),
        "recording_consent_id": uuid.uuid4(),
        "recording_chunk_id": uuid.uuid4(),
        "recording_transcript_version_id": uuid.uuid4(),
        "recording_segment_id": uuid.uuid4(),
        "marker_id": uuid.uuid4(),
        "online_meeting_metadata_id": uuid.uuid4(),
        "online_meeting_transcript_import_id": uuid.uuid4(),
        "document_source_id": uuid.uuid4(),
        "document_fragment_id": uuid.uuid4(),
        "email_source_id": uuid.uuid4(),
        "source_candidate_id": uuid.uuid4(),
        "source_snapshot_id": uuid.uuid4(),
        "live_session_id": uuid.uuid4(),
        "live_window_id": uuid.uuid4(),
        "provisional_signal_id": uuid.uuid4(),
        "live_brief_progress_id": uuid.uuid4(),
        "methodology_definition_id": uuid.uuid4(),
        "methodology_definition_version_id": uuid.uuid4(),
        "methodology_projection_id": uuid.uuid4(),
        "methodology_review_id": uuid.uuid4(),
        "connection_id": uuid.uuid4(),
        "oauth_state_id": uuid.uuid4(),
        "credential_id": uuid.uuid4(),
        "crm_entity_mapping_id": uuid.uuid4(),
        "crm_field_mapping_id": uuid.uuid4(),
        "crm_stage_mapping_id": uuid.uuid4(),
        "prospect_target_id": uuid.uuid4(),
        "prospect_run_id": uuid.uuid4(),
        "prospect_source_id": uuid.uuid4(),
        "prospect_observation_id": uuid.uuid4(),
    }
    tenant_b = {
        "suffix": "B",
        "organisation_id": uuid.uuid4(),
        "user_id": uuid.uuid4(),
        "company_id": uuid.uuid4(),
        "contact_id": uuid.uuid4(),
        "opportunity_id": uuid.uuid4(),
        "opportunity_audit_id": uuid.uuid4(),
        "action_id": uuid.uuid4(),
        "action_version_id": uuid.uuid4(),
        "action_audit_event_id": uuid.uuid4(),
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
        "recording_id": uuid.uuid4(),
        "recording_consent_id": uuid.uuid4(),
        "recording_chunk_id": uuid.uuid4(),
        "recording_transcript_version_id": uuid.uuid4(),
        "recording_segment_id": uuid.uuid4(),
        "marker_id": uuid.uuid4(),
        "online_meeting_metadata_id": uuid.uuid4(),
        "online_meeting_transcript_import_id": uuid.uuid4(),
        "document_source_id": uuid.uuid4(),
        "document_fragment_id": uuid.uuid4(),
        "email_source_id": uuid.uuid4(),
        "source_candidate_id": uuid.uuid4(),
        "source_snapshot_id": uuid.uuid4(),
        "live_session_id": uuid.uuid4(),
        "live_window_id": uuid.uuid4(),
        "provisional_signal_id": uuid.uuid4(),
        "live_brief_progress_id": uuid.uuid4(),
        "methodology_definition_id": uuid.uuid4(),
        "methodology_definition_version_id": uuid.uuid4(),
        "methodology_projection_id": uuid.uuid4(),
        "methodology_review_id": uuid.uuid4(),
        "connection_id": uuid.uuid4(),
        "oauth_state_id": uuid.uuid4(),
        "credential_id": uuid.uuid4(),
        "crm_entity_mapping_id": uuid.uuid4(),
        "crm_field_mapping_id": uuid.uuid4(),
        "crm_stage_mapping_id": uuid.uuid4(),
        "prospect_target_id": uuid.uuid4(),
        "prospect_run_id": uuid.uuid4(),
        "prospect_source_id": uuid.uuid4(),
        "prospect_observation_id": uuid.uuid4(),
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
                            INSERT INTO organisation_module_entitlements
                                (organisation_id, module_key, enabled, source,
                                 configured_by_user_id, enabled_at)
                            VALUES
                                (:organisation_id, 'prospect', true,
                                 'manual_private_beta', :user_id, now())
                            """
                        ),
                        identity_parameters,
                    )
                    await connection.execute(
                        text(
                            """
                            INSERT INTO prospect_usage_counters
                                (organisation_id, usage_date, scope_key, research_run_count)
                            VALUES (:organisation_id, current_date, 'organisation', 1)
                            """
                        ),
                        identity_parameters,
                    )
                    await connection.execute(
                        text(
                            """
                            INSERT INTO prospect_research_targets
                                (id, organisation_id, provider_key,
                                 provider_candidate_id, name, normalized_domain,
                                 website_url, provider_attribution)
                            VALUES
                                (:prospect_target_id, :organisation_id, 'mock',
                                 :provider_candidate_id, :target_name,
                                 :target_domain, :target_url, 'Synthetic RLS data')
                            """
                        ),
                        {
                            **identity_parameters,
                            "provider_candidate_id": f"rls-company-{suffix.lower()}",
                            "target_name": f"RLS Prospect {suffix}",
                            "target_domain": f"rls-prospect-{suffix.lower()}.example",
                            "target_url": f"https://rls-prospect-{suffix.lower()}.example/",
                        },
                    )
                    await connection.execute(
                        text(
                            """
                            INSERT INTO prospect_research_runs
                                (id, organisation_id, target_id,
                                 requested_by_user_id, status, provider_key,
                                 provider_version, request_fingerprint,
                                 idempotency_key, completed_at)
                            VALUES
                                (:prospect_run_id, :organisation_id,
                                 :prospect_target_id, :user_id, 'completed',
                                 'mock', 'mock-v1', :request_fingerprint,
                                 :idempotency_key, now())
                            """
                        ),
                        {
                            **identity_parameters,
                            "request_fingerprint": suffix.lower() * 64,
                            "idempotency_key": f"rls:{suffix.lower()}",
                        },
                    )
                    await connection.execute(
                        text(
                            """
                            INSERT INTO prospect_research_sources
                                (id, organisation_id, run_id, target_id,
                                 source_key, source_type, url, canonical_url,
                                 domain, title, publisher, retrieved_at,
                                 authority_class, content_fingerprint)
                            VALUES
                                (:prospect_source_id, :organisation_id,
                                 :prospect_run_id, :prospect_target_id,
                                 'official', 'official_website', :source_url,
                                 :source_url, :source_domain, 'Official profile',
                                 'RLS Prospect', now(), 'official_public',
                                 :source_fingerprint)
                            """
                        ),
                        {
                            **identity_parameters,
                            "source_url": f"https://rls-prospect-{suffix.lower()}.example/about",
                            "source_domain": f"rls-prospect-{suffix.lower()}.example",
                            "source_fingerprint": suffix.lower() * 64,
                        },
                    )
                    await connection.execute(
                        text(
                            """
                            INSERT INTO prospect_research_observations
                                (id, organisation_id, run_id, target_id,
                                 observation_key, category, statement,
                                 trust_state, freshness, generated_at)
                            VALUES
                                (:prospect_observation_id, :organisation_id,
                                 :prospect_run_id, :prospect_target_id,
                                 'company_profile', 'company_profile',
                                 'A tenant-scoped public company profile.',
                                 'verified', 'stable', now())
                            """
                        ),
                        identity_parameters,
                    )
                    await connection.execute(
                        text(
                            """
                            INSERT INTO prospect_research_observation_sources
                                (organisation_id, observation_id, source_id, run_id)
                            VALUES
                                (:organisation_id, :prospect_observation_id,
                                 :prospect_source_id, :prospect_run_id)
                            """
                        ),
                        identity_parameters,
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
                            INSERT INTO integration_connections
                                (id, organisation_id, connector_key,
                                 connection_status, created_by_user_id,
                                 credential_reference, capability_state_json,
                                 external_account_id, external_account_name,
                                 granted_scopes_json)
                            VALUES
                                (:connection_id, :organisation_id, 'hubspot',
                                 'active', :user_id, :credential_reference,
                                 '["update_opportunity"]'::json,
                                 :external_account_id, :external_account_name,
                                 '["oauth","crm.objects.deals.read",'
                                 '"crm.objects.deals.write"]'::json)
                            """
                        ),
                        {
                            **identity_parameters,
                            "credential_reference": str(tenant["credential_id"]),
                            "external_account_id": f"hubspot-{suffix.lower()}",
                            "external_account_name": f"RLS HubSpot {suffix}",
                        },
                    )
                    await connection.execute(
                        text(
                            """
                            INSERT INTO oauth_connection_states
                                (id, organisation_id, user_id, connector_key,
                                 state_hash, redirect_uri, expires_at)
                            VALUES
                                (:oauth_state_id, :organisation_id, :user_id,
                                 'hubspot', :state_hash,
                                 'https://app.example.test/settings/integrations/hubspot/callback',
                                 now() + interval '10 minutes')
                            """
                        ),
                        {**identity_parameters, "state_hash": suffix.lower() * 64},
                    )
                    await connection.execute(
                        text(
                            """
                            INSERT INTO encrypted_connector_credentials
                                (id, organisation_id, connection_id, connector_key,
                                 encrypted_payload, nonce, key_version)
                            VALUES
                                (:credential_id, :organisation_id, :connection_id,
                                 'hubspot', :encrypted_payload, :nonce, 1)
                            """
                        ),
                        {
                            **identity_parameters,
                            "encrypted_payload": b"synthetic-ciphertext",
                            "nonce": bytes([1 if suffix == "A" else 2]) * 12,
                        },
                    )
                    await connection.execute(
                        text(
                            """
                            INSERT INTO crm_entity_mappings
                                (id, organisation_id, connection_id,
                                 revenueos_entity_type, revenueos_entity_id,
                                 external_object_type, external_object_id,
                                 created_by_user_id)
                            VALUES
                                (:crm_entity_mapping_id, :organisation_id,
                                 :connection_id, 'opportunity', :opportunity_id,
                                 'deal', :external_object_id, :user_id)
                            """
                        ),
                        {**identity_parameters, "external_object_id": f"deal-{suffix.lower()}"},
                    )
                    await connection.execute(
                        text(
                            """
                            INSERT INTO crm_field_mappings
                                (id, organisation_id, connection_id, entity_type,
                                 revenueos_field, external_property_name,
                                 external_property_type, authority,
                                 configured_by_user_id)
                            VALUES
                                (:crm_field_mapping_id, :organisation_id,
                                 :connection_id, 'opportunity', 'amount',
                                 'amount', 'number', 'review_before_sync',
                                 :user_id)
                            """
                        ),
                        identity_parameters,
                    )
                    await connection.execute(
                        text(
                            """
                            INSERT INTO crm_stage_mappings
                                (id, organisation_id, connection_id,
                                 revenueos_stage, external_pipeline_id,
                                 external_stage_id, configured_by_user_id)
                            VALUES
                                (:crm_stage_mapping_id, :organisation_id,
                                 :connection_id, 'discovery', 'default',
                                 :external_stage_id, :user_id)
                            """
                        ),
                        {**identity_parameters, "external_stage_id": f"stage-{suffix.lower()}"},
                    )
                    await connection.execute(
                        text(
                            """
                            INSERT INTO methodology_definitions
                                (id, organisation_id, status, current_version,
                                 created_by_user_id)
                            VALUES
                                (:methodology_definition_id, :organisation_id,
                                 'active', 1, :user_id)
                            """
                        ),
                        identity_parameters,
                    )
                    await connection.execute(
                        text(
                            """
                            INSERT INTO methodology_definition_versions
                                (id, organisation_id, definition_id, version,
                                 schema_version, content_json,
                                 content_fingerprint, created_by_user_id)
                            VALUES
                                (:methodology_definition_version_id,
                                 :organisation_id, :methodology_definition_id,
                                 1, 1, CAST(:methodology_content AS json),
                                 :methodology_fingerprint, :user_id)
                            """
                        ),
                        {
                            **identity_parameters,
                            "methodology_content": (
                                '{"key":"rls_methodology","name":"RLS Methodology",'
                                '"description":"RLS custom definition",'
                                '"version":1,"standard":false,"fields":[]}'
                            ),
                            "methodology_fingerprint": suffix.lower() * 64,
                        },
                    )
                    await connection.execute(
                        text(
                            """
                            INSERT INTO organisation_methodology_settings
                                (organisation_id, selection,
                                 updated_by_user_id)
                            VALUES (:organisation_id, 'bant', :user_id)
                            """
                        ),
                        identity_parameters,
                    )
                    await connection.execute(
                        text(
                            """
                            INSERT INTO methodology_projections
                                (id, organisation_id, opportunity_id,
                                 methodology_kind, definition_key,
                                 definition_version, projection_version,
                                 engine_version, schema_version,
                                 source_fingerprint, content_json,
                                 generated_by_user_id)
                            VALUES
                                (:methodology_projection_id, :organisation_id,
                                 :opportunity_id, 'standard', 'bant', 1, 1,
                                 1, 1, :methodology_fingerprint,
                                 '{}'::json, :user_id)
                            """
                        ),
                        {
                            **identity_parameters,
                            "methodology_fingerprint": suffix.upper() * 64,
                        },
                    )
                    await connection.execute(
                        text(
                            """
                            INSERT INTO methodology_reviews
                                (id, organisation_id, projection_id,
                                 opportunity_id, field_key, action,
                                 reviewed_by_user_id, idempotency_key)
                            VALUES
                                (:methodology_review_id, :organisation_id,
                                 :methodology_projection_id, :opportunity_id,
                                 'budget', 'confirm_interpretation', :user_id,
                                 :methodology_review_key)
                            """
                        ),
                        {
                            **identity_parameters,
                            "methodology_review_key": f"rls-methodology-review-{suffix.lower()}",
                        },
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
                            INSERT INTO action_proposals
                                (id, organisation_id, opportunity_id, interaction_id,
                                 action_type, status, priority, audience, risk_class,
                                 current_version, source_fingerprint, semantic_key,
                                 created_by_user_id)
                            VALUES
                                (:action_id, :organisation_id, :opportunity_id,
                                 :interaction_id, 'create_task', 'proposed', 'normal',
                                 'internal', 'internal_low_risk', 1,
                                 :source_fingerprint, :semantic_key, :user_id)
                            """
                        ),
                        {
                            **identity_parameters,
                            "source_fingerprint": f"{suffix.lower():0<64}"[:64],
                            "semantic_key": f"{suffix.upper():0<64}"[:64],
                        },
                    )
                    await connection.execute(
                        text(
                            """
                            INSERT INTO action_proposal_versions
                                (id, organisation_id, action_id, version, title,
                                 description, payload_json, source_refs_json,
                                 provenance_summary, content_fingerprint,
                                 created_by_user_id)
                            VALUES
                                (:action_version_id, :organisation_id, :action_id, 1,
                                 :action_title, :action_description,
                                 :payload_json, '[]'::json, :provenance_summary,
                                 :content_fingerprint, :user_id)
                            """
                        ),
                        {
                            **identity_parameters,
                            "action_title": f"RLS Action {suffix}",
                            "action_description": f"Tenant-isolated Action {suffix}",
                            "payload_json": '{"kind":"create_task","title":"Review"}',
                            "provenance_summary": "Validated tenant evidence",
                            "content_fingerprint": f"{suffix.lower():0<64}"[:64],
                        },
                    )
                    await connection.execute(
                        text(
                            """
                            INSERT INTO action_audit_events
                                (id, organisation_id, action_id, actor_user_id,
                                 event_type, proposal_version, metadata_json)
                            VALUES
                                (:action_audit_event_id, :organisation_id, :action_id,
                                 :user_id, 'proposed', 1, '{}'::json)
                            """
                        ),
                        identity_parameters,
                    )
                    await connection.execute(
                        text(
                            """
                            INSERT INTO interaction_markers
                                (id, organisation_id, interaction_id,
                                 created_by_user_id, marker_type,
                                 recording_offset_ms, idempotency_key)
                            VALUES
                                (:marker_id, :organisation_id,
                                 :interaction_id, :user_id,
                                 'buying_signal', 1000, :marker_key)
                            """
                        ),
                        {
                            **identity_parameters,
                            "marker_key": f"rls-marker-{suffix.lower()}",
                        },
                    )
                    await connection.execute(
                        text(
                            """
                            INSERT INTO online_meeting_metadata
                                (id, organisation_id, interaction_id,
                                 meeting_platform, capture_source,
                                 ingestion_state)
                            VALUES
                                (:online_meeting_metadata_id,
                                 :organisation_id, :interaction_id,
                                 'google_meet', 'platform_transcript', 'ready')
                            """
                        ),
                        identity_parameters,
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
                            INSERT INTO document_sources
                                (id, organisation_id, company_id, opportunity_id,
                                 interaction_id, capture_session_id, source_evidence_id,
                                 uploaded_by_user_id, document_type, source_ownership,
                                 display_filename, storage_key, mime_type, byte_size,
                                 checksum_sha256, document_at, idempotency_key,
                                 authority_confirmed_at,
                                 external_processing_acknowledged_at)
                            VALUES
                                (:document_source_id, :organisation_id, :company_id,
                                 :opportunity_id, :interaction_id, :capture_session_id,
                                 :evidence_id, :user_id, 'rfp', 'customer_provided',
                                 'rls-requirements.txt', :document_storage_key,
                                 'text/plain', 12, :document_checksum, now(),
                                 :document_idempotency_key, now(), now())
                            """
                        ),
                        {
                            **identity_parameters,
                            "document_storage_key": (
                                f"{tenant['organisation_id']}/documents/{tenant['document_source_id']}.txt"
                            ),
                            "document_checksum": "d" * 64,
                            "document_idempotency_key": f"rls-document-{suffix.lower()}",
                        },
                    )
                    await connection.execute(
                        text(
                            """
                            INSERT INTO document_fragments
                                (id, organisation_id, document_source_id,
                                 source_evidence_id, paragraph_index, content_text)
                            VALUES
                                (:document_fragment_id, :organisation_id,
                                 :document_source_id, :evidence_id, 0,
                                 'RLS customer requirement')
                            """
                        ),
                        identity_parameters,
                    )
                    await connection.execute(
                        text(
                            """
                            INSERT INTO email_sources
                                (id, organisation_id, company_id, opportunity_id,
                                 interaction_id, capture_session_id, source_evidence_id,
                                 submitted_by_user_id, sender_contact_id, source_type,
                                 direction, sender_identity_state, origin_class,
                                 support_class, subject, body_text, normalized_body_text,
                                 quote_handling, message_at, content_sha256,
                                 idempotency_key, authority_confirmed_at,
                                 external_processing_acknowledged_at)
                            VALUES
                                (:email_source_id, :organisation_id, :company_id,
                                 :opportunity_id, :interaction_id, :capture_session_id,
                                 :evidence_id, :user_id, :contact_id, 'customer_sent',
                                 'inbound', 'verified_contact', 'customer_direct',
                                 'direct', 'RLS email', 'Please proceed',
                                 'Please proceed', 'none', now(), :email_checksum,
                                 :email_idempotency_key, now(), now())
                            """
                        ),
                        {
                            **identity_parameters,
                            "email_checksum": "e" * 64,
                            "email_idempotency_key": f"rls-email-{suffix.lower()}",
                        },
                    )
                    await connection.execute(
                        text(
                            """
                            INSERT INTO source_candidate_evidence
                                (id, organisation_id, source_kind,
                                 document_source_id, source_evidence_id,
                                 document_fragment_id, evidence_category, statement,
                                 original_statement, statement_fingerprint,
                                 interpretation_origin, origin_class, support_class,
                                 source_location_json, validation_state, review_state,
                                 conflict_state)
                            VALUES
                                (:source_candidate_id, :organisation_id, 'document',
                                 :document_source_id, :evidence_id,
                                 :document_fragment_id, 'technical_requirement',
                                 'RLS customer requirement',
                                 'RLS customer requirement', :statement_fingerprint,
                                 'ai_inferred', 'customer_direct', 'direct',
                                 CAST(:source_location_json AS json),
                                 'unreviewed', 'pending', 'not_assessed')
                            """
                        ),
                        {
                            **identity_parameters,
                            "statement_fingerprint": "f" * 64,
                            "source_location_json": (
                                '{"reference":"Paragraph 1","pageNumber":null,"section":null,"paragraphIndex":0}'
                            ),
                        },
                    )
                    await connection.execute(
                        text(
                            """
                            INSERT INTO revenue_brain_source_snapshots
                                (id, organisation_id, company_id, opportunity_id,
                                 interaction_id, source_kind, document_source_id,
                                 source_evidence_id, source_evidence_ids, content_json,
                                 schema_version, version)
                            VALUES
                                (:source_snapshot_id, :organisation_id, :company_id,
                                 :opportunity_id, :interaction_id, 'document',
                                 :document_source_id, :evidence_id,
                                 '[]'::json,
                                 CAST(:source_snapshot_content_json AS json), 1, 1)
                            """
                        ),
                        {
                            **identity_parameters,
                            "source_snapshot_content_json": ('{"schemaVersion":1,"items":[]}'),
                        },
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
                            INSERT INTO recording_sessions
                                (id, organisation_id, interaction_id,
                                 capture_session_id, source_evidence_id,
                                 created_by_user_id, recording_type,
                                 lifecycle_status, consent_state,
                                 duration_seconds, expected_mime_type,
                                 final_mime_type, total_bytes, chunk_count,
                                 idempotency_key, upload_completed_at,
                                 transcription_completed_at, session_expires_at)
                            VALUES
                                (:recording_id, :organisation_id,
                                 :interaction_id, :capture_session_id,
                                 :evidence_id, :user_id,
                                 'live_audio_recording', 'completed',
                                 'acknowledged', 60, 'audio/webm',
                                 'audio/webm', 4, 1,
                                 :recording_idempotency_key, now(), now(),
                                 now() + interval '1 day')
                            """
                        ),
                        {
                            **identity_parameters,
                            "recording_idempotency_key": f"rls-recording-{suffix.lower()}",
                        },
                    )
                    await connection.execute(
                        text(
                            """
                            INSERT INTO recording_consents
                                (id, organisation_id, interaction_id,
                                 recording_session_id, user_id, notice_version,
                                 consent_method, user_attested_authority)
                            VALUES
                                (:recording_consent_id, :organisation_id,
                                 :interaction_id, :recording_id, :user_id, 1,
                                 'participant_notice_confirmed', true)
                            """
                        ),
                        identity_parameters,
                    )
                    await connection.execute(
                        text(
                            """
                            INSERT INTO recording_chunks
                                (id, organisation_id, recording_session_id,
                                 sequence_number, byte_size, checksum_sha256,
                                 storage_key, upload_state,
                                 upload_idempotency_key, upload_expires_at,
                                 uploaded_at)
                            VALUES
                                (:recording_chunk_id, :organisation_id,
                                 :recording_id, 0, 4, :recording_checksum,
                                 :recording_storage_key, 'verified',
                                 :recording_chunk_key, now() + interval '1 day',
                                 now())
                            """
                        ),
                        {
                            **identity_parameters,
                            "recording_checksum": suffix.lower() * 64,
                            "recording_storage_key": (
                                f"recordings/{tenant['organisation_id']}/{tenant['recording_id']}/rls.part"
                            ),
                            "recording_chunk_key": f"rls-recording-chunk-{suffix.lower()}",
                        },
                    )
                    await connection.execute(
                        text(
                            """
                            INSERT INTO transcript_versions
                                (id, organisation_id, interaction_id,
                                 meeting_id, transcript_id,
                                 recording_session_id, evidence_id, version,
                                 raw_text, language, source, status,
                                 provider_name)
                            VALUES
                                (:recording_transcript_version_id,
                                 :organisation_id, :interaction_id,
                                 :meeting_id, :transcript_id, :recording_id,
                                 :evidence_id, 1, :raw_text, 'en',
                                 'recorded_audio', 'final', 'mock')
                            """
                        ),
                        {
                            **identity_parameters,
                            "raw_text": f"RLS recorded transcript {suffix}",
                        },
                    )
                    await connection.execute(
                        text(
                            """
                            INSERT INTO transcript_segments
                                (id, organisation_id, transcript_version_id,
                                 sequence_number, start_ms, end_ms, speaker_role, text)
                            VALUES
                                (:recording_segment_id, :organisation_id,
                                 :recording_transcript_version_id, 0, 0, 60000, 'customer',
                                 :segment_text)
                            """
                        ),
                        {
                            **identity_parameters,
                            "segment_text": f"RLS recorded transcript {suffix}",
                        },
                    )
                    await connection.execute(
                        text(
                            """
                            INSERT INTO live_interaction_sessions
                                (id, organisation_id, interaction_id,
                                 transcript_version_id, brief_id,
                                 created_by_user_id, status, source_kind,
                                 last_processed_sequence,
                                 processed_character_count,
                                 processing_request_count, started_at,
                                 stopped_at, retention_expires_at)
                            VALUES
                                (:live_session_id, :organisation_id,
                                 :interaction_id, :recording_transcript_version_id,
                                 :brief_id, :user_id, 'completed',
                                 'progressive_transcript', 0, 25, 1,
                                 now(), now(), now() + interval '30 days')
                            """
                        ),
                        identity_parameters,
                    )
                    await connection.execute(
                        text(
                            """
                            INSERT INTO live_processing_windows
                                (id, organisation_id, live_session_id,
                                 trigger_idempotency_key, window_fingerprint,
                                 first_sequence, last_sequence, segment_count,
                                 character_count, status, signal_count,
                                 completed_at)
                            VALUES
                                (:live_window_id, :organisation_id,
                                 :live_session_id, :live_window_key,
                                 :live_window_fingerprint, 0, 0, 1, 25,
                                 'completed', 1, now())
                            """
                        ),
                        {
                            **identity_parameters,
                            "live_window_key": f"rls-live-window-{suffix.lower()}",
                            "live_window_fingerprint": suffix.lower() * 64,
                        },
                    )
                    await connection.execute(
                        text(
                            """
                            INSERT INTO provisional_signals
                                (id, organisation_id, interaction_id,
                                 live_session_id, transcript_version_id,
                                 signal_type, statement, lifecycle_status,
                                 is_provisional, priority, evidence_strength,
                                 resolution_status, signal_fingerprint,
                                 subject_fingerprint, source_sequence_start,
                                 source_sequence_end, detected_at,
                                 last_updated_at)
                            VALUES
                                (:provisional_signal_id, :organisation_id,
                                 :interaction_id, :live_session_id,
                                 :recording_transcript_version_id,
                                 'buying_signal', :live_signal_statement,
                                 'promoted_candidate', true, 'high',
                                 'customer_attributed', 'confirmed',
                                 :live_signal_fingerprint,
                                 :live_subject_fingerprint, 0, 0, now(), now())
                            """
                        ),
                        {
                            **identity_parameters,
                            "live_signal_statement": f"RLS provisional signal {suffix}.",
                            "live_signal_fingerprint": suffix.upper() * 64,
                            "live_subject_fingerprint": suffix.lower() * 64,
                        },
                    )
                    await connection.execute(
                        text(
                            """
                            INSERT INTO live_brief_progress
                                (id, organisation_id, live_session_id,
                                 item_type, item_index, item_fingerprint,
                                 progress_status, source_sequence_end)
                            VALUES
                                (:live_brief_progress_id, :organisation_id,
                                 :live_session_id, 'objective', 0,
                                 :live_progress_fingerprint,
                                 'possibly_addressed', 0)
                            """
                        ),
                        {
                            **identity_parameters,
                            "live_progress_fingerprint": suffix.lower() * 64,
                        },
                    )
                    await connection.execute(
                        text(
                            """
                            INSERT INTO online_meeting_transcript_imports
                                (id, organisation_id, interaction_id,
                                 capture_session_id, evidence_id,
                                 transcript_version_id, imported_by_user_id,
                                 provenance, source_format, language,
                                 content_sha256, character_count,
                                 timestamps_present, speaker_labels_present,
                                 idempotency_key)
                            VALUES
                                (:online_meeting_transcript_import_id,
                                 :organisation_id, :interaction_id,
                                 :capture_session_id, :evidence_id,
                                 :recording_transcript_version_id, :user_id,
                                 'platform_generated', 'vtt', 'en-AU',
                                 :online_transcript_checksum, 25, true, true,
                                 :online_transcript_key)
                            """
                        ),
                        {
                            **identity_parameters,
                            "online_transcript_checksum": suffix.lower() * 64,
                            "online_transcript_key": f"rls-online-transcript-{suffix.lower()}",
                        },
                    )
                    await connection.execute(
                        text(
                            """
                            UPDATE recording_sessions
                            SET transcript_version_id = :recording_transcript_version_id
                            WHERE organisation_id = :organisation_id
                              AND id = :recording_id
                            """
                        ),
                        identity_parameters,
                    )
                    await connection.execute(
                        text(
                            """
                            INSERT INTO recording_usage_counters
                                (organisation_id, usage_date, uploaded_bytes,
                                 transcription_minutes,
                                 transcription_request_count)
                            VALUES (:organisation_id, CURRENT_DATE, 4, 1, 1)
                            """
                        ),
                        identity_parameters,
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

                savepoint = await connection.begin_nested()
                with pytest.raises(DBAPIError):
                    await connection.execute(
                        text(
                            """
                            INSERT INTO recording_chunks
                                (id, organisation_id, recording_session_id,
                                 sequence_number, byte_size, checksum_sha256,
                                 storage_key, upload_state,
                                 upload_idempotency_key, upload_expires_at)
                            VALUES
                                (:id, :organisation_id,
                                 :recording_session_id, 9, 4,
                                 :checksum, :storage_key, 'pending',
                                 'cross-tenant-recording-chunk', now())
                            """
                        ),
                        {
                            "id": uuid.uuid4(),
                            "organisation_id": tenant_a["organisation_id"],
                            "recording_session_id": tenant_b["recording_id"],
                            "checksum": "c" * 64,
                            "storage_key": (f"recordings/{tenant_a['organisation_id']}/cross-tenant.part"),
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
                                    'action_proposals',
                                    'action_proposal_versions',
                                    'action_audit_events',
                                    'integration_connections',
                                    'execution_previews',
                                    'action_executions',
                                    'action_execution_attempts',
                                    'integration_audit_events',
                                    'mock_connector_objects',
                                    'oauth_connection_states',
                                    'encrypted_connector_credentials',
                                    'crm_entity_mappings',
                                    'crm_field_mappings',
                                    'crm_stage_mappings',
                                    'tasks',
                                    'interactions',
                                    'online_meeting_metadata',
                                    'online_meeting_transcript_imports',
                                    'interaction_markers',
                                    'pre_interaction_briefs',
                                    'capture_sessions',
                                    'evidence',
                                    'visual_assets',
                                    'visual_candidate_evidence',
                                    'document_sources',
                                    'document_fragments',
                                    'email_sources',
                                    'source_candidate_evidence',
                                    'revenue_brain_source_snapshots',
                                    'recording_usage_counters',
                                    'recording_sessions',
                                    'recording_consents',
                                    'recording_chunks',
                                    'transcript_versions',
                                    'transcript_segments',
                                    'live_interaction_sessions',
                                    'live_processing_windows',
                                    'provisional_signals',
                                    'live_brief_progress',
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
                                    'beta_system_events',
                                    'methodology_definitions',
                                    'methodology_definition_versions',
                                    'organisation_methodology_settings',
                                    'methodology_projections',
                                    'methodology_reviews',
                                    'organisation_module_entitlements',
                                    'prospect_usage_counters',
                                    'prospect_research_targets',
                                    'prospect_research_runs',
                                    'prospect_research_sources',
                                    'prospect_research_observations',
                                    'prospect_research_observation_sources'
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
                empty_wo022_tables = {
                    "execution_previews",
                    "action_executions",
                    "action_execution_attempts",
                    "integration_audit_events",
                    "mock_connector_objects",
                }
                expected_tenant_a_counts = {
                    table: (0 if table in empty_wo022_tables else 2 if table == "revenue_brain_snapshots" else 1)
                    for table in tenant_tables
                }
                assert tenant_a_counts == expected_tenant_a_counts
                company_update = await connection.execute(
                    text("UPDATE companies SET name = 'Blocked' WHERE id = :id"),
                    {"id": tenant_b["company_id"]},
                )
                assert company_update.rowcount == 0
                prospect_update = await connection.execute(
                    text(
                        """
                        UPDATE prospect_research_observations
                        SET statement = 'Blocked cross-tenant update.'
                        WHERE id = :id
                        """
                    ),
                    {"id": tenant_b["prospect_observation_id"]},
                )
                assert prospect_update.rowcount == 0
                prospect_delete = await connection.execute(
                    text("DELETE FROM prospect_research_sources WHERE id = :id"),
                    {"id": tenant_b["prospect_source_id"]},
                )
                assert prospect_delete.rowcount == 0
                savepoint = await connection.begin_nested()
                with pytest.raises(DBAPIError):
                    await connection.execute(
                        text(
                            """
                            INSERT INTO prospect_research_targets
                                (id, organisation_id, provider_key,
                                 provider_candidate_id, name, normalized_domain,
                                 website_url, provider_attribution)
                            VALUES
                                (:id, :organisation_id, 'mock',
                                 'forged-cross-tenant', 'Forged target',
                                 'forged.example', 'https://forged.example/',
                                 'Synthetic RLS data')
                            """
                        ),
                        {
                            "id": uuid.uuid4(),
                            "organisation_id": tenant_b["organisation_id"],
                        },
                    )
                await savepoint.rollback()
                crm_mapping_update = await connection.execute(
                    text(
                        """
                        UPDATE crm_entity_mappings
                        SET external_object_id = 'blocked-cross-tenant-write'
                        WHERE id = :id
                        """
                    ),
                    {"id": tenant_b["crm_entity_mapping_id"]},
                )
                assert crm_mapping_update.rowcount == 0
                methodology_definition_update = await connection.execute(
                    text("UPDATE methodology_definitions SET status = 'archived' WHERE id = :id"),
                    {"id": tenant_b["methodology_definition_id"]},
                )
                assert methodology_definition_update.rowcount == 0
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
                    daily_repository = DailyRepository(session)
                    own_daily_opportunities = await daily_repository.opportunities(
                        tenant_a["organisation_id"],
                        tenant_a["user_id"],
                    )
                    assert {item.opportunity.id for item in own_daily_opportunities} == {tenant_a["opportunity_id"]}
                    assert (
                        await daily_repository.opportunities(
                            tenant_b["organisation_id"],
                            tenant_b["user_id"],
                        )
                        == []
                    )
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
                        INSERT INTO live_interaction_sessions
                            (id, organisation_id, interaction_id,
                             transcript_version_id, created_by_user_id,
                             status, source_kind, retention_expires_at)
                        VALUES
                            (:id, :organisation_id, :interaction_id,
                             :transcript_version_id, :user_id, 'active',
                             'progressive_transcript', now() + interval '30 days')
                        """,
                        {
                            "id": uuid.uuid4(),
                            "organisation_id": tenant_a["organisation_id"],
                            "interaction_id": tenant_b["interaction_id"],
                            "transcript_version_id": tenant_b["recording_transcript_version_id"],
                            "user_id": tenant_a["user_id"],
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
                await connection.execute(
                    text(
                        "UPDATE recording_sessions SET transcript_version_id = NULL "
                        "WHERE organisation_id IN (:organisation_a, :organisation_b)"
                    ),
                    {
                        "organisation_a": tenant_a["organisation_id"],
                        "organisation_b": tenant_b["organisation_id"],
                    },
                )
                for table in (
                    "prospect_research_observation_sources",
                    "prospect_research_observations",
                    "prospect_research_sources",
                    "prospect_research_runs",
                    "prospect_research_targets",
                    "prospect_usage_counters",
                    "organisation_module_entitlements",
                    "crm_stage_mappings",
                    "crm_field_mappings",
                    "crm_entity_mappings",
                    "encrypted_connector_credentials",
                    "oauth_connection_states",
                    "integration_connections",
                    "beta_system_events",
                    "beta_data_requests",
                    "beta_feedback",
                    "methodology_reviews",
                    "methodology_projections",
                    "organisation_methodology_settings",
                    "methodology_definition_versions",
                    "methodology_definitions",
                    "ai_usage_counters",
                    "onboarding_progress",
                    "data_notice_acknowledgements",
                    "organisation_beta_settings",
                    "revenue_brain_insights",
                    "live_brief_progress",
                    "provisional_signals",
                    "live_processing_windows",
                    "live_interaction_sessions",
                    "revenue_brain_interaction_snapshots",
                    "interaction_intelligence_snapshots",
                    "revenue_brain_snapshots",
                    "ai_artifacts",
                    "ai_jobs",
                    "opportunity_audit_events",
                    "pre_interaction_briefs",
                    "candidate_evidence",
                    "revenue_brain_source_snapshots",
                    "source_candidate_evidence",
                    "document_fragments",
                    "document_sources",
                    "email_sources",
                    "visual_candidate_evidence",
                    "visual_assets",
                    "online_meeting_transcript_imports",
                    "transcript_segments",
                    "transcript_versions",
                    "recording_chunks",
                    "recording_consents",
                    "recording_sessions",
                    "recording_usage_counters",
                    "evidence_fragments",
                    "debrief_turns",
                    "debrief_sessions",
                    "evidence",
                    "capture_sessions",
                    "interaction_audit_events",
                    "interaction_markers",
                    "meeting_audit_events",
                    "transcripts",
                    "meeting_participants",
                    "meetings",
                    "online_meeting_metadata",
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
                role_exists = await connection.scalar(
                    text("SELECT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = :role_name)"),
                    {"role_name": role_name},
                )
                if role_exists:
                    await connection.exec_driver_sql(f'DROP OWNED BY "{role_name}"')
                    await connection.exec_driver_sql(f'DROP ROLE "{role_name}"')
            await engine.dispose()

    asyncio.run(scenario())
