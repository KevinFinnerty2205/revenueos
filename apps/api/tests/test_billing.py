from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import time
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from revenueos.auth import AuthenticatedUser, get_current_user
from revenueos.beta_maintenance import EXPORT_VERSION, _delete_organisation_records, _export_payload
from revenueos.billing_contracts import BillingOperationRequest, CheckoutCreateRequest, PlanChangeRequest
from revenueos.billing_provider import (
    DeterministicBillingProvider,
    ProviderCheckout,
    ProviderInvoiceSnapshot,
    ProviderPlanChangeResult,
    ProviderPriceReference,
    ProviderSubscriptionSnapshot,
    StripeTestBillingProvider,
)
from revenueos.billing_services import BillingService
from revenueos.commercial_contracts import BillingInterval, PlanCode
from revenueos.commercial_services import CommercialService
from revenueos.config import Settings
from revenueos.database import set_tenant_database_context
from revenueos.errors import PublicAPIError
from revenueos.main import create_app
from revenueos.models import (
    BillingOperation,
    BillingProviderEventReceipt,
    BillingSubscription,
    CommercialPlanVersion,
    CommercialStateEvent,
    Organisation,
    OrganisationCommercialState,
)
from tests.conftest import PRIMARY_ORGANISATION_ID, PRIMARY_USER_ID, SECONDARY_ORGANISATION_ID, TEST_DB_URL

WEBHOOK_SECRET = "test-billing-webhook-secret-0001"


class TimeoutOnceBillingProvider(DeterministicBillingProvider):
    def __init__(self, settings: Settings) -> None:
        super().__init__(settings)
        self.timeout_once = True

    async def create_checkout(
        self,
        *,
        organisation_id: UUID,
        customer_identifier: str,
        price: ProviderPriceReference,
        idempotency_key: str,
    ) -> ProviderCheckout:
        result = await super().create_checkout(
            organisation_id=organisation_id,
            customer_identifier=customer_identifier,
            price=price,
            idempotency_key=idempotency_key,
        )
        if self.timeout_once:
            self.timeout_once = False
            raise PublicAPIError(
                "billing_provider_unavailable",
                "We couldn't confirm your payment yet. No second charge has been attempted.",
                503,
            )
        return result


class TimeoutOncePlanUpgradeProvider(DeterministicBillingProvider):
    def __init__(self, settings: Settings) -> None:
        super().__init__(settings)
        self.timeout_once = True

    async def apply_plan_upgrade(
        self,
        identifier: str,
        *,
        price: ProviderPriceReference,
        idempotency_key: str,
    ) -> ProviderPlanChangeResult:
        result = await super().apply_plan_upgrade(
            identifier,
            price=price,
            idempotency_key=idempotency_key,
        )
        if self.timeout_once:
            self.timeout_once = False
            raise PublicAPIError(
                "billing_provider_unavailable",
                "The provider applied the request but its response was lost.",
                503,
            )
        return result


class TimeoutOnceCancellationProvider(DeterministicBillingProvider):
    def __init__(self, settings: Settings) -> None:
        super().__init__(settings)
        self.timeout_once = True

    async def cancel_at_period_end(self, identifier: str, *, idempotency_key: str) -> ProviderSubscriptionSnapshot:
        result = await super().cancel_at_period_end(identifier, idempotency_key=idempotency_key)
        if self.timeout_once:
            self.timeout_once = False
            raise PublicAPIError(
                "billing_provider_unavailable",
                "The provider applied the request but its response was lost.",
                503,
            )
        return result


class TimeoutOnceScheduledPlanCancellationProvider(DeterministicBillingProvider):
    def __init__(self, settings: Settings) -> None:
        super().__init__(settings)
        self.timeout_once = True

    async def cancel_scheduled_plan_change(
        self, identifier: str, *, idempotency_key: str
    ) -> ProviderSubscriptionSnapshot:
        result = await super().cancel_scheduled_plan_change(identifier, idempotency_key=idempotency_key)
        if self.timeout_once:
            self.timeout_once = False
            raise PublicAPIError(
                "billing_provider_unavailable",
                "The provider removed the schedule but its response was lost.",
                503,
            )
        return result


class MismatchedUpgradeInvoiceProvider(DeterministicBillingProvider):
    async def apply_plan_upgrade(
        self,
        identifier: str,
        *,
        price: ProviderPriceReference,
        idempotency_key: str,
    ) -> ProviderPlanChangeResult:
        result = await super().apply_plan_upgrade(
            identifier,
            price=price,
            idempotency_key=idempotency_key,
        )
        assert result.invoice is not None
        return replace(
            result,
            invoice=replace(result.invoice, customer_identifier="cus_test_wrong_organisation"),
        )


def billing_settings() -> Settings:
    return Settings(
        environment="test",
        auth_mode="mock",
        mock_auth_enabled=True,
        database_url=TEST_DB_URL,
        log_level="WARNING",
        feature_billing_enabled=True,
        billing_provider_name="deterministic",
        billing_webhook_secret=WEBHOOK_SECRET,
    )


def signed_event(
    *,
    event_id: str,
    event_type: str,
    organisation_id: UUID,
    customer_id: str,
    subscription_id: str | None = None,
    invoice_id: str | None = None,
    object_id: str | None = None,
    created: datetime,
) -> tuple[bytes, str]:
    payload = json.dumps(
        {
            "id": event_id,
            "type": event_type,
            "organisation_id": str(organisation_id),
            "customer_id": customer_id,
            "subscription_id": subscription_id,
            "invoice_id": invoice_id,
            "object_id": object_id,
            "created": int(created.timestamp()),
        },
        separators=(",", ":"),
    ).encode()
    signature = hmac.new(WEBHOOK_SECRET.encode(), payload, hashlib.sha256).hexdigest()
    return payload, f"sha256={signature}"


