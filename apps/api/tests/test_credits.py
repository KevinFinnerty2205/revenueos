from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from revenueos.auth import AuthenticatedUser, get_current_user
from revenueos.beta_maintenance import _export_payload, delete_organisation
from revenueos.billing_provider import DeterministicBillingProvider, ProviderCheckout
from revenueos.billing_services import BillingService
from revenueos.config import Settings
from revenueos.credit_provider import DeterministicMeteredProvider
from revenueos.credit_services import (
    MAX_CREDITS,
    TEST_ACTION_CODE,
    TEST_PACK_ID,
    TEST_PROVIDER_CAPABILITY,
    CreditService,
)
from revenueos.database import set_tenant_database_context
from revenueos.errors import PublicAPIError
from revenueos.main import create_app
from revenueos.models import (
    BetaDataRequest,
    BillingAccount,
    BillingOperation,
    CreditActionPriceVersion,
    CreditLedgerEntry,
    CreditLot,
    CreditOperation,
    CreditPackVersion,
    CreditQuote,
    Organisation,
    OrganisationCommercialState,
    OrganisationCreditBalance,
)
from tests.conftest import (
    PRIMARY_ORGANISATION_ID,
    PRIMARY_USER_ID,
    SECONDARY_ORGANISATION_ID,
    SECONDARY_USER_ID,
    TEST_DB_URL,
)

WEBHOOK_SECRET = "test-credit-webhook-secret-0001"


def credit_settings() -> Settings:
    return Settings(
        environment="test",
        auth_mode="mock",
        mock_auth_enabled=True,
        database_url=TEST_DB_URL,
        log_level="WARNING",
        feature_credits_enabled=True,
        feature_billing_enabled=True,
        billing_provider_name="deterministic",
        billing_webhook_secret=WEBHOOK_SECRET,
    )


async def prepared_service(
    session: AsyncSession,
    *,
    clock: list[datetime] | None = None,
    max_per_operation: int = 1_000,
    max_per_day: int = 10_000,
    trial_cap: int | None = 500,
    rate_limit: int = 100,
) -> CreditService:
    service = CreditService(session, credit_settings(), clock=(lambda: clock[0]) if clock else None)
    await service.ensure_test_catalogue()
    await service.configure_policy(
        PRIMARY_ORGANISATION_ID,
        metered_actions_enabled=True,
        max_credits_per_operation=max_per_operation,
        max_credits_per_day=max_per_day,
        max_provider_cost_micros_per_day=100_000_000,
        trial_max_credits_per_day=trial_cap,
        max_operations_per_minute=rate_limit,
        actor_reference="wo-049-test-support",
        reason="Deterministic test-only exposure policy.",
    )
    return service


async def grant_test_purchase(
    session: AsyncSession, service: CreditService, *, key: str = "purchase-event-0001"
) -> UUID:
    operation = BillingOperation(
        id=uuid.uuid4(),
        organisation_id=PRIMARY_ORGANISATION_ID,
        requested_by_user_id=PRIMARY_USER_ID,
        operation_type="credit_purchase",
        idempotency_key=f"billing-{key}",
        request_fingerprint="a" * 64,
        status="succeeded",
        credit_pack_version_id=TEST_PACK_ID,
        amount=Decimal("20.00"),
        currency="AUD",
        provider_object_id=f"cs_test_{key}",
    )
    session.add(operation)
    await session.commit()
    await set_tenant_database_context(session, PRIMARY_ORGANISATION_ID)
    lot = await service.grant_verified_purchase(
        PRIMARY_ORGANISATION_ID,
        billing_operation_id=operation.id,
        provider_event_id=key,
    )
    return lot.id


def test_append_only_ledger_balance_consumption_order_settlement_refund_and_correction() -> None:
    async def scenario() -> None:
        engine = create_async_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
        try:
            async with async_sessionmaker(engine, expire_on_commit=False)() as session:
                await set_tenant_database_context(session, PRIMARY_ORGANISATION_ID)
                service = await prepared_service(session)
                purchased_lot_id = await grant_test_purchase(session, service)
                promotional = await service.grant_promotional(
                    PRIMARY_ORGANISATION_ID,
                    credits=10,
                    idempotency_key="promo-grant-0001",
                    source_reference="support-promo-0001",
                    actor_reference="support-operator-1",
                    reason="Bounded synthetic promotional grant.",
                    expires_at=datetime.now(UTC) + timedelta(days=2),
                )
                duplicate = await service.grant_promotional(
                    PRIMARY_ORGANISATION_ID,
                    credits=10,
                    idempotency_key="promo-grant-0001",
                    source_reference="support-promo-0001",
                    actor_reference="support-operator-1",
                    reason="Bounded synthetic promotional grant.",
                    expires_at=promotional.expires_at,
                )
                assert duplicate.id == promotional.id
                with pytest.raises(PublicAPIError) as promotional_conflict:
                    await service.grant_promotional(
                        PRIMARY_ORGANISATION_ID,
                        credits=11,
                        idempotency_key="promo-grant-0001",
                        source_reference="support-promo-0001",
                        actor_reference="support-operator-1",
                        reason="Bounded synthetic promotional grant.",
                        expires_at=promotional.expires_at,
                    )
                assert promotional_conflict.value.code == "credit_idempotency_conflict"
                projection = await service.projection(PRIMARY_ORGANISATION_ID)
                assert projection.balance.available == 110
                assert projection.balance.purchased_available == 100
                assert projection.balance.promotional_available == 10

                quote = await service.create_quote(
                    PRIMARY_ORGANISATION_ID,
                    PRIMARY_USER_ID,
                    action_code=TEST_ACTION_CODE,
                    quantity=3,
                )
                reserved = await service.reserve(
                    PRIMARY_ORGANISATION_ID,
                    PRIMARY_USER_ID,
                    quote_id=quote.quote_id,
                    idempotency_key="reservation-0001",
                )
                retried = await service.reserve(
                    PRIMARY_ORGANISATION_ID,
                    PRIMARY_USER_ID,
                    quote_id=quote.quote_id,
                    idempotency_key="reservation-0001",
                )
                assert retried == reserved
                conflicting_quote = await service.create_quote(
                    PRIMARY_ORGANISATION_ID,
                    PRIMARY_USER_ID,
                    action_code=TEST_ACTION_CODE,
                    quantity=1,
                )
                with pytest.raises(PublicAPIError) as reservation_conflict:
                    await service.reserve(
                        PRIMARY_ORGANISATION_ID,
                        PRIMARY_USER_ID,
                        quote_id=conflicting_quote.quote_id,
                        idempotency_key="reservation-0001",
                    )
                assert reservation_conflict.value.code == "credit_idempotency_conflict"
                projection = await service.projection(PRIMARY_ORGANISATION_ID)
                assert projection.balance.available == 95
                assert projection.balance.reserved == 15
                assert projection.balance.promotional_reserved == 10
                assert projection.balance.purchased_reserved == 5

                settled = await service.settle(
                    PRIMARY_ORGANISATION_ID,
                    reserved.operation_id,
                    successful_units=2,
                    provider_cost_micros=600_000,
                    provider_cost_currency="AUD",
                    idempotency_key="settlement-0001",
                )
                assert settled.status == "settled"
                assert settled.outcome == "partial"
                assert settled.settled_credits == 10
                assert settled.released_credits == 5
                with pytest.raises(PublicAPIError) as settlement_conflict:
                    await service.settle(
                        PRIMARY_ORGANISATION_ID,
                        reserved.operation_id,
                        successful_units=3,
                        provider_cost_micros=600_000,
                        provider_cost_currency="AUD",
                        idempotency_key="settlement-0001",
                    )
                assert settlement_conflict.value.code == "credit_idempotency_conflict"
                projection = await service.projection(PRIMARY_ORGANISATION_ID)
                assert projection.balance.available == 100
                assert projection.balance.purchased_available == 100
                assert projection.balance.promotional_available == 0
                assert projection.balance.reserved == 0

                consumption = await session.scalar(
                    select(CreditLedgerEntry).where(
                        CreditLedgerEntry.organisation_id == PRIMARY_ORGANISATION_ID,
                        CreditLedgerEntry.operation_id == reserved.operation_id,
                        CreditLedgerEntry.event_type == "consumption",
                    )
                )
                assert consumption is not None and consumption.credit_type == "promotional"
                refunded = await service.refund_consumption(
                    PRIMARY_ORGANISATION_ID,
                    consumption_entry_id=consumption.id,
                    credits=5,
                    idempotency_key="refund-0001",
                    actor_reference="support-operator-2",
                    reason="Partial synthetic service-value refund.",
                )
                assert refunded.credit_type == "promotional"
                assert refunded.expires_at == promotional.expires_at
                with pytest.raises(PublicAPIError) as refund_conflict:
                    await service.refund_consumption(
                        PRIMARY_ORGANISATION_ID,
                        consumption_entry_id=consumption.id,
                        credits=4,
                        idempotency_key="refund-0001",
                        actor_reference="support-operator-2",
                        reason="Partial synthetic service-value refund.",
                    )
                assert refund_conflict.value.code == "credit_idempotency_conflict"
                assert (await service.projection(PRIMARY_ORGANISATION_ID)).balance.available == 105
                corrected = await service.correct_balance(
                    PRIMARY_ORGANISATION_ID,
                    credits=2,
                    direction="decrease",
                    credit_type="promotional",
                    reference="case-wo049-001",
                    idempotency_key="correction-0001",
                    actor_reference="support-operator-3",
                    reason="Correct the synthetic promotional allowance.",
                )
                assert corrected.available == 103
                assert (
                    await service.correct_balance(
                        PRIMARY_ORGANISATION_ID,
                        credits=2,
                        direction="decrease",
                        credit_type="promotional",
                        reference="case-wo049-001",
                        idempotency_key="correction-0001",
                        actor_reference="support-operator-3",
                        reason="Correct the synthetic promotional allowance.",
                    )
                ).available == 103
                with pytest.raises(PublicAPIError) as correction_conflict:
                    await service.correct_balance(
                        PRIMARY_ORGANISATION_ID,
                        credits=1,
                        direction="decrease",
                        credit_type="promotional",
                        reference="case-wo049-001",
                        idempotency_key="correction-0001",
                        actor_reference="support-operator-3",
                        reason="Correct the synthetic promotional allowance.",
                    )
                assert correction_conflict.value.code == "credit_idempotency_conflict"
                assert (await service.reconcile_balance(PRIMARY_ORGANISATION_ID)).consistent is True
                purchased_lot = await session.get(CreditLot, purchased_lot_id)
                assert purchased_lot is not None and purchased_lot.expires_at is None
                assert (
                    await session.scalar(
                        select(func.count())
                        .select_from(CreditLedgerEntry)
                        .where(CreditLedgerEntry.organisation_id == PRIMARY_ORGANISATION_ID)
                    )
                    == 8
                )
                exported = await _export_payload(session, PRIMARY_ORGANISATION_ID, credit_settings())
                exported_credits = exported["credits"]
                assert isinstance(exported_credits, dict)
                assert exported_credits["balance"]["purchased_available"] == 100
                assert len(exported_credits["transactions"]) == 8
                exported_credit_text = json.dumps(exported_credits, default=str)
                assert "provider_cost_micros" not in exported_credit_text
                assert "idempotency" not in exported_credit_text
        finally:
            await engine.dispose()

    asyncio.run(scenario())


