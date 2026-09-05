from __future__ import annotations

import hashlib
import hmac
import json
import time
import uuid
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from decimal import Decimal
from typing import Literal, Protocol, cast
from urllib.parse import urlencode
from uuid import UUID

import httpx

from revenueos.billing_contracts import BillingProviderName, BillingSubscriptionStatus, InvoiceStatus
from revenueos.commercial_contracts import BillingInterval, PlanCode
from revenueos.config import Settings
from revenueos.errors import PublicAPIError


@dataclass(frozen=True)
class ProviderPriceReference:
    identifier: str
    plan_code: PlanCode
    billing_interval: BillingInterval
    amount: Decimal
    currency: Literal["AUD"] = "AUD"

    @property
    def amount_minor(self) -> int:
        return int(self.amount * 100)


@dataclass(frozen=True)
class ProviderCheckout:
    identifier: str
    customer_identifier: str
    subscription_identifier: str | None
    hosted_url: str
    status: Literal["open", "complete", "expired"]


@dataclass(frozen=True)
class ProviderSubscriptionSnapshot:
    identifier: str
    customer_identifier: str
    price_identifier: str
    status: BillingSubscriptionStatus
    current_period_start: datetime | None
    current_period_end: datetime | None
    cancel_at_period_end: bool
    ended_at: datetime | None
    provider_updated_at: datetime


@dataclass(frozen=True)
class ProviderInvoiceSnapshot:
    identifier: str
    customer_identifier: str
    subscription_identifier: str
    invoice_date: datetime
    amount_due: Decimal
    amount_paid: Decimal
    tax_amount: Decimal | None
    currency: Literal["AUD"]
    status: InvoiceStatus
    hosted_invoice_url: str | None
    receipt_url: str | None
    provider_updated_at: datetime


@dataclass(frozen=True)
class VerifiedBillingEvent:
    identifier: str
    event_type: str
    organisation_id: UUID
    customer_identifier: str
    subscription_identifier: str | None
    invoice_identifier: str | None
    object_identifier: str | None
    created_at: datetime


class BillingProvider(Protocol):
    name: BillingProviderName
    mode: Literal["test"]

    async def ensure_customer(self, organisation_id: UUID, *, idempotency_key: str) -> str: ...

    async def create_checkout(
        self,
        *,
        organisation_id: UUID,
        customer_identifier: str,
        price: ProviderPriceReference,
        idempotency_key: str,
    ) -> ProviderCheckout: ...

    async def retrieve_checkout(self, identifier: str) -> ProviderCheckout: ...

    async def retrieve_subscription(self, identifier: str) -> ProviderSubscriptionSnapshot: ...

    async def retrieve_invoice(self, identifier: str) -> ProviderInvoiceSnapshot: ...

    async def cancel_at_period_end(self, identifier: str, *, idempotency_key: str) -> ProviderSubscriptionSnapshot: ...

    async def reactivate(self, identifier: str, *, idempotency_key: str) -> ProviderSubscriptionSnapshot: ...

    async def schedule_plan_change(
        self,
        identifier: str,
        *,
        price: ProviderPriceReference,
        idempotency_key: str,
    ) -> ProviderSubscriptionSnapshot: ...

    async def create_portal(self, customer_identifier: str, *, idempotency_key: str) -> str: ...

    async def verify_webhook(self, payload: bytes, signature: str | None) -> VerifiedBillingEvent: ...


def _aware_from_timestamp(value: object) -> datetime | None:
    if not isinstance(value, (int, float)):
        return None
    return datetime.fromtimestamp(value, tz=UTC)


def _required_string(data: dict[str, object], key: str) -> str:
    value = data.get(key)
    if not isinstance(value, str) or not value:
        raise PublicAPIError("billing_provider_response_invalid", "Billing status could not be confirmed.", 502)
    return value


