from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import Field

from revenueos.commercial_contracts import BillingInterval, PlanCode
from revenueos.contracts import APIModel

BillingProviderName = Literal["deterministic", "stripe"]
BillingSubscriptionStatus = Literal[
    "pending",
    "active",
    "past_due",
    "cancel_at_period_end",
    "cancelled",
    "unpaid",
    "incomplete",
    "unknown_reconciliation",
]
InvoiceStatus = Literal["draft", "open", "paid", "void", "uncollectible", "refunded"]


class BillingPlanOptionResponse(APIModel):
    plan_code: PlanCode
    display_name: str
    billing_interval: BillingInterval | None
    amount: str | None
    currency: Literal["AUD"]
    included_user_limit: int | None
    self_service_available: bool
    payment_statement: str


class BillingSubscriptionResponse(APIModel):
    id: UUID
    plan_code: PlanCode
    plan_name: str
    billing_interval: BillingInterval
    amount: str
    currency: Literal["AUD"]
    status: BillingSubscriptionStatus
    current_period_start: datetime | None
    current_period_end: datetime | None
    cancel_at_period_end: bool
    pending_plan_code: PlanCode | None
    pending_billing_interval: BillingInterval | None
    payment_needs_attention: bool


class BillingInvoiceResponse(APIModel):
    id: UUID
    invoice_date: datetime
    amount_due: str
    amount_paid: str
    tax_amount: str | None
    currency: Literal["AUD"]
    status: InvoiceStatus
    hosted_invoice_url: str | None
    receipt_url: str | None


class BillingProjectionResponse(APIModel):
    configured: bool
    provider: BillingProviderName
    mode: Literal["test"]
    legal_entity_name: Literal["Management Services Australia Pty. Ltd."] = "Management Services Australia Pty. Ltd."
    legal_entity_abn: Literal["15 113 119 556"] = "15 113 119 556"
    subscription: BillingSubscriptionResponse | None
    invoices: list[BillingInvoiceResponse]
    checkout_options: list[BillingPlanOptionResponse]
    portal_available: bool
    message: str


class CheckoutCreateRequest(APIModel):
    plan_code: PlanCode
    billing_interval: BillingInterval
    idempotency_key: str = Field(min_length=16, max_length=200, pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]*$")


class CheckoutCreateResponse(APIModel):
    operation_id: UUID
    checkout_url: str
    status: Literal["redirect_ready", "confirmation_pending"]
    plan_code: PlanCode
    billing_interval: BillingInterval
    amount: str
    currency: Literal["AUD"]
    payment_statement: str


class BillingOperationRequest(APIModel):
    idempotency_key: str = Field(min_length=16, max_length=200, pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]*$")


class PlanChangeRequest(BillingOperationRequest):
    plan_code: PlanCode
    billing_interval: BillingInterval


class HostedActionResponse(APIModel):
    operation_id: UUID
    hosted_url: str | None
    status: Literal["succeeded", "confirmation_pending"]
    message: str


class BillingWebhookResponse(APIModel):
    outcome: Literal["processed", "duplicate", "ignored_stale", "reconciliation_required"]


class BillingSuccessResponse(APIModel):
    confirmed: bool
    status: BillingSubscriptionStatus | Literal["not_configured"]
    message: str
