from __future__ import annotations

import asyncio
import base64
import hashlib
import hmac
import json
import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from urllib.parse import parse_qs, urlparse

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from revenueos.auth import get_current_user
from revenueos.config import Settings
from revenueos.credential_store import ConnectorCredential
from revenueos.crm_connector_worker import CRMConnectorWorkerService
from revenueos.integration_executors import ExecutorConnectionContext
from revenueos.models import (
    CRMConnectionState,
    CRMSyncCursor,
    CRMSyncJob,
    EncryptedConnectorCredential,
    IntegrationConnection,
)
from revenueos.salesforce_connector import (
    SALESFORCE_REQUIRED_SCOPES,
    SalesforceAPIError,
    SalesforceClient,
    SalesforceIdentity,
    SalesforceOAuthResult,
    validate_salesforce_instance_url,
)

from .conftest import PRIMARY_ORGANISATION_ID, PRIMARY_USER_ID, TEST_DB_URL
from .test_meeting_api import secondary_user


def _master_key() -> str:
    return base64.urlsafe_b64encode(b"s" * 32).decode().rstrip("=")


def _enable_salesforce(app: FastAPI) -> Settings:
    settings = app.state.settings
    settings.feature_integrations_enabled = True
    settings.feature_action_execution_enabled = True
    settings.feature_salesforce_crm_enabled = True
    settings.salesforce_client_id = "salesforce-test-client"
    settings.salesforce_client_secret = SecretStr("salesforce-test-secret")
    settings.salesforce_oauth_redirect_uri = "http://localhost:3000/settings/integrations/salesforce/callback"
    settings.connector_credential_master_key = SecretStr(_master_key())
    return settings


def _settings() -> Settings:
    return Settings(
        feature_integrations_enabled=True,
        feature_action_execution_enabled=True,
        feature_salesforce_crm_enabled=True,
        salesforce_client_id="salesforce-test-client",
        salesforce_client_secret=SecretStr("salesforce-test-secret"),
        salesforce_oauth_redirect_uri="http://localhost:3000/settings/integrations/salesforce/callback",
        connector_credential_master_key=SecretStr(_master_key()),
    )


class _MemoryStore:
    def __init__(self, credential: ConnectorCredential) -> None:
        self.credential = credential

    async def put(self, organisation_id, connection_id, credential):
        del organisation_id, connection_id
        self.credential = credential
        return "credential-ref"

    async def get(self, organisation_id, connection_id, credential_reference):
        del organisation_id, connection_id, credential_reference
        return self.credential

    async def get_for_update(self, organisation_id, connection_id, credential_reference):
        return await self.get(organisation_id, connection_id, credential_reference)

    async def revoke(self, organisation_id, connection_id, credential_reference):
        del organisation_id, connection_id, credential_reference


def _credential(*, expired: bool = False) -> ConnectorCredential:
    return ConnectorCredential(
        access_token="salesforce-access",
        refresh_token="salesforce-refresh",
        expires_at=datetime.now(UTC) + timedelta(minutes=-1 if expired else 30),
        scopes=SALESFORCE_REQUIRED_SCOPES,
        external_account_id="00D000000000001",
        api_base_url="https://example.my.salesforce.com",
    )


def _context() -> ExecutorConnectionContext:
    return ExecutorConnectionContext(
        organisation_id=PRIMARY_ORGANISATION_ID,
        connection_id=uuid.uuid4(),
        credential_reference="credential-ref",
        execution_mode="live",
        external_tenant_id="00D000000000001",
    )


@pytest.mark.parametrize(
    "value",
    (
        "http://example.my.salesforce.com",
        "https://salesforce.com",
        "https://example.my.salesforce.com.evil.test",
        "https://user@example.my.salesforce.com",
        "https://example.my.salesforce.com:443",
        "https://example.my.salesforce.com/services/data",
    ),
)
def test_salesforce_instance_url_rejects_untrusted_origins(value: str) -> None:
    with pytest.raises(SalesforceAPIError, match="provider_instance_url_invalid"):
        validate_salesforce_instance_url(value)


