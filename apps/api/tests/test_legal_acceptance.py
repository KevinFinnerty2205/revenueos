from __future__ import annotations

import asyncio

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from revenueos.billing_contracts import CheckoutCreateRequest
from revenueos.billing_provider import DeterministicBillingProvider
from revenueos.billing_services import BillingService
from revenueos.commercial_services import CommercialService
from revenueos.config import Settings
from revenueos.database import set_tenant_database_context
from revenueos.errors import PublicAPIError
from revenueos.legal_releases import CURRENT_PRIVACY_NOTICE, CURRENT_TERMS_RELEASE
from revenueos.legal_services import LegalService
from revenueos.models import BillingOperation, OrganisationCommercialState, TermsAcceptance
from revenueos.operations import PreflightCheck, production_preflight
from revenueos.tenant import TenantContext
from tests.conftest import PRIMARY_ORGANISATION_ID, PRIMARY_USER_ID, TEST_DB_URL


def _settings(**changes: object) -> Settings:
    values: dict[str, object] = {
        "environment": "test",
        "auth_mode": "mock",
        "mock_auth_enabled": True,
        "database_url": TEST_DB_URL,
        "feature_billing_enabled": True,
    }
    values.update(changes)
    return Settings(**values)  # type: ignore[arg-type]


def test_admin_acceptance_is_explicit_server_owned_and_idempotent(client: TestClient) -> None:
    engine = create_async_engine(TEST_DB_URL, connect_args={"check_same_thread": False})

    async def remove_baseline() -> None:
        async with async_sessionmaker(engine, expire_on_commit=False)() as session:
            await session.execute(
                delete(TermsAcceptance).where(TermsAcceptance.organisation_id == PRIMARY_ORGANISATION_ID)
            )
            await session.commit()

    asyncio.run(remove_baseline())
    try:
        response = client.get("/api/v1/legal/terms-acceptance")
        assert response.status_code == 200
        assert response.json() == {
            "terms": {
                "status": "draft",
                "version": CURRENT_TERMS_RELEASE.version,
                "fingerprint": f"sha256:{CURRENT_TERMS_RELEASE.sha256}",
                "effectiveDate": None,
                "href": "/terms",
            },
            "privacyNotice": {
                "status": "draft",
                "version": CURRENT_PRIVACY_NOTICE.version,
                "fingerprint": f"sha256:{CURRENT_PRIVACY_NOTICE.sha256}",
                "effectiveDate": None,
                "href": "/privacy",
            },
            "accepted": False,
            "acceptanceAvailable": True,
            "canAccept": True,
            "evidence": None,
            "message": "An organisation administrator must accept the current Terms before continuing.",
        }
        assert (
            client.post(
                "/api/v1/legal/terms-acceptance",
                json={"authorityAndTermsAccepted": False, "source": "trial_onboarding"},
            ).status_code
            == 422
        )
        assert (
            client.post(
                "/api/v1/legal/terms-acceptance",
                json={
                    "authorityAndTermsAccepted": True,
                    "source": "trial_onboarding",
                    "organisationId": "00000000-0000-4000-8000-000000000012",
                    "acceptedByUserId": "00000000-0000-4000-8000-000000000011",
                    "acceptedAt": "2000-01-01T00:00:00Z",
                    "termsVersion": "forged",
                    "termsFingerprint": "sha256:forged",
                },
            ).status_code
            == 422
        )

        first = client.post(
            "/api/v1/legal/terms-acceptance",
            json={"authorityAndTermsAccepted": True, "source": "trial_onboarding"},
        )
        assert first.status_code == 200
        body = first.json()
        assert body["accepted"] is True
        assert body["evidence"]["acceptedByUserId"] == str(PRIMARY_USER_ID)
        assert body["evidence"]["acceptanceSource"] == "trial_onboarding"
        assert body["evidence"]["termsVersion"] == CURRENT_TERMS_RELEASE.version
        assert body["evidence"]["termsFingerprint"] == f"sha256:{CURRENT_TERMS_RELEASE.sha256}"
        assert body["evidence"]["termsEffectiveDate"] is None
        assert body["evidence"]["privacyNoticePresentedAt"] == body["evidence"]["acceptedAt"]

        repeated = client.post(
            "/api/v1/legal/terms-acceptance",
            json={"authorityAndTermsAccepted": True, "source": "subscription_checkout"},
        )
        assert repeated.status_code == 200
        assert repeated.json()["evidence"] == body["evidence"]

        async def verify() -> None:
            async with async_sessionmaker(engine, expire_on_commit=False)() as session:
                count = await session.scalar(
                    select(func.count())
                    .select_from(TermsAcceptance)
                    .where(TermsAcceptance.organisation_id == PRIMARY_ORGANISATION_ID)
                )
                assert count == 1

        asyncio.run(verify())
    finally:
        asyncio.run(engine.dispose())


