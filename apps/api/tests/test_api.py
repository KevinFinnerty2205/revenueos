import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from revenueos.config import Settings
from revenueos.main import create_app


def test_health_returns_exact_process_status(client: TestClient) -> None:
    response = client.get("/health", headers={"X-Request-ID": "test-health-001"})

    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}
    assert response.headers["X-Request-ID"] == "test-health-001"


def test_invalid_request_id_is_replaced(client: TestClient) -> None:
    response = client.get("/health", headers={"X-Request-ID": "unsafe request id"})

    assert response.status_code == 200
    assert response.headers["X-Request-ID"] != "unsafe request id"
    assert len(response.headers["X-Request-ID"]) == 36


def test_ready_reports_configured_local_dependencies(client: TestClient) -> None:
    response = client.get("/ready")

    assert response.status_code == 200
    assert response.json()["status"] == "ready"
    assert response.json()["dependencies"]["database"]["status"] == "ready"
    assert response.json()["dependencies"]["authentication"]["status"] == "ready"
    assert "url" not in response.text.lower()


def test_ready_reports_limited_mode_without_persistence() -> None:
    app = create_app(
        Settings(
            environment="test",
            auth_mode="mock",
            mock_auth_enabled=True,
            database_url=None,
            log_level="WARNING",
        ),
    )

    response = TestClient(app).get("/ready")

    assert response.status_code == 503
    assert response.json()["status"] == "not_ready"
    assert response.json()["dependencies"]["database"] == {
        "status": "unavailable",
        "detail": "Persistence is unavailable.",
    }


def test_me_uses_trusted_development_auth_context(client: TestClient) -> None:
    response = client.get(
        "/api/v1/me?organisationId=00000000-0000-4000-8000-000000000099",
        headers={"X-Request-ID": "test-me-001"},
    )

    assert response.status_code == 200
    assert response.json()["authMode"] == "mock"
    assert response.json()["role"] == "admin"
    assert response.json()["organisation"] == {
        "id": "00000000-0000-4000-8000-000000000002",
        "name": "Example Revenue Team",
        "slug": "example-revenue-team",
    }
    assert response.json()["requestId"] == "test-me-001"


def test_unauthenticated_clerk_request_is_rejected() -> None:
    app = create_app(
        Settings(
            environment="test",
            auth_mode="clerk",
            mock_auth_enabled=False,
            database_url=None,
            clerk_jwks_url="https://clerk.example.test/.well-known/jwks.json",
            clerk_issuer="https://clerk.example.test",
            clerk_audience="revenueos-api",
            log_level="WARNING",
        ),
    )

    response = TestClient(app).get("/api/v1/me")

    assert response.status_code == 401
    assert response.json()["code"] == "authentication_required"
    assert response.json()["message"] == "Authentication is required."
    assert response.json()["requestId"] == response.headers["X-Request-ID"]


def test_unknown_route_returns_safe_error(client: TestClient) -> None:
    response = client.get("/not-a-route")

    assert response.status_code == 404
    assert response.json()["code"] == "http_error"
    assert response.json()["message"] == "The requested resource was not found."
    assert set(response.json()) == {"code", "message", "requestId"}


def test_production_rejects_mock_authentication() -> None:
    with pytest.raises(ValidationError, match="Production requires Clerk mode"):
        Settings(
            environment="production",
            auth_mode="mock",
            mock_auth_enabled=True,
        )


def test_production_engage_requires_deployment_suppression_key() -> None:
    with pytest.raises(ValidationError, match="suppression HMAC key"):
        Settings(
            environment="production",
            auth_mode="clerk",
            mock_auth_enabled=False,
            clerk_jwks_url="https://identity.example.test/jwks",
            clerk_issuer="https://identity.example.test",
            clerk_audience="revenueos",
            database_url="postgresql+asyncpg://example.invalid/revenueos",
            cors_origins="https://app.example.test",
        )


def test_event_intelligence_rollout_defaults_off() -> None:
    assert Settings().feature_engage_events_enabled is False