def test_exact_checkout_catalogue_idempotency_and_server_authority() -> None:
    async def scenario() -> None:
        settings = billing_settings()
        provider = DeterministicBillingProvider(settings)
        engine = create_async_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
        try:
            async with async_sessionmaker(engine, expire_on_commit=False)() as session:
                await set_tenant_database_context(session, PRIMARY_ORGANISATION_ID)
                service = BillingService(session, settings, provider)
                projection = await service.projection(PRIMARY_ORGANISATION_ID)
                exact = {
                    (item.plan_code, item.billing_interval): item.amount
                    for item in projection.checkout_options
                    if item.self_service_available
                }
                assert exact == {
                    ("core", "monthly"): "200.00",
                    ("core", "annual"): "2000.00",
                    ("growth", "monthly"): "350.00",
                    ("growth", "annual"): "3500.00",
                    ("complete", "monthly"): "500.00",
                    ("complete", "annual"): "5000.00",
                }
                enterprise = next(item for item in projection.checkout_options if item.plan_code == "enterprise")
                assert enterprise.self_service_available is False
                assert enterprise.amount is None

                request = CheckoutCreateRequest(
                    plan_code="core",
                    billing_interval="annual",
                    idempotency_key="checkout-core-annual-0001",
                )
                first = await service.create_checkout(PRIMARY_ORGANISATION_ID, PRIMARY_USER_ID, request)
                second = await service.create_checkout(PRIMARY_ORGANISATION_ID, PRIMARY_USER_ID, request)
                assert first == second
                assert first.amount == exact[("core", "annual")]
                assert first.checkout_url.startswith("https://checkout.stripe.test/")

                assert (
                    await session.scalar(
                        select(func.count())
                        .select_from(BillingOperation)
                        .where(
                            BillingOperation.organisation_id == PRIMARY_ORGANISATION_ID,
                            BillingOperation.operation_type == "checkout",
                        )
                    )
                    == 1
                )
                stored_operation = await session.get(BillingOperation, first.operation_id)
                assert stored_operation is not None and stored_operation.status == "pending"
                with pytest.raises(PublicAPIError, match="previous checkout"):
                    await service.create_checkout(
                        PRIMARY_ORGANISATION_ID,
                        PRIMARY_USER_ID,
                        CheckoutCreateRequest(
                            plan_code="complete",
                            billing_interval="monthly",
                            idempotency_key="parallel-checkout-blocked-0001",
                        ),
                    )
                with pytest.raises(PublicAPIError, match="Enterprise"):
                    await service.create_checkout(
                        PRIMARY_ORGANISATION_ID,
                        PRIMARY_USER_ID,
                        CheckoutCreateRequest(
                            plan_code="enterprise",
                            billing_interval="annual",
                            idempotency_key="enterprise-checkout-0001",
                        ),
                    )
                with pytest.raises(PublicAPIError, match="different request"):
                    await service.create_checkout(
                        PRIMARY_ORGANISATION_ID,
                        PRIMARY_USER_ID,
                        CheckoutCreateRequest(
                            plan_code="growth",
                            billing_interval="annual",
                            idempotency_key="checkout-core-annual-0001",
                        ),
                    )
        finally:
            await engine.dispose()

    asyncio.run(scenario())


@pytest.mark.parametrize(
    ("plan_code", "interval", "expected_amount"),
    [
        ("core", "monthly", "200.00"),
        ("core", "annual", "2000.00"),
        ("growth", "monthly", "350.00"),
        ("growth", "annual", "3500.00"),
        ("complete", "monthly", "500.00"),
        ("complete", "annual", "5000.00"),
    ],
)
def test_each_authorised_checkout_offer_uses_the_server_catalogue(
    plan_code: PlanCode,
    interval: BillingInterval,
    expected_amount: str,
) -> None:
    async def scenario() -> None:
        settings = billing_settings()
        provider = DeterministicBillingProvider(settings)
        engine = create_async_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
        try:
            async with async_sessionmaker(engine, expire_on_commit=False)() as session:
                await set_tenant_database_context(session, PRIMARY_ORGANISATION_ID)
                service = BillingService(session, settings, provider)
                checkout = await service.create_checkout(
                    PRIMARY_ORGANISATION_ID,
                    PRIMARY_USER_ID,
                    CheckoutCreateRequest(
                        plan_code=plan_code,
                        billing_interval=interval,
                        idempotency_key=f"authorised-{plan_code}-{interval}-checkout-0001",
                    ),
                )
                assert checkout.amount == expected_amount
                operation = await session.get(BillingOperation, checkout.operation_id)
                assert operation is not None and operation.provider_object_id is not None
                provider_checkout = await provider.retrieve_checkout(operation.provider_object_id)
                assert provider_checkout.subscription_identifier is not None
                provider_subscription = await provider.retrieve_subscription(provider_checkout.subscription_identifier)
                assert provider_subscription.price_identifier == f"price_test_{plan_code}_{interval}_aud"
        finally:
            await engine.dispose()

    asyncio.run(scenario())


