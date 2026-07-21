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


def test_openapi_contains_sprint_three_domain_endpoints(client: TestClient) -> None:
    response = client.get("/openapi.json")

    assert response.status_code == 200
    paths = set(response.json()["paths"])
    assert paths == {
        "/health",
        "/ready",
        "/api/v1/me",
        "/api/v1/companies",
        "/api/v1/companies/{company_id}",
        "/api/v1/contacts",
        "/api/v1/contacts/{contact_id}",
        "/api/v1/opportunities",
        "/api/v1/opportunities/{opportunity_id}",
        "/api/v1/tasks",
        "/api/v1/tasks/{task_id}",
        "/api/v1/meetings",
        "/api/v1/meetings/{meeting_id}",
        "/api/v1/meetings/{meeting_id}/history",
        "/api/v1/meetings/{meeting_id}/intelligence",
        "/api/v1/meetings/{meeting_id}/intelligence/generate",
        "/api/v1/meetings/{meeting_id}/intelligence/executive-summary",
        "/api/v1/meetings/{meeting_id}/intelligence/buying-signals",
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