def test_openapi_contains_current_domain_endpoints(client: TestClient) -> None:
    response = client.get("/openapi.json")

    assert response.status_code == 200
    paths = set(response.json()["paths"])
    assert paths == {
        "/health",
        "/health/live",
        "/health/ready",
        "/ready",
        "/api/v1/me",
        "/api/v1/beta/capabilities",
        "/api/v1/beta/data-notice",
        "/api/v1/beta/data-notice/acknowledgements",
        "/api/v1/beta/onboarding",
        "/api/v1/beta/feedback",
        "/api/v1/beta/admin",
        "/api/v1/beta/admin/retention",
        "/api/v1/beta/admin/feedback",
        "/api/v1/beta/admin/members/{user_id}",
        "/api/v1/beta/admin/exports",
        "/api/v1/beta/admin/data-requests",
        "/api/v1/beta/admin/exports/{request_id}/download",
        "/api/v1/beta/admin/organisation-deletion",
        "/api/v1/ask",
        "/api/v1/ask/capabilities",
        "/api/v1/ask/telemetry",
        "/api/v1/crm/availability",
        "/api/v1/crm/admin/entitlement",
        "/api/v1/crm/settings",
        "/api/v1/crm/members",
        "/api/v1/crm/custom-fields",
        "/api/v1/crm/custom-fields/{definition_id}",
        "/api/v1/crm/custom-fields/{definition_id}/archive",
        "/api/v1/crm/records/{entity_type}/{entity_id}",
        "/api/v1/crm/records/{entity_type}/{entity_id}/custom-fields/{definition_id}",
        "/api/v1/crm/records/{entity_type}/{entity_id}/archive",
        "/api/v1/crm/records/{entity_type}/{entity_id}/restore",
        "/api/v1/create/availability",
        "/api/v1/create/admin/entitlement",
        "/api/v1/create/templates",
        "/api/v1/create/templates/{template_id}",
        "/api/v1/create/template-slides/{slide_id}",
        "/api/v1/create/templates/{template_id}/versions/{version_id}/approve",
        "/api/v1/create/value-models",
        "/api/v1/create/value-models/{model_id}",
        "/api/v1/create/value-models/{model_id}/versions",
        "/api/v1/create/value-models/{model_id}/versions/{version_id}/approve",
        "/api/v1/create/value-models/{model_id}/archive",
        "/api/v1/create/business-cases",
        "/api/v1/create/business-cases/{case_id}",
        "/api/v1/create/business-cases/{case_id}/calculate",
        "/api/v1/create/business-cases/{case_id}/approve",
        "/api/v1/create/business-cases/{case_id}/archive",
        "/api/v1/create/presentations",
        "/api/v1/create/presentations/{presentation_id}",
        "/api/v1/create/presentations/{presentation_id}/plan",
        "/api/v1/create/presentations/{presentation_id}/generate",
        "/api/v1/create/presentations/{presentation_id}/slides/{plan_item_id}",
        "/api/v1/create/presentations/{presentation_id}/review",
        "/api/v1/create/presentations/{presentation_id}/approve",
        "/api/v1/create/presentations/{presentation_id}/download-grant",
        "/api/v1/create/presentations/{presentation_id}/download",
        "/api/v1/accounts/{account_id}/brain",
        "/api/v1/accounts/{account_id}/brain/reported-interactions",
        "/api/v1/accounts/{account_id}/brain/visual-evidence",
        "/api/v1/accounts/{account_id}/brain/reasoning",
        "/api/v1/evidence/capabilities",
        "/api/v1/evidence/documents",
        "/api/v1/evidence/documents/{document_id}",
        "/api/v1/evidence/documents/{document_id}/content",
        "/api/v1/evidence/documents/{document_id}/process",
        "/api/v1/evidence/documents/{document_id}/review",
        "/api/v1/evidence/emails",
        "/api/v1/evidence/emails/{email_id}",
        "/api/v1/evidence/emails/{email_id}/process",
        "/api/v1/evidence/emails/{email_id}/review",
        "/api/v1/evidence/opportunities/{opportunity_id}",
        "/api/v1/evidence/accounts/{company_id}/brain",
        "/api/v1/prospect/availability",
        "/api/v1/prospect/admin/entitlement",
        "/api/v1/prospect/discovery/capabilities",
        "/api/v1/prospect/target-markets",
        "/api/v1/prospect/target-markets/{target_market_id}",
        "/api/v1/prospect/target-markets/{target_market_id}/archive",
        "/api/v1/prospect/target-markets/{target_market_id}/discover",
        "/api/v1/prospect/discovery/{run_id}",
        "/api/v1/prospect/candidates/{candidate_id}/save",
        "/api/v1/prospect/candidates/{candidate_id}/exclude",
        "/api/v1/prospect/candidates/{candidate_id}/restore",
        "/api/v1/prospect/companies/search",
        "/api/v1/prospect/research",
        "/api/v1/prospect/research/{target_id}",
        "/api/v1/prospect/research/{target_id}/refresh",
        "/api/v1/prospect/research/{target_id}/promote",
        "/api/v1/prospect/research/{target_id}/people",
        "/api/v1/prospect/research/{target_id}/people/discover",
        "/api/v1/prospect/people/{person_id}",
        "/api/v1/prospect/people/{person_id}/research",
        "/api/v1/prospect/people/{person_id}/refresh",
        "/api/v1/prospect/people/{person_id}/buying-roles/{hypothesis_id}",
        "/api/v1/prospect/people/{person_id}/promote",
        "/api/v1/prospect/accounts/{company_id}/research-link",
        "/api/v1/prospect/contacts/{contact_id}/research-link",
        "/api/v1/engage/availability",
        "/api/v1/engage/admin/entitlement",
        "/api/v1/engage/policy",
        "/api/v1/engage/contacts/{contact_id}",
        "/api/v1/engage/contacts/{contact_id}/outreach",
        "/api/v1/engage/contacts/{contact_id}/suppression",
        "/api/v1/engage/outreach/{outreach_id}",
        "/api/v1/engage/outreach/{outreach_id}/approve",
        "/api/v1/engage/outreach/{outreach_id}/execution-preview",
        "/api/v1/engage/outreach/{outreach_id}/send",
        "/api/v1/engage/campaigns",
        "/api/v1/engage/campaigns/{campaign_id}",
        "/api/v1/engage/campaigns/{campaign_id}/launch",
        "/api/v1/engage/campaigns/{campaign_id}/pause",
        "/api/v1/engage/campaigns/{campaign_id}/resume",
        "/api/v1/engage/campaigns/{campaign_id}/stop",
        "/api/v1/engage/campaigns/{campaign_id}/enrollments",
        "/api/v1/engage/enrollments/{enrollment_id}",
        "/api/v1/engage/enrollments/{enrollment_id}/stop",
        "/api/v1/engage/enrollments/{enrollment_id}/outcome",
        "/api/v1/engage/events",
        "/api/v1/engage/events/{event_id}",
        "/api/v1/engage/events/{event_id}/attendee-imports/preview",
        "/api/v1/engage/events/{event_id}/attendee-imports/{import_id}",
        "/api/v1/engage/events/{event_id}/attendee-imports/{import_id}/confirm",
        "/api/v1/engage/events/{event_id}/attendees",
        "/api/v1/engage/events/{event_id}/attendees/{attendee_id}",
        "/api/v1/engage/events/{event_id}/attendees/{attendee_id}/plan",
        "/api/v1/engage/events/{event_id}/attendees/{attendee_id}/encounter",
        "/api/v1/engage/events/{event_id}/attendees/{attendee_id}/promote",
        "/api/v1/engage/events/{event_id}/attendees/{attendee_id}/outreach",
        "/api/v1/companies",
        "/api/v1/companies/{company_id}",
        "/api/v1/contacts",
        "/api/v1/contacts/{contact_id}",
        "/api/v1/daily",
        "/api/v1/insights/sales/metadata",
        "/api/v1/insights/sales/metrics",
        "/api/v1/insights/sales/metrics/{metric_id}",
        "/api/v1/insights/sales/overview",
        "/api/v1/insights/sales/funnel",
        "/api/v1/insights/sales/activity",
        "/api/v1/insights/sales/win-loss",
        "/api/v1/targets",
        "/api/v1/targets/metadata",
        "/api/v1/targets/{target_id}",
        "/api/v1/targets/{target_id}/revisions",
        "/api/v1/targets/{target_id}/archive",
        "/api/v1/pipeline",
        "/api/v1/pipelines",
        "/api/v1/pipelines/{pipeline_id}",
        "/api/v1/pipelines/{pipeline_id}/archive",
        "/api/v1/pipelines/{pipeline_id}/stages",
        "/api/v1/pipelines/{pipeline_id}/stages/{stage_id}",
        "/api/v1/pipelines/{pipeline_id}/stages/{stage_id}/archive",
        "/api/v1/opportunities",
        "/api/v1/opportunities/{opportunity_id}",
        "/api/v1/opportunities/{opportunity_id}/pipeline",
        "/api/v1/opportunities/{opportunity_id}/stage",
        "/api/v1/opportunities/{opportunity_id}/close-won",
        "/api/v1/opportunities/{opportunity_id}/close-lost",
        "/api/v1/opportunities/{opportunity_id}/reopen",
        "/api/v1/opportunities/{opportunity_id}/brain/reasoning",
        "/api/v1/opportunities/{opportunity_id}/workspace",
        "/api/v1/opportunities/{opportunity_id}/workspace/latest-meeting-navigation",
        "/api/v1/opportunities/{opportunity_id}/methodology",
        "/api/v1/opportunities/{opportunity_id}/methodology/generate",
        "/api/v1/opportunities/{opportunity_id}/methodology/history",
        "/api/v1/opportunities/{opportunity_id}/methodology/{field_key}/review",
        "/api/v1/methodologies",
        "/api/v1/methodologies/current",
        "/api/v1/methodologies/custom",
        "/api/v1/methodologies/custom/{definition_id}",
        "/api/v1/opportunities/{opportunity_id}/actions",
        "/api/v1/opportunities/{opportunity_id}/actions/generate",
        "/api/v1/actions/{action_id}",
        "/api/v1/actions/{action_id}/approve",
        "/api/v1/actions/{action_id}/reject",
        "/api/v1/actions/{action_id}/complete",
        "/api/v1/actions/{action_id}/execution-preview",
        "/api/v1/actions/{action_id}/execution-options",
        "/api/v1/actions/{action_id}/execute",
        "/api/v1/actions/{action_id}/executions",
        "/api/v1/executions/{execution_id}",
        "/api/v1/integrations",
        "/api/v1/integrations/connections",
        "/api/v1/integrations/connections/{connection_id}",
        "/api/v1/integrations/connections/{connection_id}/test",
        "/api/v1/integrations/hubspot/oauth/start",
        "/api/v1/integrations/hubspot/oauth/callback",
        "/api/v1/integrations/connections/{connection_id}/crm/search",
        "/api/v1/integrations/connections/{connection_id}/crm/entities/{entity_type}/{entity_id}",
        "/api/v1/integrations/crm/entities/{entity_type}/{entity_id}",
        "/api/v1/integrations/connections/{connection_id}/crm/fields/{entity_type}",
        "/api/v1/integrations/connections/{connection_id}/crm/fields",
        "/api/v1/integrations/connections/{connection_id}/crm/stages",
        "/api/v1/executions/{execution_id}/reconcile",
        "/api/v1/tasks",
        "/api/v1/tasks/{task_id}",
        "/api/v1/interactions",
        "/api/v1/interactions/{interaction_id}",
        "/api/v1/interactions/{interaction_id}/complete",
        "/api/v1/interactions/{interaction_id}/start",
        "/api/v1/interactions/{interaction_id}/companion/brief",
        "/api/v1/interactions/{interaction_id}/companion/brief/review",
        "/api/v1/interactions/{interaction_id}/companion/markers",
        "/api/v1/interactions/{interaction_id}/companion/markers/{marker_id}",
        "/api/v1/interactions/{interaction_id}/live-intelligence",
        "/api/v1/interactions/{interaction_id}/live-intelligence/start",
        "/api/v1/interactions/{interaction_id}/live-intelligence/process",
        "/api/v1/interactions/{interaction_id}/live-intelligence/stop",
        "/api/v1/interactions/{interaction_id}/live-intelligence/{signal_id}/dismiss",
        "/api/v1/interactions/{interaction_id}/live-intelligence/reconcile",
        "/api/v1/interactions/{interaction_id}/online-meeting/capabilities",
        "/api/v1/interactions/{interaction_id}/online-meeting/transcript",
        "/api/v1/interactions/{interaction_id}/online-meeting/transcripts",
        "/api/v1/interactions/{interaction_id}/debrief",
        "/api/v1/interactions/{interaction_id}/debrief/{session_id}",
        "/api/v1/interactions/{interaction_id}/debrief/{session_id}/response",
        "/api/v1/interactions/{interaction_id}/debrief/{session_id}/voice-response",
        "/api/v1/interactions/{interaction_id}/debrief/{session_id}/finish",
        "/api/v1/interactions/{interaction_id}/debrief/{session_id}/review",
        "/api/v1/interactions/{interaction_id}/debrief/{session_id}/cancel",
        "/api/v1/interactions/{interaction_id}/recordings",
        "/api/v1/interactions/{interaction_id}/recordings/{recording_id}",
        "/api/v1/interactions/{interaction_id}/recordings/{recording_id}/start",
        "/api/v1/interactions/{interaction_id}/recordings/{recording_id}/pause",
        "/api/v1/interactions/{interaction_id}/recordings/{recording_id}/resume",
        "/api/v1/interactions/{interaction_id}/recordings/{recording_id}/stop",
        "/api/v1/interactions/{interaction_id}/recordings/{recording_id}/chunks",
        "/api/v1/interactions/{interaction_id}/recordings/{recording_id}/chunks/{chunk_id}/content",
        "/api/v1/interactions/{interaction_id}/recordings/{recording_id}/chunks/{chunk_id}/complete",
        "/api/v1/interactions/{interaction_id}/recordings/{recording_id}/finalize",
        "/api/v1/interactions/{interaction_id}/recordings/{recording_id}/cancel",
        "/api/v1/interactions/{interaction_id}/recordings/{recording_id}/transcription",
        "/api/v1/interactions/{interaction_id}/visual-evidence/uploads",
        "/api/v1/interactions/{interaction_id}/visual-evidence",
        "/api/v1/interactions/{interaction_id}/visual-evidence/{visual_id}",
        "/api/v1/interactions/{interaction_id}/visual-evidence/{visual_id}/content",
        "/api/v1/interactions/{interaction_id}/visual-evidence/{visual_id}/complete",
        "/api/v1/interactions/{interaction_id}/visual-evidence/{visual_id}/process",
        "/api/v1/interactions/{interaction_id}/visual-evidence/{visual_id}/review",
        "/api/v1/meetings",
        "/api/v1/meetings/{meeting_id}",
        "/api/v1/meetings/{meeting_id}/opportunity",
        "/api/v1/meetings/{meeting_id}/history",
        "/api/v1/meetings/{meeting_id}/intelligence",
        "/api/v1/meetings/{meeting_id}/intelligence/generate",
        "/api/v1/meetings/{meeting_id}/intelligence/executive-summary",
        "/api/v1/meetings/{meeting_id}/intelligence/buying-signals",
        "/api/v1/meetings/{meeting_id}/intelligence/objections-competitive-signals",
        "/api/v1/meetings/{meeting_id}/intelligence/stakeholders",
        "/api/v1/meetings/{meeting_id}/intelligence/next-best-action",
        "/api/v1/meetings/{meeting_id}/intelligence/decisions",
        "/api/v1/meetings/{meeting_id}/intelligence/action-items",
        "/api/v1/meetings/{meeting_id}/intelligence/risks-blockers",
        "/api/v1/meetings/{meeting_id}/intelligence/open-questions",
        "/api/v1/meetings/{meeting_id}/intelligence/follow-up-email",
        "/api/v1/meetings/{meeting_id}/participants",
        "/api/v1/meetings/{meeting_id}/participants/{participant_id}",
        "/api/v1/meetings/{meeting_id}/transcript",
    }
    assert not any(path.startswith(("/ai", "/integrations")) for path in paths)
