from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import os
import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import delete, func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from revenueos.billing_contracts import BillingOperationRequest, CheckoutCreateRequest, PlanChangeRequest
from revenueos.billing_provider import DeterministicBillingProvider
from revenueos.billing_services import BillingService
from revenueos.commercial_services import PLAN_CATALOGUE, ensure_plan_catalogue
from revenueos.config import Settings
from revenueos.database import set_tenant_database_context
from revenueos.errors import PublicAPIError
from revenueos.legal_releases import CURRENT_PRIVACY_NOTICE, CURRENT_TERMS_RELEASE
from revenueos.models import (
    BillingAccount,
    BillingInvoiceProjection,
    BillingOperation,
    BillingProviderEventReceipt,
    BillingSubscription,
    Organisation,
    OrganisationCommercialState,
    OrganisationMembership,
    OrganisationModuleEntitlement,
    TermsAcceptance,
    User,
)

WEBHOOK_SECRET = "postgresql-billing-webhook-secret-0001"


def _signed_event(
    *,
    event_id: str,
    event_type: str,
    organisation_id: uuid.UUID,
    customer_id: str,
    subscription_id: str | None = None,
    invoice_id: str | None = None,
    object_id: str | None = None,
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
            "created": int(datetime.now(UTC).timestamp()),
        },
        separators=(",", ":"),
    ).encode()
    digest = hmac.new(WEBHOOK_SECRET.encode(), payload, hashlib.sha256).hexdigest()
    return payload, f"sha256={digest}"