def test_verified_webhooks_trial_conversion_duplicates_failures_invoice_and_out_of_order() -> None:
    async def scenario() -> None:
        settings = billing_settings()
        provider = DeterministicBillingProvider(settings)
        engine = create_async_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        start = datetime(2032, 1, 1, tzinfo=UTC)
        try:
            async with session_factory() as session:
                await set_tenant_database_context(session, PRIMARY_ORGANISATION_ID)
                state = await session.get(OrganisationCommercialState, PRIMARY_ORGANISATION_ID)
                assert state is not None
                commercial = CommercialService(session, settings, now=lambda: start)
                trial = await commercial.start_trial(
                    PRIMARY_ORGANISATION_ID,
                    actor_reference="test-support",
                    reason="Synthetic conversion trial.",
                    expected_lock_version=state.lock_version,
                )
                assert trial.status == "trial_active"

                service = BillingService(session, settings, provider, now=lambda: start + timedelta(days=20))
                checkout = await service.create_checkout(
                    PRIMARY_ORGANISATION_ID,
                    PRIMARY_USER_ID,
                    CheckoutCreateRequest(
                        plan_code="core",
                        billing_interval="annual",
                        idempotency_key="trial-paid-core-annual-0001",
                    ),
                )
                pending = await service.success_status(PRIMARY_ORGANISATION_ID)
                assert pending.confirmed is False
                provider_checkout = await provider.retrieve_checkout(
                    str(
                        await session.scalar(
                            select(BillingOperation.provider_object_id).where(
                                BillingOperation.id == checkout.operation_id
                            )
                        )
                    )
                )
                assert provider_checkout.subscription_identifier is not None
                subscription_snapshot = provider.complete_checkout(
                    provider_checkout.identifier,
                    period_start=start + timedelta(days=20),
                    period_end=start + timedelta(days=385),
                )
                payload, signature = signed_event(
                    event_id="evt_checkout_complete_001",
                    event_type="checkout.session.completed",
                    organisation_id=PRIMARY_ORGANISATION_ID,
                    customer_id=provider_checkout.customer_identifier,
                    subscription_id=subscription_snapshot.identifier,
                    object_id=provider_checkout.identifier,
                    created=start + timedelta(days=20),
                )
                assert await service.process_webhook(payload, signature) == "processed"
                assert await service.process_webhook(payload, signature) == "duplicate"
                commercial_state = await session.get(OrganisationCommercialState, PRIMARY_ORGANISATION_ID)
                assert commercial_state is not None
                plan = await session.get(CommercialPlanVersion, commercial_state.plan_version_id)
                assert plan is not None and plan.code == "core"
                assert commercial_state.status == "active"
                assert commercial_state.billing_interval == "annual"
                assert commercial_state.trial_used_at == start
                assert commercial_state.source == "billing_provider"
                organisation = await session.get(Organisation, PRIMARY_ORGANISATION_ID)
                assert organisation is not None and organisation.name == "Example Revenue Team"
                receipt_count = await session.scalar(
                    select(func.count())
                    .select_from(BillingProviderEventReceipt)
                    .where(BillingProviderEventReceipt.provider_event_id == "evt_checkout_complete_001")
                )
                assert receipt_count == 1

                provider.set_subscription_status(subscription_snapshot.identifier, "past_due")
                failure_payload, failure_signature = signed_event(
                    event_id="evt_payment_failed_001",
                    event_type="invoice.payment_failed",
                    organisation_id=PRIMARY_ORGANISATION_ID,
                    customer_id=provider_checkout.customer_identifier,
                    subscription_id=subscription_snapshot.identifier,
                    invoice_id="in_failed_001",
                    object_id="in_failed_001",
                    created=start + timedelta(days=21),
                )
                provider.add_invoice(
                    ProviderInvoiceSnapshot(
                        identifier="in_failed_001",
                        customer_identifier=provider_checkout.customer_identifier,
                        subscription_identifier=subscription_snapshot.identifier,
                        invoice_date=start + timedelta(days=21),
                        amount_due=Decimal("2000.00"),
                        amount_paid=Decimal("0.00"),
                        tax_amount=None,
                        currency="AUD",
                        status="open",
                        hosted_invoice_url="https://invoice.stripe.test/i/in_failed_001",
                        receipt_url=None,
                        provider_updated_at=start + timedelta(days=21),
                    )
                )
                assert await service.process_webhook(failure_payload, failure_signature) == "processed"
                assert await service.process_webhook(failure_payload, failure_signature) == "duplicate"
                failed_projection = await service.projection(PRIMARY_ORGANISATION_ID)
                assert failed_projection.subscription is not None
                assert failed_projection.subscription.status == "past_due"
                assert failed_projection.subscription.payment_needs_attention is True
                assert len(failed_projection.invoices) == 1
                commercial_state = await session.get(OrganisationCommercialState, PRIMARY_ORGANISATION_ID)
                assert commercial_state is not None and commercial_state.status == "active"

                provider.set_subscription_status(subscription_snapshot.identifier, "unpaid")
                unpaid_payload, unpaid_signature = signed_event(
                    event_id="evt_payment_terminal_unpaid_001",
                    event_type="customer.subscription.updated",
                    organisation_id=PRIMARY_ORGANISATION_ID,
                    customer_id=provider_checkout.customer_identifier,
                    subscription_id=subscription_snapshot.identifier,
                    object_id=subscription_snapshot.identifier,
                    created=start + timedelta(days=22),
                )
                assert await service.process_webhook(unpaid_payload, unpaid_signature) == "processed"
                unpaid_projection = await service.projection(PRIMARY_ORGANISATION_ID)
                assert unpaid_projection.subscription is not None
                assert unpaid_projection.subscription.status == "unpaid"
                assert "paid functionality is inactive" in unpaid_projection.message
                unpaid_state = await session.get(OrganisationCommercialState, PRIMARY_ORGANISATION_ID)
                assert unpaid_state is not None and unpaid_state.status == "inactive"
                organisation = await session.get(Organisation, PRIMARY_ORGANISATION_ID)
                assert organisation is not None and organisation.name == "Example Revenue Team"

                provider.set_subscription_status(subscription_snapshot.identifier, "active")
                recovered_payload, recovered_signature = signed_event(
                    event_id="evt_payment_recovered_001",
                    event_type="customer.subscription.updated",
                    organisation_id=PRIMARY_ORGANISATION_ID,
                    customer_id=provider_checkout.customer_identifier,
                    subscription_id=subscription_snapshot.identifier,
                    object_id=subscription_snapshot.identifier,
                    created=start + timedelta(days=23),
                )
                assert await service.process_webhook(recovered_payload, recovered_signature) == "processed"
                recovered_state = await session.get(OrganisationCommercialState, PRIMARY_ORGANISATION_ID)
                assert recovered_state is not None and recovered_state.status == "active"

                provider.set_subscription_status(
                    subscription_snapshot.identifier,
                    "cancelled",
                    ended_at=start + timedelta(days=385),
                )
                cancel_payload, cancel_signature = signed_event(
                    event_id="evt_cancelled_002",
                    event_type="customer.subscription.deleted",
                    organisation_id=PRIMARY_ORGANISATION_ID,
                    customer_id=provider_checkout.customer_identifier,
                    subscription_id=subscription_snapshot.identifier,
                    object_id=subscription_snapshot.identifier,
                    created=start + timedelta(days=385),
                )
                assert await service.process_webhook(cancel_payload, cancel_signature) == "processed"
                cancelled_state = await session.get(OrganisationCommercialState, PRIMARY_ORGANISATION_ID)
                assert cancelled_state is not None and cancelled_state.status == "inactive"
                stale_payload, stale_signature = signed_event(
                    event_id="evt_stale_update_001",
                    event_type="customer.subscription.updated",
                    organisation_id=PRIMARY_ORGANISATION_ID,
                    customer_id=provider_checkout.customer_identifier,
                    subscription_id=subscription_snapshot.identifier,
                    object_id=subscription_snapshot.identifier,
                    created=start + timedelta(days=30),
                )
                assert await service.process_webhook(stale_payload, stale_signature) == "processed"
                still_cancelled = await service.projection(PRIMARY_ORGANISATION_ID)
                assert still_cancelled.subscription is not None
                assert still_cancelled.subscription.status == "cancelled"
                final_state = await session.get(OrganisationCommercialState, PRIMARY_ORGANISATION_ID)
                assert final_state is not None and final_state.status == "inactive"
                commercial_effects = await session.scalar(
                    select(func.count())
                    .select_from(CommercialStateEvent)
                    .where(CommercialStateEvent.organisation_id == PRIMARY_ORGANISATION_ID)
                )
                assert commercial_effects == 5  # trial, paid, terminal unpaid, recovery, period-end cancellation
        finally:
            await engine.dispose()

    asyncio.run(scenario())


def test_unknown_checkout_outcome_retries_with_one_provider_session_and_no_entitlement() -> None:
    async def scenario() -> None:
        settings = billing_settings()
        provider = TimeoutOnceBillingProvider(settings)
        engine = create_async_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
        try:
            async with async_sessionmaker(engine, expire_on_commit=False)() as session:
                await set_tenant_database_context(session, PRIMARY_ORGANISATION_ID)
                service = BillingService(session, settings, provider)
                request = CheckoutCreateRequest(
                    plan_code="growth",
                    billing_interval="monthly",
                    idempotency_key="timeout-safe-checkout-0001",
                )
                with pytest.raises(PublicAPIError, match="No second charge"):
                    await service.create_checkout(PRIMARY_ORGANISATION_ID, PRIMARY_USER_ID, request)
                operation = await session.scalar(
                    select(BillingOperation).where(
                        BillingOperation.organisation_id == PRIMARY_ORGANISATION_ID,
                        BillingOperation.idempotency_key == request.idempotency_key,
                    )
                )
                assert operation is not None and operation.status == "unknown"
                with pytest.raises(PublicAPIError, match="previous checkout"):
                    await service.create_checkout(
                        PRIMARY_ORGANISATION_ID,
                        PRIMARY_USER_ID,
                        CheckoutCreateRequest(
                            plan_code="complete",
                            billing_interval="annual",
                            idempotency_key="different-checkout-must-wait-0001",
                        ),
                    )
                retried = await service.create_checkout(PRIMARY_ORGANISATION_ID, PRIMARY_USER_ID, request)
                assert retried.status == "redirect_ready"
                assert len(provider.checkouts) == 1
                assert (
                    await session.scalar(
                        select(func.count())
                        .select_from(BillingOperation)
                        .where(
                            BillingOperation.organisation_id == PRIMARY_ORGANISATION_ID,
                            BillingOperation.idempotency_key == request.idempotency_key,
                        )
                    )
                    == 1
                )
                pending = await service.success_status(PRIMARY_ORGANISATION_ID)
                assert pending.confirmed is False
                assert pending.status == "not_configured"
        finally:
            await engine.dispose()

    asyncio.run(scenario())


