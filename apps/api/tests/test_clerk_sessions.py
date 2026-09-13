from __future__ import annotations

import asyncio

import httpx

from revenueos.clerk_sessions import ClerkBackendSessionRevoker, SessionRevocationResult, create_session_revoker
from revenueos.config import Settings


def _settings(**changes: object) -> Settings:
    values: dict[str, object] = {
        "environment": "test",
        "auth_mode": "clerk",
        "mock_auth_enabled": False,
        "clerk_secret_key": "sk_test_synthetic",
    }
    values.update(changes)
    return Settings(**values)  # type: ignore[arg-type]


def test_revokes_only_sessions_returned_for_the_exact_user() -> None:
    calls: list[tuple[str, str]] = []
    active = {
        "sess_A1": "org_A1",
        "sess_A2": "org_A1",
        "sess_B1": "org_B1",
    }

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append((request.method, request.url.path))
        assert request.headers["Authorization"] == "Bearer sk_test_synthetic"
        if request.method == "GET":
            assert request.url.params["user_id"] == "user_A1"
            assert request.url.params["status"] == "active"
            return httpx.Response(
                200,
                request=request,
                json=[
                    {
                        "id": session_id,
                        "user_id": "user_A1",
                        "status": "active",
                        "last_active_organization_id": organisation_id,
                    }
                    for session_id, organisation_id in active.items()
                ],
            )
        session_id = request.url.path.split("/")[-2]
        active.pop(session_id)
        return httpx.Response(200, request=request, json={"id": session_id, "status": "revoked"})

    async def scenario() -> SessionRevocationResult:
        async with httpx.AsyncClient(
            base_url="https://api.clerk.com/v1",
            transport=httpx.MockTransport(handler),
        ) as client:
            return await ClerkBackendSessionRevoker(_settings(), http_client=client).revoke_active_sessions(
                "user_A1",
                "org_A1",
            )

    result = asyncio.run(scenario())

    assert result.outcome == "succeeded"
    assert result.revoked_session_count == 2
    assert active == {"sess_B1": "org_B1"}
    assert calls == [
        ("GET", "/v1/sessions"),
        ("POST", "/v1/sessions/sess_A1/revoke"),
        ("POST", "/v1/sessions/sess_A2/revoke"),
        ("GET", "/v1/sessions"),
    ]


def test_refuses_a_mismatched_user_before_revoking_any_session() -> None:
    methods: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        methods.append(request.method)
        return httpx.Response(
            200,
            request=request,
            json=[
                {
                    "id": "sess_B1",
                    "user_id": "user_B1",
                    "status": "active",
                    "last_active_organization_id": "org_A1",
                }
            ],
        )

    async def scenario() -> SessionRevocationResult:
        async with httpx.AsyncClient(
            base_url="https://api.clerk.com/v1",
            transport=httpx.MockTransport(handler),
        ) as client:
            return await ClerkBackendSessionRevoker(_settings(), http_client=client).revoke_active_sessions(
                "user_A1",
                "org_A1",
            )

    result = asyncio.run(scenario())

    assert result.outcome == "failed"
    assert result.failure_code == "clerk_session_identity_invalid"
    assert result.revoked_session_count == 0
    assert methods == ["GET"]


def test_refuses_malformed_returned_organisation_before_revocation() -> None:
    methods: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        methods.append(request.method)
        return httpx.Response(
            200,
            request=request,
            json=[
                {
                    "id": "sess_A1",
                    "user_id": "user_A1",
                    "status": "active",
                    "last_active_organization_id": 42,
                }
            ],
        )

    async def scenario() -> SessionRevocationResult:
        async with httpx.AsyncClient(
            base_url="https://api.clerk.com/v1",
            transport=httpx.MockTransport(handler),
        ) as client:
            return await ClerkBackendSessionRevoker(_settings(), http_client=client).revoke_active_sessions(
                "user_A1",
                "org_A1",
            )

    result = asyncio.run(scenario())

    assert result.outcome == "failed"
    assert result.failure_code == "clerk_session_identity_invalid"
    assert methods == ["GET"]