def test_salesforce_external_client_app_oauth_verifies_signature_identity_and_pkce() -> None:
    settings = _settings()
    identity_url = "https://login.salesforce.com/id/00D000000000001/005000000000001"
    issued_at = "1788652800000"
    signature = base64.b64encode(
        hmac.new(
            settings.salesforce_client_secret.get_secret_value().encode(),
            f"{identity_url}{issued_at}".encode(),
            hashlib.sha256,
        ).digest()
    ).decode()
    calls: list[tuple[str, str]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append((request.method, request.url.path))
        if request.url.path == "/services/oauth2/token":
            form = request.content.decode()
            assert "code_verifier=local-verifier" in form
            return httpx.Response(
                200,
                json={
                    "access_token": "salesforce-access",
                    "refresh_token": "salesforce-refresh",
                    "instance_url": "https://example.my.salesforce.com",
                    "id": identity_url,
                    "issued_at": issued_at,
                    "signature": signature,
                    "scope": "api openid refresh_token",
                },
            )
        assert request.url.host == "example.my.salesforce.com"
        assert request.headers["Authorization"] == "Bearer salesforce-access"
        return httpx.Response(
            200,
            json={
                "user_id": "005000000000001",
                "organization_id": "00D000000000001",
                "preferred_username": "admin@example.test",
                "name": "CRM Admin",
            },
        )

    async def scenario() -> None:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http_client:
            client = SalesforceClient(settings, _MemoryStore(_credential()), http_client=http_client)
            url = client.authorisation_url("oauth-state", "pkce-challenge")
            query = parse_qs(urlparse(url).query)
            assert query["scope"][0].split() == list(SALESFORCE_REQUIRED_SCOPES)
            assert query["code_challenge_method"] == ["S256"]
            assert query["code_challenge"] == ["pkce-challenge"]
            result = await client.exchange_code("authorisation-code", "local-verifier")
            assert result.identity.organization_id == "00D000000000001"
            assert result.credential.api_base_url == "https://example.my.salesforce.com"

    asyncio.run(scenario())
    assert calls == [("POST", "/services/oauth2/token"), ("GET", "/services/oauth2/userinfo")]


def test_salesforce_client_refreshes_pages_and_treats_write_timeout_as_unknown() -> None:
    store = _MemoryStore(_credential(expired=True))
    calls: list[tuple[str, str]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append((request.method, request.url.path))
        if request.url.path == "/services/oauth2/token":
            return httpx.Response(
                200,
                json={
                    "access_token": "rotated-access",
                    "refresh_token": "rotated-refresh",
                    "instance_url": "https://example.my.salesforce.com",
                },
            )
        if request.method == "GET":
            assert request.headers["Authorization"] == "Bearer rotated-access"
            return httpx.Response(
                200,
                json={
                    "done": True,
                    "records": [
                        {
                            "Id": "001000000000001",
                            "Name": "Acme",
                            "Website": "https://acme.example",
                            "SystemModstamp": "2026-09-06T00:00:00Z",
                            "LastModifiedDate": "2026-09-06T00:00:00Z",
                            "IsDeleted": False,
                            "untrustedPayload": "must not survive",
                        }
                    ],
                },
            )
        raise httpx.ReadTimeout("unknown write outcome", request=request)

    async def scenario() -> None:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http_client:
            client = SalesforceClient(_settings(), store, http_client=http_client)
            page = await client.list_records(_context(), "account", cursor=None, modified_after=None, limit=500)
            assert page.records[0].fields["name"] == "Acme"
            assert page.records[0].fields["domain"] == "https://acme.example"
            assert set(page.records[0].fields) == {"name", "domain", "industry", "owner"}
            assert "untrustedPayload" not in str(page.records[0])
            with pytest.raises(SalesforceAPIError) as failure:
                await client.update_record(_context(), page.records[0], {"name": "Acme Australia"})
            assert failure.value.uncertain is True
            assert failure.value.retryable is False
            assert store.credential.refresh_token == "rotated-refresh"

    asyncio.run(scenario())
    assert calls[0] == ("POST", "/services/oauth2/token")


def test_salesforce_person_accounts_fail_closed_instead_of_becoming_business_accounts() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/Account/describe"):
            return httpx.Response(200, json={"fields": [{"name": "IsPersonAccount"}]})
        return httpx.Response(
            200,
            json={
                "done": True,
                "records": [
                    {
                        "Id": "001000000000001",
                        "Name": "Taylor Person",
                        "SystemModstamp": "2026-09-06T00:00:00Z",
                        "LastModifiedDate": "2026-09-06T00:00:00Z",
                        "IsDeleted": False,
                        "IsPersonAccount": True,
                    }
                ],
            },
        )

    async def scenario() -> None:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http_client:
            client = SalesforceClient(_settings(), _MemoryStore(_credential()), http_client=http_client)
            with pytest.raises(SalesforceAPIError, match="provider_person_account_unsupported"):
                await client.list_records(_context(), "account", cursor=None, modified_after=None, limit=100)

    asyncio.run(scenario())


def test_salesforce_initial_sync_uses_provider_pagination_without_a_total_limit() -> None:
    calls: list[str] = []

    def record(record_id: str, stamp: str) -> dict[str, object]:
        return {
            "Id": record_id,
            "Name": f"Account {record_id}",
            "SystemModstamp": stamp,
            "LastModifiedDate": "2026-09-01T00:00:00Z",
            "IsDeleted": False,
        }

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.path)
        if request.url.path.endswith("/Account/describe"):
            return httpx.Response(200, json={"fields": []})
        if request.url.path.endswith("/queryAll"):
            assert "LIMIT" not in request.url.params["q"]
            assert request.headers["Sforce-Query-Options"] == "batchSize=200"
            return httpx.Response(
                200,
                json={
                    "done": False,
                    "nextRecordsUrl": "/services/data/v67.0/query/01g000000000001",
                    "records": [record("001000000000001", "2026-09-06T01:00:00Z")],
                },
            )
        assert request.url.path == "/services/data/v67.0/query/01g000000000001"
        return httpx.Response(
            200,
            json={
                "done": True,
                "records": [record("001000000000002", "2026-09-06T01:00:00Z")],
            },
        )

    async def scenario() -> None:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http_client:
            sf = SalesforceClient(_settings(), _MemoryStore(_credential()), http_client=http_client)
            first = await sf.list_records(
                _context(),
                "account",
                cursor=None,
                modified_after=datetime(2026, 9, 6, 1, tzinfo=UTC),
                limit=10,
            )
            assert first.next_cursor == "/services/data/v67.0/query/01g000000000001"
            assert first.records[0].modified_at == datetime(2026, 9, 6, 1, tzinfo=UTC)
            second = await sf.list_records(
                _context(),
                "account",
                cursor=first.next_cursor,
                modified_after=datetime(2026, 9, 6, 1, tzinfo=UTC),
                limit=10,
            )
            assert second.next_cursor is None
            assert second.records[0].external_object_id == "001000000000002"

    asyncio.run(scenario())
    assert calls == [
        "/services/data/v67.0/sobjects/Account/describe",
        "/services/data/v67.0/queryAll",
        "/services/data/v67.0/query/01g000000000001",
    ]


def test_salesforce_create_preserves_decimal_and_never_retries_after_verification_loss() -> None:
    post_bodies: list[dict[str, object]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/Opportunity/describe"):
            return httpx.Response(200, json={"fields": [{"name": "CurrencyIsoCode"}]})
        if request.method == "POST":
            post_bodies.append(json.loads(request.content))
            return httpx.Response(201, json={"id": "006000000000001", "success": True})
        raise httpx.ReadTimeout("verification response lost", request=request)

    async def scenario() -> None:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http_client:
            sf = SalesforceClient(_settings(), _MemoryStore(_credential()), http_client=http_client)
            with pytest.raises(SalesforceAPIError) as failure:
                await sf.create_record(
                    _context(),
                    "opportunity",
                    {
                        "name": "Exact amount",
                        "estimated_value": Decimal("123456789012345.67"),
                        "currency": "AUD",
                    },
                )
            assert failure.value.uncertain is True
            assert failure.value.external_object_id == "006000000000001"

    asyncio.run(scenario())
    assert post_bodies == [
        {
            "Name": "Exact amount",
            "Amount": "123456789012345.67",
            "CurrencyIsoCode": "AUD",
        }
    ]


def test_salesforce_amount_write_fails_closed_without_explicit_currency_capability() -> None:
    methods: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        methods.append(request.method)
        assert request.url.path.endswith("/Opportunity/describe")
        return httpx.Response(200, json={"fields": []})

    async def scenario() -> None:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http_client:
            sf = SalesforceClient(_settings(), _MemoryStore(_credential()), http_client=http_client)
            with pytest.raises(SalesforceAPIError, match="provider_currency_capability_required"):
                await sf.create_record(
                    _context(),
                    "opportunity",
                    {"estimated_value": Decimal("100.00"), "currency": "AUD"},
                )

    asyncio.run(scenario())
    assert methods == ["GET"]


def test_salesforce_oauth_is_tenant_bound_encrypted_and_queues_read_only_initial_sync(
    app: FastAPI,
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _enable_salesforce(app)
    result = SalesforceOAuthResult(
        credential=_credential(),
        identity=SalesforceIdentity(
            user_id="005000000000001",
            organization_id="00D000000000001",
            preferred_username="admin@example.test",
            name="CRM Admin",
        ),
    )

    async def exchange_code(self: SalesforceClient, code: str, verifier: str) -> SalesforceOAuthResult:
        del self
        assert code == "authorisation-code"
        assert len(verifier) >= 64
        return result

    monkeypatch.setattr(SalesforceClient, "exchange_code", exchange_code)
    started = client.post("/api/v1/integrations/salesforce/oauth/start")
    assert started.status_code == 200, started.text
    query = parse_qs(urlparse(started.json()["authorisationUrl"]).query)
    state = query["state"][0]
    assert query["code_challenge_method"] == ["S256"]

    app.dependency_overrides[get_current_user] = secondary_user
    try:
        wrong_tenant = client.post(
            "/api/v1/integrations/salesforce/oauth/callback",
            json={"state": state, "code": "authorisation-code"},
        )
        assert wrong_tenant.status_code == 400
        assert wrong_tenant.json()["code"] == "oauth_state_invalid"
    finally:
        app.dependency_overrides.pop(get_current_user, None)

    callback = client.post(
        "/api/v1/integrations/salesforce/oauth/callback",
        json={"state": state, "code": "authorisation-code"},
    )
    assert callback.status_code == 200, callback.text
    assert callback.json()["connectorKey"] == "salesforce"
    assert callback.json()["externalTenantId"] == "00D000000000001"
    assert "salesforce-access" not in callback.text
    assert "salesforce-refresh" not in callback.text

    app.state.settings.feature_hubspot_crm_enabled = True
    app.state.settings.hubspot_client_id = "hubspot-test-client"
    app.state.settings.hubspot_client_secret = SecretStr("hubspot-test-secret")
    app.state.settings.hubspot_oauth_redirect_uri = "http://localhost:3000/settings/integrations/hubspot/callback"
    switch_blocked = client.post("/api/v1/integrations/hubspot/oauth/start")
    assert switch_blocked.status_code == 409
    assert switch_blocked.json()["code"] == "primary_crm_already_connected"
    replay = client.post(
        "/api/v1/integrations/salesforce/oauth/callback",
        json={"state": state, "code": "authorisation-code"},
    )
    assert replay.status_code == 409
    assert replay.json()["code"] == "oauth_state_replayed"

    rejected_tenants: list[str] = []

    async def revoke_duplicate_tenant(
        self: SalesforceClient,
        credential: ConnectorCredential,
    ) -> None:
        del self
        rejected_tenants.append(credential.external_account_id)

    monkeypatch.setattr(SalesforceClient, "revoke", revoke_duplicate_tenant)
    app.dependency_overrides[get_current_user] = secondary_user
    try:
        duplicate_start = client.post("/api/v1/integrations/salesforce/oauth/start")
        duplicate_state = parse_qs(urlparse(duplicate_start.json()["authorisationUrl"]).query)["state"][0]
        duplicate_tenant = client.post(
            "/api/v1/integrations/salesforce/oauth/callback",
            json={"state": duplicate_state, "code": "authorisation-code"},
        )
        assert duplicate_tenant.status_code == 409
        assert duplicate_tenant.json()["code"] == "provider_tenant_already_connected"
        duplicate_replay = client.post(
            "/api/v1/integrations/salesforce/oauth/callback",
            json={"state": duplicate_state, "code": "authorisation-code"},
        )
        assert duplicate_replay.status_code == 409
        assert duplicate_replay.json()["code"] == "oauth_state_replayed"
    finally:
        app.dependency_overrides.pop(get_current_user, None)
    assert rejected_tenants == ["00D000000000001"]

    status = client.get(f"/api/v1/integrations/connections/{callback.json()['id']}/crm/status")
    assert status.status_code == 200
    assert status.json()["lifecycle"] == "initial_sync"
    assert status.json()["writebackEnabled"] is False

    async def verify_persistence() -> None:
        engine = create_async_engine(TEST_DB_URL)
        async with async_sessionmaker(engine, expire_on_commit=False)() as session:
            encrypted = await session.scalar(select(EncryptedConnectorCredential))
            crm_state = await session.scalar(select(CRMConnectionState))
            initial_job = await session.scalar(select(CRMSyncJob))
            assert encrypted is not None
            assert b"salesforce-access" not in encrypted.encrypted_payload
            assert b"salesforce-refresh" not in encrypted.encrypted_payload
            assert crm_state is not None and crm_state.writeback_enabled is False
            assert initial_job is not None and initial_job.mode == "initial" and initial_job.status == "queued"
        await engine.dispose()

    asyncio.run(verify_persistence())


def test_salesforce_reconnect_cannot_reclaim_a_provider_tenant_now_used_by_another_org(
    app: FastAPI,
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _enable_salesforce(app)
    result = SalesforceOAuthResult(
        credential=_credential(),
        identity=SalesforceIdentity(
            user_id="005000000000001",
            organization_id="00D000000000001",
            preferred_username="admin@example.test",
            name="CRM Admin",
        ),
    )
    revoked_organisations: list[str] = []

    async def exchange_code(self: SalesforceClient, code: str, verifier: str) -> SalesforceOAuthResult:
        del self, code
        assert len(verifier) >= 64
        return result

    async def revoke(self: SalesforceClient, value: ConnectorCredential) -> None:
        del self
        revoked_organisations.append(value.external_account_id)

    monkeypatch.setattr(SalesforceClient, "exchange_code", exchange_code)
    monkeypatch.setattr(SalesforceClient, "revoke", revoke)

    def connect_current_user() -> dict[str, object]:
        started = client.post("/api/v1/integrations/salesforce/oauth/start")
        assert started.status_code == 200, started.text
        state = parse_qs(urlparse(started.json()["authorisationUrl"]).query)["state"][0]
        completed = client.post(
            "/api/v1/integrations/salesforce/oauth/callback",
            json={"state": state, "code": "authorisation-code"},
        )
        assert completed.status_code == 200, completed.text
        return completed.json()

    primary = connect_current_user()
    assert client.delete(f"/api/v1/integrations/connections/{primary['id']}").status_code == 200

    app.dependency_overrides[get_current_user] = secondary_user
    try:
        secondary = connect_current_user()
        assert secondary["connectionStatus"] == "active"
    finally:
        app.dependency_overrides.pop(get_current_user, None)

    reconnect_start = client.post("/api/v1/integrations/salesforce/oauth/start")
    reconnect_state = parse_qs(urlparse(reconnect_start.json()["authorisationUrl"]).query)["state"][0]
    rejected = client.post(
        "/api/v1/integrations/salesforce/oauth/callback",
        json={"state": reconnect_state, "code": "authorisation-code"},
    )
    assert rejected.status_code == 409
    assert rejected.json()["code"] == "provider_tenant_already_connected"
    replay = client.post(
        "/api/v1/integrations/salesforce/oauth/callback",
        json={"state": reconnect_state, "code": "authorisation-code"},
    )
    assert replay.status_code == 409
    assert replay.json()["code"] == "oauth_state_replayed"
    assert revoked_organisations == ["00D000000000001", "00D000000000001"]


def test_incremental_scheduler_is_interval_bounded_idempotent_and_resets_only_page_state() -> None:
    async def scenario() -> None:
        engine = create_async_engine(TEST_DB_URL)
        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        connection_id = uuid.uuid4()
        now = datetime.now(UTC)
        watermark = now - timedelta(minutes=10)
        async with session_factory() as session:
            session.add(
                IntegrationConnection(
                    id=connection_id,
                    organisation_id=PRIMARY_ORGANISATION_ID,
                    connector_key="salesforce",
                    connection_status="active",
                    created_by_user_id=PRIMARY_USER_ID,
                    connected_at=watermark,
                    last_verified_at=watermark,
                    revoked_at=None,
                    credential_reference=None,
                    capability_state_json=["sync_accounts"],
                    external_account_id="005000000000001",
                    external_account_name="CRM Admin",
                    external_account_email="admin@example.test",
                    external_tenant_id="00D000000000001",
                    granted_scopes_json=list(SALESFORCE_REQUIRED_SCOPES),
                    metadata_version=1,
                    created_at=watermark,
                    updated_at=watermark,
                )
            )
            session.add(
                CRMConnectionState(
                    id=uuid.uuid4(),
                    organisation_id=PRIMARY_ORGANISATION_ID,
                    connection_id=connection_id,
                    provider_key="salesforce",
                    lifecycle="ready",
                    health_status="healthy",
                    connector_enabled=True,
                    writeback_enabled=False,
                    mapping_version=1,
                    records_seen=3,
                    records_applied=3,
                    conflict_count=0,
                    initial_sync_started_at=watermark,
                    initial_sync_completed_at=watermark,
                    last_successful_sync_at=watermark,
                    last_health_checked_at=watermark,
                    last_safe_error_code=None,
                    configured_by_user_id=PRIMARY_USER_ID,
                    created_at=watermark,
                    updated_at=watermark,
                )
            )
            for object_type in ("account", "contact", "opportunity"):
                session.add(
                    CRMSyncCursor(
                        id=uuid.uuid4(),
                        organisation_id=PRIMARY_ORGANISATION_ID,
                        connection_id=connection_id,
                        provider_key="salesforce",
                        object_type=object_type,
                        strategy="full",
                        cursor_token="finished-page",
                        high_watermark_at=watermark,
                        page_count=2,
                        record_count=3,
                        completed_at=watermark,
                        created_at=watermark,
                        updated_at=watermark,
                    )
                )
            await session.commit()

        worker = CRMConnectorWorkerService(session_factory, _settings())
        assert await worker.schedule_due_incremental_syncs() is True
        assert await worker.schedule_due_incremental_syncs() is False
        async with session_factory() as session:
            jobs = list((await session.scalars(select(CRMSyncJob))).all())
            cursors = list((await session.scalars(select(CRMSyncCursor))).all())
            assert len(jobs) == 1
            assert jobs[0].mode == "incremental" and len(jobs[0].idempotency_key) == 64
            assert all(cursor.strategy == "incremental" for cursor in cursors)
            assert all(cursor.cursor_token is None and cursor.completed_at is None for cursor in cursors)
            assert all(cursor.high_watermark_at is not None for cursor in cursors)
        await engine.dispose()

    asyncio.run(scenario())
