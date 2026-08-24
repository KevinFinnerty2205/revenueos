from __future__ import annotations

import asyncio
import base64
import hashlib
import uuid
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from urllib.parse import parse_qs, urlparse

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from revenueos.action_contracts import LogInteractionPayload, OpportunityUpdatePayload
from revenueos.auth import get_current_user
from revenueos.config import Settings
from revenueos.credential_store import (
    ConnectorCredential,
    EncryptedDatabaseCredentialStore,
)
from revenueos.domain import ActionRiskClass
from revenueos.hubspot_connector import (
    HUBSPOT_REQUIRED_SCOPES,
    HubSpotAPIError,
    HubSpotClient,
    HubSpotCRMExecutor,
    HubSpotExternalState,
    HubSpotPipeline,
    HubSpotProperty,
    HubSpotRecord,
)
from revenueos.integration_executors import (
    ApprovedActionInput,
    ApprovedExternalTarget,
    ExecutorConnectionContext,
    PermanentExecutionFailure,
    UnknownExternalStateFailure,
)
from revenueos.models import EncryptedConnectorCredential, IntegrationConnection, OAuthConnectionState, User

from .conftest import PRIMARY_ORGANISATION_ID, PRIMARY_USER_ID, TEST_DB_URL
from .test_business_api import create_company, create_contact, create_opportunity
from .test_integration_execution import _run_execution_worker, _seed_approved_action
from .test_meeting_api import secondary_user


def _master_key() -> str:
    return base64.urlsafe_b64encode(b"k" * 32).decode().rstrip("=")


def _enable_hubspot(app: FastAPI) -> Settings:
    settings = app.state.settings
    settings.feature_integrations_enabled = True
    settings.feature_action_execution_enabled = True
    settings.feature_hubspot_crm_enabled = True
    settings.hubspot_client_id = "test-client-id"
    settings.hubspot_client_secret = SecretStr("test-client-secret")
    settings.hubspot_oauth_redirect_uri = "http://localhost:3000/settings/integrations/hubspot/callback"
    settings.connector_credential_master_key = SecretStr(_master_key())
    return settings