def test_exact_balance_full_and_zero_settlement_release_and_refund_guards() -> None:
    async def scenario() -> None:
        engine = create_async_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
        try:
            async with async_sessionmaker(engine, expire_on_commit=False)() as session:
                await set_tenant_database_context(session, PRIMARY_ORGANISATION_ID)
                service = await prepared_service(session)
                assert (await service.projection(PRIMARY_ORGANISATION_ID)).balance.available == 0
                await service.grant_promotional(
                    PRIMARY_ORGANISATION_ID,
                    credits=10,
                    idempotency_key="exact-balance-grant",
                    source_reference="exact-balance-grant",
                    actor_reference="support-exact-balance",
                    reason="Fund exact-balance lifecycle checks.",
                )
                zero_quote = await service.create_quote(
                    PRIMARY_ORGANISATION_ID, PRIMARY_USER_ID, action_code=TEST_ACTION_CODE, quantity=2
                )
                zero_operation = await service.reserve(
                    PRIMARY_ORGANISATION_ID,
                    PRIMARY_USER_ID,
                    quote_id=zero_quote.quote_id,
                    idempotency_key="exact-zero-reservation",
                )
                assert (await service.projection(PRIMARY_ORGANISATION_ID)).balance.available == 0
                assert zero_operation.provider_execution_authorised is True
                zero = await service.settle(
                    PRIMARY_ORGANISATION_ID,
                    zero_operation.operation_id,
                    successful_units=0,
                    provider_cost_micros=0,
                    provider_cost_currency="AUD",
                    idempotency_key="exact-zero-settlement",
                )
                assert zero.settled_credits == 0 and zero.released_credits == 10
                assert (await service.projection(PRIMARY_ORGANISATION_ID)).balance.available == 10

                full_quote = await service.create_quote(
                    PRIMARY_ORGANISATION_ID, PRIMARY_USER_ID, action_code=TEST_ACTION_CODE, quantity=2
                )
                full_operation = await service.reserve(
                    PRIMARY_ORGANISATION_ID,
                    PRIMARY_USER_ID,
                    quote_id=full_quote.quote_id,
                    idempotency_key="exact-full-reservation",
                )
                full = await service.settle(
                    PRIMARY_ORGANISATION_ID,
                    full_operation.operation_id,
                    successful_units=2,
                    provider_cost_micros=700_000,
                    provider_cost_currency="AUD",
                    idempotency_key="exact-full-settlement",
                )
                assert full.settled_credits == 10 and full.released_credits == 0
                assert (
                    await service.settle(
                        PRIMARY_ORGANISATION_ID,
                        full_operation.operation_id,
                        successful_units=2,
                        provider_cost_micros=700_000,
                        provider_cost_currency="AUD",
                        idempotency_key="exact-full-settlement",
                    )
                ) == full
                consumption = await session.scalar(
                    select(CreditLedgerEntry).where(
                        CreditLedgerEntry.organisation_id == PRIMARY_ORGANISATION_ID,
                        CreditLedgerEntry.operation_id == full_operation.operation_id,
                        CreditLedgerEntry.event_type == "consumption",
                    )
                )
                assert consumption is not None
                with pytest.raises(PublicAPIError) as excessive_refund:
                    await service.refund_consumption(
                        PRIMARY_ORGANISATION_ID,
                        consumption_entry_id=consumption.id,
                        credits=11,
                        idempotency_key="excessive-refund",
                        actor_reference="support-exact-balance",
                        reason="Reject a refund beyond original consumption.",
                    )
                assert excessive_refund.value.code == "credit_refund_exceeds_consumption"
                first_refund = await service.refund_consumption(
                    PRIMARY_ORGANISATION_ID,
                    consumption_entry_id=consumption.id,
                    credits=5,
                    idempotency_key="partial-refund",
                    actor_reference="support-exact-balance",
                    reason="Apply a bounded partial service refund.",
                )
                second_refund = await service.refund_consumption(
                    PRIMARY_ORGANISATION_ID,
                    consumption_entry_id=consumption.id,
                    credits=5,
                    idempotency_key="partial-refund",
                    actor_reference="support-exact-balance",
                    reason="Apply a bounded partial service refund.",
                )
                assert first_refund.id == second_refund.id
                with pytest.raises(PublicAPIError) as release_after_settlement:
                    await service.release(
                        PRIMARY_ORGANISATION_ID,
                        full_operation.operation_id,
                        idempotency_key="release-settled-operation",
                        reason="A settled operation must not release twice.",
                    )
                assert release_after_settlement.value.code == "credit_operation_state_invalid"

                insufficient_quote = await service.create_quote(
                    PRIMARY_ORGANISATION_ID, PRIMARY_USER_ID, action_code=TEST_ACTION_CODE, quantity=2
                )
                with pytest.raises(PublicAPIError) as insufficient:
                    await service.reserve(
                        PRIMARY_ORGANISATION_ID,
                        PRIMARY_USER_ID,
                        quote_id=insufficient_quote.quote_id,
                        idempotency_key="insufficient-reservation",
                    )
                assert insufficient.value.code == "insufficient_credits"
                release_quote = await service.create_quote(
                    PRIMARY_ORGANISATION_ID, PRIMARY_USER_ID, action_code=TEST_ACTION_CODE, quantity=1
                )
                release_operation = await service.reserve(
                    PRIMARY_ORGANISATION_ID,
                    PRIMARY_USER_ID,
                    quote_id=release_quote.quote_id,
                    idempotency_key="release-reservation",
                )
                released = await service.release(
                    PRIMARY_ORGANISATION_ID,
                    release_operation.operation_id,
                    idempotency_key="release-before-provider",
                    reason="The provider failed before executing billable work.",
                )
                retried_release = await service.release(
                    PRIMARY_ORGANISATION_ID,
                    release_operation.operation_id,
                    idempotency_key="release-before-provider",
                    reason="The provider failed before executing billable work.",
                )
                assert retried_release == released
                with pytest.raises(PublicAPIError) as release_conflict:
                    await service.release(
                        PRIMARY_ORGANISATION_ID,
                        release_operation.operation_id,
                        idempotency_key="release-before-provider",
                        reason="A different failure reason must not reuse an idempotency key.",
                    )
                assert release_conflict.value.code == "credit_idempotency_conflict"
                assert (await service.reconcile_balance(PRIMARY_ORGANISATION_ID)).consistent is True
        finally:
            await engine.dispose()

    asyncio.run(scenario())