@pytest.mark.parametrize(
    ("starting_point", "plan_code"),
    [
        ("trial", "core"),
        ("trial", "growth"),
        ("trial", "complete"),
        ("grace", "growth"),
        ("direct", "complete"),
    ],
)
def test_verified_paid_conversion_preserves_each_supported_organisation_state(
    starting_point: str,
    plan_code: PlanCode,
) -> None:
    async def scenario() -> None:
        settings = billing_settings()
        provider = DeterministicBillingProvider(settings)
        engine = create_async_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
        start = datetime(2032, 6, 1, tzinfo=UTC)
        observed = start if starting_point != "grace" else start + timedelta(days=15)
        try:
            async with async_sessionmaker(engine, expire_on_commit=False)() as session:
                await set_tenant_database_context(session, PRIMARY_ORGANISATION_ID)
                state = await session.get(OrganisationCommercialState, PRIMARY_ORGANISATION_ID)
                assert state is not None
                if starting_point in {"trial", "grace"}:
                    commercial = CommercialService(session, settings, now=lambda: start)
                    await commercial.start_trial(
                        PRIMARY_ORGANISATION_ID,
                        actor_reference=f"conversion-{starting_point}",
                        reason="Synthetic billing conversion coverage.",
                        expected_lock_version=state.lock_version,
                    )
                    if starting_point == "grace":
                        grace = CommercialService(session, settings, now=lambda: observed)
                        assert (await grace.projection(PRIMARY_ORGANISATION_ID)).status == "grace"

                service = BillingService(session, settings, provider, now=lambda: observed)
                checkout = await service.create_checkout(
                    PRIMARY_ORGANISATION_ID,
                    PRIMARY_USER_ID,
                    CheckoutCreateRequest(
                        plan_code=plan_code,
                        billing_interval="monthly",
                        idempotency_key=f"{starting_point}-{plan_code}-paid-0001",
                    ),
                )
                operation = await session.get(BillingOperation, checkout.operation_id)
                assert operation is not None and operation.provider_object_id is not None
                provider_checkout = await provider.retrieve_checkout(operation.provider_object_id)
                snapshot = provider.complete_checkout(
                    provider_checkout.identifier,
                    period_start=observed,
                    period_end=observed + timedelta(days=30),
                )
                payload, signature = signed_event(
                    event_id=f"evt_{starting_point}_{plan_code}_paid_001",
                    event_type="checkout.session.completed",
                    organisation_id=PRIMARY_ORGANISATION_ID,
                    customer_id=snapshot.customer_identifier,
                    subscription_id=snapshot.identifier,
                    object_id=provider_checkout.identifier,
                    created=observed,
                )
                assert await service.process_webhook(payload, signature) == "processed"
                paid = await session.get(OrganisationCommercialState, PRIMARY_ORGANISATION_ID)
                assert paid is not None and paid.status == "active"
                plan = await session.get(CommercialPlanVersion, paid.plan_version_id)
                assert plan is not None and plan.code == plan_code
                assert paid.source == "billing_provider"
                assert (paid.trial_used_at is not None) is (starting_point != "direct")
                organisation = await session.get(Organisation, PRIMARY_ORGANISATION_ID)
                assert organisation is not None and organisation.name == "Example Revenue Team"
        finally:
            await engine.dispose()

    asyncio.run(scenario())


def test_cancel_reactivate_and_next_renewal_downgrade_are_idempotent() -> None:
    async def scenario() -> None:
        settings = billing_settings()
        provider = TimeoutOnceScheduledPlanCancellationProvider(settings)
        engine = create_async_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
        start = datetime(2033, 2, 1, tzinfo=UTC)
        try:
            async with async_sessionmaker(engine, expire_on_commit=False)() as session:
                await set_tenant_database_context(session, PRIMARY_ORGANISATION_ID)
                service = BillingService(session, settings, provider, now=lambda: start)
                checkout = await service.create_checkout(
                    PRIMARY_ORGANISATION_ID,
                    PRIMARY_USER_ID,
                    CheckoutCreateRequest(
                        plan_code="complete",
                        billing_interval="monthly",
                        idempotency_key="lifecycle-complete-monthly-0001",
                    ),
                )
                operation = await session.get(BillingOperation, checkout.operation_id)
                assert operation is not None and operation.provider_object_id is not None
                provider_checkout = await provider.retrieve_checkout(operation.provider_object_id)
                snapshot = provider.complete_checkout(
                    provider_checkout.identifier,
                    period_start=start,
                    period_end=start + timedelta(days=28),
                )
                payload, signature = signed_event(
                    event_id="evt_lifecycle_active_001",
                    event_type="checkout.session.completed",
                    organisation_id=PRIMARY_ORGANISATION_ID,
                    customer_id=snapshot.customer_identifier,
                    subscription_id=snapshot.identifier,
                    object_id=provider_checkout.identifier,
                    created=start,
                )
                await service.process_webhook(payload, signature)

                cancel_request = BillingOperationRequest(idempotency_key="cancel-period-end-0001")
                first_cancel = await service.cancel(PRIMARY_ORGANISATION_ID, PRIMARY_USER_ID, cancel_request)
                second_cancel = await service.cancel(PRIMARY_ORGANISATION_ID, PRIMARY_USER_ID, cancel_request)
                assert first_cancel == second_cancel
                cancelled = await service.projection(PRIMARY_ORGANISATION_ID)
                assert cancelled.subscription is not None
                assert cancelled.subscription.cancel_at_period_end is True

                reactivate_request = BillingOperationRequest(idempotency_key="reactivate-period-0001")
                first_reactivation = await service.reactivate(
                    PRIMARY_ORGANISATION_ID, PRIMARY_USER_ID, reactivate_request
                )
                second_reactivation = await service.reactivate(
                    PRIMARY_ORGANISATION_ID, PRIMARY_USER_ID, reactivate_request
                )
                assert first_reactivation == second_reactivation
                reactivated = await service.projection(PRIMARY_ORGANISATION_ID)
                assert reactivated.subscription is not None
                assert reactivated.subscription.status == "active"
                assert reactivated.subscription.cancel_at_period_end is False

                change_request = PlanChangeRequest(
                    plan_code="growth",
                    billing_interval="annual",
                    idempotency_key="growth-next-renewal-0001",
                )
                first_change = await service.change_plan(PRIMARY_ORGANISATION_ID, PRIMARY_USER_ID, change_request)
                second_change = await service.change_plan(PRIMARY_ORGANISATION_ID, PRIMARY_USER_ID, change_request)
                assert first_change == second_change
                scheduled = await service.projection(PRIMARY_ORGANISATION_ID)
                assert scheduled.subscription is not None
                assert scheduled.subscription.plan_code == "complete"
                assert scheduled.subscription.pending_plan_code == "growth"

                replacement = await service.change_plan(
                    PRIMARY_ORGANISATION_ID,
                    PRIMARY_USER_ID,
                    PlanChangeRequest(
                        plan_code="core",
                        billing_interval="monthly",
                        idempotency_key="replace-scheduled-downgrade-0001",
                    ),
                )
                assert replacement.status == "succeeded"
                replaced = await service.projection(PRIMARY_ORGANISATION_ID)
                assert replaced.subscription is not None
                assert replaced.subscription.pending_plan_code == "core"
                assert provider.pending_price_changes[snapshot.identifier] == "price_test_core_monthly_aud"

                keep_request = PlanChangeRequest(
                    plan_code="complete",
                    billing_interval="monthly",
                    idempotency_key="cancel-scheduled-downgrade-0001",
                )
                with pytest.raises(PublicAPIError, match="response was lost"):
                    await service.change_plan(PRIMARY_ORGANISATION_ID, PRIMARY_USER_ID, keep_request)
                unresolved = await service.projection(PRIMARY_ORGANISATION_ID)
                assert unresolved.subscription is not None
                assert unresolved.subscription.pending_plan_code == "core"

                kept = await service.change_plan(PRIMARY_ORGANISATION_ID, PRIMARY_USER_ID, keep_request)
                repeated_keep = await service.change_plan(PRIMARY_ORGANISATION_ID, PRIMARY_USER_ID, keep_request)
                assert kept.status == "succeeded"
                assert repeated_keep == kept
                assert snapshot.identifier not in provider.pending_price_changes
                no_pending = await service.projection(PRIMARY_ORGANISATION_ID)
                assert no_pending.subscription is not None
                assert no_pending.subscription.pending_plan_code is None

                await service.change_plan(
                    PRIMARY_ORGANISATION_ID,
                    PRIMARY_USER_ID,
                    PlanChangeRequest(
                        plan_code="growth",
                        billing_interval="annual",
                        idempotency_key="growth-next-renewal-0002",
                    ),
                )

                provider.renew_with_scheduled_plan(
                    snapshot.identifier,
                    period_start=start + timedelta(days=28),
                    period_end=start + timedelta(days=393),
                )
                renewal_payload, renewal_signature = signed_event(
                    event_id="evt_renewal_growth_001",
                    event_type="customer.subscription.updated",
                    organisation_id=PRIMARY_ORGANISATION_ID,
                    customer_id=snapshot.customer_identifier,
                    subscription_id=snapshot.identifier,
                    object_id=snapshot.identifier,
                    created=start + timedelta(days=28),
                )
                await service.process_webhook(renewal_payload, renewal_signature)
                renewed = await service.projection(PRIMARY_ORGANISATION_ID)
                assert renewed.subscription is not None
                assert renewed.subscription.plan_code == "growth"
                assert renewed.subscription.billing_interval == "annual"
                assert renewed.subscription.pending_plan_code is None
                commercial_state = await session.get(OrganisationCommercialState, PRIMARY_ORGANISATION_ID)
                assert commercial_state is not None
                plan = await session.get(CommercialPlanVersion, commercial_state.plan_version_id)
                assert plan is not None and plan.code == "growth"
        finally:
            await engine.dispose()

    asyncio.run(scenario())