def test_member_cannot_bind_and_draft_release_is_disabled_outside_test() -> None:
    async def scenario() -> None:
        engine = create_async_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
        try:
            async with async_sessionmaker(engine, expire_on_commit=False)() as session:
                await set_tenant_database_context(session, PRIMARY_ORGANISATION_ID)
                member = LegalService(
                    session,
                    TenantContext(PRIMARY_ORGANISATION_ID, PRIMARY_USER_ID, "member"),
                    _settings(),
                )
                with pytest.raises(PublicAPIError) as forbidden:
                    await member.accept_current("administrative_onboarding")
                assert forbidden.value.code == "forbidden"

                production_settings = _settings(feature_billing_enabled=False)
                production_settings.environment = "production"
                production = LegalService(
                    session,
                    TenantContext(PRIMARY_ORGANISATION_ID, PRIMARY_USER_ID, "admin"),
                    production_settings,
                )
                status = await production.status()
                assert status.acceptance_available is False
                assert status.accepted is False
                with pytest.raises(PublicAPIError) as unavailable:
                    await production.accept_current("administrative_onboarding")
                assert unavailable.value.code == "terms_acceptance_unavailable"
        finally:
            await engine.dispose()

    asyncio.run(scenario())


def test_production_preflight_keeps_draft_acceptance_release_blocked(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def storage_ready(_: Settings) -> PreflightCheck:
        return PreflightCheck("synthetic_storage", "pass", "Synthetic storage is ready.")

    monkeypatch.setattr("revenueos.operations.create_engine", lambda _: None)
    monkeypatch.setattr("revenueos.operations.inspect_export_storage", storage_ready)
    monkeypatch.setattr("revenueos.operations.inspect_object_storage", storage_ready)
    settings = _settings(feature_billing_enabled=False)
    settings.environment = "production"

    result = asyncio.run(production_preflight(settings))
    terms_check = next(check for check in result["checks"] if check["name"] == "terms_acceptance_release")  # type: ignore[index]
    assert terms_check["status"] == "fail"
    assert result["status"] == "blocked"


def test_trial_and_paid_checkout_fail_before_side_effects_without_current_acceptance() -> None:
    async def scenario() -> None:
        settings = _settings()
        provider = DeterministicBillingProvider(settings)
        engine = create_async_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
        try:
            async with async_sessionmaker(engine, expire_on_commit=False)() as session:
                await set_tenant_database_context(session, PRIMARY_ORGANISATION_ID)
                await session.execute(
                    delete(TermsAcceptance).where(TermsAcceptance.organisation_id == PRIMARY_ORGANISATION_ID)
                )
                await session.commit()
                await set_tenant_database_context(session, PRIMARY_ORGANISATION_ID)
                state = await session.get(OrganisationCommercialState, PRIMARY_ORGANISATION_ID)
                assert state is not None
                with pytest.raises(PublicAPIError) as trial_blocked:
                    await CommercialService(session, settings).start_trial(
                        PRIMARY_ORGANISATION_ID,
                        actor_reference="support-does-not-accept",
                        reason="The customer has not yet provided acceptance.",
                        expected_lock_version=state.lock_version,
                    )
                assert trial_blocked.value.code == "terms_acceptance_required"
                await session.rollback()
                await set_tenant_database_context(session, PRIMARY_ORGANISATION_ID)

                with pytest.raises(PublicAPIError) as checkout_blocked:
                    await BillingService(session, settings, provider).create_checkout(
                        PRIMARY_ORGANISATION_ID,
                        PRIMARY_USER_ID,
                        CheckoutCreateRequest(
                            plan_code="core",
                            billing_interval="monthly",
                            idempotency_key="terms-required-checkout-0001",
                        ),
                    )
                assert checkout_blocked.value.code == "terms_acceptance_required"
                assert provider.checkouts == {}
                assert (
                    await session.scalar(
                        select(func.count())
                        .select_from(BillingOperation)
                        .where(BillingOperation.organisation_id == PRIMARY_ORGANISATION_ID)
                    )
                    == 0
                )
        finally:
            await engine.dispose()

    asyncio.run(scenario())
