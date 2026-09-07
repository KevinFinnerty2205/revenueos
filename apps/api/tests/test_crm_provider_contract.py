from __future__ import annotations

import asyncio
import base64
import uuid
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from pydantic import SecretStr, ValidationError

from revenueos.config import Settings
from revenueos.credential_store import ConnectorCredential
from revenueos.crm_provider import CRMProviderAdapter
from revenueos.hubspot_connector import HUBSPOT_REQUIRED_SCOPES, HubSpotClient, HubSpotSyncAdapter
from revenueos.integration_executors import ExecutorConnectionContext
from revenueos.salesforce_connector import SALESFORCE_REQUIRED_SCOPES, SalesforceClient


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


def _master_key() -> str:
    return base64.urlsafe_b64encode(b"c" * 32).decode().rstrip("=")


def _context(external_account_id: str) -> ExecutorConnectionContext:
    return ExecutorConnectionContext(
        organisation_id=uuid.uuid4(),
        connection_id=uuid.uuid4(),
        credential_reference="credential-ref",
        execution_mode="live",
        external_account_id=external_account_id,
        external_tenant_id=external_account_id,
    )


@pytest.mark.parametrize("provider", ("hubspot", "salesforce"))
def test_production_crm_activation_and_provider_origins_fail_closed(provider: str) -> None:
    common: dict[str, object] = {
        "environment": "production",
        "auth_mode": "clerk",
        "mock_auth_enabled": False,
        "identity_jit_provisioning_enabled": False,
        "clerk_jwks_url": "https://identity.example.test/jwks.json",
        "clerk_issuer": "https://identity.example.test",
        "clerk_audience": "revenueos-api",
        "database_url": "postgresql+asyncpg://runtime.example.test/revenueos?ssl=require",
        "cors_origins": "https://app.example.test",
        "allowed_hosts": "api.example.test",
        "outreach_suppression_hmac_key": "deployment-specific-suppression-key",
        "feature_visual_evidence_enabled": False,
        "feature_recording_capture_enabled": False,
        "feature_online_meeting_capture_enabled": False,
        "feature_online_meeting_import_enabled": False,
        "feature_document_evidence_enabled": False,
        "feature_create_enabled": False,
        "feature_integrations_enabled": True,
        "feature_action_execution_enabled": True,
        "connector_credential_master_key": _master_key(),
    }
    if provider == "hubspot":
        provider_settings = {
            "feature_hubspot_crm_enabled": True,
            "hubspot_client_id": "hubspot-production-client-id",
            "hubspot_client_secret": "hubspot-production-client-secret",
            "hubspot_oauth_redirect_uri": "https://app.example.test/settings/integrations/hubspot/callback",
        }
        approval_key = "hubspot_production_activation_approved"
        redirect_key = "hubspot_oauth_redirect_uri"
        origin_key = "hubspot_api_base_url"
    else:
        provider_settings = {
            "feature_salesforce_crm_enabled": True,
            "salesforce_client_id": "salesforce-production-client-id",
            "salesforce_client_secret": "salesforce-production-client-secret",
            "salesforce_oauth_redirect_uri": "https://app.example.test/settings/integrations/salesforce/callback",
        }
        approval_key = "salesforce_production_activation_approved"
        redirect_key = "salesforce_oauth_redirect_uri"
        origin_key = "salesforce_token_url"

    with pytest.raises(ValidationError, match="explicit owner approval"):
        Settings(**{**common, **provider_settings})  # type: ignore[arg-type]
    with pytest.raises(ValidationError, match="HTTPS redirect URI"):
        Settings(
            **{
                **common,
                **provider_settings,
                approval_key: True,
                redirect_key: "http://app.example.test/callback",
            }
        )  # type: ignore[arg-type]
    with pytest.raises(ValidationError, match="official HTTPS"):
        Settings(
            **{
                **common,
                **provider_settings,
                approval_key: True,
                origin_key: "https://attacker.example.test/oauth",
            }
        )  # type: ignore[arg-type]