def test_higher_tier_upgrade_is_immediate_with_provider_invoice_and_no_client_proration() -> None:
    async def scenario() -> None:
        settings = billing_settings()
        provider = DeterministicBillingProvider(settings)
        provider.next_upgrade_invoice_amount = Decimal("137.25")
        engine = create_async_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
        start = datetime(2033, 5, 1, tzinfo=UTC)
        try:
            async with async_sessionmaker(engine, expire_on_commit=False)() as session:
                await set_tenant_database_context(session, PRIMARY_ORGANISATION_ID)
                service = BillingService(session, settings, provider, now=lambda: start)
                checkout = await service.create_checkout(
                    PRIMARY_ORGANISATION_ID,
                    PRIMARY_USER_ID,
                    CheckoutCreateRequest(
                        plan_code="core",
                        billing_interval="annual",
                        idempotency_key="upgrade-source-core-annual-0001",
                    ),
                )
                operation = await session.get(BillingOperation, checkout.operation_id)
                assert operation is not None and operation.provider_object_id is not None
                provider_checkout = await provider.retrieve_checkout(operation.provider_object_id)
                snapshot = provider.complete_checkout(
                    provider_checkout.identifier,
                    period_start=start,
                    period_end=start + timedelta(days=365),
                )
                payload, signature = signed_event(
                    event_id="evt_upgrade_source_active_001",
                    event_type="checkout.session.completed",
                    organisation_id=PRIMARY_ORGANISATION_ID,
                    customer_id=snapshot.customer_identifier,
                    subscription_id=snapshot.identifier,
                    object_id=provider_checkout.identifier,
                    created=start,
                )
                assert await service.process_webhook(payload, signature) == "processed"

                request = PlanChangeRequest(
                    plan_code="growth",
                    billing_interval="monthly",
                    idempotency_key="immediate-growth-upgrade-0001",
                )
                first = await service.change_plan(PRIMARY_ORGANISATION_ID, PRIMARY_USER_ID, request)
                second = await service.change_plan(PRIMARY_ORGANISATION_ID, PRIMARY_USER_ID, request)
                assert first == second
                assert first.status == "succeeded"

                upgraded = await service.projection(PRIMARY_ORGANISATION_ID)
                assert upgraded.subscription is not None
                assert upgraded.subscription.plan_code == "growth"
                assert upgraded.subscription.billing_interval == "monthly"
                assert upgraded.subscription.pending_plan_code is None
                assert len(upgraded.invoices) == 1
                assert upgraded.invoices[0].amount_due == "137.25"
                assert upgraded.invoices[0].amount_paid == "137.25"
                assert snapshot.identifier not in provider.pending_price_changes
                commercial_state = await session.get(OrganisationCommercialState, PRIMARY_ORGANISATION_ID)
                assert commercial_state is not None and commercial_state.status == "active"
                commercial_plan = await session.get(CommercialPlanVersion, commercial_state.plan_version_id)
                assert commercial_plan is not None and commercial_plan.code == "growth"
                effects_before_webhook = await session.scalar(
                    select(func.count())
                    .select_from(CommercialStateEvent)
                    .where(CommercialStateEvent.organisation_id == PRIMARY_ORGANISATION_ID)
                )
                upgrade_payload, upgrade_signature = signed_event(
                    event_id="evt_immediate_upgrade_duplicate_001",
                    event_type="customer.subscription.updated",
                    organisation_id=PRIMARY_ORGANISATION_ID,
                    customer_id=snapshot.customer_identifier,
                    subscription_id=snapshot.identifier,
                    object_id=snapshot.identifier,
                    created=start + timedelta(seconds=1),
                )
                assert await service.process_webhook(upgrade_payload, upgrade_signature) == "processed"
                assert await service.process_webhook(upgrade_payload, upgrade_signature) == "duplicate"
                effects_after_webhook = await session.scalar(
                    select(func.count())
                    .select_from(CommercialStateEvent)
                    .where(CommercialStateEvent.organisation_id == PRIMARY_ORGANISATION_ID)
                )
                assert effects_after_webhook == effects_before_webhook
        finally:
            await engine.dispose()

    asyncio.run(scenario())