def test_expired_and_tampered_quotes_fail_closed() -> None:
    async def scenario() -> None:
        now = [datetime.now(UTC)]
        engine = create_async_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
        try:
            async with async_sessionmaker(engine, expire_on_commit=False)() as session:
                await set_tenant_database_context(session, PRIMARY_ORGANISATION_ID)
                service = await prepared_service(session, clock=now)
                await service.grant_promotional(
                    PRIMARY_ORGANISATION_ID,
                    credits=20,
                    idempotency_key="quote-integrity-grant",
                    source_reference="quote-integrity-grant",
                    actor_reference="support-quote-integrity",
                    reason="Fund expired and tampered quote checks.",
                )
                expired = await service.create_quote(
                    PRIMARY_ORGANISATION_ID, PRIMARY_USER_ID, action_code=TEST_ACTION_CODE, quantity=1
                )
                now[0] += timedelta(seconds=601)
                with pytest.raises(PublicAPIError) as expired_error:
                    await service.reserve(
                        PRIMARY_ORGANISATION_ID,
                        PRIMARY_USER_ID,
                        quote_id=expired.quote_id,
                        idempotency_key="expired-quote-reservation",
                    )
                assert expired_error.value.code == "credit_quote_expired"
                tampered = await service.create_quote(
                    PRIMARY_ORGANISATION_ID, PRIMARY_USER_ID, action_code=TEST_ACTION_CODE, quantity=1
                )
                row = await session.get(CreditQuote, tampered.quote_id)
                assert row is not None
                row.quantity = 2
                await session.commit()
                await set_tenant_database_context(session, PRIMARY_ORGANISATION_ID)
                with pytest.raises(PublicAPIError) as tampered_error:
                    await service.reserve(
                        PRIMARY_ORGANISATION_ID,
                        PRIMARY_USER_ID,
                        quote_id=tampered.quote_id,
                        idempotency_key="tampered-quote-reservation",
                    )
                assert tampered_error.value.code == "credit_quote_tampered"
                user_bound = await service.create_quote(
                    PRIMARY_ORGANISATION_ID, PRIMARY_USER_ID, action_code=TEST_ACTION_CODE, quantity=1
                )
                with pytest.raises(PublicAPIError) as wrong_user:
                    await service.reserve(
                        PRIMARY_ORGANISATION_ID,
                        SECONDARY_USER_ID,
                        quote_id=user_bound.quote_id,
                        idempotency_key="wrong-user-quote-reservation",
                    )
                assert wrong_user.value.code == "credit_quote_not_found"
        finally:
            await engine.dispose()

    asyncio.run(scenario())


def test_expiry_trial_grant_validation_and_negative_balance_protection() -> None:
    async def scenario() -> None:
        now = [datetime(2032, 1, 1, tzinfo=UTC)]
        engine = create_async_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
        try:
            async with async_sessionmaker(engine, expire_on_commit=False)() as session:
                await set_tenant_database_context(session, PRIMARY_ORGANISATION_ID)
                service = await prepared_service(session, clock=now)
                commercial = await session.get(OrganisationCommercialState, PRIMARY_ORGANISATION_ID)
                assert commercial is not None
                commercial.status = "trial"
                commercial.billing_interval = None
                commercial.trial_started_at = now[0]
                commercial.trial_ends_at = now[0] + timedelta(days=14)
                commercial.grace_ends_at = commercial.trial_ends_at + timedelta(days=30)
                commercial.trial_used_at = now[0]
                await session.commit()
                await set_tenant_database_context(session, PRIMARY_ORGANISATION_ID)
                await grant_test_purchase(session, service, key="trial-purchased-credits")
                lot = await service.grant_promotional(
                    PRIMARY_ORGANISATION_ID,
                    credits=20,
                    idempotency_key="trial-grant-0001",
                    source_reference="one-time-trial-org-primary",
                    actor_reference="support-trial-operator",
                    reason="One-time bounded trial Credit allowance.",
                    trial_only=True,
                )
                assert lot.expires_at == commercial.trial_ends_at
                commercial.status = "active"
                await session.commit()
                await set_tenant_database_context(session, PRIMARY_ORGANISATION_ID)
                replayed_lot = await service.grant_promotional(
                    PRIMARY_ORGANISATION_ID,
                    credits=20,
                    idempotency_key="trial-grant-0001",
                    source_reference="one-time-trial-org-primary",
                    actor_reference="support-trial-operator",
                    reason="One-time bounded trial Credit allowance.",
                    trial_only=True,
                )
                assert replayed_lot.id == lot.id
                commercial.status = "trial"
                await session.commit()
                await set_tenant_database_context(session, PRIMARY_ORGANISATION_ID)
                with pytest.raises(PublicAPIError) as capped_trial_grant:
                    await service.grant_promotional(
                        PRIMARY_ORGANISATION_ID,
                        credits=501,
                        idempotency_key="trial-grant-over-cap",
                        source_reference="trial-grant-over-cap",
                        actor_reference="support-trial-operator",
                        reason="Reject a trial grant above the configured safety cap.",
                        trial_only=True,
                    )
                assert capped_trial_grant.value.code == "credit_trial_grant_cap_exceeded"
                with pytest.raises(PublicAPIError) as duplicate_trial_grant:
                    await service.grant_promotional(
                        PRIMARY_ORGANISATION_ID,
                        credits=20,
                        idempotency_key="trial-grant-0002",
                        source_reference="different-trial-source",
                        actor_reference="support-trial-operator",
                        reason="Reject a second one-time trial Credit grant.",
                        trial_only=True,
                    )
                assert duplicate_trial_grant.value.code == "credit_trial_grant_exists"
                with pytest.raises(PublicAPIError) as invalid:
                    await service.grant_promotional(
                        PRIMARY_ORGANISATION_ID,
                        credits=0,
                        idempotency_key="invalid-grant",
                        source_reference="invalid-grant",
                        actor_reference="support-trial-operator",
                        reason="Invalid synthetic grant quantity.",
                    )
                assert invalid.value.code == "credit_amount_invalid"
                with pytest.raises(PublicAPIError) as overflow:
                    await service.grant_promotional(
                        PRIMARY_ORGANISATION_ID,
                        credits=MAX_CREDITS + 1,
                        idempotency_key="overflow-grant",
                        source_reference="overflow-grant",
                        actor_reference="support-trial-operator",
                        reason="Reject an overflowing synthetic grant quantity.",
                    )
                assert overflow.value.code == "credit_amount_invalid"
                now[0] += timedelta(days=15)
                projection = await service.projection(PRIMARY_ORGANISATION_ID)
                assert projection.balance.available == 100
                assert projection.balance.purchased_available == 100
                assert projection.balance.promotional_available == 0
                assert (await service.reconcile_balance(PRIMARY_ORGANISATION_ID)).consistent is True
                history = await service.repository.recent_ledger(PRIMARY_ORGANISATION_ID)
                assert [item.event_type for item in history].count("expiry") == 1
                with pytest.raises(PublicAPIError) as correction:
                    await service.correct_balance(
                        PRIMARY_ORGANISATION_ID,
                        credits=1,
                        direction="decrease",
                        credit_type="promotional",
                        reference="negative-balance-attempt",
                        idempotency_key="negative-balance-attempt",
                        actor_reference="support-trial-operator",
                        reason="Exercise the non-negative balance invariant.",
                    )
                assert correction.value.code == "insufficient_credits"
        finally:
            await engine.dispose()

    asyncio.run(scenario())


