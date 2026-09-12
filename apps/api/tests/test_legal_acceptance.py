from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import cast

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from revenueos.billing_contracts import CheckoutCreateRequest
from revenueos.billing_provider import DeterministicBillingProvider
from revenueos.billing_services import BillingService
from revenueos.commercial_contracts import PlanCode
from revenueos.commercial_services import CommercialService
from revenueos.config import Settings
from revenueos.database import set_tenant_database_context
from revenueos.errors import PublicAPIError
from revenueos.legal_releases import CURRENT_PRIVACY_NOTICE, CURRENT_TERMS_RELEASE
from revenueos.legal_services import LegalService
from revenueos.models import (
    BillingAccount,
    BillingOperation,
    CommercialPlanVersion,
    OrganisationCommercialState,
    OrganisationMembership,
    TermsAcceptance,
    User,
)
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


def test_privacy_notice_change_does_not_become_a_second_contract_acceptance(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def scenario() -> None:
        engine = create_async_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
        try:
            async with async_sessionmaker(engine, expire_on_commit=False)() as session:
                await set_tenant_database_context(session, PRIMARY_ORGANISATION_ID)
                original = await session.scalar(
                    select(TermsAcceptance).where(
                        TermsAcceptance.organisation_id == PRIMARY_ORGANISATION_ID,
                        TermsAcceptance.terms_version == CURRENT_TERMS_RELEASE.version,
                    )
                )
                assert original is not None
                changed_notice = type(CURRENT_PRIVACY_NOTICE)(
                    status="draft",
                    version="future-privacy-notice-v2",
                    sha256="e" * 64,
                    effective_date=None,
                    href="/privacy",
                    canonical_source="synthetic-review-only",
                )
                monkeypatch.setattr(
                    "revenueos.legal_services.CURRENT_PRIVACY_NOTICE",
                    changed_notice,
                )
                status = await LegalService(
                    session,
                    TenantContext(PRIMARY_ORGANISATION_ID, PRIMARY_USER_ID, "admin"),
                    _settings(),
                ).status()
                assert status.accepted is True
                assert status.privacy_notice.version == changed_notice.version
                assert status.evidence is not None
                assert status.evidence.privacy_notice_version == original.privacy_notice_version
                assert status.evidence.privacy_notice_version != status.privacy_notice.version
        finally:
            await engine.dispose()

    asyncio.run(scenario())


def test_new_material_terms_version_creates_a_new_event_without_mutating_history(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def scenario() -> None:
        engine = create_async_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
        try:
            async with async_sessionmaker(engine, expire_on_commit=False)() as session:
                await set_tenant_database_context(session, PRIMARY_ORGANISATION_ID)
                original = await session.scalar(
                    select(TermsAcceptance).where(
                        TermsAcceptance.organisation_id == PRIMARY_ORGANISATION_ID,
                        TermsAcceptance.terms_version == CURRENT_TERMS_RELEASE.version,
                    )
                )
                assert original is not None
                original_identity = (original.id, original.terms_version, original.terms_sha256, original.accepted_at)
                changed_terms = type(CURRENT_TERMS_RELEASE)(
                    status="draft",
                    version="future-material-terms-v2",
                    sha256="f" * 64,
                    effective_date=None,
                    href="/terms",
                    canonical_source="synthetic-review-only",
                )
                monkeypatch.setattr(
                    "revenueos.legal_services.CURRENT_TERMS_RELEASE",
                    changed_terms,
                )
                result = await LegalService(
                    session,
                    TenantContext(PRIMARY_ORGANISATION_ID, PRIMARY_USER_ID, "admin"),
                    _settings(),
                ).accept_current("administrative_onboarding")
                assert result.accepted is True
                assert result.evidence is not None
                assert result.evidence.terms_version == changed_terms.version
                await session.refresh(original)
                assert (
                    original.id,
                    original.terms_version,
                    original.terms_sha256,
                    original.accepted_at,
                ) == original_identity
                assert (
                    await session.scalar(
                        select(func.count())
                        .select_from(TermsAcceptance)
                        .where(TermsAcceptance.organisation_id == PRIMARY_ORGANISATION_ID)
                    )
                    == 2
                )
        finally:
            await engine.dispose()

    asyncio.run(scenario())


def test_acceptance_endpoint_uses_current_database_authority_and_denies_disabled_identities(
    client: TestClient,
) -> None:
    engine = create_async_engine(TEST_DB_URL, connect_args={"check_same_thread": False})

    async def set_identity_state(*, role: str, membership_status: str, user_status: str) -> None:
        async with async_sessionmaker(engine, expire_on_commit=False)() as session:
            await session.execute(
                update(OrganisationMembership)
                .where(
                    OrganisationMembership.organisation_id == PRIMARY_ORGANISATION_ID,
                    OrganisationMembership.user_id == PRIMARY_USER_ID,
                )
                .values(role=role, status=membership_status)
            )
            await session.execute(update(User).where(User.id == PRIMARY_USER_ID).values(status=user_status))
            await session.commit()

    try:
        asyncio.run(set_identity_state(role="member", membership_status="active", user_status="active"))
        member_status = client.get("/api/v1/legal/terms-acceptance")
        assert member_status.status_code == 200
        assert member_status.json()["canAccept"] is False
        assert (
            client.post(
                "/api/v1/legal/terms-acceptance",
                json={"authorityAndTermsAccepted": True, "source": "trial_onboarding"},
            ).status_code
            == 403
        )

        asyncio.run(set_identity_state(role="admin", membership_status="active", user_status="disabled"))
        assert client.get("/api/v1/legal/terms-acceptance").status_code == 403

        asyncio.run(set_identity_state(role="admin", membership_status="disabled", user_status="active"))
        assert client.get("/api/v1/legal/terms-acceptance").status_code == 403
    finally:
        asyncio.run(set_identity_state(role="admin", membership_status="active", user_status="active"))
        asyncio.run(engine.dispose())


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
    checks = cast(list[dict[str, object]], result["checks"])
    terms_check = next(check for check in checks if check["name"] == "terms_acceptance_release")
    assert terms_check["status"] == "fail"
    assert result["status"] == "blocked"


def test_trial_and_paid_checkout_fail_before_side_effects_without_or_with_old_acceptance() -> None:
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
                state_lock_version = state.lock_version
                with pytest.raises(PublicAPIError) as trial_blocked:
                    await CommercialService(session, settings).start_trial(
                        PRIMARY_ORGANISATION_ID,
                        actor_reference="support-does-not-accept",
                        reason="The customer has not yet provided acceptance.",
                        expected_lock_version=state_lock_version,
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

                old_accepted_at = datetime.now(UTC)
                session.add(
                    TermsAcceptance(
                        organisation_id=PRIMARY_ORGANISATION_ID,
                        accepted_by_user_id=PRIMARY_USER_ID,
                        release_status="draft",
                        terms_version="retired-draft-terms-v0",
                        terms_sha256="d" * 64,
                        terms_effective_date=None,
                        accepted_at=old_accepted_at,
                        acceptance_source="administrative_onboarding",
                        privacy_notice_version="retired-privacy-notice-v0",
                        privacy_notice_sha256="e" * 64,
                        privacy_notice_effective_date=None,
                        privacy_notice_presented_at=old_accepted_at,
                    )
                )
                await session.commit()
                await set_tenant_database_context(session, PRIMARY_ORGANISATION_ID)
                with pytest.raises(PublicAPIError) as old_trial_blocked:
                    await CommercialService(session, settings).start_trial(
                        PRIMARY_ORGANISATION_ID,
                        actor_reference="support-old-terms-denied",
                        reason="The customer accepted only a retired Terms release.",
                        expected_lock_version=state_lock_version,
                    )
                assert old_trial_blocked.value.code == "terms_acceptance_required"
                await session.rollback()
                await set_tenant_database_context(session, PRIMARY_ORGANISATION_ID)
                with pytest.raises(PublicAPIError) as old_checkout_blocked:
                    await BillingService(session, settings, provider).create_checkout(
                        PRIMARY_ORGANISATION_ID,
                        PRIMARY_USER_ID,
                        CheckoutCreateRequest(
                            plan_code="core",
                            billing_interval="monthly",
                            idempotency_key="old-terms-checkout-0001",
                        ),
                    )
                assert old_checkout_blocked.value.code == "terms_acceptance_required"
                assert provider.checkouts == {}
        finally:
            await engine.dispose()

    asyncio.run(scenario())


def test_production_draft_terms_deny_trial_and_checkout_before_side_effects() -> None:
    async def scenario() -> None:
        settings = _settings()
        settings.environment = "production"
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
                        actor_reference="wo-054-production-draft-terms",
                        reason="Draft Terms cannot authorise production activation.",
                        expected_lock_version=state.lock_version,
                    )
                assert trial_blocked.value.code == "terms_acceptance_unavailable"
                await session.rollback()
                await set_tenant_database_context(session, PRIMARY_ORGANISATION_ID)

                with pytest.raises(PublicAPIError) as checkout_blocked:
                    await BillingService(session, settings, provider).create_checkout(
                        PRIMARY_ORGANISATION_ID,
                        PRIMARY_USER_ID,
                        CheckoutCreateRequest(
                            plan_code="core",
                            billing_interval="monthly",
                            idempotency_key="wo-054-production-draft-checkout",
                        ),
                    )
                assert checkout_blocked.value.code == "terms_acceptance_unavailable"
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


def test_checkout_rechecks_and_persists_the_exact_terms_authority_before_provider_side_effects(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def scenario() -> None:
        settings = _settings()
        provider = DeterministicBillingProvider(settings)
        engine = create_async_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
        try:
            async with async_sessionmaker(engine, expire_on_commit=False)() as session:
                await set_tenant_database_context(session, PRIMARY_ORGANISATION_ID)
                baseline = await session.scalar(
                    select(TermsAcceptance).where(
                        TermsAcceptance.organisation_id == PRIMARY_ORGANISATION_ID,
                        TermsAcceptance.terms_version == CURRENT_TERMS_RELEASE.version,
                    )
                )
                assert baseline is not None
                service = BillingService(session, settings, provider)
                original_plan = service._plan

                async def change_release_during_checkout(plan_code: PlanCode) -> CommercialPlanVersion:
                    plan = await original_plan(plan_code)
                    monkeypatch.setattr(
                        "revenueos.legal_services.CURRENT_TERMS_RELEASE",
                        type(CURRENT_TERMS_RELEASE)(
                            status="draft",
                            version="future-material-terms-v2",
                            sha256="f" * 64,
                            effective_date=None,
                            href="/terms",
                            canonical_source="synthetic-review-only",
                        ),
                    )
                    return plan

                monkeypatch.setattr(service, "_plan", change_release_during_checkout)
                try:
                    with pytest.raises(PublicAPIError) as changed:
                        await service.create_checkout(
                            PRIMARY_ORGANISATION_ID,
                            PRIMARY_USER_ID,
                            CheckoutCreateRequest(
                                plan_code="core",
                                billing_interval="monthly",
                                idempotency_key="terms-race-checkout-0001",
                            ),
                        )
                finally:
                    monkeypatch.setattr(
                        "revenueos.legal_services.CURRENT_TERMS_RELEASE",
                        CURRENT_TERMS_RELEASE,
                    )
                assert changed.value.code == "terms_acceptance_required"
                assert provider.checkouts == {}
                assert (
                    await session.scalar(
                        select(func.count())
                        .select_from(BillingAccount)
                        .where(BillingAccount.organisation_id == PRIMARY_ORGANISATION_ID)
                    )
                    == 0
                )
                operation = await session.scalar(
                    select(BillingOperation).where(
                        BillingOperation.organisation_id == PRIMARY_ORGANISATION_ID,
                        BillingOperation.idempotency_key == "terms-race-checkout-0001",
                    )
                )
                assert operation is not None
                assert operation.status == "failed"
                assert operation.terms_acceptance_id == baseline.id
        finally:
            await engine.dispose()

    asyncio.run(scenario())