def test_upgrade_with_mismatched_provider_invoice_never_grants_entitlement() -> None:
    async def scenario() -> None:
        settings = billing_settings()
        provider = MismatchedUpgradeInvoiceProvider(settings)
        engine = create_async_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
        start = datetime(2033, 7, 1, tzinfo=UTC)
        try:
            async with async_sessionmaker(engine, expire_on_commit=False)() as session:
                await set_tenant_database_context(session, PRIMARY_ORGANISATION_ID)
                service = BillingService(session, settings, provider, now=lambda: start)
                checkout = await service.create_checkout(
                    PRIMARY_ORGANISATION_ID,
                    PRIMARY_USER_ID,
                    CheckoutCreateRequest(
                        plan_code="core",
                        billing_interval="monthly",
                        idempotency_key="mismatched-invoice-source-0001",
                    ),
                )
                operation = await session.get(BillingOperation, checkout.operation_id)
                assert operation is not None and operation.provider_object_id is not None
                provider_checkout = await provider.retrieve_checkout(operation.provider_object_id)
                snapshot = provider.complete_checkout(
                    provider_checkout.identifier,
                    period_start=start,
                    period_end=start + timedelta(days=31),
                )
                payload, signature = signed_event(
                    event_id="evt_mismatched_invoice_source_001",
                    event_type="checkout.session.completed",
                    organisation_id=PRIMARY_ORGANISATION_ID,
                    customer_id=snapshot.customer_identifier,
                    subscription_id=snapshot.identifier,
                    object_id=provider_checkout.identifier,
                    created=start,
                )
                await service.process_webhook(payload, signature)

                with pytest.raises(PublicAPIError, match="invoice could not be safely reconciled"):
                    await service.change_plan(
                        PRIMARY_ORGANISATION_ID,
                        PRIMARY_USER_ID,
                        PlanChangeRequest(
                            plan_code="growth",
                            billing_interval="monthly",
                            idempotency_key="mismatched-upgrade-invoice-0001",
                        ),
                    )
                projection = await service.projection(PRIMARY_ORGANISATION_ID)
                assert projection.subscription is not None
                assert projection.subscription.plan_code == "core"
                assert projection.invoices == []
                commercial_state = await session.get(OrganisationCommercialState, PRIMARY_ORGANISATION_ID)
                assert commercial_state is not None and commercial_state.status == "active"
                commercial_plan = await session.get(CommercialPlanVersion, commercial_state.plan_version_id)
                assert commercial_plan is not None and commercial_plan.code == "core"
        finally:
            await engine.dispose()

    asyncio.run(scenario())


def test_lost_upgrade_response_reconciles_before_retrying() -> None:
    async def upgrade_scenario() -> None:
        settings = billing_settings()
        provider = TimeoutOncePlanUpgradeProvider(settings)
        engine = create_async_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
        start = datetime(2033, 8, 1, tzinfo=UTC)
        try:
            async with async_sessionmaker(engine, expire_on_commit=False)() as session:
                await set_tenant_database_context(session, PRIMARY_ORGANISATION_ID)
                service = BillingService(session, settings, provider, now=lambda: start)
                checkout = await service.create_checkout(
                    PRIMARY_ORGANISATION_ID,
                    PRIMARY_USER_ID,
                    CheckoutCreateRequest(
                        plan_code="core",
                        billing_interval="monthly",
                        idempotency_key="lost-upgrade-source-0001",
                    ),
                )
                operation = await session.get(BillingOperation, checkout.operation_id)
                assert operation is not None and operation.provider_object_id is not None
                provider_checkout = await provider.retrieve_checkout(operation.provider_object_id)
                snapshot = provider.complete_checkout(
                    provider_checkout.identifier,
                    period_start=start,
                    period_end=start + timedelta(days=31),
                )
                payload, signature = signed_event(
                    event_id="evt_lost_upgrade_source_001",
                    event_type="checkout.session.completed",
                    organisation_id=PRIMARY_ORGANISATION_ID,
                    customer_id=snapshot.customer_identifier,
                    subscription_id=snapshot.identifier,
                    object_id=provider_checkout.identifier,
                    created=start,
                )
                await service.process_webhook(payload, signature)
                request = PlanChangeRequest(
                    plan_code="growth",
                    billing_interval="annual",
                    idempotency_key="lost-upgrade-response-0001",
                )
                with pytest.raises(PublicAPIError, match="response was lost"):
                    await service.change_plan(PRIMARY_ORGANISATION_ID, PRIMARY_USER_ID, request)
                before_confirmation = await service.projection(PRIMARY_ORGANISATION_ID)
                assert before_confirmation.subscription is not None
                assert before_confirmation.subscription.plan_code == "core"
                state = await session.get(OrganisationCommercialState, PRIMARY_ORGANISATION_ID)
                assert state is not None
                old_plan = await session.get(CommercialPlanVersion, state.plan_version_id)
                assert old_plan is not None and old_plan.code == "core"

                reconciled = await service.change_plan(PRIMARY_ORGANISATION_ID, PRIMARY_USER_ID, request)
                assert reconciled.status == "succeeded"
                after_confirmation = await service.projection(PRIMARY_ORGANISATION_ID)
                assert after_confirmation.subscription is not None
                assert after_confirmation.subscription.plan_code == "growth"
                assert len(provider.plan_change_results) == 1
        finally:
            await engine.dispose()

    asyncio.run(upgrade_scenario())


def test_lost_cancellation_response_reconciles_before_retrying() -> None:
    async def scenario() -> None:
        settings = billing_settings()
        provider = TimeoutOnceCancellationProvider(settings)
        engine = create_async_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
        start = datetime(2033, 9, 1, tzinfo=UTC)
        try:
            async with async_sessionmaker(engine, expire_on_commit=False)() as session:
                await set_tenant_database_context(session, PRIMARY_ORGANISATION_ID)
                service = BillingService(session, settings, provider, now=lambda: start)
                checkout = await service.create_checkout(
                    PRIMARY_ORGANISATION_ID,
                    PRIMARY_USER_ID,
                    CheckoutCreateRequest(
                        plan_code="core",
                        billing_interval="monthly",
                        idempotency_key="lost-cancel-source-0001",
                    ),
                )
                operation = await session.get(BillingOperation, checkout.operation_id)
                assert operation is not None and operation.provider_object_id is not None
                provider_checkout = await provider.retrieve_checkout(operation.provider_object_id)
                snapshot = provider.complete_checkout(
                    provider_checkout.identifier,
                    period_start=start,
                    period_end=start + timedelta(days=30),
                )
                payload, signature = signed_event(
                    event_id="evt_lost_cancel_source_001",
                    event_type="checkout.session.completed",
                    organisation_id=PRIMARY_ORGANISATION_ID,
                    customer_id=snapshot.customer_identifier,
                    subscription_id=snapshot.identifier,
                    object_id=provider_checkout.identifier,
                    created=start,
                )
                await service.process_webhook(payload, signature)
                request = BillingOperationRequest(idempotency_key="lost-cancel-response-0001")
                with pytest.raises(PublicAPIError, match="response was lost"):
                    await service.cancel(PRIMARY_ORGANISATION_ID, PRIMARY_USER_ID, request)
                pending = await service.cancel(PRIMARY_ORGANISATION_ID, PRIMARY_USER_ID, request)
                assert pending.status == "succeeded"
                projection = await service.projection(PRIMARY_ORGANISATION_ID)
                assert projection.subscription is not None
                assert projection.subscription.cancel_at_period_end is True
                assert projection.subscription.current_period_end is not None
                assert projection.subscription.current_period_end.replace(tzinfo=UTC) == start + timedelta(days=30)
        finally:
            await engine.dispose()

    asyncio.run(scenario())