class DeterministicBillingProvider:
    """Stateful, network-free test provider used by local development and CI."""

    name: BillingProviderName = "deterministic"
    mode: Literal["test"] = "test"
    _namespace = UUID("45ab7f3c-c853-4cd9-a521-688239bd0174")

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.checkouts: dict[str, ProviderCheckout] = {}
        self.subscriptions: dict[str, ProviderSubscriptionSnapshot] = {}
        self.invoices: dict[str, ProviderInvoiceSnapshot] = {}
        self.pending_price_changes: dict[str, str] = {}

    async def ensure_customer(self, organisation_id: UUID, *, idempotency_key: str) -> str:
        del idempotency_key
        return f"cus_test_{uuid.uuid5(self._namespace, str(organisation_id)).hex}"

    async def create_checkout(
        self,
        *,
        organisation_id: UUID,
        customer_identifier: str,
        price: ProviderPriceReference,
        idempotency_key: str,
    ) -> ProviderCheckout:
        identifier = f"cs_test_{uuid.uuid5(self._namespace, idempotency_key).hex}"
        existing = self.checkouts.get(identifier)
        if existing is not None:
            return existing
        subscription_identifier = f"sub_test_{uuid.uuid5(self._namespace, identifier).hex}"
        checkout = ProviderCheckout(
            identifier=identifier,
            customer_identifier=customer_identifier,
            subscription_identifier=subscription_identifier,
            hosted_url=f"https://checkout.stripe.test/pay/{identifier}",
            status="open",
        )
        self.checkouts[identifier] = checkout
        now = datetime.now(UTC)
        self.subscriptions[subscription_identifier] = ProviderSubscriptionSnapshot(
            identifier=subscription_identifier,
            customer_identifier=customer_identifier,
            price_identifier=price.identifier,
            status="pending",
            current_period_start=None,
            current_period_end=None,
            cancel_at_period_end=False,
            ended_at=None,
            provider_updated_at=now,
        )
        return checkout

    async def retrieve_checkout(self, identifier: str) -> ProviderCheckout:
        try:
            return self.checkouts[identifier]
        except KeyError as exc:
            raise PublicAPIError("billing_checkout_not_found", "Checkout could not be confirmed.", 404) from exc

    async def retrieve_subscription(self, identifier: str) -> ProviderSubscriptionSnapshot:
        try:
            return self.subscriptions[identifier]
        except KeyError as exc:
            raise PublicAPIError("billing_subscription_not_found", "Subscription could not be confirmed.", 404) from exc

    async def retrieve_invoice(self, identifier: str) -> ProviderInvoiceSnapshot:
        try:
            return self.invoices[identifier]
        except KeyError as exc:
            raise PublicAPIError("billing_invoice_not_found", "Invoice could not be confirmed.", 404) from exc

    async def cancel_at_period_end(self, identifier: str, *, idempotency_key: str) -> ProviderSubscriptionSnapshot:
        del idempotency_key
        current = await self.retrieve_subscription(identifier)
        updated = replace(
            current,
            status="cancel_at_period_end",
            cancel_at_period_end=True,
            provider_updated_at=datetime.now(UTC),
        )
        self.subscriptions[identifier] = updated
        return updated

    async def reactivate(self, identifier: str, *, idempotency_key: str) -> ProviderSubscriptionSnapshot:
        del idempotency_key
        current = await self.retrieve_subscription(identifier)
        if current.status == "cancelled":
            raise PublicAPIError(
                "billing_subscription_ended",
                "This subscription has ended. Choose a new checkout to reactivate the organisation.",
                409,
            )
        updated = replace(
            current,
            status="active",
            cancel_at_period_end=False,
            provider_updated_at=datetime.now(UTC),
        )
        self.subscriptions[identifier] = updated
        return updated

    async def schedule_plan_change(
        self,
        identifier: str,
        *,
        price: ProviderPriceReference,
        idempotency_key: str,
    ) -> ProviderSubscriptionSnapshot:
        del idempotency_key
        current = await self.retrieve_subscription(identifier)
        if current.status not in {"active", "cancel_at_period_end", "past_due"}:
            raise PublicAPIError(
                "billing_plan_change_unavailable", "The plan cannot be changed in its current state.", 409
            )
        self.pending_price_changes[identifier] = price.identifier
        return current

    async def create_portal(self, customer_identifier: str, *, idempotency_key: str) -> str:
        portal_id = uuid.uuid5(self._namespace, f"portal:{customer_identifier}:{idempotency_key}").hex
        return f"https://billing.stripe.test/session/{portal_id}"

    async def verify_webhook(self, payload: bytes, signature: str | None) -> VerifiedBillingEvent:
        expected = hmac.new(
            self.settings.billing_webhook_secret.get_secret_value().encode("utf-8"),
            payload,
            hashlib.sha256,
        ).hexdigest()
        supplied = (signature or "").removeprefix("sha256=")
        if not supplied or not hmac.compare_digest(expected, supplied):
            raise PublicAPIError("billing_webhook_signature_invalid", "Webhook signature is invalid.", 400)
        try:
            body = cast(dict[str, object], json.loads(payload))
            organisation_id = UUID(_required_string(body, "organisation_id"))
            created_at = _aware_from_timestamp(body.get("created"))
            if created_at is None:
                raise ValueError("missing created")
            return VerifiedBillingEvent(
                identifier=_required_string(body, "id"),
                event_type=_required_string(body, "type"),
                organisation_id=organisation_id,
                customer_identifier=_required_string(body, "customer_id"),
                subscription_identifier=cast(str | None, body.get("subscription_id")),
                invoice_identifier=cast(str | None, body.get("invoice_id")),
                object_identifier=cast(str | None, body.get("object_id")),
                created_at=created_at,
            )
        except (TypeError, ValueError, KeyError, json.JSONDecodeError) as exc:
            raise PublicAPIError("billing_webhook_invalid", "Webhook content is invalid.", 400) from exc

    def complete_checkout(
        self,
        checkout_identifier: str,
        *,
        period_start: datetime,
        period_end: datetime,
    ) -> ProviderSubscriptionSnapshot:
        checkout = self.checkouts[checkout_identifier]
        assert checkout.subscription_identifier is not None
        self.checkouts[checkout_identifier] = replace(checkout, status="complete")
        current = self.subscriptions[checkout.subscription_identifier]
        updated = replace(
            current,
            status="active",
            current_period_start=period_start,
            current_period_end=period_end,
            provider_updated_at=datetime.now(UTC),
        )
        self.subscriptions[current.identifier] = updated
        return updated

    def add_invoice(self, invoice: ProviderInvoiceSnapshot) -> None:
        self.invoices[invoice.identifier] = invoice

    def set_subscription_status(
        self,
        identifier: str,
        status: BillingSubscriptionStatus,
        *,
        cancel_at_period_end: bool = False,
        ended_at: datetime | None = None,
    ) -> ProviderSubscriptionSnapshot:
        current = self.subscriptions[identifier]
        updated = replace(
            current,
            status=status,
            cancel_at_period_end=cancel_at_period_end,
            ended_at=ended_at,
            provider_updated_at=datetime.now(UTC),
        )
        self.subscriptions[identifier] = updated
        return updated

    def renew_with_scheduled_plan(
        self,
        identifier: str,
        *,
        period_start: datetime,
        period_end: datetime,
    ) -> ProviderSubscriptionSnapshot:
        current = self.subscriptions[identifier]
        updated = replace(
            current,
            price_identifier=self.pending_price_changes.pop(identifier, current.price_identifier),
            status="active",
            current_period_start=period_start,
            current_period_end=period_end,
            provider_updated_at=datetime.now(UTC),
        )
        self.subscriptions[identifier] = updated
        return updated