@pytest.mark.parametrize(
    ("outcome", "successful_units"),
    [("success", 3), ("partial", 2), ("failure", 0), ("unknown", 0)],
)
def test_deterministic_metered_provider_covers_bounded_outcomes(
    outcome: str,
    successful_units: int,
) -> None:
    async def scenario() -> None:
        provider = DeterministicMeteredProvider()
        provider.arrange(  # type: ignore[arg-type]
            outcome,
            successful_units=successful_units,
            provider_cost_micros=300_000,
        )
        operation_id = uuid.uuid4()
        first = await provider.execute(
            operation_id=operation_id,
            requested_units=3,
            idempotency_key=f"deterministic-{outcome}",
        )
        retried = await provider.execute(
            operation_id=operation_id,
            requested_units=3,
            idempotency_key=f"deterministic-{outcome}",
        )
        assert retried == first
        assert first.outcome == outcome
        assert first.successful_units == successful_units
        assert provider.execution_count == 1

    asyncio.run(scenario())


def test_unknown_outcome_reconciliation_is_idempotent_and_provider_executes_once() -> None:
    async def scenario() -> None:
        engine = create_async_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
        try:
            async with async_sessionmaker(engine, expire_on_commit=False)() as session:
                await set_tenant_database_context(session, PRIMARY_ORGANISATION_ID)
                service = await prepared_service(session)
                await service.grant_promotional(
                    PRIMARY_ORGANISATION_ID,
                    credits=100,
                    idempotency_key="unknown-grant-0001",
                    source_reference="unknown-grant-source",
                    actor_reference="support-unknown-test",
                    reason="Fund the deterministic unknown-outcome scenario.",
                )
                quote = await service.create_quote(
                    PRIMARY_ORGANISATION_ID,
                    PRIMARY_USER_ID,
                    action_code=TEST_ACTION_CODE,
                    quantity=4,
                )
                reserved = await service.reserve(
                    PRIMARY_ORGANISATION_ID,
                    PRIMARY_USER_ID,
                    quote_id=quote.quote_id,
                    idempotency_key="unknown-reservation-0001",
                )
                provider = DeterministicMeteredProvider()
                provider.arrange("unknown", provider_cost_micros=700_000)
                await service.mark_executing(
                    PRIMARY_ORGANISATION_ID,
                    reserved.operation_id,
                    provider_request_id="deterministic:provider-operation-0001",
                    provider_capability=TEST_PROVIDER_CAPABILITY,
                )
                first = await provider.execute(
                    operation_id=reserved.operation_id,
                    requested_units=4,
                    idempotency_key="provider-operation-0001",
                )
                second = await provider.execute(
                    operation_id=reserved.operation_id,
                    requested_units=4,
                    idempotency_key="provider-operation-0001",
                )
                assert first == second
                assert provider.execution_count == 1
                assert first.provider_request_id == "deterministic:provider-operation-0001"
                await service.mark_unknown(PRIMARY_ORGANISATION_ID, reserved.operation_id)
                with pytest.raises(PublicAPIError) as premature:
                    await service.release(
                        PRIMARY_ORGANISATION_ID,
                        reserved.operation_id,
                        idempotency_key="premature-release",
                        reason="This release must remain blocked while the provider outcome is unknown.",
                    )
                assert premature.value.code == "credit_reconciliation_required"
                assert (await service.projection(PRIMARY_ORGANISATION_ID)).balance.reserved == 20
                reconciled = await service.reconcile_unknown(
                    PRIMARY_ORGANISATION_ID,
                    reserved.operation_id,
                    provider_definitely_executed=True,
                    successful_units=3,
                    provider_cost_micros=700_000,
                    provider_cost_currency="AUD",
                    idempotency_key="reconcile-unknown-0001",
                )
                retried = await service.reconcile_unknown(
                    PRIMARY_ORGANISATION_ID,
                    reserved.operation_id,
                    provider_definitely_executed=True,
                    successful_units=3,
                    provider_cost_micros=700_000,
                    provider_cost_currency="AUD",
                    idempotency_key="reconcile-unknown-0001",
                )
                assert retried == reconciled
                assert reconciled.outcome == "reconciled_success"
                assert reconciled.settled_credits == 15
                assert reconciled.released_credits == 5
                with pytest.raises(PublicAPIError) as conflicting_reconciliation:
                    await service.reconcile_unknown(
                        PRIMARY_ORGANISATION_ID,
                        reserved.operation_id,
                        provider_definitely_executed=False,
                        idempotency_key="conflicting-reconciliation",
                    )
                assert conflicting_reconciliation.value.code == "credit_operation_state_invalid"

                failed_quote = await service.create_quote(
                    PRIMARY_ORGANISATION_ID,
                    PRIMARY_USER_ID,
                    action_code=TEST_ACTION_CODE,
                    quantity=1,
                )
                failed_operation = await service.reserve(
                    PRIMARY_ORGANISATION_ID,
                    PRIMARY_USER_ID,
                    quote_id=failed_quote.quote_id,
                    idempotency_key="unknown-failure-reservation",
                )
                await service.mark_executing(
                    PRIMARY_ORGANISATION_ID,
                    failed_operation.operation_id,
                    provider_request_id="deterministic:provider-operation-0002",
                    provider_capability=TEST_PROVIDER_CAPABILITY,
                )
                await service.mark_unknown(PRIMARY_ORGANISATION_ID, failed_operation.operation_id)
                reconciled_failure = await service.reconcile_unknown(
                    PRIMARY_ORGANISATION_ID,
                    failed_operation.operation_id,
                    provider_definitely_executed=False,
                    idempotency_key="reconcile-unknown-failure",
                )
                retried_failure = await service.reconcile_unknown(
                    PRIMARY_ORGANISATION_ID,
                    failed_operation.operation_id,
                    provider_definitely_executed=False,
                    idempotency_key="reconcile-unknown-failure",
                )
                assert retried_failure == reconciled_failure
                assert reconciled_failure.outcome == "reconciled_failure"
                assert reconciled_failure.settled_credits == 0
                assert reconciled_failure.released_credits == 5
                assert (await service.reconcile_balance(PRIMARY_ORGANISATION_ID)).consistent is True
        finally:
            await engine.dispose()

    asyncio.run(scenario())