def test_webhook_signature_mapping_and_cross_tenant_queries_fail_closed() -> None:
    async def scenario() -> None:
        settings = billing_settings()
        provider = DeterministicBillingProvider(settings)
        engine = create_async_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
        try:
            async with async_sessionmaker(engine, expire_on_commit=False)() as session:
                await set_tenant_database_context(session, PRIMARY_ORGANISATION_ID)
                service = BillingService(session, settings, provider)
                checkout = await service.create_checkout(
                    PRIMARY_ORGANISATION_ID,
                    PRIMARY_USER_ID,
                    CheckoutCreateRequest(
                        plan_code="complete",
                        billing_interval="monthly",
                        idempotency_key="security-checkout-0001",
                    ),
                )
                operation = await session.get(BillingOperation, checkout.operation_id)
                assert operation is not None and operation.provider_object_id is not None
                provider_checkout = await provider.retrieve_checkout(operation.provider_object_id)
                snapshot = provider.complete_checkout(
                    provider_checkout.identifier,
                    period_start=datetime.now(UTC),
                    period_end=datetime.now(UTC) + timedelta(days=30),
                )
                payload, signature = signed_event(
                    event_id="evt_security_001",
                    event_type="checkout.session.completed",
                    organisation_id=PRIMARY_ORGANISATION_ID,
                    customer_id=snapshot.customer_identifier,
                    subscription_id=snapshot.identifier,
                    object_id=provider_checkout.identifier,
                    created=datetime.now(UTC),
                )
                with pytest.raises(PublicAPIError, match="signature"):
                    await service.process_webhook(payload, "sha256=forged")
                provider.subscriptions[snapshot.identifier] = replace(
                    snapshot,
                    price_identifier="price_test_core_monthly_aud",
                )
                assert await service.process_webhook(payload, signature) == "reconciliation_required"
                unchanged = await session.get(OrganisationCommercialState, PRIMARY_ORGANISATION_ID)
                assert unchanged is not None and unchanged.source == "migration"
                provider.subscriptions[snapshot.identifier] = snapshot
                forged_payload, forged_signature = signed_event(
                    event_id="evt_security_002",
                    event_type="customer.subscription.updated",
                    organisation_id=SECONDARY_ORGANISATION_ID,
                    customer_id=snapshot.customer_identifier,
                    subscription_id=snapshot.identifier,
                    object_id=snapshot.identifier,
                    created=datetime.now(UTC),
                )
                with pytest.raises(PublicAPIError, match="ownership"):
                    await service.process_webhook(forged_payload, forged_signature)
                await set_tenant_database_context(session, SECONDARY_ORGANISATION_ID)
                assert (
                    await session.scalar(
                        select(BillingSubscription).where(
                            BillingSubscription.organisation_id == SECONDARY_ORGANISATION_ID
                        )
                    )
                    is None
                )
        finally:
            await engine.dispose()

    asyncio.run(scenario())


def test_billing_export_is_safe_and_offboarding_refuses_blind_history_deletion() -> None:
    async def scenario() -> None:
        settings = billing_settings()
        provider = DeterministicBillingProvider(settings)
        engine = create_async_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
        factory = async_sessionmaker(engine, expire_on_commit=False)
        try:
            async with factory() as session:
                await set_tenant_database_context(session, PRIMARY_ORGANISATION_ID)
                service = BillingService(session, settings, provider)
                checkout = await service.create_checkout(
                    PRIMARY_ORGANISATION_ID,
                    PRIMARY_USER_ID,
                    CheckoutCreateRequest(
                        plan_code="core",
                        billing_interval="monthly",
                        idempotency_key="safe-export-checkout-0001",
                    ),
                )
                exported = await _export_payload(session, PRIMARY_ORGANISATION_ID, settings)
                assert exported["exportVersion"] == EXPORT_VERSION == 34
                billing = exported["billing"]
                assert isinstance(billing, dict)
                encoded = json.dumps(billing, default=str)
                assert "provider_customer_id" not in encoded
                assert "provider_object_id" not in encoded
                assert "idempotency_key" not in encoded
                assert checkout.checkout_url not in encoded

            with pytest.raises(RuntimeError, match="accounting-retention decision"):
                await _delete_organisation_records(factory, settings, PRIMARY_ORGANISATION_ID)
            async with factory() as session:
                await set_tenant_database_context(session, PRIMARY_ORGANISATION_ID)
                assert await session.get(Organisation, PRIMARY_ORGANISATION_ID) is not None
        finally:
            await engine.dispose()

    asyncio.run(scenario())


def test_api_rejects_price_tampering_enterprise_and_non_admin_mutation() -> None:
    app = create_app(billing_settings())
    with TestClient(app) as client:
        tampered = client.post(
            "/api/v1/billing/checkout",
            json={
                "planCode": "core",
                "billingInterval": "monthly",
                "amount": "1.00",
                "currency": "USD",
                "idempotencyKey": "tampered-checkout-0001",
            },
        )
        assert tampered.status_code == 422
        enterprise = client.post(
            "/api/v1/billing/checkout",
            json={
                "planCode": "enterprise",
                "billingInterval": "annual",
                "idempotencyKey": "enterprise-api-0001",
            },
        )
        assert enterprise.status_code == 409

        app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(
            user_id=PRIMARY_USER_ID,
            external_auth_id="ordinary_member",
            display_name="Ordinary member",
            email="member@example.test",
            organisation_id=PRIMARY_ORGANISATION_ID,
            organisation_name="Example Revenue Team",
            organisation_slug="example-revenue-team",
            role="member",
            auth_mode="mock",
        )
        denied = client.post(
            "/api/v1/billing/cancel",
            json={"idempotencyKey": "ordinary-member-cancel-0001"},
        )
        assert denied.status_code == 403


def test_test_live_configuration_separation() -> None:
    with pytest.raises(ValidationError, match="Live Stripe credentials"):
        Settings(stripe_secret_key="sk_live_not_authorised")
    with pytest.raises(ValidationError, match="test-mode only"):
        Settings(
            environment="production",
            auth_mode="clerk",
            mock_auth_enabled=False,
            identity_jit_provisioning_enabled=False,
            clerk_jwks_url="https://identity.example.test/jwks",
            clerk_issuer="https://identity.example.test",
            clerk_audience="revenueos",
            database_url="postgresql+asyncpg://example.invalid/revenueos",
            cors_origins="https://app.example.test",
            allowed_hosts="app.example.test",
            feature_billing_enabled=True,
            feature_engage_enabled=False,
            feature_visual_evidence_enabled=False,
            feature_online_meeting_capture_enabled=False,
            feature_document_evidence_enabled=False,
            feature_create_enabled=False,
        )
    with pytest.raises(ValidationError, match="2026-02-25.clover"):
        Settings(stripe_api_version="2025-03-31.basil")
    with pytest.raises(ValidationError, match="Stripe credentials are prohibited in production"):
        Settings(
            environment="production",
            auth_mode="clerk",
            mock_auth_enabled=False,
            identity_jit_provisioning_enabled=False,
            clerk_jwks_url="https://identity.example.test/jwks",
            clerk_issuer="https://identity.example.test",
            clerk_audience="revenueos",
            database_url="postgresql+asyncpg://example.invalid/revenueos",
            cors_origins="https://app.example.test",
            allowed_hosts="app.example.test",
            stripe_secret_key="sk_test_synthetic_never_sent_wo048",
            feature_engage_enabled=False,
            feature_visual_evidence_enabled=False,
            feature_online_meeting_capture_enabled=False,
            feature_document_evidence_enabled=False,
            feature_create_enabled=False,
        )