class StripeTestBillingProvider:
    name: BillingProviderName = "stripe"
    mode: Literal["test"] = "test"

    def __init__(self, settings: Settings) -> None:
        if settings.stripe_secret_key is None:
            raise RuntimeError("Stripe test provider requires validated test credentials.")
        self.settings = settings
        self._secret = settings.stripe_secret_key.get_secret_value()

    async def _request(
        self,
        method: Literal["GET", "POST"],
        path: str,
        *,
        form: list[tuple[str, str]] | None = None,
        idempotency_key: str | None = None,
    ) -> dict[str, object]:
        headers = {
            "Authorization": f"Bearer {self._secret}",
            "Stripe-Version": self.settings.stripe_api_version,
        }
        if method == "POST":
            headers["Content-Type"] = "application/x-www-form-urlencoded"
        if idempotency_key is not None:
            headers["Idempotency-Key"] = idempotency_key
        timeout = httpx.Timeout(
            connect=self.settings.stripe_connect_timeout_seconds,
            read=self.settings.stripe_read_timeout_seconds,
            write=self.settings.stripe_read_timeout_seconds,
            pool=self.settings.stripe_connect_timeout_seconds,
        )
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.request(
                    method,
                    f"{self.settings.stripe_api_base_url}{path}",
                    headers=headers,
                    content=urlencode(form or []),
                )
            response.raise_for_status()
            return cast(dict[str, object], response.json())
        except (httpx.HTTPError, ValueError) as exc:
            raise PublicAPIError(
                "billing_provider_unavailable",
                "We couldn't confirm your payment yet. No second charge has been attempted. Please retry or check status.",
                503,
            ) from exc

    async def ensure_customer(self, organisation_id: UUID, *, idempotency_key: str) -> str:
        data = await self._request(
            "POST",
            "/v1/customers",
            form=[("metadata[oryntela_organisation_id]", str(organisation_id))],
            idempotency_key=idempotency_key,
        )
        _require_stripe_test_object(data)
        return _required_string(data, "id")

    async def _verify_price(self, price: ProviderPriceReference) -> None:
        data = await self._request("GET", f"/v1/prices/{price.identifier}")
        _require_stripe_test_object(data)
        recurring = data.get("recurring")
        interval = recurring.get("interval") if isinstance(recurring, dict) else None
        if (
            data.get("active") is not True
            or data.get("currency") != "aud"
            or data.get("unit_amount") != price.amount_minor
            or interval != ("month" if price.billing_interval == "monthly" else "year")
            or (recurring.get("interval_count") if isinstance(recurring, dict) else None) != 1
        ):
            raise PublicAPIError(
                "billing_price_mapping_invalid",
                "The selected billing option is temporarily unavailable.",
                503,
            )

    async def create_checkout(
        self,
        *,
        organisation_id: UUID,
        customer_identifier: str,
        price: ProviderPriceReference,
        idempotency_key: str,
    ) -> ProviderCheckout:
        await self._verify_price(price)
        data = await self._request(
            "POST",
            "/v1/checkout/sessions",
            form=[
                ("mode", "subscription"),
                ("customer", customer_identifier),
                ("line_items[0][price]", price.identifier),
                ("line_items[0][quantity]", "1"),
                ("success_url", self.settings.billing_success_url),
                ("cancel_url", self.settings.billing_cancel_url),
                ("client_reference_id", str(organisation_id)),
                ("metadata[oryntela_organisation_id]", str(organisation_id)),
                ("metadata[oryntela_plan_code]", price.plan_code),
                ("metadata[oryntela_billing_interval]", price.billing_interval),
                ("subscription_data[metadata][oryntela_organisation_id]", str(organisation_id)),
            ],
            idempotency_key=idempotency_key,
        )
        _require_stripe_test_object(data)
        subscription = data.get("subscription")
        return ProviderCheckout(
            identifier=_required_string(data, "id"),
            customer_identifier=_required_string(data, "customer"),
            subscription_identifier=subscription if isinstance(subscription, str) else None,
            hosted_url=_required_string(data, "url"),
            status=cast(Literal["open", "complete", "expired"], data.get("status", "open")),
        )

    async def retrieve_checkout(self, identifier: str) -> ProviderCheckout:
        data = await self._request("GET", f"/v1/checkout/sessions/{identifier}")
        _require_stripe_test_object(data)
        subscription = data.get("subscription")
        return ProviderCheckout(
            identifier=_required_string(data, "id"),
            customer_identifier=_required_string(data, "customer"),
            subscription_identifier=subscription if isinstance(subscription, str) else None,
            hosted_url=cast(str, data.get("url") or self.settings.billing_success_url),
            status=cast(Literal["open", "complete", "expired"], data.get("status", "open")),
        )

    async def retrieve_subscription(self, identifier: str) -> ProviderSubscriptionSnapshot:
        data = await self._request("GET", f"/v1/subscriptions/{identifier}")
        return self._subscription(data, datetime.now(UTC))

    async def retrieve_invoice(self, identifier: str) -> ProviderInvoiceSnapshot:
        data = await self._request("GET", f"/v1/invoices/{identifier}")
        _require_stripe_test_object(data)
        if data.get("currency") != "aud":
            raise PublicAPIError(
                "billing_invoice_currency_mismatch",
                "The provider invoice currency could not be reconciled.",
                409,
            )
        parent = data.get("parent")
        subscription_details = parent.get("subscription_details") if isinstance(parent, dict) else None
        subscription = (
            subscription_details.get("subscription")
            if isinstance(subscription_details, dict)
            else data.get("subscription")
        )
        status = cast(str, data.get("status", "open"))
        if (
            data.get("amount_refunded") == data.get("amount_paid")
            and isinstance(data.get("amount_paid"), int)
            and data.get("amount_paid") != 0
        ):
            status = "refunded"
        allowed_status = status if status in {"draft", "open", "paid", "void", "uncollectible", "refunded"} else "open"
        return ProviderInvoiceSnapshot(
            identifier=_required_string(data, "id"),
            customer_identifier=_required_string(data, "customer"),
            subscription_identifier=subscription if isinstance(subscription, str) else "",
            invoice_date=_aware_from_timestamp(data.get("created")) or datetime.now(UTC),
            amount_due=_stripe_minor_amount(data, "amount_due"),
            amount_paid=_stripe_minor_amount(data, "amount_paid"),
            tax_amount=_stripe_tax_amount(data),
            currency="AUD",
            status=cast(InvoiceStatus, allowed_status),
            hosted_invoice_url=cast(str | None, data.get("hosted_invoice_url")),
            receipt_url=None,
            provider_updated_at=datetime.now(UTC),
        )

    async def cancel_at_period_end(self, identifier: str, *, idempotency_key: str) -> ProviderSubscriptionSnapshot:
        data = await self._request(
            "POST",
            f"/v1/subscriptions/{identifier}",
            form=[("cancel_at_period_end", "true")],
            idempotency_key=idempotency_key,
        )
        return self._subscription(data, datetime.now(UTC))

    async def reactivate(self, identifier: str, *, idempotency_key: str) -> ProviderSubscriptionSnapshot:
        data = await self._request(
            "POST",
            f"/v1/subscriptions/{identifier}",
            form=[("cancel_at_period_end", "false")],
            idempotency_key=idempotency_key,
        )
        return self._subscription(data, datetime.now(UTC))

    async def schedule_plan_change(
        self,
        identifier: str,
        *,
        price: ProviderPriceReference,
        idempotency_key: str,
    ) -> ProviderSubscriptionSnapshot:
        await self._verify_price(price)
        current = await self.retrieve_subscription(identifier)
        if current.current_period_start is None or current.current_period_end is None:
            raise PublicAPIError("billing_plan_change_unavailable", "The renewal period could not be confirmed.", 409)
        schedule = await self._request(
            "POST",
            "/v1/subscription_schedules",
            form=[("from_subscription", identifier)],
            idempotency_key=f"{idempotency_key}:schedule",
        )
        await self._request(
            "POST",
            f"/v1/subscription_schedules/{_required_string(schedule, 'id')}",
            form=[
                ("end_behavior", "release"),
                ("phases[0][start_date]", str(int(current.current_period_start.timestamp()))),
                ("phases[0][end_date]", str(int(current.current_period_end.timestamp()))),
                ("phases[0][items][0][price]", current.price_identifier),
                ("phases[0][items][0][quantity]", "1"),
                ("phases[0][proration_behavior]", "none"),
                ("phases[1][start_date]", str(int(current.current_period_end.timestamp()))),
                ("phases[1][items][0][price]", price.identifier),
                ("phases[1][items][0][quantity]", "1"),
                ("phases[1][iterations]", "1"),
                ("phases[1][proration_behavior]", "none"),
            ],
            idempotency_key=f"{idempotency_key}:phases",
        )
        return current

    async def create_portal(self, customer_identifier: str, *, idempotency_key: str) -> str:
        data = await self._request(
            "POST",
            "/v1/billing_portal/sessions",
            form=[("customer", customer_identifier), ("return_url", self.settings.billing_portal_return_url)],
            idempotency_key=idempotency_key,
        )
        _require_stripe_test_object(data)
        return _required_string(data, "url")

    async def verify_webhook(self, payload: bytes, signature: str | None) -> VerifiedBillingEvent:
        if signature is None:
            raise PublicAPIError("billing_webhook_signature_invalid", "Webhook signature is invalid.", 400)
        values: dict[str, list[str]] = {}
        for part in signature.split(","):
            key, separator, value = part.partition("=")
            if separator:
                values.setdefault(key, []).append(value)
        try:
            timestamp = int(values["t"][0])
        except (KeyError, ValueError, IndexError) as exc:
            raise PublicAPIError("billing_webhook_signature_invalid", "Webhook signature is invalid.", 400) from exc
        if abs(int(time.time()) - timestamp) > self.settings.stripe_webhook_tolerance_seconds:
            raise PublicAPIError("billing_webhook_signature_invalid", "Webhook signature is invalid.", 400)
        secret = self.settings.billing_webhook_secret.get_secret_value().encode("utf-8")
        expected = hmac.new(secret, f"{timestamp}.".encode() + payload, hashlib.sha256).hexdigest()
        if not any(hmac.compare_digest(expected, candidate) for candidate in values.get("v1", [])):
            raise PublicAPIError("billing_webhook_signature_invalid", "Webhook signature is invalid.", 400)
        try:
            event = cast(dict[str, object], json.loads(payload))
            if event.get("api_version") != self.settings.stripe_api_version:
                raise ValueError("unexpected Stripe API version")
            data = cast(dict[str, object], event["data"])
            obj = cast(dict[str, object], data["object"])
            _require_stripe_test_object(obj)
            customer_identifier = _required_string(obj, "customer")
            metadata = obj.get("metadata")
            organisation_text = metadata.get("oryntela_organisation_id") if isinstance(metadata, dict) else None
            if not isinstance(organisation_text, str):
                customer = await self._request("GET", f"/v1/customers/{customer_identifier}")
                _require_stripe_test_object(customer)
                customer_metadata = customer.get("metadata")
                organisation_text = (
                    customer_metadata.get("oryntela_organisation_id") if isinstance(customer_metadata, dict) else None
                )
            organisation_id = UUID(cast(str, organisation_text))
            event_type = _required_string(event, "type")
            subscription_identifier: str | None = None
            invoice_identifier: str | None = None
            if event_type.startswith("customer.subscription."):
                subscription_identifier = _required_string(obj, "id")
            elif event_type.startswith("invoice."):
                invoice_identifier = _required_string(obj, "id")
                parent = obj.get("parent")
                subscription_details = parent.get("subscription_details") if isinstance(parent, dict) else None
                candidate = (
                    subscription_details.get("subscription")
                    if isinstance(subscription_details, dict)
                    else obj.get("subscription")
                )
                subscription_identifier = candidate if isinstance(candidate, str) else None
            elif event_type == "checkout.session.completed":
                candidate = obj.get("subscription")
                subscription_identifier = candidate if isinstance(candidate, str) else None
            return VerifiedBillingEvent(
                identifier=_required_string(event, "id"),
                event_type=event_type,
                organisation_id=organisation_id,
                customer_identifier=customer_identifier,
                subscription_identifier=subscription_identifier,
                invoice_identifier=invoice_identifier,
                object_identifier=_required_string(obj, "id"),
                created_at=_aware_from_timestamp(event.get("created")) or datetime.now(UTC),
            )
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            raise PublicAPIError("billing_webhook_invalid", "Webhook content is invalid.", 400) from exc

    @staticmethod
    def _subscription(data: dict[str, object], observed_at: datetime) -> ProviderSubscriptionSnapshot:
        _require_stripe_test_object(data)
        items = data.get("items")
        item_data = items.get("data") if isinstance(items, dict) else None
        first = item_data[0] if isinstance(item_data, list) and item_data and isinstance(item_data[0], dict) else {}
        price = first.get("price") if isinstance(first, dict) else None
        provider_status = cast(str, data.get("status", "unknown"))
        statuses: dict[str, BillingSubscriptionStatus] = {
            "active": "active",
            "past_due": "past_due",
            "canceled": "cancelled",
            "unpaid": "unpaid",
            "incomplete": "incomplete",
            "incomplete_expired": "incomplete",
        }
        status = statuses.get(provider_status, "unknown_reconciliation")
        cancel_at_period_end = data.get("cancel_at_period_end") is True
        if cancel_at_period_end and status == "active":
            status = "cancel_at_period_end"
        return ProviderSubscriptionSnapshot(
            identifier=_required_string(data, "id"),
            customer_identifier=_required_string(data, "customer"),
            price_identifier=_required_string(cast(dict[str, object], price), "id"),
            status=status,
            current_period_start=_aware_from_timestamp(first.get("current_period_start")),
            current_period_end=_aware_from_timestamp(first.get("current_period_end")),
            cancel_at_period_end=cancel_at_period_end,
            ended_at=_aware_from_timestamp(data.get("ended_at")),
            provider_updated_at=observed_at,
        )