def test_quotes_are_server_owned_versioned_and_caps_kill_switch_and_rate_limit_fail_closed() -> None:
    async def scenario() -> None:
        engine = create_async_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
        try:
            async with async_sessionmaker(engine, expire_on_commit=False)() as session:
                await set_tenant_database_context(session, PRIMARY_ORGANISATION_ID)
                service = await prepared_service(session, max_per_operation=30, rate_limit=1)
                await service.grant_promotional(
                    PRIMARY_ORGANISATION_ID,
                    credits=100,
                    idempotency_key="quote-grant-0001",
                    source_reference="quote-grant-source",
                    actor_reference="support-quote-test",
                    reason="Fund deterministic quote and cap scenarios.",
                )
                quote_v1 = await service.create_quote(
                    PRIMARY_ORGANISATION_ID,
                    PRIMARY_USER_ID,
                    action_code=TEST_ACTION_CODE,
                    quantity=2,
                )
                price_v2 = await service.create_action_price_version(
                    action_code=TEST_ACTION_CODE,
                    display_name="Research this company",
                    required_module_code="prospect",
                    version=2,
                    credit_charge_per_unit=6,
                    customer_charge_basis="successful_unit",
                    max_units_per_operation=40,
                    customer_revenue_micros_per_unit=1_200_000,
                    cost_basis="successful_unit",
                    provider_cost_minor_units=20,
                    provider_currency="USD",
                    provider_minor_units_per_major=100,
                    fx_rate_to_aud=Decimal("1.50000000"),
                    fx_source="deterministic test assumption",
                    fx_observed_at=datetime.now(UTC),
                    other_variable_cost_micros=50_000,
                    expected_variable_cost_micros_per_unit=350_000,
                    maximum_variable_cost_micros_per_unit=400_000,
                    status="test_active",
                    pricing_note="TEST ONLY / NOT CUSTOMER PRICING — V2",
                    actor_reference="wo-049-test-pricing",
                )
                quote_v2 = await service.create_quote(
                    PRIMARY_ORGANISATION_ID,
                    PRIMARY_USER_ID,
                    action_code=TEST_ACTION_CODE,
                    quantity=2,
                )
                assert quote_v1.action_price_version_id != price_v2.id
                assert quote_v1.maximum_credit_cost == 10
                assert quote_v2.action_price_version_id == price_v2.id
                assert quote_v2.maximum_credit_cost == 12
                reserved_v1 = await service.reserve(
                    PRIMARY_ORGANISATION_ID,
                    PRIMARY_USER_ID,
                    quote_id=quote_v1.quote_id,
                    idempotency_key="honour-v1-quote",
                )
                assert reserved_v1.reserved_credits == 10
                with pytest.raises(PublicAPIError) as limited:
                    await service.reserve(
                        PRIMARY_ORGANISATION_ID,
                        PRIMARY_USER_ID,
                        quote_id=quote_v2.quote_id,
                        idempotency_key="rate-limited-v2",
                    )
                assert limited.value.code == "credit_rate_limit_exceeded"
                await service.set_execution_control(
                    scope="action",
                    key=TEST_ACTION_CODE,
                    enabled=False,
                    actor_reference="emergency-operator",
                    reason="Exercise deterministic emergency disablement.",
                )
                with pytest.raises(PublicAPIError) as disabled:
                    await service.mark_executing(
                        PRIMARY_ORGANISATION_ID,
                        reserved_v1.operation_id,
                        provider_request_id="must-not-execute",
                        provider_capability=TEST_PROVIDER_CAPABILITY,
                    )
                assert disabled.value.code == "credit_action_disabled"
                released = await service.release(
                    PRIMARY_ORGANISATION_ID,
                    reserved_v1.operation_id,
                    idempotency_key="release-after-disable",
                    reason="Emergency disablement permits safe release of reserved work.",
                )
                assert released.status == "released"
                await service.set_execution_control(
                    scope="action",
                    key=TEST_ACTION_CODE,
                    enabled=True,
                    actor_reference="emergency-operator",
                    reason="Restore the deterministic action for remaining control tests.",
                )
                await set_tenant_database_context(session, PRIMARY_ORGANISATION_ID)
                await service.configure_policy(
                    PRIMARY_ORGANISATION_ID,
                    metered_actions_enabled=True,
                    max_credits_per_operation=30,
                    max_credits_per_day=10_000,
                    max_provider_cost_micros_per_day=100_000_000,
                    trial_max_credits_per_day=500,
                    max_operations_per_minute=10,
                    actor_reference="wo-049-test-support",
                    reason="Permit the remaining deterministic circuit-breaker checks.",
                )
                provider_quote = await service.create_quote(
                    PRIMARY_ORGANISATION_ID,
                    PRIMARY_USER_ID,
                    action_code=TEST_ACTION_CODE,
                    quantity=1,
                )
                provider_operation = await service.reserve(
                    PRIMARY_ORGANISATION_ID,
                    PRIMARY_USER_ID,
                    quote_id=provider_quote.quote_id,
                    idempotency_key="provider-control-reservation",
                )
                await service.configure_policy(
                    PRIMARY_ORGANISATION_ID,
                    metered_actions_enabled=False,
                    max_credits_per_operation=30,
                    max_credits_per_day=10_000,
                    max_provider_cost_micros_per_day=100_000_000,
                    trial_max_credits_per_day=500,
                    max_operations_per_minute=10,
                    actor_reference="wo-049-test-support",
                    reason="Exercise execution-time organisation policy revocation.",
                )
                with pytest.raises(PublicAPIError) as policy_disabled:
                    await service.mark_executing(
                        PRIMARY_ORGANISATION_ID,
                        provider_operation.operation_id,
                        provider_request_id="organisation-policy-blocked",
                        provider_capability=TEST_PROVIDER_CAPABILITY,
                    )
                assert policy_disabled.value.code == "credit_exposure_policy_unavailable"
                await service.configure_policy(
                    PRIMARY_ORGANISATION_ID,
                    metered_actions_enabled=True,
                    max_credits_per_operation=30,
                    max_credits_per_day=10_000,
                    max_provider_cost_micros_per_day=100_000_000,
                    trial_max_credits_per_day=500,
                    max_operations_per_minute=10,
                    actor_reference="wo-049-test-support",
                    reason="Restore the organisation policy for provider-capability checks.",
                )
                await service.set_execution_control(
                    scope="provider_capability",
                    key=TEST_PROVIDER_CAPABILITY,
                    enabled=False,
                    actor_reference="emergency-operator",
                    reason="Exercise deterministic provider-capability disablement.",
                )
                with pytest.raises(PublicAPIError) as provider_disabled:
                    await service.mark_executing(
                        PRIMARY_ORGANISATION_ID,
                        provider_operation.operation_id,
                        provider_request_id="provider-capability-blocked",
                        provider_capability=TEST_PROVIDER_CAPABILITY,
                    )
                assert provider_disabled.value.code == "credit_provider_capability_disabled"
                await service.set_execution_control(
                    scope="provider_capability",
                    key=TEST_PROVIDER_CAPABILITY,
                    enabled=True,
                    actor_reference="emergency-operator",
                    reason="Restore deterministic provider execution before the global check.",
                )
                await service.mark_executing(
                    PRIMARY_ORGANISATION_ID,
                    provider_operation.operation_id,
                    provider_request_id="provider-capability-restored",
                    provider_capability=TEST_PROVIDER_CAPABILITY,
                )
                await service.set_execution_control(
                    scope="global",
                    key="metered_actions",
                    enabled=False,
                    actor_reference="emergency-operator",
                    reason="Exercise global emergency disablement after provider execution.",
                )
                settled_after_disable = await service.settle(
                    PRIMARY_ORGANISATION_ID,
                    provider_operation.operation_id,
                    successful_units=1,
                    provider_cost_micros=300_000,
                    provider_cost_currency="AUD",
                    idempotency_key="settlement-after-global-disable",
                )
                assert settled_after_disable.status == "settled"
                with pytest.raises(PublicAPIError) as globally_disabled:
                    await service.create_quote(
                        PRIMARY_ORGANISATION_ID,
                        PRIMARY_USER_ID,
                        action_code=TEST_ACTION_CODE,
                        quantity=1,
                    )
                assert globally_disabled.value.code == "credit_action_disabled"
                assert (await service.reconcile_balance(PRIMARY_ORGANISATION_ID)).consistent is True
        finally:
            await engine.dispose()

    asyncio.run(scenario())


@pytest.mark.parametrize(
    ("cap", "expected_code"),
    [
        ("operation", "credit_operation_cap_exceeded"),
        ("daily", "credit_daily_cap_exceeded"),
        ("provider", "credit_provider_cost_cap_exceeded"),
        ("trial", "credit_trial_cap_exceeded"),
    ],
)
def test_each_exposure_cap_blocks_reservation_before_provider_execution(cap: str, expected_code: str) -> None:
    async def scenario() -> None:
        engine = create_async_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
        try:
            async with async_sessionmaker(engine, expire_on_commit=False)() as session:
                await set_tenant_database_context(session, PRIMARY_ORGANISATION_ID)
                service = await prepared_service(session)
                commercial = await session.get(OrganisationCommercialState, PRIMARY_ORGANISATION_ID)
                assert commercial is not None
                if cap == "trial":
                    trial_started_at = datetime.now(UTC)
                    commercial.status = "trial"
                    commercial.billing_interval = None
                    commercial.trial_started_at = trial_started_at
                    commercial.trial_ends_at = trial_started_at + timedelta(days=14)
                    commercial.grace_ends_at = trial_started_at + timedelta(days=44)
                    commercial.trial_used_at = trial_started_at
                await session.commit()
                await set_tenant_database_context(session, PRIMARY_ORGANISATION_ID)
                await service.configure_policy(
                    PRIMARY_ORGANISATION_ID,
                    metered_actions_enabled=True,
                    max_credits_per_operation=4 if cap == "operation" else 100,
                    max_credits_per_day=4 if cap == "daily" else 1_000,
                    max_provider_cost_micros_per_day=399_999 if cap == "provider" else 100_000_000,
                    trial_max_credits_per_day=4 if cap == "trial" else 100,
                    max_operations_per_minute=100,
                    actor_reference="wo-049-cap-test",
                    reason="Configure one deterministic fail-closed exposure cap.",
                )
                await service.grant_promotional(
                    PRIMARY_ORGANISATION_ID,
                    credits=100,
                    idempotency_key=f"{cap}-cap-grant",
                    source_reference=f"{cap}-cap-grant",
                    actor_reference="wo-049-cap-test",
                    reason="Fund the deterministic exposure-cap check.",
                )
                quote = await service.create_quote(
                    PRIMARY_ORGANISATION_ID, PRIMARY_USER_ID, action_code=TEST_ACTION_CODE, quantity=1
                )
                with pytest.raises(PublicAPIError) as blocked:
                    await service.reserve(
                        PRIMARY_ORGANISATION_ID,
                        PRIMARY_USER_ID,
                        quote_id=quote.quote_id,
                        idempotency_key=f"{cap}-cap-reservation",
                    )
                assert blocked.value.code == expected_code
                assert (await service.projection(PRIMARY_ORGANISATION_ID)).balance.available == 100
                assert (await service.projection(PRIMARY_ORGANISATION_ID)).balance.reserved == 0
        finally:
            await engine.dispose()

    asyncio.run(scenario())