def test_stripe_test_adapter_pins_version_item_periods_and_signed_test_events() -> None:
    settings = Settings(
        environment="test",
        stripe_secret_key="sk_test_synthetic_never_sent_wo048",
        billing_webhook_secret=WEBHOOK_SECRET,
    )
    provider = StripeTestBillingProvider(settings)
    period_start = datetime(2034, 1, 1, tzinfo=UTC)
    period_end = datetime(2034, 2, 1, tzinfo=UTC)
    snapshot = provider._subscription(
        {
            "id": "sub_test_001",
            "customer": "cus_test_001",
            "livemode": False,
            "status": "active",
            "cancel_at_period_end": False,
            "current_period_start": 1,
            "current_period_end": 2,
            "items": {
                "data": [
                    {
                        "price": {"id": "price_test_001"},
                        "current_period_start": int(period_start.timestamp()),
                        "current_period_end": int(period_end.timestamp()),
                    }
                ]
            },
        },
        datetime.now(UTC),
    )
    assert snapshot.current_period_start == period_start
    assert snapshot.current_period_end == period_end

    timestamp = int(time.time())
    event = {
        "id": "evt_test_stripe_001",
        "type": "customer.subscription.updated",
        "api_version": "2026-02-25.clover",
        "created": timestamp,
        "data": {
            "object": {
                "id": "sub_test_001",
                "customer": "cus_test_001",
                "livemode": False,
                "metadata": {"oryntela_organisation_id": str(PRIMARY_ORGANISATION_ID)},
            }
        },
    }
    payload = json.dumps(event, separators=(",", ":")).encode()
    signature = hmac.new(
        WEBHOOK_SECRET.encode(),
        f"{timestamp}.".encode() + payload,
        hashlib.sha256,
    ).hexdigest()
    verified = asyncio.run(provider.verify_webhook(payload, f"t={timestamp},v1={signature}"))
    assert verified.organisation_id == PRIMARY_ORGANISATION_ID
    assert verified.subscription_identifier == "sub_test_001"

    live_payload = payload.replace(b'"livemode":false', b'"livemode":true')
    live_signature = hmac.new(
        WEBHOOK_SECRET.encode(),
        f"{timestamp}.".encode() + live_payload,
        hashlib.sha256,
    ).hexdigest()
    with pytest.raises(PublicAPIError, match="outside the authorised test mode"):
        asyncio.run(provider.verify_webhook(live_payload, f"t={timestamp},v1={live_signature}"))


def test_stripe_test_adapter_uses_provider_proration_and_reuses_subscription_schedule() -> None:
    async def scenario() -> None:
        settings = Settings(
            environment="test",
            stripe_secret_key="sk_test_synthetic_never_sent_wo048",
            billing_webhook_secret=WEBHOOK_SECRET,
        )
        provider = StripeTestBillingProvider(settings)
        calls: list[tuple[str, str, list[tuple[str, str]], str | None]] = []
        period_start = datetime(2034, 3, 1, tzinfo=UTC)
        period_end = datetime(2034, 4, 1, tzinfo=UTC)

        def subscription_data(price_identifier: str) -> dict[str, object]:
            return {
                "id": "sub_test_change_001",
                "customer": "cus_test_change_001",
                "livemode": False,
                "status": "active",
                "cancel_at_period_end": False,
                "schedule": "sub_sched_test_001",
                "items": {
                    "data": [
                        {
                            "id": "si_test_001",
                            "price": {"id": price_identifier},
                            "current_period_start": int(period_start.timestamp()),
                            "current_period_end": int(period_end.timestamp()),
                        }
                    ]
                },
            }

        async def request(
            method: str,
            path: str,
            *,
            form: list[tuple[str, str]] | None = None,
            idempotency_key: str | None = None,
        ) -> dict[str, object]:
            calls.append((method, path, form or [], idempotency_key))
            if path.startswith("/v1/prices/"):
                amount = 35000 if path.endswith("growth_monthly") else 20000
                return {
                    "id": path.rsplit("/", 1)[-1],
                    "livemode": False,
                    "active": True,
                    "currency": "aud",
                    "unit_amount": amount,
                    "recurring": {"interval": "month", "interval_count": 1},
                }
            if method == "GET" and path == "/v1/subscriptions/sub_test_change_001":
                return subscription_data("price_test_core_monthly")
            if method == "POST" and path == "/v1/subscriptions/sub_test_change_001":
                upgraded = subscription_data("price_test_growth_monthly")
                upgraded["latest_invoice"] = {
                    "id": "in_test_proration_001",
                    "customer": "cus_test_change_001",
                    "livemode": False,
                    "created": int(period_start.timestamp()),
                    "amount_due": 15750,
                    "amount_paid": 15750,
                    "amount_refunded": 0,
                    "currency": "aud",
                    "status": "paid",
                    "parent": {"subscription_details": {"subscription": "sub_test_change_001"}},
                    "hosted_invoice_url": "https://invoice.stripe.test/i/in_test_proration_001",
                }
                return upgraded
            return {"id": "sub_sched_test_001", "livemode": False}

        provider._request = request  # type: ignore[method-assign]
        result = await provider.apply_plan_upgrade(
            "sub_test_change_001",
            price=ProviderPriceReference(
                identifier="price_test_growth_monthly",
                plan_code="growth",
                billing_interval="monthly",
                amount=Decimal("350.00"),
            ),
            idempotency_key="upgrade-provider-proration-0001",
        )
        assert result.subscription.price_identifier == "price_test_growth_monthly"
        assert result.invoice is not None and result.invoice.amount_due == Decimal("157.50")
        update_call = next(
            call for call in calls if call[1] == "/v1/subscriptions/sub_test_change_001" and call[0] == "POST"
        )
        assert ("items[0][id]", "si_test_001") in update_call[2]
        assert ("items[0][price]", "price_test_growth_monthly") in update_call[2]
        assert ("proration_behavior", "always_invoice") in update_call[2]
        assert ("payment_behavior", "pending_if_incomplete") in update_call[2]
        assert update_call[3] == "upgrade-provider-proration-0001:upgrade"
        assert any(call[1] == "/v1/subscription_schedules/sub_sched_test_001/release" for call in calls)

        calls.clear()
        await provider.schedule_plan_change(
            "sub_test_change_001",
            price=ProviderPriceReference(
                identifier="price_test_core_monthly",
                plan_code="core",
                billing_interval="monthly",
                amount=Decimal("200.00"),
            ),
            idempotency_key="scheduled-provider-downgrade-0001",
        )
        assert not any(call[1] == "/v1/subscription_schedules" for call in calls)
        phase_call = next(
            call for call in calls if call[0] == "POST" and call[1] == "/v1/subscription_schedules/sub_sched_test_001"
        )
        assert ("phases[1][items][0][price]", "price_test_core_monthly") in phase_call[2]
        assert ("phases[1][proration_behavior]", "none") in phase_call[2]

    asyncio.run(scenario())