def test_hubspot_oauth_state_is_one_time_tenant_bound_and_tokens_are_not_returned(
    app: FastAPI,
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _enable_hubspot(app)
    credential = ConnectorCredential(
        access_token="access-token-must-stay-secret",
        refresh_token="refresh-token-must-stay-secret",
        expires_at=datetime.now(UTC) + timedelta(minutes=30),
        scopes=HUBSPOT_REQUIRED_SCOPES,
        external_account_id="1234567",
    )

    async def exchange_code(self: HubSpotClient, code: str) -> tuple[ConnectorCredential, str | None]:
        del self
        assert code == "authorisation-code"
        return credential, "example.hubspot.com"

    monkeypatch.setattr(HubSpotClient, "exchange_code", exchange_code)
    start = client.post("/api/v1/integrations/hubspot/oauth/start")
    assert start.status_code == 200, start.text
    query = parse_qs(urlparse(start.json()["authorisationUrl"]).query)
    state = query["state"][0]
    assert query["scope"][0].split() == list(HUBSPOT_REQUIRED_SCOPES)

    app.dependency_overrides[get_current_user] = secondary_user
    try:
        wrong_tenant = client.post(
            "/api/v1/integrations/hubspot/oauth/callback",
            json={"state": state, "code": "authorisation-code"},
        )
        assert wrong_tenant.status_code == 400
        assert wrong_tenant.json()["code"] == "oauth_state_invalid"
    finally:
        app.dependency_overrides.pop(get_current_user, None)

    callback = client.post(
        "/api/v1/integrations/hubspot/oauth/callback",
        json={"state": state, "code": "authorisation-code"},
    )
    assert callback.status_code == 200, callback.text
    assert callback.json()["connectorKey"] == "hubspot"
    assert callback.json()["executionMode"] == "live"
    assert callback.json()["externalAccountId"] == "1234567"
    assert "access-token" not in callback.text
    assert "refresh-token" not in callback.text

    replay = client.post(
        "/api/v1/integrations/hubspot/oauth/callback",
        json={"state": state, "code": "authorisation-code"},
    )
    assert replay.status_code == 409
    assert replay.json()["code"] == "oauth_state_replayed"

    changed_credential = replace(
        credential,
        access_token="replacement-access-token",
        refresh_token="replacement-refresh-token",
        external_account_id="7654321",
    )
    revoked_accounts: list[str] = []

    async def exchange_changed_account(
        self: HubSpotClient,
        code: str,
    ) -> tuple[ConnectorCredential, str | None]:
        del self
        assert code == "replacement-code"
        return changed_credential, "other.hubspot.com"

    async def revoke_changed_account(
        self: HubSpotClient,
        value: ConnectorCredential,
    ) -> None:
        del self
        revoked_accounts.append(value.external_account_id)

    monkeypatch.setattr(HubSpotClient, "exchange_code", exchange_changed_account)
    monkeypatch.setattr(HubSpotClient, "revoke", revoke_changed_account)
    replacement_start = client.post("/api/v1/integrations/hubspot/oauth/start")
    replacement_state = parse_qs(urlparse(replacement_start.json()["authorisationUrl"]).query)["state"][0]
    account_change = client.post(
        "/api/v1/integrations/hubspot/oauth/callback",
        json={"state": replacement_state, "code": "replacement-code"},
    )
    assert account_change.status_code == 409
    assert account_change.json()["code"] == "connection_account_changed"
    assert revoked_accounts == ["7654321"]
    connections = client.get("/api/v1/integrations/connections")
    assert connections.status_code == 200
    assert connections.json()["items"][0]["externalAccountId"] == "1234567"

    async def verify_ciphertext() -> None:
        engine = create_async_engine(TEST_DB_URL)
        async with async_sessionmaker(engine, expire_on_commit=False)() as session:
            record = await session.scalar(
                select(EncryptedConnectorCredential).where(
                    EncryptedConnectorCredential.organisation_id == PRIMARY_ORGANISATION_ID
                )
            )
            assert record is not None
            assert b"access-token-must-stay-secret" not in record.encrypted_payload
            assert b"refresh-token-must-stay-secret" not in record.encrypted_payload
        await engine.dispose()

    asyncio.run(verify_ciphertext())


def test_encrypted_credential_store_rejects_cross_connection_and_tampering() -> None:
    async def scenario() -> None:
        engine = create_async_engine(TEST_DB_URL)
        connection_id = uuid.uuid4()
        other_connection_id = uuid.uuid4()
        async with async_sessionmaker(engine, expire_on_commit=False)() as session:
            now = datetime.now(UTC)
            for value, connector_key in (
                (connection_id, "hubspot"),
                (other_connection_id, "mock_crm"),
            ):
                session.add(
                    IntegrationConnection(
                        id=value,
                        organisation_id=PRIMARY_ORGANISATION_ID,
                        connector_key=connector_key,
                        connection_status="active",
                        created_by_user_id=PRIMARY_USER_ID,
                        connected_at=now,
                        last_verified_at=now,
                        revoked_at=None,
                        credential_reference=None,
                        capability_state_json=["update_opportunity"],
                        external_account_id="123",
                        external_account_name="Test",
                        granted_scopes_json=list(HUBSPOT_REQUIRED_SCOPES),
                        metadata_version=1,
                        created_at=now,
                        updated_at=now,
                    )
                )
            await session.flush()
            store = EncryptedDatabaseCredentialStore(session, _master_key())
            credential = ConnectorCredential(
                access_token="access-secret",
                refresh_token="refresh-secret",
                expires_at=now + timedelta(minutes=30),
                scopes=HUBSPOT_REQUIRED_SCOPES,
                external_account_id="123",
            )
            reference = await store.put(PRIMARY_ORGANISATION_ID, connection_id, credential)
            assert await store.get(PRIMARY_ORGANISATION_ID, connection_id, reference) == credential
            with pytest.raises(ValueError, match="unavailable"):
                await store.get(PRIMARY_ORGANISATION_ID, other_connection_id, reference)
            record = await session.scalar(
                select(EncryptedConnectorCredential).where(EncryptedConnectorCredential.connection_id == connection_id)
            )
            assert record is not None
            record.encrypted_payload = bytes([record.encrypted_payload[0] ^ 1]) + record.encrypted_payload[1:]
            await session.flush()
            with pytest.raises(ValueError, match="unavailable"):
                await store.get(PRIMARY_ORGANISATION_ID, connection_id, reference)
            await session.rollback()
        await engine.dispose()

    asyncio.run(scenario())


def test_hubspot_client_refreshes_then_reads_and_marks_write_timeout_uncertain() -> None:
    class MemoryStore:
        def __init__(self, credential: ConnectorCredential) -> None:
            self.credential = credential

        async def put(self, organisation_id, connection_id, credential):
            del organisation_id, connection_id
            self.credential = credential
            return "credential-ref"

        async def get(self, organisation_id, connection_id, credential_reference):
            del organisation_id, connection_id, credential_reference
            return self.credential

        async def revoke(self, organisation_id, connection_id, credential_reference):
            del organisation_id, connection_id, credential_reference

    settings = Settings(
        feature_integrations_enabled=True,
        feature_action_execution_enabled=True,
        feature_hubspot_crm_enabled=True,
        hubspot_client_id="test-client-id",
        hubspot_client_secret=SecretStr("test-client-secret"),
        hubspot_oauth_redirect_uri="http://localhost:3000/settings/integrations/hubspot/callback",
        connector_credential_master_key=SecretStr(_master_key()),
    )
    store = MemoryStore(
        ConnectorCredential(
            access_token="expired",
            refresh_token="refresh",
            expires_at=datetime.now(UTC) - timedelta(seconds=1),
            scopes=HUBSPOT_REQUIRED_SCOPES,
            external_account_id="123",
        )
    )
    calls: list[tuple[str, str]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append((request.method, request.url.path))
        if request.url.path == "/oauth/2026-03/token":
            return httpx.Response(
                200,
                json={
                    "access_token": "refreshed",
                    "refresh_token": "rotated",
                    "expires_in": 1800,
                    "scopes": list(HUBSPOT_REQUIRED_SCOPES),
                },
            )
        if request.method == "GET":
            assert request.headers["Authorization"] == "Bearer refreshed"
            return httpx.Response(
                200,
                json={
                    "id": "deal-1",
                    "properties": {"amount": "100.00", "deal_currency_code": "AUD"},
                    "updatedAt": datetime.now(UTC).isoformat(),
                },
            )
        raise httpx.ReadTimeout("uncertain write", request=request)

    async def scenario() -> None:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http_client:
            client = HubSpotClient(settings, store, http_client=http_client)
            context = ExecutorConnectionContext(
                organisation_id=PRIMARY_ORGANISATION_ID,
                connection_id=uuid.uuid4(),
                credential_reference="credential-ref",
                execution_mode="live",
            )
            record = await client.get_record(context, "deals", "deal-1", ("amount", "deal_currency_code"))
            assert record.properties["amount"] == "100.00"
            assert store.credential.refresh_token == "rotated"
            with pytest.raises(HubSpotAPIError) as failure:
                await client.update_record(context, "deals", "deal-1", {"amount": "200"})
            assert failure.value.uncertain is True
            assert failure.value.retryable is False

    asyncio.run(scenario())
    assert calls == [
        ("POST", "/oauth/2026-03/token"),
        ("GET", "/crm/objects/2026-03/deals/deal-1"),
        ("PATCH", "/crm/objects/2026-03/deals/deal-1"),
    ]


def _context() -> ExecutorConnectionContext:
    return ExecutorConnectionContext(
        organisation_id=PRIMARY_ORGANISATION_ID,
        connection_id=uuid.uuid4(),
        credential_reference="credential-ref",
        execution_mode="live",
    )


def _opportunity_action(
    *,
    field: str = "estimated_value",
    proposed_value: str = "200.00",
    authority: str = "review_before_sync",
) -> ApprovedActionInput:
    return ApprovedActionInput(
        organisation_id=PRIMARY_ORGANISATION_ID,
        action_id=uuid.uuid4(),
        action_version=1,
        opportunity_id=uuid.uuid4(),
        action_type="update_opportunity",
        risk_class=ActionRiskClass.DATA_MUTATION,
        title="Review CRM update",
        target_entity_type="opportunity",
        target_entity_id=uuid.uuid4(),
        payload=OpportunityUpdatePayload(
            kind="update_opportunity",
            field=field,
            current_value=None,
            proposed_value=proposed_value,
            reason="Final reviewed evidence supports this exact update.",
        ),
        revenueos_currency="AUD",
        external_target=ApprovedExternalTarget(
            mapping_id=uuid.uuid4(),
            external_object_type="deals",
            external_object_id="deal-1",
            external_property_name="amount" if field == "estimated_value" else "hs_next_step",
            external_property_type="number" if field == "estimated_value" else "string",
            field_authority=authority,
            proposed_external_value=proposed_value,
        ),
    )


class _ExecutorClient:
    def __init__(self) -> None:
        self.amount = "100.00"
        self.currency = "AUD"
        self.activities: list[HubSpotRecord] = []
        self.created_properties: dict[str, str] | None = None

    async def get_record(self, context, object_type, object_id, properties):
        del context, object_type, object_id, properties
        return HubSpotRecord(
            id="deal-1",
            properties={"amount": self.amount, "deal_currency_code": self.currency},
            updatedAt="2026-08-24T01:00:00Z",
        )

    async def update_record(self, context, object_type, object_id, properties):
        del context, object_type, object_id
        self.amount = properties["amount"]
        return HubSpotRecord(
            id="deal-1",
            properties={"amount": self.amount},
            updatedAt="2026-08-24T01:01:00Z",
        )

    async def search_by_property(self, context, object_type, property_name, value, properties):
        del context, object_type, property_name, value, properties
        return self.activities

    async def create_meeting(self, context, *, properties, deal_id):
        del context
        assert deal_id == "deal-1"
        self.created_properties = properties
        record = HubSpotRecord(
            id="meeting-1",
            properties={"hs_internal_meeting_notes": properties["hs_internal_meeting_notes"]},
            updatedAt="2026-08-24T01:01:00Z",
        )
        self.activities = [record]
        return record


def test_hubspot_executor_previews_exact_amount_and_enforces_currency_and_authority() -> None:
    async def scenario() -> None:
        client = _ExecutorClient()
        executor = HubSpotCRMExecutor(client)  # type: ignore[arg-type]
        action = _opportunity_action()
        state = await executor.current_external_state(action, _context())
        assert isinstance(state, HubSpotExternalState)
        preview = executor.preview_execution(action, state)
        assert preview.kind == "crm"
        assert preview.current_external_value == "100.00"
        assert preview.new_value == "200.00"
        result = await executor.execute(
            action,
            idempotency_key="amount-update-1",
            current_external_state=state,
            context=_context(),
        )
        assert result.external_result_id == "deal-1"
        assert client.amount == "200.00"

        client.currency = "USD"
        with pytest.raises(PermanentExecutionFailure, match="different currencies"):
            await executor.current_external_state(_opportunity_action(), _context())
        with pytest.raises(PermanentExecutionFailure, match="source of truth"):
            executor.validate_action(_opportunity_action(authority="crm_authoritative"))

    asyncio.run(scenario())


def test_hubspot_activity_is_bounded_and_idempotently_reconciled() -> None:
    async def scenario() -> None:
        client = _ExecutorClient()
        executor = HubSpotCRMExecutor(client)  # type: ignore[arg-type]
        action = ApprovedActionInput(
            organisation_id=PRIMARY_ORGANISATION_ID,
            action_id=uuid.uuid4(),
            action_version=1,
            opportunity_id=uuid.uuid4(),
            action_type="log_interaction",
            risk_class=ActionRiskClass.DATA_MUTATION,
            title="Log interaction",
            target_entity_type="opportunity",
            target_entity_id=uuid.uuid4(),
            payload=LogInteractionPayload(
                kind="log_interaction",
                interaction_id=uuid.uuid4(),
                occurred_at=datetime(2026, 8, 24, 1, tzinfo=UTC),
                interaction_type="online_meeting",
                title="Technical review",
                summary="Final reviewed summary only.",
                agreed_next_steps=("Send the approved security pack.",),
            ),
            external_target=ApprovedExternalTarget(
                mapping_id=uuid.uuid4(),
                external_object_type="deals",
                external_object_id="deal-1",
            ),
        )
        first = await executor.execute(
            action,
            idempotency_key="activity-1",
            current_external_state=None,
            context=_context(),
        )
        second = await executor.execute(
            action,
            idempotency_key="activity-1",
            current_external_state=None,
            context=_context(),
        )
        assert first.external_result_id == second.external_result_id == "meeting-1"
        assert client.created_properties is not None
        assert client.created_properties["hs_meeting_body"] == (
            "Final reviewed summary only.\n\nAgreed next steps:\n• Send the approved security pack."
        )
        assert "transcript" not in str(client.created_properties).casefold()
        assert len(client.activities) == 1

    asyncio.run(scenario())


def test_hubspot_write_timeout_reconciles_or_enters_unknown_state_without_blind_retry() -> None:
    class TimeoutClient(_ExecutorClient):
        def __init__(self, *, applied: bool) -> None:
            super().__init__()
            self.applied = applied
            self.reads = 0

        async def get_record(self, context, object_type, object_id, properties):
            self.reads += 1
            if not self.applied and self.reads > 1:
                raise HubSpotAPIError("provider_unavailable", retryable=True)
            return await super().get_record(context, object_type, object_id, properties)

        async def update_record(self, context, object_type, object_id, properties):
            del context, object_type, object_id
            if self.applied:
                self.amount = properties["amount"]
            raise HubSpotAPIError("provider_timeout", uncertain=True)

    async def scenario() -> None:
        action = _opportunity_action()
        applied_client = TimeoutClient(applied=True)
        applied_executor = HubSpotCRMExecutor(applied_client)  # type: ignore[arg-type]
        state = await applied_executor.current_external_state(action, _context())
        result = await applied_executor.execute(
            action,
            idempotency_key="timeout-applied",
            current_external_state=state,
            context=_context(),
        )
        assert result.state == {"reconciled": True}

        unknown_client = TimeoutClient(applied=False)
        unknown_executor = HubSpotCRMExecutor(unknown_client)  # type: ignore[arg-type]
        unknown_state = await unknown_executor.current_external_state(action, _context())
        with pytest.raises(UnknownExternalStateFailure):
            await unknown_executor.execute(
                action,
                idempotency_key="timeout-unknown",
                current_external_state=unknown_state,
                context=_context(),
            )
        assert unknown_client.reads == 2

    asyncio.run(scenario())


def test_hubspot_rate_limit_and_malformed_response_are_safe() -> None:
    settings = Settings(
        feature_integrations_enabled=True,
        feature_action_execution_enabled=True,
        feature_hubspot_crm_enabled=True,
        hubspot_client_id="test-client-id",
        hubspot_client_secret=SecretStr("test-client-secret"),
        hubspot_oauth_redirect_uri="http://localhost:3000/settings/integrations/hubspot/callback",
        connector_credential_master_key=SecretStr(_master_key()),
    )

    class MemoryStore:
        async def get(self, organisation_id, connection_id, credential_reference):
            del organisation_id, connection_id, credential_reference
            return ConnectorCredential(
                access_token="access",
                refresh_token="refresh",
                expires_at=datetime.now(UTC) + timedelta(minutes=10),
                scopes=HUBSPOT_REQUIRED_SCOPES,
                external_account_id="123",
            )

        async def put(self, organisation_id, connection_id, credential):
            del organisation_id, connection_id, credential
            return "credential-ref"

        async def revoke(self, organisation_id, connection_id, credential_reference):
            del organisation_id, connection_id, credential_reference

    responses = [
        httpx.Response(429, headers={"Retry-After": "7"}, json={"status": "error"}),
        httpx.Response(200, content=b"not-json"),
    ]

    def handler(request: httpx.Request) -> httpx.Response:
        return responses.pop(0)

    async def scenario() -> None:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http_client:
            client = HubSpotClient(settings, MemoryStore(), http_client=http_client)
            with pytest.raises(HubSpotAPIError) as rate_limited:
                await client.get_record(_context(), "deals", "deal-1", ("amount",))
            assert rate_limited.value.retry_after_seconds == 7
            with pytest.raises(HubSpotAPIError, match="provider_response_invalid"):
                await client.get_record(_context(), "deals", "deal-1", ("amount",))

    asyncio.run(scenario())


def test_hubspot_oauth_rejects_expired_changed_and_declined_callbacks(
    app: FastAPI,
    client: TestClient,
) -> None:
    _enable_hubspot(app)

    def start_state() -> str:
        response = client.post("/api/v1/integrations/hubspot/oauth/start")
        assert response.status_code == 200
        return parse_qs(urlparse(response.json()["authorisationUrl"]).query)["state"][0]

    expired_state = start_state()

    async def expire_state() -> None:
        engine = create_async_engine(TEST_DB_URL)
        async with async_sessionmaker(engine, expire_on_commit=False)() as session:
            await session.execute(
                update(OAuthConnectionState)
                .where(OAuthConnectionState.state_hash == hashlib.sha256(expired_state.encode()).hexdigest())
                .values(expires_at=datetime.now(UTC) - timedelta(seconds=1))
            )
            await session.commit()
        await engine.dispose()

    asyncio.run(expire_state())
    expired = client.post(
        "/api/v1/integrations/hubspot/oauth/callback",
        json={"state": expired_state, "code": "code"},
    )
    assert expired.status_code == 409
    assert expired.json()["code"] == "oauth_state_expired"

    changed_state = start_state()
    app.state.settings.hubspot_oauth_redirect_uri = "http://localhost:3000/changed-callback"
    changed = client.post(
        "/api/v1/integrations/hubspot/oauth/callback",
        json={"state": changed_state, "code": "code"},
    )
    assert changed.status_code == 400
    assert changed.json()["code"] == "oauth_redirect_mismatch"
    app.state.settings.hubspot_oauth_redirect_uri = "http://localhost:3000/settings/integrations/hubspot/callback"

    declined_state = start_state()
    declined = client.post(
        "/api/v1/integrations/hubspot/oauth/callback",
        json={"state": declined_state, "providerError": "access_denied"},
    )
    assert declined.status_code == 400
    assert declined.json()["code"] == "oauth_authorisation_declined"
    replay = client.post(
        "/api/v1/integrations/hubspot/oauth/callback",
        json={"state": declined_state, "code": "code"},
    )
    assert replay.status_code == 409
    assert replay.json()["code"] == "oauth_state_replayed"
    assert client.post("/api/v1/integrations/hubspot/oauth/callback", json={"state": declined_state}).status_code == 422


def test_hubspot_configuration_rejects_members_and_disabled_users(
    app: FastAPI,
    client: TestClient,
) -> None:
    _enable_hubspot(app)
    member = replace(secondary_user(), role="member")
    app.dependency_overrides[get_current_user] = lambda: member
    try:
        assert client.post("/api/v1/integrations/hubspot/oauth/start").status_code == 403
    finally:
        app.dependency_overrides.pop(get_current_user, None)

    state_response = client.post("/api/v1/integrations/hubspot/oauth/start")
    state = parse_qs(urlparse(state_response.json()["authorisationUrl"]).query)["state"][0]

    async def disable_user() -> None:
        engine = create_async_engine(TEST_DB_URL)
        async with async_sessionmaker(engine, expire_on_commit=False)() as session:
            await session.execute(update(User).where(User.id == PRIMARY_USER_ID).values(status="disabled"))
            await session.commit()
        await engine.dispose()

    asyncio.run(disable_user())
    denied = client.post(
        "/api/v1/integrations/hubspot/oauth/callback",
        json={"state": state, "code": "code"},
    )
    assert denied.status_code == 403
    assert denied.json()["code"] == "forbidden"


def _connect_hubspot(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> dict[str, object]:
    credential = ConnectorCredential(
        access_token="test-access",
        refresh_token="test-refresh",
        expires_at=datetime.now(UTC) + timedelta(minutes=30),
        scopes=HUBSPOT_REQUIRED_SCOPES,
        external_account_id="1234567",
    )

    async def exchange_code(self: HubSpotClient, code: str) -> tuple[ConnectorCredential, str | None]:
        del self
        assert code == "test-code"
        return credential, "RevenueOS test account"

    monkeypatch.setattr(HubSpotClient, "exchange_code", exchange_code)
    start = client.post("/api/v1/integrations/hubspot/oauth/start")
    state = parse_qs(urlparse(start.json()["authorisationUrl"]).query)["state"][0]
    callback = client.post(
        "/api/v1/integrations/hubspot/oauth/callback",
        json={"state": state, "code": "test-code"},
    )
    assert callback.status_code == 200, callback.text
    return callback.json()


def test_crm_mapping_is_explicit_tenant_scoped_typed_and_admin_governed(
    app: FastAPI,
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _enable_hubspot(app)
    connection = _connect_hubspot(client, monkeypatch)
    company = create_company(client)
    contact = create_contact(client, str(company["id"]))
    opportunity = create_opportunity(client, str(company["id"]))
    second_opportunity = create_opportunity(client, str(company["id"]), name="Renewal")

    async def search_records(self, context, object_type, query, properties, *, limit=10):
        del self, context, query, properties, limit
        assert object_type in {"deals", "contacts"}
        return [
            HubSpotRecord(
                id="external-1",
                properties=(
                    {"dealname": "Expansion", "dealstage": "appointmentscheduled"}
                    if object_type == "deals"
                    else {"firstname": "Jordan", "lastname": "Lee", "email": "jordan@example.test"}
                ),
                updatedAt="2026-08-24T01:00:00Z",
            )
        ]

    async def get_record(self, context, object_type, object_id, properties):
        del self, context, properties
        if object_id == "missing":
            raise HubSpotAPIError("external_object_not_found")
        assert object_type in {"deals", "contacts"}
        return HubSpotRecord(id=object_id, properties={}, updatedAt="2026-08-24T01:00:00Z")

    async def properties(self, context, object_type):
        del self, context, object_type
        return [
            HubSpotProperty.model_validate(
                {
                    "name": "amount",
                    "label": "Amount",
                    "type": "number",
                    "fieldType": "number",
                    "modificationMetadata": {"readOnlyValue": False},
                }
            ),
            HubSpotProperty.model_validate(
                {
                    "name": "readonly_text",
                    "label": "Read only",
                    "type": "string",
                    "fieldType": "text",
                    "modificationMetadata": {"readOnlyValue": True},
                }
            ),
        ]

    async def pipelines(self, context):
        del self, context
        return [
            HubSpotPipeline.model_validate(
                {
                    "id": "default",
                    "label": "Sales pipeline",
                    "stages": [{"id": "qualified", "label": "Qualified"}],
                }
            )
        ]

    monkeypatch.setattr(HubSpotClient, "search_records", search_records)
    monkeypatch.setattr(HubSpotClient, "get_record", get_record)
    monkeypatch.setattr(HubSpotClient, "properties", properties)
    monkeypatch.setattr(HubSpotClient, "pipelines", pipelines)

    search = client.get(
        f"/api/v1/integrations/connections/{connection['id']}/crm/search",
        params={"entityType": "opportunity", "query": "Expansion"},
    )
    assert search.status_code == 200
    assert search.json()["items"][0]["externalObjectId"] == "external-1"

    linked = client.put(
        f"/api/v1/integrations/crm/entities/opportunity/{opportunity['id']}",
        json={
            "connectionId": connection["id"],
            "externalObjectType": "deal",
            "externalObjectId": "external-1",
        },
    )
    assert linked.status_code == 200, linked.text
    duplicate_external = client.put(
        f"/api/v1/integrations/crm/entities/opportunity/{second_opportunity['id']}",
        json={
            "connectionId": connection["id"],
            "externalObjectType": "deal",
            "externalObjectId": "external-1",
        },
    )
    assert duplicate_external.status_code == 409

    linked_contact = client.put(
        f"/api/v1/integrations/crm/entities/contact/{contact['id']}",
        json={
            "connectionId": connection["id"],
            "externalObjectType": "contact",
            "externalObjectId": "contact-1",
        },
    )
    assert linked_contact.status_code == 200
    missing = client.put(
        f"/api/v1/integrations/crm/entities/opportunity/{second_opportunity['id']}",
        json={
            "connectionId": connection["id"],
            "externalObjectType": "deal",
            "externalObjectId": "missing",
        },
    )
    assert missing.status_code == 409
    assert missing.json()["code"] == "external_object_not_found"

    amount_mapping = client.put(
        f"/api/v1/integrations/connections/{connection['id']}/crm/fields",
        json={
            "entityType": "opportunity",
            "revenueosField": "estimated_value",
            "externalPropertyName": "amount",
            "authority": "review_before_sync",
        },
    )
    assert amount_mapping.status_code == 200
    incompatible = client.put(
        f"/api/v1/integrations/connections/{connection['id']}/crm/fields",
        json={
            "entityType": "opportunity",
            "revenueosField": "stage",
            "externalPropertyName": "amount",
            "authority": "review_before_sync",
        },
    )
    assert incompatible.status_code == 422
    read_only = client.put(
        f"/api/v1/integrations/connections/{connection['id']}/crm/fields",
        json={
            "entityType": "opportunity",
            "revenueosField": "description",
            "externalPropertyName": "readonly_text",
        },
    )
    assert read_only.status_code == 422
    stage_mapping = client.put(
        f"/api/v1/integrations/connections/{connection['id']}/crm/stages",
        json={
            "revenueosStage": "qualification",
            "externalPipelineId": "default",
            "externalStageId": "qualified",
        },
    )
    assert stage_mapping.status_code == 200

    member = replace(secondary_user(), role="member")
    app.dependency_overrides[get_current_user] = lambda: member
    try:
        assert (
            client.put(
                f"/api/v1/integrations/connections/{connection['id']}/crm/fields",
                json={
                    "entityType": "opportunity",
                    "revenueosField": "estimated_value",
                    "externalPropertyName": "amount",
                },
            ).status_code
            == 403
        )
        assert (
            client.get(
                f"/api/v1/integrations/connections/{connection['id']}/crm/search",
                params={"entityType": "opportunity", "query": "Expansion"},
            ).status_code
            == 404
        )
    finally:
        app.dependency_overrides.pop(get_current_user, None)

    removed = client.delete(
        f"/api/v1/integrations/connections/{connection['id']}/crm/entities/opportunity/{opportunity['id']}"
    )
    assert removed.status_code == 204


def test_live_crm_action_reads_previews_confirms_updates_and_records_sync(
    app: FastAPI,
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _enable_hubspot(app)
    connection = _connect_hubspot(client, monkeypatch)
    company = create_company(client)
    opportunity = create_opportunity(client, str(company["id"]))
    remote = {"amount": "100.00", "currency": "AUD", "updated_at": "2026-08-24T01:00:00Z"}

    async def get_record(self, context, object_type, object_id, properties):
        del self, context, object_type, properties
        return HubSpotRecord(
            id=object_id,
            properties={"amount": remote["amount"], "deal_currency_code": remote["currency"]},
            updatedAt=remote["updated_at"],
        )

    async def update_record(self, context, object_type, object_id, properties):
        del self, context, object_type
        remote["amount"] = properties["amount"]
        remote["updated_at"] = "2026-08-24T01:05:00Z"
        return HubSpotRecord(
            id=object_id,
            properties={"amount": remote["amount"]},
            updatedAt=remote["updated_at"],
        )

    async def properties(self, context, object_type):
        del self, context, object_type
        return [
            HubSpotProperty.model_validate(
                {
                    "name": "amount",
                    "label": "Amount",
                    "type": "number",
                    "fieldType": "number",
                    "modificationMetadata": {"readOnlyValue": False},
                }
            )
        ]

    monkeypatch.setattr(HubSpotClient, "get_record", get_record)
    monkeypatch.setattr(HubSpotClient, "update_record", update_record)
    monkeypatch.setattr(HubSpotClient, "properties", properties)
    linked = client.put(
        f"/api/v1/integrations/crm/entities/opportunity/{opportunity['id']}",
        json={
            "connectionId": connection["id"],
            "externalObjectType": "deal",
            "externalObjectId": "deal-1",
        },
    )
    assert linked.status_code == 200
    mapped = client.put(
        f"/api/v1/integrations/connections/{connection['id']}/crm/fields",
        json={
            "entityType": "opportunity",
            "revenueosField": "estimated_value",
            "externalPropertyName": "amount",
            "authority": "review_before_sync",
        },
    )
    assert mapped.status_code == 200
    action_id = _seed_approved_action(
        opportunity_id=str(opportunity["id"]),
        action_type="update_opportunity",
        risk_class="data_mutation",
        target_entity_type="opportunity",
        target_entity_id=str(opportunity["id"]),
        payload={
            "kind": "update_opportunity",
            "field": "estimated_value",
            "currentValue": opportunity["estimatedValue"],
            "proposedValue": "200.00",
            "reason": "The customer approved the expanded commercial scope.",
        },
        title="Review opportunity amount update",
    )
    preview = client.post(
        f"/api/v1/actions/{action_id}/execution-preview",
        json={"connectionId": connection["id"]},
    )
    assert preview.status_code == 200, preview.text
    assert preview.json()["content"]["currentExternalValue"] == "100.00"
    assert preview.json()["content"]["newValue"] == "200.00"
    assert preview.json()["confirmationLabel"] == "Update CRM"
    confirmed = client.post(
        f"/api/v1/actions/{action_id}/execute",
        json={
            "previewId": preview.json()["id"],
            "connectionId": connection["id"],
            "confirmed": True,
        },
    )
    assert confirmed.status_code == 202
    duplicate = client.post(
        f"/api/v1/actions/{action_id}/execute",
        json={
            "previewId": preview.json()["id"],
            "connectionId": connection["id"],
            "confirmed": True,
        },
    )
    assert duplicate.status_code == 202
    assert duplicate.json()["id"] == confirmed.json()["id"]

    _run_execution_worker(app)
    execution = client.get(f"/api/v1/executions/{confirmed.json()['id']}")
    assert execution.status_code == 200
    assert execution.json()["executionStatus"] == "succeeded"
    assert remote["amount"] == "200.00"
    mapping = client.get(
        f"/api/v1/integrations/connections/{connection['id']}/crm/entities/opportunity/{opportunity['id']}"
    )
    assert mapping.json()["lastSyncedAt"] is not None
    unchanged = client.get(f"/api/v1/opportunities/{opportunity['id']}")
    assert unchanged.status_code == 200
    assert unchanged.json()["estimatedValue"] == opportunity["estimatedValue"]

    stale_action_id = _seed_approved_action(
        opportunity_id=str(opportunity["id"]),
        action_type="update_opportunity",
        risk_class="data_mutation",
        target_entity_type="opportunity",
        target_entity_id=str(opportunity["id"]),
        payload={
            "kind": "update_opportunity",
            "field": "estimated_value",
            "currentValue": opportunity["estimatedValue"],
            "proposedValue": "300.00",
            "reason": "A separately reviewed commercial change was proposed.",
        },
        title="Review another opportunity amount update",
    )
    stale_preview = client.post(
        f"/api/v1/actions/{stale_action_id}/execution-preview",
        json={"connectionId": connection["id"]},
    ).json()
    stale_execution = client.post(
        f"/api/v1/actions/{stale_action_id}/execute",
        json={
            "previewId": stale_preview["id"],
            "connectionId": connection["id"],
            "confirmed": True,
        },
    ).json()
    remote["amount"] = "250.00"
    remote["updated_at"] = "2026-08-24T01:06:00Z"
    _run_execution_worker(app)
    stale_result = client.get(f"/api/v1/executions/{stale_execution['id']}").json()
    assert stale_result["executionStatus"] == "failed_permanent"
    assert stale_result["safeFailureCode"] == "stale_external_state"
    assert remote["amount"] == "250.00"