@pytest.mark.parametrize(
    ("cap", "expected_code"),
    [
        ("daily", "credit_daily_cap_exceeded"),
        ("provider", "credit_provider_cost_cap_exceeded"),
        ("trial", "credit_trial_cap_exceeded"),
    ],
)
def test_in_flight_reservations_count_towards_daily_exposure_caps(cap: str, expected_code: str) -> None:
    async def scenario() -> None:
        engine = create_async_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
        try:
            async with async_sessionmaker(engine, expire_on_commit=False)() as session:
                await set_tenant_database_context(session, PRIMARY_ORGANISATION_ID)
                service = await prepared_service(session)
                commercial = await session.get(OrganisationCommercialState, PRIMARY_ORGANISATION_ID)
                assert commercial is not None
                if cap == "trial":
                    trial_started_at = datetime.now(UTC)
                    commercial.status = "trial"
                    commercial.billing_interval = None
                    commercial.trial_started_at = trial_started_at
                    commercial.trial_ends_at = trial_started_at + timedelta(days=14)
                    commercial.grace_ends_at = trial_started_at + timedelta(days=44)
                    commercial.trial_used_at = trial_started_at
                await session.commit()
                await set_tenant_database_context(session, PRIMARY_ORGANISATION_ID)
                await service.configure_policy(
                    PRIMARY_ORGANISATION_ID,
                    metered_actions_enabled=True,
                    max_credits_per_operation=100,
                    max_credits_per_day=9 if cap == "daily" else 1_000,
                    max_provider_cost_micros_per_day=799_999 if cap == "provider" else 100_000_000,
                    trial_max_credits_per_day=9 if cap == "trial" else 100,
                    max_operations_per_minute=100,
                    actor_reference="wo-049-active-exposure-test",
                    reason="Count in-flight work towards bounded daily exposure.",
                )
                await service.grant_promotional(
                    PRIMARY_ORGANISATION_ID,
                    credits=100,
                    idempotency_key=f"{cap}-active-exposure-grant",
                    source_reference=f"{cap}-active-exposure-grant",
                    actor_reference="wo-049-active-exposure-test",
                    reason="Fund two exposure-controlled reservations.",
                )
                first_quote = await service.create_quote(
                    PRIMARY_ORGANISATION_ID, PRIMARY_USER_ID, action_code=TEST_ACTION_CODE, quantity=1
                )
                second_quote = await service.create_quote(
                    PRIMARY_ORGANISATION_ID, PRIMARY_USER_ID, action_code=TEST_ACTION_CODE, quantity=1
                )
                await service.reserve(
                    PRIMARY_ORGANISATION_ID,
                    PRIMARY_USER_ID,
                    quote_id=first_quote.quote_id,
                    idempotency_key=f"{cap}-active-exposure-first",
                )
                with pytest.raises(PublicAPIError) as blocked:
                    await service.reserve(
                        PRIMARY_ORGANISATION_ID,
                        PRIMARY_USER_ID,
                        quote_id=second_quote.quote_id,
                        idempotency_key=f"{cap}-active-exposure-second",
                    )
                assert blocked.value.code == expected_code
                projection = await service.projection(PRIMARY_ORGANISATION_ID)
                assert projection.balance.available == 95
                assert projection.balance.reserved == 5
        finally:
            await engine.dispose()

    asyncio.run(scenario())


def test_action_price_charge_basis_controls_partial_settlement_policy() -> None:
    async def scenario() -> None:
        engine = create_async_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
        try:
            async with async_sessionmaker(engine, expire_on_commit=False)() as session:
                await set_tenant_database_context(session, PRIMARY_ORGANISATION_ID)
                service = await prepared_service(session)
                await service.create_action_price_version(
                    action_code=TEST_ACTION_CODE,
                    display_name="Research this company",
                    required_module_code="prospect",
                    version=2,
                    credit_charge_per_unit=5,
                    customer_charge_basis="requested_unit",
                    max_units_per_operation=40,
                    customer_revenue_micros_per_unit=1_000_000,
                    cost_basis="successful_unit",
                    provider_cost_minor_units=20,
                    provider_currency="USD",
                    provider_minor_units_per_major=100,
                    fx_rate_to_aud=Decimal("1.50000000"),
                    fx_source="deterministic test assumption",
                    fx_observed_at=datetime.now(UTC),
                    other_variable_cost_micros=50_000,
                    expected_variable_cost_micros_per_unit=350_000,
                    maximum_variable_cost_micros_per_unit=400_000,
                    status="test_active",
                    pricing_note="TEST ONLY / NOT CUSTOMER PRICING — requested-unit policy",
                    actor_reference="wo-049-charge-basis-test",
                )
                await service.grant_promotional(
                    PRIMARY_ORGANISATION_ID,
                    credits=15,
                    idempotency_key="charge-basis-grant",
                    source_reference="charge-basis-grant",
                    actor_reference="wo-049-charge-basis-test",
                    reason="Fund an explicitly versioned requested-unit charge policy.",
                )
                quote = await service.create_quote(
                    PRIMARY_ORGANISATION_ID,
                    PRIMARY_USER_ID,
                    action_code=TEST_ACTION_CODE,
                    quantity=3,
                )
                operation = await service.reserve(
                    PRIMARY_ORGANISATION_ID,
                    PRIMARY_USER_ID,
                    quote_id=quote.quote_id,
                    idempotency_key="charge-basis-reservation",
                )
                settled = await service.settle(
                    PRIMARY_ORGANISATION_ID,
                    operation.operation_id,
                    successful_units=1,
                    provider_cost_micros=300_000,
                    provider_cost_currency="AUD",
                    idempotency_key="charge-basis-settlement",
                )
                assert settled.outcome == "partial"
                assert settled.settled_credits == 15
                assert settled.released_credits == 0
                assert (await service.projection(PRIMARY_ORGANISATION_ID)).balance.available == 0
        finally:
            await engine.dispose()

    asyncio.run(scenario())


@pytest.mark.parametrize(
    ("revenue", "cost", "floor", "margin", "eligible"),
    [
        (1_000_000, 400_000, 5_000, 6_000, True),
        (1_000_000, 500_000, 5_000, 5_000, True),
        (1_000_000, 600_000, 5_000, 4_000, False),
        (1_000_000, 1_000_000, 1, 0, False),
        (1_000_000, 1_100_000, 1, -1_000, False),
    ],
)
def test_exact_margin_math_distinguishes_margin_from_markup(
    revenue: int, cost: int, floor: int, margin: int, eligible: bool
) -> None:
    result = CreditService.validate_margin(revenue, cost, floor)
    assert result.gross_margin_basis_points == margin
    assert result.production_eligible is eligible


def test_exact_money_and_purchased_revenue_attribution_use_integer_micros() -> None:
    async def scenario() -> None:
        engine = create_async_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
        try:
            async with async_sessionmaker(engine, expire_on_commit=False)() as session:
                await set_tenant_database_context(session, PRIMARY_ORGANISATION_ID)
                service = await prepared_service(session)
                purchased_lot_id = await grant_test_purchase(session, service, key="money-attribution")
                quote = await service.create_quote(
                    PRIMARY_ORGANISATION_ID, PRIMARY_USER_ID, action_code=TEST_ACTION_CODE, quantity=1
                )
                reserved = await service.reserve(
                    PRIMARY_ORGANISATION_ID,
                    PRIMARY_USER_ID,
                    quote_id=quote.quote_id,
                    idempotency_key="money-attribution-reservation",
                )
                await service.settle(
                    PRIMARY_ORGANISATION_ID,
                    reserved.operation_id,
                    successful_units=1,
                    provider_cost_micros=350_000,
                    provider_cost_currency="AUD",
                    idempotency_key="money-attribution-settlement",
                )
                lot = await session.get(CreditLot, purchased_lot_id)
                operation = await session.get(CreditOperation, reserved.operation_id)
                price = await session.get(CreditActionPriceVersion, quote.action_price_version_id)
                assert lot is not None and operation is not None and price is not None
                assert lot.original_revenue_micros == 20_000_000
                assert lot.remaining_revenue_micros == 19_000_000
                assert operation.customer_revenue_micros == 1_000_000
                assert operation.provider_cost_micros == 350_000
                assert price.provider_cost_minor_units == 20
                assert price.provider_currency == "USD"
                assert price.fx_rate_to_aud == Decimal("1.50000000")
                assert price.expected_variable_cost_micros_per_unit == 350_000
                assert price.maximum_variable_cost_micros_per_unit == 400_000
        finally:
            await engine.dispose()

    asyncio.run(scenario())