def test_postgresql_billing_idempotency_overlap_and_lifecycle_races_converge() -> None:
    database_url = os.getenv("DATABASE_URL", "")
    if not database_url.startswith(("postgresql", "postgres")):
        pytest.skip("A PostgreSQL DATABASE_URL is required for billing concurrency tests.")

    async def scenario() -> None:
        engine = create_async_engine(database_url)
        factory = async_sessionmaker(engine, expire_on_commit=False)
        settings = Settings(
            environment="test",
            auth_mode="mock",
            mock_auth_enabled=True,
            database_url=database_url,
            feature_billing_enabled=True,
            billing_provider_name="deterministic",
            billing_webhook_secret=WEBHOOK_SECRET,
        )
        provider = DeterministicBillingProvider(settings)
        suffix = uuid.uuid4().hex
        checkout_event_id = f"evt_postgres_checkout_{suffix}"
        overlap_event_id = f"evt_postgres_overlap_{suffix}"
        invoice_event_id = f"evt_postgres_invoice_{suffix}"
        organisation_id, user_id = uuid.uuid4(), uuid.uuid4()
        overlap_organisation_id, overlap_user_id = uuid.uuid4(), uuid.uuid4()

        async def add_tenant(tenant_id: uuid.UUID, tenant_user_id: uuid.UUID, label: str) -> None:
            async with factory() as session:
                session.add(
                    Organisation(
                        id=tenant_id,
                        name=f"Billing concurrency {label}",
                        slug=f"billing-concurrency-{label}-{tenant_id}",
                    )
                )
                session.add(
                    User(
                        id=tenant_user_id,
                        external_auth_id=f"billing-concurrency-{label}-{tenant_user_id}",
                        email=f"billing-{label}-{tenant_user_id}@example.test",
                        display_name=f"Billing {label} User",
                    )
                )
                await session.flush()
                session.add(
                    OrganisationMembership(
                        organisation_id=tenant_id,
                        user_id=tenant_user_id,
                        role="admin",
                    )
                )
                session.add(
                    TermsAcceptance(
                        organisation_id=tenant_id,
                        accepted_by_user_id=tenant_user_id,
                        release_status=CURRENT_TERMS_RELEASE.status,
                        terms_version=CURRENT_TERMS_RELEASE.version,
                        terms_sha256=CURRENT_TERMS_RELEASE.sha256,
                        terms_effective_date=CURRENT_TERMS_RELEASE.effective_date,
                        accepted_at=datetime.now(UTC),
                        acceptance_source="subscription_checkout",
                        privacy_notice_version=CURRENT_PRIVACY_NOTICE.version,
                        privacy_notice_sha256=CURRENT_PRIVACY_NOTICE.sha256,
                        privacy_notice_effective_date=CURRENT_PRIVACY_NOTICE.effective_date,
                        privacy_notice_presented_at=datetime.now(UTC),
                    )
                )
                await session.commit()

        try:
            await add_tenant(organisation_id, user_id, "primary")
            await add_tenant(overlap_organisation_id, overlap_user_id, "overlap")

            async def checkout_attempt() -> object:
                async with factory() as session:
                    await set_tenant_database_context(session, organisation_id)
                    try:
                        return await BillingService(session, settings, provider).create_checkout(
                            organisation_id,
                            user_id,
                            CheckoutCreateRequest(
                                plan_code="core",
                                billing_interval="monthly",
                                idempotency_key="postgres-concurrent-checkout-0001",
                            ),
                        )
                    except PublicAPIError as exc:
                        return exc

            checkout_attempts = await asyncio.gather(checkout_attempt(), checkout_attempt())
            checkout_successes = [item for item in checkout_attempts if not isinstance(item, PublicAPIError)]
            checkout_failures = [item for item in checkout_attempts if isinstance(item, PublicAPIError)]
            assert checkout_successes
            assert all(
                failure.code in {"billing_checkout_reconciliation_required", "billing_state_conflict"}
                for failure in checkout_failures
            )
            assert len(provider.checkouts) == 1

            async with factory() as session:
                await set_tenant_database_context(session, organisation_id)
                operation = await session.scalar(
                    select(BillingOperation).where(
                        BillingOperation.organisation_id == organisation_id,
                        BillingOperation.operation_type == "checkout",
                    )
                )
                account = await session.scalar(
                    select(BillingAccount).where(BillingAccount.organisation_id == organisation_id)
                )
                assert operation is not None and operation.provider_object_id is not None
                assert account is not None
                assert (
                    await session.scalar(
                        select(func.count())
                        .select_from(BillingOperation)
                        .where(
                            BillingOperation.organisation_id == organisation_id,
                            BillingOperation.operation_type == "checkout",
                        )
                    )
                    == 1
                )
                checkout = await provider.retrieve_checkout(operation.provider_object_id)
                subscription = provider.complete_checkout(
                    checkout.identifier,
                    period_start=datetime.now(UTC),
                    period_end=datetime.now(UTC) + timedelta(days=30),
                )
                checkout_payload, checkout_signature = _signed_event(
                    event_id=checkout_event_id,
                    event_type="checkout.session.completed",
                    organisation_id=organisation_id,
                    customer_id=account.provider_customer_id,
                    subscription_id=subscription.identifier,
                    object_id=checkout.identifier,
                )
                assert (
                    await BillingService(session, settings, provider).process_webhook(
                        checkout_payload, checkout_signature
                    )
                    == "processed"
                )

            # Prove a webhook arriving after the provider mutation but before the local
            # operation commit is retryable and does not poison its immutable receipt.
            overlap_customer_id = f"cus_test_overlap_{overlap_organisation_id.hex}"
            async with factory() as session:
                await set_tenant_database_context(session, overlap_organisation_id)
                overlap_account = BillingAccount(
                    id=uuid.uuid4(),
                    organisation_id=overlap_organisation_id,
                    provider="deterministic",
                    provider_mode="test",
                    provider_customer_id=overlap_customer_id,
                    status="active",
                )
                session.add(overlap_account)
                await session.commit()

            async with factory() as operation_session:
                await set_tenant_database_context(operation_session, overlap_organisation_id)
                await ensure_plan_catalogue(operation_session)
                core = next(plan for plan in PLAN_CATALOGUE if plan.code == "core")
                overlap_checkout = await provider.create_checkout(
                    organisation_id=overlap_organisation_id,
                    customer_identifier=overlap_customer_id,
                    price=BillingService(operation_session, settings, provider)._provider_price(core, "monthly"),
                    idempotency_key="checkout-overlap-provider-0001",
                )
                overlap_subscription = provider.complete_checkout(
                    overlap_checkout.identifier,
                    period_start=datetime.now(UTC),
                    period_end=datetime.now(UTC) + timedelta(days=30),
                )
                operation_session.add(
                    BillingOperation(
                        id=uuid.uuid4(),
                        organisation_id=overlap_organisation_id,
                        requested_by_user_id=overlap_user_id,
                        provider_mode="test",
                        operation_type="checkout",
                        idempotency_key="postgres-overlap-checkout-0001",
                        request_fingerprint="a" * 64,
                        status="pending",
                        plan_version_id=core.id,
                        billing_interval="monthly",
                        amount=Decimal("200.00"),
                        currency="AUD",
                        provider_object_id=overlap_checkout.identifier,
                        hosted_url=overlap_checkout.hosted_url,
                    )
                )
                await operation_session.flush()
                overlap_payload, overlap_signature = _signed_event(
                    event_id=overlap_event_id,
                    event_type="checkout.session.completed",
                    organisation_id=overlap_organisation_id,
                    customer_id=overlap_customer_id,
                    subscription_id=overlap_subscription.identifier,
                    object_id=overlap_checkout.identifier,
                )
                async with factory() as webhook_session:
                    with pytest.raises(PublicAPIError) as overlap_error:
                        await BillingService(webhook_session, settings, provider).process_webhook(
                            overlap_payload, overlap_signature
                        )
                    assert overlap_error.value.code == "billing_webhook_reconciliation_required"
                    assert overlap_error.value.status_code == 503
                await operation_session.commit()

            async with factory() as session:
                await set_tenant_database_context(session, overlap_organisation_id)
                assert (
                    await session.scalar(
                        select(func.count())
                        .select_from(BillingProviderEventReceipt)
                        .where(BillingProviderEventReceipt.provider_event_id == overlap_event_id)
                    )
                    == 0
                )
                assert (
                    await BillingService(session, settings, provider).process_webhook(
                        overlap_payload, overlap_signature
                    )
                    == "processed"
                )

            async def change_plan() -> object:
                async with factory() as session:
                    await set_tenant_database_context(session, organisation_id)
                    try:
                        return await BillingService(session, settings, provider).change_plan(
                            organisation_id,
                            user_id,
                            PlanChangeRequest(
                                plan_code="growth",
                                billing_interval="monthly",
                                idempotency_key="postgres-concurrent-upgrade-0001",
                            ),
                        )
                    except PublicAPIError as exc:
                        return exc

            upgrades = await asyncio.gather(change_plan(), change_plan())
            assert all(not isinstance(item, PublicAPIError) for item in upgrades)

            upgraded_subscription = next(
                item for item in provider.subscriptions.values() if item.identifier == subscription.identifier
            )
            assert upgraded_subscription.latest_invoice_identifier is not None
            invoice_payload, invoice_signature = _signed_event(
                event_id=invoice_event_id,
                event_type="invoice.paid",
                organisation_id=organisation_id,
                customer_id=account.provider_customer_id,
                subscription_id=subscription.identifier,
                invoice_id=upgraded_subscription.latest_invoice_identifier,
                object_id=upgraded_subscription.latest_invoice_identifier,
            )

            async def deliver_invoice() -> str:
                async with factory() as session:
                    return await BillingService(session, settings, provider).process_webhook(
                        invoice_payload, invoice_signature
                    )

            invoice_outcomes = await asyncio.gather(deliver_invoice(), deliver_invoice())
            assert invoice_outcomes.count("duplicate") == 1
            assert next(outcome for outcome in invoice_outcomes if outcome != "duplicate") in {
                "processed",
                "ignored_stale",
            }

            async with factory() as session:
                await set_tenant_database_context(session, organisation_id)
                await BillingService(session, settings, provider).cancel(
                    organisation_id,
                    user_id,
                    BillingOperationRequest(idempotency_key="postgres-cancel-seed-0001"),
                )

            async def subscription_action(action: str) -> object:
                async with factory() as session:
                    await set_tenant_database_context(session, organisation_id)
                    service = BillingService(session, settings, provider)
                    try:
                        if action == "cancel":
                            return await service.cancel(
                                organisation_id,
                                user_id,
                                BillingOperationRequest(idempotency_key="postgres-cancel-race-0001"),
                            )
                        return await service.reactivate(
                            organisation_id,
                            user_id,
                            BillingOperationRequest(idempotency_key="postgres-reactivate-race-0001"),
                        )
                    except PublicAPIError as exc:
                        return exc

            lifecycle_results = await asyncio.gather(subscription_action("cancel"), subscription_action("reactivate"))
            assert all(not isinstance(item, PublicAPIError) for item in lifecycle_results)

            async with factory() as session:
                await set_tenant_database_context(session, organisation_id)
                stored_subscription = await session.scalar(
                    select(BillingSubscription).where(BillingSubscription.organisation_id == organisation_id)
                )
                assert stored_subscription is not None
                provider_subscription = await provider.retrieve_subscription(
                    stored_subscription.provider_subscription_id
                )
                assert stored_subscription.status == provider_subscription.status
                assert stored_subscription.cancel_at_period_end == provider_subscription.cancel_at_period_end
                assert (
                    await session.scalar(
                        select(func.count())
                        .select_from(BillingOperation)
                        .where(
                            BillingOperation.organisation_id == organisation_id,
                            BillingOperation.operation_type == "plan_change",
                        )
                    )
                    == 1
                )
                assert (
                    await session.scalar(
                        select(func.count())
                        .select_from(BillingProviderEventReceipt)
                        .where(BillingProviderEventReceipt.provider_event_id == invoice_event_id)
                    )
                    == 1
                )
                assert (
                    await session.scalar(
                        select(func.count())
                        .select_from(BillingInvoiceProjection)
                        .where(BillingInvoiceProjection.organisation_id == organisation_id)
                    )
                    == 2
                )

                session.add(
                    BillingSubscription(
                        id=uuid.uuid4(),
                        organisation_id=organisation_id,
                        billing_account_id=stored_subscription.billing_account_id,
                        provider_subscription_id="sub_test_forbidden_second_current",
                        plan_version_id=stored_subscription.plan_version_id,
                        billing_interval="monthly",
                        amount=Decimal("350.00"),
                        currency="AUD",
                        status="active",
                        current_period_start=datetime.now(UTC),
                        current_period_end=datetime.now(UTC) + timedelta(days=30),
                        payment_status="paid",
                        paid_period_start=datetime.now(UTC),
                        paid_through=datetime.now(UTC) + timedelta(days=30),
                        cancel_at_period_end=False,
                        provider_updated_at=datetime.now(UTC),
                        last_provider_event_id="evt_forbidden_second_current",
                        lock_version=1,
                    )
                )
                with pytest.raises(IntegrityError):
                    await session.commit()
        finally:
            async with factory() as session:
                for tenant_id in (organisation_id, overlap_organisation_id):
                    await set_tenant_database_context(session, tenant_id)
                    await session.execute(
                        update(OrganisationCommercialState)
                        .where(OrganisationCommercialState.organisation_id == tenant_id)
                        .values(
                            source="migration",
                            actor_reference="billing-concurrency-test-cleanup",
                            reason="Preserve compatibility with the repository-wide PostgreSQL downgrade proof.",
                        )
                    )
                    await session.execute(
                        delete(OrganisationModuleEntitlement).where(
                            OrganisationModuleEntitlement.organisation_id == tenant_id
                        )
                    )
                    await session.commit()
            await engine.dispose()

    asyncio.run(scenario())
