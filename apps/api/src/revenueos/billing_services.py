from __future__ import annotations

import hashlib
import json
import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from decimal import Decimal
from typing import Literal, cast
from urllib.parse import urlsplit
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from revenueos.billing_contracts import (
    BillingInvoiceResponse,
    BillingOperationRequest,
    BillingPlanOptionResponse,
    BillingProjectionResponse,
    BillingSubscriptionResponse,
    BillingSubscriptionStatus,
    BillingSuccessResponse,
    CheckoutCreateRequest,
    CheckoutCreateResponse,
    HostedActionResponse,
    InvoiceStatus,
    PlanChangeRequest,
)
from revenueos.billing_provider import (
    BillingProvider,
    ProviderInvoiceSnapshot,
    ProviderPlanChangeResult,
    ProviderPriceReference,
    ProviderSubscriptionSnapshot,
    VerifiedBillingEvent,
)
from revenueos.billing_repositories import BillingRepository
from revenueos.commercial_contracts import BillingInterval, PlanCode
from revenueos.commercial_services import CommercialService, ensure_plan_catalogue
from revenueos.config import Settings
from revenueos.credit_services import CreditService
from revenueos.database import set_tenant_database_context
from revenueos.errors import PublicAPIError
from revenueos.models import (
    BillingAccount,
    BillingInvoiceProjection,
    BillingOperation,
    BillingProviderEventReceipt,
    BillingSubscription,
    CommercialPlanVersion,
    OrganisationCommercialState,
)


def utc_now() -> datetime:
    return datetime.now(UTC)


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


def _amount_text(value: Decimal) -> str:
    return f"{value:.2f}"


def _fingerprint(value: dict[str, object]) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


_PLAN_RANK: dict[PlanCode, int] = {"core": 0, "growth": 1, "complete": 2, "enterprise": 3}