def test_production_action_price_requires_owner_approved_margin_policy() -> None:
    async def scenario() -> None:
        engine = create_async_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
        try:
            async with async_sessionmaker(engine, expire_on_commit=False)() as session:
                settings = credit_settings().model_copy(
                    update={
                        "environment": "production",
                        "feature_credits_enabled": False,
                        "credits_margin_floor_basis_points": None,
                        "credits_margin_policy_reference": None,
                    }
                )
                service = CreditService(session, settings)
                with pytest.raises(PublicAPIError) as unapproved:
                    await service.create_action_price_version(
                        action_code="UNAPPROVED_PRODUCTION_ACTION",
                        display_name="Unapproved production action",
                        required_module_code="prospect",
                        version=1,
                        credit_charge_per_unit=5,
                        customer_charge_basis="successful_unit",
                        max_units_per_operation=1,
                        customer_revenue_micros_per_unit=1_000_000,
                        cost_basis="successful_unit",
                        provider_cost_minor_units=10,
                        provider_currency="USD",
                        provider_minor_units_per_major=100,
                        fx_rate_to_aud=Decimal("1.50000000"),
                        fx_source="synthetic production-rejection test",
                        fx_observed_at=datetime.now(UTC),
                        other_variable_cost_micros=10_000,
                        expected_variable_cost_micros_per_unit=160_000,
                        maximum_variable_cost_micros_per_unit=200_000,
                        status="production_active",
                        pricing_note="Reject without explicit owner margin approval.",
                        actor_reference="wo-049-production-rejection-test",
                    )
                assert unapproved.value.code == "credit_production_price_not_approved"
                test_service = CreditService(session, credit_settings())
                with pytest.raises(PublicAPIError) as understated_cost:
                    await test_service.create_action_price_version(
                        action_code="UNDERSTATED_TEST_COST",
                        display_name="Understated test cost",
                        required_module_code="prospect",
                        version=1,
                        credit_charge_per_unit=5,
                        customer_charge_basis="successful_unit",
                        max_units_per_operation=1,
                        customer_revenue_micros_per_unit=1_000_000,
                        cost_basis="successful_unit",
                        provider_cost_minor_units=20,
                        provider_currency="USD",
                        provider_minor_units_per_major=100,
                        fx_rate_to_aud=Decimal("1.50000000"),
                        fx_source="synthetic cost-consistency test",
                        fx_observed_at=datetime.now(UTC),
                        other_variable_cost_micros=50_000,
                        expected_variable_cost_micros_per_unit=349_999,
                        maximum_variable_cost_micros_per_unit=400_000,
                        status="test_active",
                        pricing_note="Reject inconsistent TEST-only provider-cost assumptions.",
                        actor_reference="wo-049-cost-consistency-test",
                    )
                assert understated_cost.value.code == "credit_action_price_invalid"
                scaled_price = await test_service.create_action_price_version(
                    action_code="SCALED_PROVIDER_COST_TEST",
                    display_name="Scaled provider cost test",
                    required_module_code="prospect",
                    version=1,
                    credit_charge_per_unit=5,
                    customer_charge_basis="successful_unit",
                    max_units_per_operation=1,
                    customer_revenue_micros_per_unit=2_000_000,
                    cost_basis="successful_unit",
                    provider_cost_minor_units=2,
                    provider_currency="JPY",
                    provider_minor_units_per_major=1,
                    fx_rate_to_aud=Decimal("0.50000000"),
                    fx_source="synthetic non-decimal-scale test",
                    fx_observed_at=datetime.now(UTC),
                    other_variable_cost_micros=100_000,
                    expected_variable_cost_micros_per_unit=1_100_000,
                    maximum_variable_cost_micros_per_unit=1_200_000,
                    status="test_active",
                    pricing_note="TEST ONLY / NOT CUSTOMER PRICING — exact minor-unit scale.",
                    actor_reference="wo-049-cost-scale-test",
                )
                assert scaled_price.provider_minor_units_per_major == 1
        finally:
            await engine.dispose()

    asyncio.run(scenario())


def _signed_credit_event(
    *,
    event_id: str,
    organisation_id: UUID,
    customer_id: str,
    checkout_id: str,
    amount_minor: int,
    currency: str = "AUD",
    pack_id: UUID = TEST_PACK_ID,
    payment_status: str = "paid",
) -> tuple[bytes, str]:
    payload = json.dumps(
        {
            "id": event_id,
            "type": "checkout.session.completed",
            "organisation_id": str(organisation_id),
            "customer_id": customer_id,
            "object_id": checkout_id,
            "created": int(datetime.now(UTC).timestamp()),
            "amount_minor_units": amount_minor,
            "currency": currency,
            "credit_pack_version_id": str(pack_id),
            "payment_status": payment_status,
        },
        separators=(",", ":"),
    ).encode()
    signature = hmac.new(WEBHOOK_SECRET.encode(), payload, hashlib.sha256).hexdigest()
    return payload, f"sha256={signature}"


def test_verified_billing_payment_is_the_only_purchase_grant_authority() -> None:
    async def scenario() -> None:
        settings = credit_settings()
        provider = DeterministicBillingProvider(settings)
        engine = create_async_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
        try:
            async with async_sessionmaker(engine, expire_on_commit=False)() as session:
                await set_tenant_database_context(session, PRIMARY_ORGANISATION_ID)
                credits = CreditService(session, settings)
                await credits.ensure_test_catalogue()
                await session.commit()
                await set_tenant_database_context(session, PRIMARY_ORGANISATION_ID)
                pack = await session.get(CreditPackVersion, TEST_PACK_ID)
                assert pack is not None
                customer_id = "cus_test_credit_purchase"
                checkout_id = "cs_test_credit_purchase"
                session.add(
                    BillingAccount(
                        id=uuid.uuid4(),
                        organisation_id=PRIMARY_ORGANISATION_ID,
                        provider="deterministic",
                        provider_mode="test",
                        provider_customer_id=customer_id,
                        status="active",
                    )
                )
                operation = BillingOperation(
                    id=uuid.uuid4(),
                    organisation_id=PRIMARY_ORGANISATION_ID,
                    requested_by_user_id=PRIMARY_USER_ID,
                    operation_type="credit_purchase",
                    idempotency_key="credit-checkout-0001",
                    request_fingerprint="b" * 64,
                    status="pending",
                    credit_pack_version_id=pack.id,
                    amount=Decimal("20.00"),
                    currency="AUD",
                    provider_object_id=checkout_id,
                )
                session.add(operation)
                await session.commit()
                await set_tenant_database_context(session, PRIMARY_ORGANISATION_ID)
                provider.checkouts[checkout_id] = ProviderCheckout(
                    identifier=checkout_id,
                    customer_identifier=customer_id,
                    subscription_identifier=None,
                    hosted_url=f"https://checkout.stripe.test/pay/{checkout_id}",
                    status="complete",
                    payment_status="paid",
                )
                with pytest.raises(PublicAPIError) as pending_payment:
                    await credits.grant_verified_purchase(
                        PRIMARY_ORGANISATION_ID,
                        billing_operation_id=operation.id,
                        provider_event_id="unverified-payment",
                    )
                assert pending_payment.value.code == "credit_purchase_unverified"
                operation.status = "failed"
                await session.commit()
                await set_tenant_database_context(session, PRIMARY_ORGANISATION_ID)
                with pytest.raises(PublicAPIError) as failed_payment:
                    await credits.grant_verified_purchase(
                        PRIMARY_ORGANISATION_ID,
                        billing_operation_id=operation.id,
                        provider_event_id="failed-payment",
                    )
                assert failed_payment.value.code == "credit_purchase_unverified"
                operation.status = "pending"
                await session.commit()
                await set_tenant_database_context(session, PRIMARY_ORGANISATION_ID)
                assert (await credits.projection(PRIMARY_ORGANISATION_ID)).balance.available == 0
                billing = BillingService(session, settings, provider)
                pending_payload, pending_signature = _signed_credit_event(
                    event_id="evt_credit_payment_pending",
                    organisation_id=PRIMARY_ORGANISATION_ID,
                    customer_id=customer_id,
                    checkout_id=checkout_id,
                    amount_minor=2_000,
                    payment_status="unpaid",
                )
                assert await billing.process_webhook(pending_payload, pending_signature) == "reconciliation_required"
                assert (await credits.projection(PRIMARY_ORGANISATION_ID)).balance.available == 0
                mismatches = (
                    ("evt_credit_bad_amount", PRIMARY_ORGANISATION_ID, 1_999, "AUD", TEST_PACK_ID),
                    ("evt_credit_bad_currency", PRIMARY_ORGANISATION_ID, 2_000, "USD", TEST_PACK_ID),
                    ("evt_credit_bad_pack", PRIMARY_ORGANISATION_ID, 2_000, "AUD", uuid.uuid4()),
                    ("evt_credit_bad_organisation", SECONDARY_ORGANISATION_ID, 2_000, "AUD", TEST_PACK_ID),
                )
                for event_id, event_organisation_id, amount_minor, currency, pack_id in mismatches:
                    bad_payload, bad_signature = _signed_credit_event(
                        event_id=event_id,
                        organisation_id=event_organisation_id,
                        customer_id=customer_id,
                        checkout_id=checkout_id,
                        amount_minor=amount_minor,
                        currency=currency,
                        pack_id=pack_id,
                    )
                    with pytest.raises(PublicAPIError):
                        await billing.process_webhook(bad_payload, bad_signature)
                assert (await credits.projection(PRIMARY_ORGANISATION_ID)).balance.available == 0
                payload, signature = _signed_credit_event(
                    event_id="evt_credit_paid_0001",
                    organisation_id=PRIMARY_ORGANISATION_ID,
                    customer_id=customer_id,
                    checkout_id=checkout_id,
                    amount_minor=2_000,
                )
                assert await billing.process_webhook(payload, signature) == "processed"
                assert await billing.process_webhook(payload, signature) == "duplicate"
                repeated_fact, repeated_signature = _signed_credit_event(
                    event_id="evt_credit_paid_reconciliation",
                    organisation_id=PRIMARY_ORGANISATION_ID,
                    customer_id=customer_id,
                    checkout_id=checkout_id,
                    amount_minor=2_000,
                )
                assert await billing.process_webhook(repeated_fact, repeated_signature) == "processed"
                assert (await credits.projection(PRIMARY_ORGANISATION_ID)).balance.available == 100
                assert (
                    await session.scalar(
                        select(func.count())
                        .select_from(CreditLedgerEntry)
                        .where(
                            CreditLedgerEntry.organisation_id == PRIMARY_ORGANISATION_ID,
                            CreditLedgerEntry.event_type == "purchase",
                        )
                    )
                    == 1
                )
        finally:
            await engine.dispose()

    asyncio.run(scenario())