async def _assert_account_page_contract(
    adapter: CRMProviderAdapter,
    context: ExecutorConnectionContext,
) -> None:
    page = await adapter.list_records(
        context,
        "account",
        cursor=None,
        modified_after=datetime(2026, 9, 1, tzinfo=UTC),
        limit=500,
    )
    assert len(page.records) == 1
    assert page.next_cursor is None or (0 < len(page.next_cursor) <= 2048)
    assert page.high_watermark_at.tzinfo is not None
    record = page.records[0]
    assert record.object_type == "account"
    assert record.external_object_id
    assert record.external_version
    assert record.modified_at.tzinfo is not None
    assert record.fields["name"] == "Acme Australia"
    assert set(record.fields) <= {"name", "domain", "industry", "owner"}
    assert "Untrusted_Custom_Field__c" not in record.fields
    assert "untrusted_custom_field" not in record.fields


@pytest.mark.parametrize("provider", ("hubspot", "salesforce"))
def test_production_crm_adapters_share_the_bounded_provider_contract(provider: str) -> None:
    async def scenario() -> None:
        if provider == "hubspot":
            external_account_id = "1234567"
            credential = ConnectorCredential(
                access_token="hubspot-access",
                refresh_token="hubspot-refresh",
                expires_at=datetime.now(UTC) + timedelta(minutes=30),
                scopes=HUBSPOT_REQUIRED_SCOPES,
                external_account_id=external_account_id,
            )

            def handler(request: httpx.Request) -> httpx.Response:
                assert request.url.path == "/crm/objects/2026-03/companies/search"
                assert request.headers["Authorization"] == "Bearer hubspot-access"
                assert request.read().decode().count('"limit":200') == 1
                return httpx.Response(
                    200,
                    json={
                        "results": [
                            {
                                "id": "101",
                                "properties": {
                                    "name": " Acme Australia ",
                                    "domain": "acme.example",
                                    "untrusted_custom_field": "must not cross adapter",
                                },
                                "updatedAt": "2026-09-06T01:00:00Z",
                            }
                        ],
                        "total": 1,
                    },
                )

            settings = Settings(
                feature_integrations_enabled=True,
                feature_action_execution_enabled=True,
                feature_hubspot_crm_enabled=True,
                hubspot_client_id="hubspot-client",
                hubspot_client_secret=SecretStr("hubspot-secret"),
                hubspot_oauth_redirect_uri="http://localhost:3000/settings/integrations/hubspot/callback",
                connector_credential_master_key=SecretStr(_master_key()),
            )

            async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http_client:
                adapter = HubSpotSyncAdapter(HubSpotClient(settings, _MemoryStore(credential), http_client=http_client))
                await _assert_account_page_contract(adapter, _context(external_account_id))
            return

        external_account_id = "00D000000000001"
        credential = ConnectorCredential(
            access_token="salesforce-access",
            refresh_token="salesforce-refresh",
            expires_at=datetime.now(UTC) + timedelta(minutes=30),
            scopes=SALESFORCE_REQUIRED_SCOPES,
            external_account_id=external_account_id,
            api_base_url="https://example.my.salesforce.com",
        )
        describe_calls = 0

        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal describe_calls
            assert request.headers["Authorization"] == "Bearer salesforce-access"
            if request.url.path.endswith("/sobjects/Account/describe"):
                describe_calls += 1
                return httpx.Response(200, json={"fields": []})
            assert request.url.path.endswith("/queryAll")
            query = request.url.params["q"]
            assert "LIMIT" not in query
            assert request.headers["Sforce-Query-Options"] == "batchSize=200"
            assert "SystemModstamp >= 2026-09-01T00:00:00Z" in query
            return httpx.Response(
                200,
                json={
                    "records": [
                        {
                            "Id": "001000000000001",
                            "Name": "Acme Australia",
                            "Website": "acme.example",
                            "Untrusted_Custom_Field__c": "must not cross adapter",
                            "SystemModstamp": "2026-09-06T01:00:00Z",
                            "LastModifiedDate": "2026-09-06T01:00:00Z",
                        }
                    ],
                    "done": True,
                },
            )

        settings = Settings(
            feature_integrations_enabled=True,
            feature_action_execution_enabled=True,
            feature_salesforce_crm_enabled=True,
            salesforce_client_id="salesforce-client",
            salesforce_client_secret=SecretStr("salesforce-secret"),
            salesforce_oauth_redirect_uri="http://localhost:3000/settings/integrations/salesforce/callback",
            connector_credential_master_key=SecretStr(_master_key()),
        )
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http_client:
            adapter = SalesforceClient(settings, _MemoryStore(credential), http_client=http_client)
            await _assert_account_page_contract(adapter, _context(external_account_id))
            await _assert_account_page_contract(adapter, _context(external_account_id))
            assert describe_calls == 1

    asyncio.run(scenario())