class BillingPriceMapper:
    """Maps the canonical WO-047 catalogue to bounded provider execution references."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def provider_identifier(self, plan_code: PlanCode, interval: BillingInterval) -> str:
        if self.settings.billing_provider_name == "deterministic":
            return f"price_test_{plan_code}_{interval}_aud"
        configured = self.settings.stripe_price_identifiers[(plan_code, interval)]
        if configured is None:
            raise PublicAPIError(
                "billing_price_mapping_unavailable",
                "The selected billing option is temporarily unavailable.",
                503,
            )
        return configured

    def reverse(self, identifier: str) -> tuple[PlanCode, BillingInterval] | None:
        for plan_code in cast(tuple[PlanCode, ...], ("core", "growth", "complete")):
            for interval in cast(tuple[BillingInterval, ...], ("monthly", "annual")):
                if self.provider_identifier(plan_code, interval) == identifier:
                    return plan_code, interval
        return None


class BillingService:
    def __init__(
        self,
        session: AsyncSession,
        settings: Settings,
        provider: BillingProvider,
        *,
        now: Callable[[], datetime] = utc_now,
    ) -> None:
        self.session = session
        self.settings = settings
        self.provider = provider
        self.repository = BillingRepository(session)
        self.prices = BillingPriceMapper(settings)
        self._now = now

    async def projection(self, organisation_id: UUID) -> BillingProjectionResponse:
        await ensure_plan_catalogue(self.session)
        account = await self.repository.account(organisation_id, self.provider.name, self.provider.mode)
        subscription = await self.repository.subscription(organisation_id)
        invoices = await self.repository.invoices(organisation_id)
        return BillingProjectionResponse(
            configured=account is not None,
            provider=self.provider.name,
            mode="test",
            subscription=await self._subscription_response(subscription) if subscription is not None else None,
            invoices=[self._invoice_response(invoice) for invoice in invoices],
            checkout_options=await self._checkout_options(),
            portal_available=account is not None and self.settings.feature_billing_enabled,
            message=self._projection_message(account, subscription),
        )

    async def success_status(self, organisation_id: UUID) -> BillingSuccessResponse:
        subscription = await self.repository.subscription(organisation_id)
        if subscription is None:
            return BillingSuccessResponse(
                confirmed=False,
                status="not_configured",
                message="Payment confirmation is pending. No entitlement change has been made.",
            )
        status = cast(BillingSubscriptionStatus, subscription.status)
        confirmed = status in {"active", "cancel_at_period_end"}
        return BillingSuccessResponse(
            confirmed=confirmed,
            status=status,
            message=(
                "Payment is confirmed and the organisation subscription is active."
                if confirmed
                else "Payment confirmation is pending. No entitlement change has been made from this page."
            ),
        )

    async def create_checkout(
        self,
        organisation_id: UUID,
        user_id: UUID,
        request: CheckoutCreateRequest,
    ) -> CheckoutCreateResponse:
        self._require_enabled()
        if request.plan_code == "enterprise":
            raise PublicAPIError(
                "enterprise_checkout_unavailable",
                "Enterprise uses a contact and manual commercial process; self-service checkout is unavailable.",
                409,
            )
        await ensure_plan_catalogue(self.session)
        plan = await self._plan(request.plan_code)
        amount = self._plan_amount(plan, request.billing_interval)
        fingerprint = _fingerprint(
            {"plan_code": request.plan_code, "billing_interval": request.billing_interval, "amount": str(amount)}
        )
        existing = await self.repository.operation(organisation_id, "checkout", request.idempotency_key, lock=True)
        if existing is not None:
            self._require_same_fingerprint(existing, fingerprint)
            if existing.hosted_url is not None and existing.provider_object_id is not None:
                checkout = await self.provider.retrieve_checkout(existing.provider_object_id)
                if checkout.status == "expired":
                    existing.status = "failed"
                    existing.safe_error_code = "billing_checkout_expired"
                    existing.completed_at = _aware(self._now())
                    await self._commit(organisation_id)
                    raise PublicAPIError(
                        "billing_checkout_expired",
                        "That hosted checkout has expired. Start a new checkout with a new retry key.",
                        409,
                    )
                return self._checkout_response(
                    existing,
                    request.plan_code,
                    request.billing_interval,
                    amount,
                    status="confirmation_pending" if checkout.status == "complete" else "redirect_ready",
                )
        unresolved = await self.session.scalar(
            select(BillingOperation)
            .where(
                BillingOperation.organisation_id == organisation_id,
                BillingOperation.operation_type == "checkout",
                BillingOperation.status.in_(("pending", "unknown")),
                BillingOperation.id != (existing.id if existing is not None else uuid.UUID(int=0)),
            )
            .with_for_update()
        )
        if unresolved is not None:
            raise PublicAPIError(
                "billing_checkout_reconciliation_required",
                "A previous checkout is still open or awaiting reconciliation. Retry that checkout or check status before starting another.",
                409,
            )
        current = await self.repository.subscription(organisation_id, lock=True)
        if current is not None and current.status != "cancelled":
            raise PublicAPIError(
                "billing_subscription_exists",
                "This organisation already has a subscription or unresolved checkout. Use billing management or check status before trying again.",
                409,
            )
        operation = existing or BillingOperation(
            id=uuid.uuid4(),
            organisation_id=organisation_id,
            requested_by_user_id=user_id,
            operation_type="checkout",
            idempotency_key=request.idempotency_key,
            request_fingerprint=fingerprint,
            status="pending",
            plan_version_id=plan.id,
            billing_interval=request.billing_interval,
            amount=amount,
            currency="AUD",
        )
        if existing is None:
            self.session.add(operation)
            try:
                await self.session.flush()
            except IntegrityError as exc:
                await self.session.rollback()
                await set_tenant_database_context(self.session, organisation_id)
                raise PublicAPIError(
                    "billing_checkout_reconciliation_required",
                    "Another checkout is already in progress. Check its status before trying again.",
                    409,
                ) from exc
        try:
            account = await self._ensure_account(organisation_id)
            checkout = await self.provider.create_checkout(
                organisation_id=organisation_id,
                customer_identifier=account.provider_customer_id,
                price=self._provider_price(plan, request.billing_interval),
                idempotency_key=f"checkout:{organisation_id}:{request.idempotency_key}",
            )
            if checkout.customer_identifier != account.provider_customer_id:
                raise PublicAPIError("billing_customer_mismatch", "Checkout could not be safely confirmed.", 409)
            hosted_url = self._safe_hosted_url(checkout.hosted_url)
            operation.provider_object_id = checkout.identifier
            operation.hosted_url = hosted_url
            # The hosted session exists, but payment is unresolved until the verified completion event.
            operation.status = "pending"
            operation.safe_error_code = None
            operation.completed_at = None
            await self._commit(organisation_id)
            return self._checkout_response(operation, request.plan_code, request.billing_interval, amount)
        except PublicAPIError as exc:
            operation.status = "unknown" if exc.status_code >= 500 else "failed"
            operation.safe_error_code = exc.code
            operation.completed_at = _aware(self._now())
            await self._commit(organisation_id)
            raise

    async def create_portal(
        self, organisation_id: UUID, user_id: UUID, request: BillingOperationRequest
    ) -> HostedActionResponse:
        self._require_enabled()
        account = await self.repository.account(organisation_id, self.provider.name, self.provider.mode)
        if account is None:
            raise PublicAPIError("billing_not_configured", "Billing is not configured for this organisation.", 409)
        fingerprint = _fingerprint({"billing_account_id": str(account.id)})
        existing = await self.repository.operation(organisation_id, "portal", request.idempotency_key, lock=True)
        if existing is not None:
            self._require_same_fingerprint(existing, fingerprint)
            if existing.hosted_url is not None:
                return HostedActionResponse(
                    operation_id=existing.id,
                    hosted_url=existing.hosted_url,
                    status="succeeded",
                    message="Hosted billing management is ready.",
                )
        operation = existing or self._operation(
            organisation_id, user_id, "portal", request.idempotency_key, fingerprint
        )
        if existing is None:
            self.session.add(operation)
            await self.session.flush()
        try:
            hosted_url = await self.provider.create_portal(
                account.provider_customer_id,
                idempotency_key=f"portal:{organisation_id}:{request.idempotency_key}",
            )
            operation.hosted_url = self._safe_hosted_url(hosted_url)
            operation.status = "succeeded"
            operation.completed_at = _aware(self._now())
            await self._commit(organisation_id)
            return HostedActionResponse(
                operation_id=operation.id,
                hosted_url=operation.hosted_url,
                status="succeeded",
                message="Hosted billing management is ready. Provider changes reconcile through verified webhooks.",
            )
        except PublicAPIError as exc:
            await self._record_operation_failure(organisation_id, operation, exc)
            raise

    async def cancel(
        self, organisation_id: UUID, user_id: UUID, request: BillingOperationRequest
    ) -> HostedActionResponse:
        return await self._subscription_action(organisation_id, user_id, request, action="cancel")

    async def reactivate(
        self, organisation_id: UUID, user_id: UUID, request: BillingOperationRequest
    ) -> HostedActionResponse:
        return await self._subscription_action(organisation_id, user_id, request, action="reactivate")

    async def change_plan(
        self, organisation_id: UUID, user_id: UUID, request: PlanChangeRequest
    ) -> HostedActionResponse:
        self._require_enabled()
        if request.plan_code == "enterprise":
            raise PublicAPIError(
                "enterprise_plan_change_unavailable",
                "Enterprise changes require the manual commercial process.",
                409,
            )
        subscription = await self.repository.subscription(organisation_id, lock=True)
        if subscription is None:
            raise PublicAPIError("billing_subscription_not_found", "No subscription is available to change.", 404)
        plan = await self._plan(request.plan_code)
        amount = self._plan_amount(plan, request.billing_interval)
        fingerprint = _fingerprint(
            {
                "subscription_id": str(subscription.id),
                "plan_code": request.plan_code,
                "billing_interval": request.billing_interval,
            }
        )
        existing = await self.repository.operation(organisation_id, "plan_change", request.idempotency_key, lock=True)
        if existing is not None:
            self._require_same_fingerprint(existing, fingerprint)
            if existing.status == "succeeded":
                return self._plan_change_response(existing, confirmed=True)
            if existing.status == "failed":
                raise PublicAPIError(
                    "billing_operation_failed",
                    "That billing operation was rejected. Start a new request with a new retry key.",
                    409,
                )
        if subscription.status != "active" or subscription.cancel_at_period_end:
            raise PublicAPIError(
                "billing_plan_change_unavailable",
                "Plan changes require an active paid subscription. Resolve payment attention or reverse any scheduled cancellation first.",
                409,
            )
        current_plan = await self.session.get(CommercialPlanVersion, subscription.plan_version_id)
        if current_plan is None:
            raise PublicAPIError("billing_projection_invalid", "Billing information is temporarily unavailable.", 503)
        current_plan_code = cast(PlanCode, current_plan.code)
        is_higher_tier = _PLAN_RANK[request.plan_code] > _PLAN_RANK[current_plan_code]
        cancels_pending_change = (
            current_plan_code == request.plan_code
            and subscription.billing_interval == request.billing_interval
            and subscription.pending_plan_version_id is not None
        )
        operation = existing or self._operation(
            organisation_id,
            user_id,
            "plan_change",
            request.idempotency_key,
            fingerprint,
            plan_version_id=plan.id,
            billing_interval=request.billing_interval,
            amount=amount,
        )
        if existing is None:
            self.session.add(operation)
            await self.session.flush()
        account = await self.repository.account(organisation_id, self.provider.name, self.provider.mode)
        if account is None:
            raise PublicAPIError("billing_not_configured", "Billing is not configured for this organisation.", 409)
        provider_key = f"plan-change:{organisation_id}:{request.idempotency_key}"
        try:
            if existing is not None and not cancels_pending_change:
                reconciled = await self.provider.reconcile_plan_change(subscription.provider_subscription_id)
                self._verify_plan_change_ownership(account, subscription, reconciled.subscription)
                mapped = self.prices.reverse(reconciled.subscription.price_identifier)
                if (
                    mapped == (request.plan_code, request.billing_interval)
                    and reconciled.subscription.status == "active"
                    and (not is_higher_tier or reconciled.invoice is not None)
                ):
                    await self._apply_plan_change_result(
                        organisation_id,
                        account,
                        subscription,
                        reconciled,
                        event_identifier=f"operation:{operation.id}:reconcile",
                    )
                    subscription.pending_plan_version_id = None
                    subscription.pending_billing_interval = None
                    operation.status = "succeeded"
                    operation.safe_error_code = None
                    operation.completed_at = _aware(self._now())
                    await self._commit(organisation_id)
                    return self._plan_change_response(operation, confirmed=True)

            if current_plan_code == request.plan_code and subscription.billing_interval == request.billing_interval:
                if subscription.pending_plan_version_id is None:
                    raise PublicAPIError(
                        "billing_plan_unchanged", "The selected plan and billing interval are already active.", 409
                    )
                snapshot = await self.provider.cancel_scheduled_plan_change(
                    subscription.provider_subscription_id,
                    idempotency_key=provider_key,
                )
                self._verify_plan_change_ownership(account, subscription, snapshot)
                subscription.pending_plan_version_id = None
                subscription.pending_billing_interval = None
                subscription.lock_version += 1
            elif is_higher_tier:
                result = await self.provider.apply_plan_upgrade(
                    subscription.provider_subscription_id,
                    price=self._provider_price(plan, request.billing_interval),
                    idempotency_key=provider_key,
                )
                self._verify_plan_change_ownership(account, subscription, result.subscription)
                mapped = self.prices.reverse(result.subscription.price_identifier)
                if (
                    mapped != (request.plan_code, request.billing_interval)
                    or result.subscription.status != "active"
                    or result.invoice is None
                ):
                    operation.status = "unknown"
                    operation.safe_error_code = "billing_upgrade_confirmation_pending"
                    operation.completed_at = _aware(self._now())
                    await self._commit(organisation_id)
                    return self._plan_change_response(operation, confirmed=False)
                await self._apply_plan_change_result(
                    organisation_id,
                    account,
                    subscription,
                    result,
                    event_identifier=f"operation:{operation.id}:upgrade",
                )
                subscription.pending_plan_version_id = None
                subscription.pending_billing_interval = None
            else:
                snapshot = await self.provider.schedule_plan_change(
                    subscription.provider_subscription_id,
                    price=self._provider_price(plan, request.billing_interval),
                    idempotency_key=provider_key,
                )
                self._verify_plan_change_ownership(account, subscription, snapshot)
                subscription.pending_plan_version_id = plan.id
                subscription.pending_billing_interval = request.billing_interval
                subscription.lock_version += 1
            operation.status = "succeeded"
            operation.safe_error_code = None
            operation.completed_at = _aware(self._now())
            await self._commit(organisation_id)
            return self._plan_change_response(operation, confirmed=True)
        except PublicAPIError as exc:
            await self._record_operation_failure(organisation_id, operation, exc)
            raise

    async def process_webhook(
        self, payload: bytes, signature: str | None
    ) -> Literal["processed", "duplicate", "ignored_stale", "reconciliation_required"]:
        self._require_enabled()
        event = await self.provider.verify_webhook(payload, signature)
        await set_tenant_database_context(self.session, event.organisation_id)
        account = await self.repository.account(event.organisation_id, self.provider.name, self.provider.mode)
        if account is None or account.provider_customer_id != event.customer_identifier:
            raise PublicAPIError(
                "billing_webhook_mapping_unverified",
                "Webhook billing ownership could not be verified.",
                409,
            )
        existing = await self.repository.provider_event_receipt(
            event.organisation_id, self.provider.name, self.provider.mode, event.identifier
        )
        if existing is not None:
            return "duplicate"
        result: Literal["processed", "ignored_stale", "reconciliation_required"]
        if event.event_type == "checkout.session.completed":
            result = await self._process_checkout_event(account, event)
        elif event.event_type.startswith("customer.subscription."):
            result = await self._process_subscription_event(account, event)
        elif event.event_type.startswith("invoice."):
            result = await self._process_invoice_event(account, event)
        else:
            result = "reconciliation_required"
        self.session.add(
            BillingProviderEventReceipt(
                id=uuid.uuid4(),
                organisation_id=event.organisation_id,
                provider=self.provider.name,
                provider_mode=self.provider.mode,
                provider_event_id=event.identifier,
                event_type=event.event_type,
                provider_created_at=event.created_at,
                result=result,
                safe_detail_code="unsupported_event" if result == "reconciliation_required" else None,
            )
        )
        try:
            await self._commit(event.organisation_id)
        except PublicAPIError as exc:
            if isinstance(exc.__cause__, IntegrityError):
                await set_tenant_database_context(self.session, event.organisation_id)
                duplicate = await self.repository.provider_event_receipt(
                    event.organisation_id, self.provider.name, self.provider.mode, event.identifier
                )
                if duplicate is not None:
                    return "duplicate"
            raise
        return result

    async def _process_checkout_event(
        self, account: BillingAccount, event: VerifiedBillingEvent
    ) -> Literal["processed", "ignored_stale", "reconciliation_required"]:
        if event.object_identifier is None:
            return "reconciliation_required"
        checkout = await self.provider.retrieve_checkout(event.object_identifier)
        if checkout.customer_identifier != account.provider_customer_id or checkout.status != "complete":
            return "reconciliation_required"
        operation = await self.session.scalar(
            select(BillingOperation).where(
                BillingOperation.organisation_id == event.organisation_id,
                BillingOperation.operation_type.in_(("checkout", "credit_purchase")),
                BillingOperation.provider_object_id == checkout.identifier,
            )
        )
        if operation is None:
            return "reconciliation_required"
        if operation.operation_type == "credit_purchase":
            if event.payment_status != "paid" or checkout.payment_status != "paid":
                return "reconciliation_required"
            if (
                event.amount_minor_units is None
                or event.currency != "AUD"
                or event.credit_pack_version_id is None
                or operation.credit_pack_version_id != event.credit_pack_version_id
                or operation.amount is None
                or int(operation.amount * 100) != event.amount_minor_units
            ):
                raise PublicAPIError(
                    "credit_purchase_payment_mismatch",
                    "The verified Credit-pack payment did not match the server-owned purchase operation.",
                    409,
                )
            operation.status = "succeeded"
            operation.completed_at = _aware(self._now())
            await CreditService(self.session, self.settings, clock=self._now).grant_verified_purchase(
                event.organisation_id,
                billing_operation_id=operation.id,
                provider_event_id=event.identifier,
                commit=False,
            )
            return "processed"
        if checkout.subscription_identifier is None:
            return "reconciliation_required"
        checkout_subscription = await self.provider.retrieve_subscription(checkout.subscription_identifier)
        mapped = self.prices.reverse(checkout_subscription.price_identifier)
        if mapped is None:
            return "reconciliation_required"
        checkout_plan = await self._plan(mapped[0])
        if operation.plan_version_id != checkout_plan.id or operation.billing_interval != mapped[1]:
            return "reconciliation_required"
        verified = replace_event_subscription(event, checkout.subscription_identifier)
        result = await self._process_subscription_event(account, verified)
        if result == "processed":
            operation.status = "succeeded"
            operation.safe_error_code = None
            operation.completed_at = _aware(self._now())
        return result

    async def _process_subscription_event(
        self, account: BillingAccount, event: VerifiedBillingEvent
    ) -> Literal["processed", "ignored_stale", "reconciliation_required"]:
        if event.subscription_identifier is None:
            return "reconciliation_required"
        snapshot = await self.provider.retrieve_subscription(event.subscription_identifier)
        return await self._reconcile_subscription_snapshot(account, event, snapshot)

    async def _reconcile_subscription_snapshot(
        self,
        account: BillingAccount,
        event: VerifiedBillingEvent,
        snapshot: ProviderSubscriptionSnapshot,
    ) -> Literal["processed", "ignored_stale", "reconciliation_required"]:
        if snapshot.customer_identifier != account.provider_customer_id:
            return "reconciliation_required"
        mapped = self.prices.reverse(snapshot.price_identifier)
        if mapped is None:
            return "reconciliation_required"
        plan_code, interval = mapped
        plan = await self._plan(plan_code)
        subscription = await self.repository.subscription_by_provider_id(
            event.organisation_id,
            account.id,
            snapshot.identifier,
            lock=True,
        )
        if subscription is not None and subscription.status == "cancelled" and snapshot.status != "cancelled":
            return "ignored_stale"
        if subscription is None:
            subscription = BillingSubscription(
                id=uuid.uuid4(),
                organisation_id=event.organisation_id,
                billing_account_id=account.id,
                provider_subscription_id=snapshot.identifier,
                plan_version_id=plan.id,
                billing_interval=interval,
                amount=self._plan_amount(plan, interval),
                currency="AUD",
                status=snapshot.status,
                current_period_start=snapshot.current_period_start,
                current_period_end=snapshot.current_period_end,
                cancel_at_period_end=snapshot.cancel_at_period_end,
                ended_at=snapshot.ended_at,
                provider_updated_at=max(event.created_at, snapshot.provider_updated_at),
                last_provider_event_id=event.identifier,
                lock_version=1,
            )
            self.session.add(subscription)
            await self.session.flush()
        else:
            subscription.plan_version_id = plan.id
            subscription.billing_interval = interval
            subscription.amount = self._plan_amount(plan, interval)
            subscription.status = snapshot.status
            subscription.current_period_start = snapshot.current_period_start
            subscription.current_period_end = snapshot.current_period_end
            subscription.cancel_at_period_end = snapshot.cancel_at_period_end
            subscription.ended_at = snapshot.ended_at
            subscription.provider_updated_at = max(
                _aware(subscription.provider_updated_at), event.created_at, snapshot.provider_updated_at
            )
            subscription.last_provider_event_id = event.identifier
            subscription.lock_version += 1
        if subscription.pending_plan_version_id == plan.id and subscription.pending_billing_interval == interval:
            subscription.pending_plan_version_id = None
            subscription.pending_billing_interval = None
        account.last_reconciled_at = _aware(self._now())
        await self._apply_commercial_fact(event.organisation_id, plan_code, interval, snapshot.status, event.identifier)
        return "processed"

    async def _process_invoice_event(
        self, account: BillingAccount, event: VerifiedBillingEvent
    ) -> Literal["processed", "ignored_stale", "reconciliation_required"]:
        if event.invoice_identifier is None:
            return "reconciliation_required"
        invoice = await self.provider.retrieve_invoice(event.invoice_identifier)
        if invoice.customer_identifier != account.provider_customer_id or not invoice.subscription_identifier:
            return "reconciliation_required"
        subscription_event = replace_event_subscription(event, invoice.subscription_identifier)
        subscription_result = await self._process_subscription_event(account, subscription_event)
        if subscription_result == "reconciliation_required":
            return subscription_result
        subscription = await self.repository.subscription_by_provider_id(
            event.organisation_id, account.id, invoice.subscription_identifier
        )
        if subscription is None:
            return "reconciliation_required"
        await self._upsert_invoice_async(event.organisation_id, subscription.id, invoice)
        return subscription_result

    async def _upsert_invoice_async(
        self, organisation_id: UUID, subscription_id: UUID, snapshot: ProviderInvoiceSnapshot
    ) -> None:
        existing = await self.repository.invoice_by_provider_id(organisation_id, snapshot.identifier)
        hosted_invoice_url = self._safe_optional_hosted_url(snapshot.hosted_invoice_url)
        receipt_url = self._safe_optional_hosted_url(snapshot.receipt_url)
        if existing is None:
            self.session.add(
                BillingInvoiceProjection(
                    id=uuid.uuid4(),
                    organisation_id=organisation_id,
                    subscription_id=subscription_id,
                    provider_invoice_id=snapshot.identifier,
                    invoice_date=snapshot.invoice_date,
                    amount_due=snapshot.amount_due,
                    amount_paid=snapshot.amount_paid,
                    tax_amount=snapshot.tax_amount,
                    currency="AUD",
                    status=snapshot.status,
                    hosted_invoice_url=hosted_invoice_url,
                    receipt_url=receipt_url,
                    provider_updated_at=snapshot.provider_updated_at,
                )
            )
            return
        if snapshot.provider_updated_at < _aware(existing.provider_updated_at):
            return
        existing.invoice_date = snapshot.invoice_date
        existing.amount_due = snapshot.amount_due
        existing.amount_paid = snapshot.amount_paid
        existing.tax_amount = snapshot.tax_amount
        existing.status = snapshot.status
        existing.hosted_invoice_url = hosted_invoice_url
        existing.receipt_url = receipt_url
        existing.provider_updated_at = snapshot.provider_updated_at

    async def _apply_commercial_fact(
        self,
        organisation_id: UUID,
        plan_code: PlanCode,
        interval: BillingInterval,
        billing_status: BillingSubscriptionStatus,
        event_identifier: str,
    ) -> None:
        state = await self.session.scalar(
            select(OrganisationCommercialState)
            .where(OrganisationCommercialState.organisation_id == organisation_id)
            .with_for_update()
        )
        if billing_status in {"active", "cancel_at_period_end"}:
            plan = await self._plan(plan_code)
            if (
                state is not None
                and state.status == "active"
                and state.plan_version_id == plan.id
                and state.billing_interval == interval
                and state.source == "billing_provider"
            ):
                return
            expected_version = state.lock_version if state is not None else 0
            commercial = CommercialService(self.session, self.settings, now=self._now)
            await commercial.assign_plan(
                organisation_id,
                plan_code=plan_code,
                billing_interval=interval,
                actor_reference=f"billing:{self.provider.name}:{event_identifier}"[:200],
                reason="Verified test-mode billing reconciliation activated the paid subscription.",
                expected_lock_version=expected_version,
                source="billing_provider",
                commit=False,
            )
            return
        if (
            billing_status in {"cancelled", "unpaid"}
            and state is not None
            and state.status == "active"
            and state.source == "billing_provider"
        ):
            commercial = CommercialService(self.session, self.settings, now=self._now)
            await commercial.change_state(
                organisation_id,
                status="inactive",
                actor_reference=f"billing:{self.provider.name}:{event_identifier}"[:200],
                reason="Verified test-mode billing reconciliation confirmed paid commercial authority ended.",
                expected_lock_version=state.lock_version,
                source="billing_provider",
                commit=False,
            )
        # Provider-governed past-due recovery preserves access. Terminal unpaid/cancelled facts end paid authority only.

    async def _subscription_action(
        self,
        organisation_id: UUID,
        user_id: UUID,
        request: BillingOperationRequest,
        *,
        action: Literal["cancel", "reactivate"],
    ) -> HostedActionResponse:
        self._require_enabled()
        subscription = await self.repository.subscription(organisation_id, lock=True)
        if subscription is None:
            raise PublicAPIError("billing_subscription_not_found", "No subscription is available.", 404)
        fingerprint = _fingerprint({"subscription_id": str(subscription.id), "action": action})
        existing = await self.repository.operation(organisation_id, action, request.idempotency_key, lock=True)
        if existing is not None:
            self._require_same_fingerprint(existing, fingerprint)
            if existing.status == "succeeded":
                return self._subscription_action_response(existing, action, confirmed=True)
            if existing.status == "failed":
                raise PublicAPIError(
                    "billing_operation_failed",
                    "That billing operation was rejected. Start a new request with a new retry key.",
                    409,
                )
        if action == "cancel" and subscription.status not in {
            "active",
            "past_due",
            "cancel_at_period_end",
        }:
            raise PublicAPIError(
                "billing_cancellation_unavailable",
                "This subscription cannot be scheduled for cancellation in its current state.",
                409,
            )
        if action == "reactivate" and (
            not subscription.cancel_at_period_end
            or subscription.status != "cancel_at_period_end"
            or (
                subscription.current_period_end is not None
                and _aware(subscription.current_period_end) <= _aware(self._now())
            )
        ):
            raise PublicAPIError(
                "billing_reactivation_unavailable",
                "Only a scheduled cancellation can be reversed before the paid period ends.",
                409,
            )
        operation = existing or self._operation(organisation_id, user_id, action, request.idempotency_key, fingerprint)
        if existing is None:
            self.session.add(operation)
            await self.session.flush()
        try:
            account = await self.repository.account(organisation_id, self.provider.name, self.provider.mode)
            if account is None:
                raise PublicAPIError("billing_not_configured", "Billing is not configured for this organisation.", 409)
            if existing is not None:
                reconciled = await self.provider.retrieve_subscription(subscription.provider_subscription_id)
                self._verify_plan_change_ownership(account, subscription, reconciled)
                confirmed = (
                    reconciled.cancel_at_period_end
                    if action == "cancel"
                    else reconciled.status == "active" and not reconciled.cancel_at_period_end
                )
                if confirmed:
                    self._apply_subscription_action_snapshot(subscription, reconciled)
                    operation.status = "succeeded"
                    operation.safe_error_code = None
                    operation.completed_at = _aware(self._now())
                    await self._commit(organisation_id)
                    return self._subscription_action_response(operation, action, confirmed=True)
            if action == "cancel":
                snapshot = await self.provider.cancel_at_period_end(
                    subscription.provider_subscription_id,
                    idempotency_key=f"cancel:{organisation_id}:{request.idempotency_key}",
                )
            else:
                snapshot = await self.provider.reactivate(
                    subscription.provider_subscription_id,
                    idempotency_key=f"reactivate:{organisation_id}:{request.idempotency_key}",
                )
            self._verify_plan_change_ownership(account, subscription, snapshot)
            self._apply_subscription_action_snapshot(subscription, snapshot)
            operation.status = "succeeded"
            operation.safe_error_code = None
            operation.completed_at = _aware(self._now())
            await self._commit(organisation_id)
            return self._subscription_action_response(operation, action, confirmed=True)
        except PublicAPIError as exc:
            await self._record_operation_failure(organisation_id, operation, exc)
            raise

    async def _apply_plan_change_result(
        self,
        organisation_id: UUID,
        account: BillingAccount,
        subscription: BillingSubscription,
        result: ProviderPlanChangeResult,
        *,
        event_identifier: str,
    ) -> tuple[PlanCode, BillingInterval]:
        self._verify_plan_change_ownership(account, subscription, result.subscription)
        mapped = self.prices.reverse(result.subscription.price_identifier)
        if mapped is None:
            raise PublicAPIError(
                "billing_price_mapping_invalid", "The provider plan could not be safely reconciled.", 409
            )
        if result.invoice is not None and (
            result.invoice.customer_identifier != account.provider_customer_id
            or result.invoice.subscription_identifier != subscription.provider_subscription_id
        ):
            raise PublicAPIError(
                "billing_invoice_ownership_mismatch", "The provider invoice could not be safely reconciled.", 409
            )
        event = VerifiedBillingEvent(
            identifier=event_identifier,
            event_type="billing.plan_change.reconciled",
            organisation_id=organisation_id,
            customer_identifier=account.provider_customer_id,
            subscription_identifier=result.subscription.identifier,
            invoice_identifier=result.invoice.identifier if result.invoice is not None else None,
            object_identifier=result.subscription.identifier,
            created_at=_aware(self._now()),
        )
        outcome = await self._reconcile_subscription_snapshot(account, event, result.subscription)
        if outcome != "processed":
            raise PublicAPIError(
                "billing_plan_change_reconciliation_required",
                "The provider plan change could not be safely confirmed.",
                409,
            )
        if result.invoice is not None:
            await self._upsert_invoice_async(organisation_id, subscription.id, result.invoice)
        return mapped

    @staticmethod
    def _verify_plan_change_ownership(
        account: BillingAccount,
        subscription: BillingSubscription,
        snapshot: ProviderSubscriptionSnapshot,
    ) -> None:
        if snapshot.customer_identifier != account.provider_customer_id:
            raise PublicAPIError("billing_customer_mismatch", "Subscription ownership could not be verified.", 409)
        BillingService._verify_subscription_customer(subscription, snapshot)

    @staticmethod
    def _apply_subscription_action_snapshot(
        subscription: BillingSubscription, snapshot: ProviderSubscriptionSnapshot
    ) -> None:
        subscription.status = snapshot.status
        subscription.cancel_at_period_end = snapshot.cancel_at_period_end
        subscription.provider_updated_at = snapshot.provider_updated_at
        subscription.lock_version += 1

    @staticmethod
    def _subscription_action_response(
        operation: BillingOperation,
        action: Literal["cancel", "reactivate"],
        *,
        confirmed: bool,
    ) -> HostedActionResponse:
        return HostedActionResponse(
            operation_id=operation.id,
            hosted_url=None,
            status="succeeded" if confirmed else "confirmation_pending",
            message=(
                "Cancellation is scheduled. Access continues until the current paid period ends."
                if action == "cancel"
                else "Scheduled cancellation has been reversed."
            ),
        )

    @staticmethod
    def _plan_change_response(operation: BillingOperation, *, confirmed: bool) -> HostedActionResponse:
        return HostedActionResponse(
            operation_id=operation.id,
            hosted_url=None,
            status="succeeded" if confirmed else "confirmation_pending",
            message=(
                "Billing plan change confirmed. Higher-tier changes apply only after provider payment confirmation; "
                "lower-tier and interval changes apply at renewal."
                if confirmed
                else "The provider has not confirmed the immediate upgrade. The existing commercial plan remains "
                "authoritative; check billing status before retrying."
            ),
        )

    async def _ensure_account(self, organisation_id: UUID) -> BillingAccount:
        existing = await self.repository.account(organisation_id, self.provider.name, self.provider.mode)
        if existing is not None:
            return existing
        customer_identifier = await self.provider.ensure_customer(
            organisation_id, idempotency_key=f"billing-account:{organisation_id}"
        )
        account = BillingAccount(
            id=uuid.uuid4(),
            organisation_id=organisation_id,
            provider=self.provider.name,
            provider_mode=self.provider.mode,
            provider_customer_id=customer_identifier,
            status="active",
        )
        self.session.add(account)
        await self.session.flush()
        return account

    async def _checkout_options(self) -> list[BillingPlanOptionResponse]:
        rows = (
            await self.session.scalars(
                select(CommercialPlanVersion)
                .where(CommercialPlanVersion.status == "active")
                .order_by(CommercialPlanVersion.version.desc(), CommercialPlanVersion.code)
            )
        ).all()
        options: list[BillingPlanOptionResponse] = []
        for plan in rows:
            plan_code = cast(PlanCode, plan.code)
            if plan_code == "enterprise":
                options.append(
                    BillingPlanOptionResponse(
                        plan_code="enterprise",
                        display_name=plan.display_name,
                        billing_interval=None,
                        amount=None,
                        currency="AUD",
                        included_user_limit=None,
                        self_service_available=False,
                        payment_statement="Contact us for a manual commercial process.",
                    )
                )
                continue
            for interval in cast(tuple[BillingInterval, ...], ("monthly", "annual")):
                amount = self._plan_amount(plan, interval)
                options.append(
                    BillingPlanOptionResponse(
                        plan_code=plan_code,
                        display_name=plan.display_name,
                        billing_interval=interval,
                        amount=_amount_text(amount),
                        currency="AUD",
                        included_user_limit=plan.included_user_limit,
                        self_service_available=self.settings.feature_billing_enabled,
                        payment_statement=self._payment_statement(amount, interval),
                    )
                )
        return options

    async def _subscription_response(self, subscription: BillingSubscription) -> BillingSubscriptionResponse:
        plan = await self.session.get(CommercialPlanVersion, subscription.plan_version_id)
        if plan is None:
            raise PublicAPIError("billing_projection_invalid", "Billing information is temporarily unavailable.", 503)
        pending_plan = (
            await self.session.get(CommercialPlanVersion, subscription.pending_plan_version_id)
            if subscription.pending_plan_version_id is not None
            else None
        )
        status = cast(BillingSubscriptionStatus, subscription.status)
        return BillingSubscriptionResponse(
            id=subscription.id,
            plan_code=cast(PlanCode, plan.code),
            plan_name=plan.display_name,
            billing_interval=cast(BillingInterval, subscription.billing_interval),
            amount=_amount_text(subscription.amount),
            currency="AUD",
            status=status,
            current_period_start=subscription.current_period_start,
            current_period_end=subscription.current_period_end,
            cancel_at_period_end=subscription.cancel_at_period_end,
            pending_plan_code=cast(PlanCode, pending_plan.code) if pending_plan is not None else None,
            pending_billing_interval=cast(BillingInterval | None, subscription.pending_billing_interval),
            payment_needs_attention=status in {"past_due", "unpaid", "incomplete", "unknown_reconciliation"},
        )

    @staticmethod
    def _invoice_response(invoice: BillingInvoiceProjection) -> BillingInvoiceResponse:
        return BillingInvoiceResponse(
            id=invoice.id,
            invoice_date=invoice.invoice_date,
            amount_due=_amount_text(invoice.amount_due),
            amount_paid=_amount_text(invoice.amount_paid),
            tax_amount=_amount_text(invoice.tax_amount) if invoice.tax_amount is not None else None,
            currency="AUD",
            status=cast(InvoiceStatus, invoice.status),
            hosted_invoice_url=invoice.hosted_invoice_url,
            receipt_url=invoice.receipt_url,
        )

    async def _plan(self, plan_code: PlanCode) -> CommercialPlanVersion:
        plan = await self.session.scalar(
            select(CommercialPlanVersion)
            .where(CommercialPlanVersion.code == plan_code, CommercialPlanVersion.status == "active")
            .order_by(CommercialPlanVersion.version.desc())
        )
        if plan is None:
            raise PublicAPIError("commercial_catalogue_unavailable", "Commercial plan information is unavailable.", 503)
        return plan

    def _provider_price(self, plan: CommercialPlanVersion, interval: BillingInterval) -> ProviderPriceReference:
        code = cast(PlanCode, plan.code)
        return ProviderPriceReference(
            identifier=self.prices.provider_identifier(code, interval),
            plan_code=code,
            billing_interval=interval,
            amount=self._plan_amount(plan, interval),
        )

    @staticmethod
    def _plan_amount(plan: CommercialPlanVersion, interval: BillingInterval) -> Decimal:
        amount = plan.monthly_price_amount if interval == "monthly" else plan.annual_price_amount
        if amount is None:
            raise PublicAPIError("enterprise_checkout_unavailable", "Enterprise uses a manual commercial process.", 409)
        return amount

    @staticmethod
    def _payment_statement(amount: Decimal, interval: BillingInterval) -> str:
        suffix = "billed monthly" if interval == "monthly" else "billed annually as an annual prepayment"
        return f"AUD ${amount:,.0f} {suffix}."

    @staticmethod
    def _projection_message(account: BillingAccount | None, subscription: BillingSubscription | None) -> str:
        if account is None or subscription is None:
            return "Billing is not configured or is manually managed. No provider subscription is being represented."
        if subscription.status == "past_due":
            return (
                "Payment recovery is in progress under the provider's bounded retry policy. Access and existing data "
                "are preserved; use hosted billing management to resolve it."
            )
        if subscription.status == "unpaid":
            return (
                "Provider payment recovery has ended and paid functionality is inactive. Existing data is preserved; "
                "use hosted billing management to resolve it."
            )
        if subscription.status in {"incomplete", "unknown_reconciliation"}:
            return (
                "Payment has not been confirmed. No new paid entitlement has been granted; existing data is preserved."
            )
        if subscription.status == "cancel_at_period_end":
            return "Cancellation is scheduled. Paid access continues until the current period ends."
        if subscription.status == "cancelled":
            return "The provider subscription has ended. Existing data has not been deleted."
        return "The test-mode provider subscription has been verified and reconciled."

    @staticmethod
    def _operation(
        organisation_id: UUID,
        user_id: UUID,
        operation_type: str,
        idempotency_key: str,
        fingerprint: str,
        *,
        plan_version_id: UUID | None = None,
        billing_interval: BillingInterval | None = None,
        amount: Decimal | None = None,
    ) -> BillingOperation:
        return BillingOperation(
            id=uuid.uuid4(),
            organisation_id=organisation_id,
            requested_by_user_id=user_id,
            operation_type=operation_type,
            idempotency_key=idempotency_key,
            request_fingerprint=fingerprint,
            status="pending",
            plan_version_id=plan_version_id,
            billing_interval=billing_interval,
            amount=amount,
            currency="AUD" if amount is not None else None,
        )

    @staticmethod
    def _require_same_fingerprint(operation: BillingOperation, fingerprint: str) -> None:
        if operation.request_fingerprint != fingerprint:
            raise PublicAPIError(
                "billing_idempotency_conflict",
                "That billing retry key was already used for a different request.",
                409,
            )

    @staticmethod
    def _verify_subscription_customer(
        subscription: BillingSubscription, snapshot: ProviderSubscriptionSnapshot
    ) -> None:
        if subscription.provider_subscription_id != snapshot.identifier:
            raise PublicAPIError("billing_subscription_mismatch", "Subscription ownership could not be verified.", 409)

    def _require_enabled(self) -> None:
        if not self.settings.feature_billing_enabled:
            raise PublicAPIError(
                "billing_test_mode_unavailable",
                "Test-mode billing is not enabled in this environment.",
                503,
            )

    @staticmethod
    def _safe_hosted_url(value: str) -> str:
        parsed = urlsplit(value)
        hostname = (parsed.hostname or "").casefold()
        if (
            parsed.scheme != "https"
            or parsed.username
            or parsed.password
            or not (hostname.endswith(".stripe.com") or hostname.endswith(".stripe.test"))
        ):
            raise PublicAPIError("billing_provider_url_invalid", "The hosted billing destination is invalid.", 502)
        return value

    def _safe_optional_hosted_url(self, value: str | None) -> str | None:
        return self._safe_hosted_url(value) if value is not None else None

    @staticmethod
    def _checkout_response(
        operation: BillingOperation,
        plan_code: PlanCode,
        interval: BillingInterval,
        amount: Decimal,
        *,
        status: Literal["redirect_ready", "confirmation_pending"] = "redirect_ready",
    ) -> CheckoutCreateResponse:
        assert operation.hosted_url is not None
        return CheckoutCreateResponse(
            operation_id=operation.id,
            checkout_url=operation.hosted_url,
            status=status,
            plan_code=plan_code,
            billing_interval=interval,
            amount=_amount_text(amount),
            currency="AUD",
            payment_statement=BillingService._payment_statement(amount, interval),
        )

    async def _record_operation_failure(
        self, organisation_id: UUID, operation: BillingOperation, error: PublicAPIError
    ) -> None:
        operation.status = "unknown" if error.status_code >= 500 else "failed"
        operation.safe_error_code = error.code
        operation.completed_at = _aware(self._now())
        await self._commit(organisation_id)

    async def _commit(self, organisation_id: UUID) -> None:
        try:
            await self.session.commit()
            await set_tenant_database_context(self.session, organisation_id)
        except (IntegrityError, SQLAlchemyError) as exc:
            await self.session.rollback()
            raise PublicAPIError(
                "billing_state_conflict",
                "Billing status changed while this request was being processed. Check status before retrying.",
                409,
            ) from exc


def replace_event_subscription(event: VerifiedBillingEvent, subscription_identifier: str) -> VerifiedBillingEvent:
    return VerifiedBillingEvent(
        identifier=event.identifier,
        event_type=event.event_type,
        organisation_id=event.organisation_id,
        customer_identifier=event.customer_identifier,
        subscription_identifier=subscription_identifier,
        invoice_identifier=event.invoice_identifier,
        object_identifier=event.object_identifier,
        created_at=event.created_at,
        amount_minor_units=event.amount_minor_units,
        currency=event.currency,
        credit_pack_version_id=event.credit_pack_version_id,
        payment_status=event.payment_status,
    )