def test_reconciliation_detects_reserved_credit_type_projection_swap() -> None:
    async def scenario() -> None:
        engine = create_async_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
        try:
            async with async_sessionmaker(engine, expire_on_commit=False)() as session:
                await set_tenant_database_context(session, PRIMARY_ORGANISATION_ID)
                service = await prepared_service(session)
                await grant_test_purchase(session, service, key="reconciliation-buckets")
                await service.grant_promotional(
                    PRIMARY_ORGANISATION_ID,
                    credits=10,
                    idempotency_key="reconciliation-buckets-promo",
                    source_reference="reconciliation-buckets-promo",
                    actor_reference="wo-049-reconciliation-test",
                    reason="Fund per-type reconciliation coverage.",
                )
                quote = await service.create_quote(
                    PRIMARY_ORGANISATION_ID, PRIMARY_USER_ID, action_code=TEST_ACTION_CODE, quantity=3
                )
                await service.reserve(
                    PRIMARY_ORGANISATION_ID,
                    PRIMARY_USER_ID,
                    quote_id=quote.quote_id,
                    idempotency_key="reconciliation-buckets-reservation",
                )
                balance = await session.get(OrganisationCreditBalance, PRIMARY_ORGANISATION_ID)
                assert balance is not None
                balance.purchased_reserved = 10
                balance.promotional_reserved = 5
                await session.commit()
                await set_tenant_database_context(session, PRIMARY_ORGANISATION_ID)
                reconciliation = await service.reconcile_balance(PRIMARY_ORGANISATION_ID)
                assert reconciliation.projection_reserved == reconciliation.ledger_reserved == 15
                assert reconciliation.projection_purchased_reserved == 10
                assert reconciliation.ledger_purchased_reserved == 5
                assert reconciliation.consistent is False
        finally:
            await engine.dispose()

    asyncio.run(scenario())


def test_credit_api_is_admin_safe_and_rejects_client_owned_economics() -> None:
    settings = credit_settings()
    app = create_app(settings)
    with TestClient(app) as client:
        projection = client.get("/api/v1/credits")
        assert projection.status_code == 200
        assert projection.json()["productionPricesAvailable"] is False
        assert projection.json()["autoTopUp"] is False
        forged = client.post(
            "/api/v1/credits/quotes",
            json={
                "actionCode": TEST_ACTION_CODE,
                "quantity": 1,
                "balance": 999_999,
                "creditCost": 1,
                "providerCost": 0,
            },
        )
        assert forged.status_code == 422

    app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(
        user_id=PRIMARY_USER_ID,
        external_auth_id="member-credit-test",
        display_name="Member",
        email="member@example.test",
        organisation_id=PRIMARY_ORGANISATION_ID,
        organisation_name="Example Revenue Team",
        organisation_slug="example-revenue-team",
        role="member",
        auth_mode="mock",
    )
    with TestClient(app) as client:
        denied = client.get("/api/v1/credits")
        assert denied.status_code == 403
    app.dependency_overrides.clear()


def test_cross_tenant_credit_operations_fail_closed() -> None:
    async def scenario() -> None:
        engine = create_async_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
        try:
            async with async_sessionmaker(engine, expire_on_commit=False)() as session:
                await set_tenant_database_context(session, PRIMARY_ORGANISATION_ID)
                service = await prepared_service(session)
                await service.grant_promotional(
                    PRIMARY_ORGANISATION_ID,
                    credits=10,
                    idempotency_key="tenant-grant-0001",
                    source_reference="tenant-grant-source",
                    actor_reference="support-tenant-test",
                    reason="Fund cross-tenant denial test.",
                )
                quote = await service.create_quote(
                    PRIMARY_ORGANISATION_ID,
                    PRIMARY_USER_ID,
                    action_code=TEST_ACTION_CODE,
                    quantity=1,
                )
                operation = await service.reserve(
                    PRIMARY_ORGANISATION_ID,
                    PRIMARY_USER_ID,
                    quote_id=quote.quote_id,
                    idempotency_key="tenant-reservation-0001",
                )
                await set_tenant_database_context(session, SECONDARY_ORGANISATION_ID)
                with pytest.raises(PublicAPIError) as cross_tenant:
                    await service.release(
                        SECONDARY_ORGANISATION_ID,
                        operation.operation_id,
                        idempotency_key="cross-tenant-release",
                        reason="Attempt a forbidden cross-tenant release.",
                    )
                assert cross_tenant.value.code == "credit_operation_not_found"
                assert await service.repository.recent_ledger(SECONDARY_ORGANISATION_ID) == []
        finally:
            await engine.dispose()

    asyncio.run(scenario())


def test_offboarding_fails_closed_when_credit_transaction_history_exists() -> None:
    async def scenario() -> None:
        engine = create_async_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
        factory = async_sessionmaker(engine, expire_on_commit=False)
        request_id = uuid.uuid4()
        try:
            async with factory() as session:
                await set_tenant_database_context(session, PRIMARY_ORGANISATION_ID)
                service = await prepared_service(session)
                await service.grant_promotional(
                    PRIMARY_ORGANISATION_ID,
                    credits=10,
                    idempotency_key="retained-credit-history",
                    source_reference="retained-credit-history",
                    actor_reference="support-retention-test",
                    reason="Create synthetic Credit history for offboarding.",
                )
                session.add(
                    BetaDataRequest(
                        id=request_id,
                        organisation_id=PRIMARY_ORGANISATION_ID,
                        requested_by_user_id=PRIMARY_USER_ID,
                        request_type="organisation_deletion",
                        status="pending",
                        confirmed_at=datetime.now(UTC),
                    )
                )
                await session.commit()
            with pytest.raises(RuntimeError, match="Credit transaction history"):
                await delete_organisation(factory, credit_settings(), PRIMARY_ORGANISATION_ID, request_id)
            async with factory() as session:
                assert await session.get(Organisation, PRIMARY_ORGANISATION_ID) is not None
                request = await session.get(BetaDataRequest, request_id)
                assert request is not None
                assert request.status == "failed"
                assert request.failure_code == "organisation_deletion_failed"
        finally:
            await engine.dispose()

    asyncio.run(scenario())
