from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import Field

from revenueos.contracts import APIModel

CreditType = Literal["purchased", "promotional"]
CreditLedgerEventType = Literal[
    "purchase",
    "promotional_grant",
    "reservation",
    "consumption",
    "release",
    "refund",
    "correction",
    "expiry",
]
CreditOperationStatus = Literal["reserved", "executing", "unknown", "settled", "released"]
CreditOperationOutcome = Literal[
    "pending",
    "success",
    "partial",
    "failure",
    "unknown",
    "reconciled_success",
    "reconciled_failure",
]


class CreditBalanceResponse(APIModel):
    available: int = Field(ge=0)
    purchased_available: int = Field(ge=0)
    promotional_available: int = Field(ge=0)
    reserved: int = Field(ge=0)
    purchased_reserved: int = Field(ge=0)
    promotional_reserved: int = Field(ge=0)
    total_held: int = Field(ge=0)


class CreditActivityResponse(APIModel):
    id: UUID
    event_type: CreditLedgerEventType
    credit_type: CreditType
    available_change: int
    reserved_change: int
    action_code: str | None
    operation_id: UUID | None
    reason: str
    created_at: datetime


class CreditPackResponse(APIModel):
    id: UUID
    pack_code: str
    display_name: str
    version: int
    credit_quantity: int
    amount_minor_units: int
    currency: Literal["AUD"]
    test_only: Literal[True]
    purchase_available: Literal[False]
    pricing_note: str


class CreditsProjectionResponse(APIModel):
    unit_name: Literal["Oryntela Credit"]
    balance: CreditBalanceResponse
    recent_activity: list[CreditActivityResponse]
    test_packs: list[CreditPackResponse]
    low_balance: bool
    auto_top_up: Literal[False]
    production_prices_available: Literal[False]
    message: str


class CreditQuoteRequest(APIModel):
    action_code: str = Field(min_length=3, max_length=100, pattern=r"^[A-Z][A-Z0-9_]*$")
    quantity: int = Field(ge=1, le=1_000_000)


class CreditQuoteResponse(APIModel):
    quote_id: UUID
    action_price_version_id: UUID
    action_code: str
    action_name: str
    quantity: int
    credit_cost_per_unit: int
    maximum_credit_cost: int
    current_balance: int
    sufficient_balance: bool
    expires_at: datetime
    pricing_notice: str


class CreditReservationRequest(APIModel):
    quote_id: UUID
    idempotency_key: str = Field(min_length=8, max_length=200)


class CreditOperationResponse(APIModel):
    operation_id: UUID
    quote_id: UUID
    action_price_version_id: UUID
    action_code: str
    quantity: int
    reserved_credits: int
    settled_credits: int
    released_credits: int
    successful_units: int
    status: CreditOperationStatus
    outcome: CreditOperationOutcome
    provider_execution_authorised: bool


class CreditReconciliationResponse(APIModel):
    consistent: bool
    projection_purchased_available: int
    ledger_purchased_available: int
    projection_promotional_available: int
    ledger_promotional_available: int
    projection_reserved: int
    ledger_reserved: int
    lot_available: int
    lot_reserved: int


class MarginValidationResponse(APIModel):
    customer_revenue_micros: int
    maximum_variable_cost_micros: int
    gross_profit_micros: int
    gross_margin_basis_points: int
    required_margin_basis_points: int | None
    positive_margin: bool
    meets_required_margin: bool
    production_eligible: bool