def test_lost_revoke_response_is_unknown_and_is_not_blindly_retried() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if request.method == "GET":
            return httpx.Response(
                200,
                request=request,
                json=[
                    {
                        "id": "sess_A1",
                        "user_id": "user_A1",
                        "status": "active",
                        "last_active_organization_id": "org_A1",
                    }
                ],
            )
        raise httpx.ReadTimeout("synthetic response loss", request=request)

    async def scenario() -> SessionRevocationResult:
        async with httpx.AsyncClient(
            base_url="https://api.clerk.com/v1",
            transport=httpx.MockTransport(handler),
        ) as client:
            return await ClerkBackendSessionRevoker(_settings(), http_client=client).revoke_active_sessions(
                "user_A1",
                "org_A1",
            )

    result = asyncio.run(scenario())

    assert result.outcome == "unknown"
    assert result.failure_code == "clerk_session_revoke_outcome_unknown"
    assert result.revoked_session_count == 0
    assert calls == 2


def test_listing_failure_is_bounded_and_safe() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, request=request, json={"private": "provider detail"})

    async def scenario() -> SessionRevocationResult:
        async with httpx.AsyncClient(
            base_url="https://api.clerk.com/v1",
            transport=httpx.MockTransport(handler),
        ) as client:
            return await ClerkBackendSessionRevoker(_settings(), http_client=client).revoke_active_sessions(
                "user_A1",
                "org_A1",
            )

    result = asyncio.run(scenario())

    assert result.outcome == "failed"
    assert result.failure_code == "clerk_session_management_unauthorised"
    assert "private" not in repr(result)


def test_already_absent_session_is_not_counted_as_revoked() -> None:
    list_calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal list_calls
        if request.method == "GET":
            list_calls += 1
            sessions = (
                [
                    {
                        "id": "sess_A1",
                        "user_id": "user_A1",
                        "status": "active",
                        "last_active_organization_id": "org_A1",
                    }
                ]
                if list_calls == 1
                else []
            )
            return httpx.Response(200, request=request, json=sessions)
        return httpx.Response(404, request=request)

    async def scenario() -> SessionRevocationResult:
        async with httpx.AsyncClient(
            base_url="https://api.clerk.com/v1",
            transport=httpx.MockTransport(handler),
        ) as client:
            return await ClerkBackendSessionRevoker(_settings(), http_client=client).revoke_active_sessions(
                "user_A1",
                "org_A1",
            )

    result = asyncio.run(scenario())

    assert result.outcome == "succeeded"
    assert result.revoked_session_count == 0


def test_session_appearing_during_revocation_is_found_in_the_next_bounded_batch() -> None:
    active = ["sess_A1"]
    revoked: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET":
            return httpx.Response(
                200,
                request=request,
                json=[
                    {
                        "id": session_id,
                        "user_id": "user_A1",
                        "status": "active",
                        "last_active_organization_id": "org_A1",
                    }
                    for session_id in active
                ],
            )
        session_id = request.url.path.split("/")[-2]
        active.remove(session_id)
        revoked.append(session_id)
        if session_id == "sess_A1":
            active.append("sess_A2")
        return httpx.Response(200, request=request, json={"id": session_id, "status": "revoked"})

    async def scenario() -> SessionRevocationResult:
        async with httpx.AsyncClient(
            base_url="https://api.clerk.com/v1",
            transport=httpx.MockTransport(handler),
        ) as client:
            return await ClerkBackendSessionRevoker(_settings(), http_client=client).revoke_active_sessions(
                "user_A1",
                "org_A1",
            )

    result = asyncio.run(scenario())

    assert result.outcome == "succeeded"
    assert result.revoked_session_count == 2
    assert revoked == ["sess_A1", "sess_A2"]


def test_local_adapter_is_explicitly_not_a_provider_operation() -> None:
    settings = Settings(environment="test", auth_mode="mock", mock_auth_enabled=True)
    result = asyncio.run(create_session_revoker(settings).revoke_active_sessions("user_dev_001", "org_dev_001"))
    assert result.outcome == "not_required"
    assert result.revoked_session_count == 0