def build_billing_provider(settings: Settings) -> BillingProvider:
    if settings.billing_provider_name == "stripe":
        return StripeTestBillingProvider(settings)
    return DeterministicBillingProvider(settings)


def _require_stripe_test_object(value: dict[str, object]) -> None:
    if value.get("livemode") is not False:
        raise PublicAPIError(
            "billing_provider_mode_mismatch",
            "The billing provider returned an object outside the authorised test mode.",
            409,
        )


def _stripe_minor_amount(value: dict[str, object], key: str) -> Decimal:
    amount = value.get(key)
    if not isinstance(amount, int) or isinstance(amount, bool) or amount < 0:
        raise PublicAPIError(
            "billing_invoice_amount_invalid",
            "The provider invoice amount could not be reconciled.",
            409,
        )
    return Decimal(amount) / 100


def _stripe_tax_amount(value: dict[str, object]) -> Decimal | None:
    taxes = value.get("total_taxes")
    if taxes is None:
        return None
    if not isinstance(taxes, list):
        raise PublicAPIError(
            "billing_invoice_tax_invalid",
            "The provider invoice tax could not be reconciled.",
            409,
        )
    total = Decimal("0")
    for tax in taxes:
        if not isinstance(tax, dict):
            raise PublicAPIError(
                "billing_invoice_tax_invalid",
                "The provider invoice tax could not be reconciled.",
                409,
            )
        total += _stripe_minor_amount(cast(dict[str, object], tax), "amount")
    return total
