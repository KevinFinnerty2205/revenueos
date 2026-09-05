from datetime import datetime
from typing import Literal

from pydantic import Field

from revenueos.contracts import APIModel

PlanCode = Literal["core", "growth", "complete", "enterprise"]
BillingInterval = Literal["monthly", "annual"]
CommercialStatus = Literal["trial_active", "active", "grace", "expired", "inactive", "suspended"]
ModuleCode = Literal["core", "prospect", "engage", "create", "crm"]
ModuleAccess = Literal["none", "read", "write"]
OperationalStatus = Literal["available", "mock_only", "unavailable"]


class CommercialPlanResponse(APIModel):
    code: PlanCode
    display_name: str
    version: int


class CommercialModuleResponse(APIModel):
    code: ModuleCode
    display_name: str
    access_level: ModuleAccess
    commercially_included: bool
    operational_status: OperationalStatus


class CommercialTrialResponse(APIModel):
    length_days: Literal[14] = 14
    started_at: datetime | None
    ends_at: datetime | None
    grace_ends_at: datetime | None
    days_remaining: int = Field(ge=0, le=14)
    automatic_charge: Literal[False] = False
    payment_method_required: Literal[False] = False


class CommercialProjectionResponse(APIModel):
    plan: CommercialPlanResponse
    status: CommercialStatus
    billing_interval: BillingInterval | None
    trial: CommercialTrialResponse
    included_user_limit: int | None
    active_user_count: int = Field(ge=0)
    seats_available: int | None = Field(default=None, ge=0)
    seat_limit_status: Literal["within_limit", "requires_resolution"]
    modules: list[CommercialModuleResponse]
    effective_at: datetime
    state_version: int = Field(gt=0)
    can_create_new_work: bool
    read_access_ends_at: datetime | None
    message: str


class InternalPlanVersionResponse(APIModel):
    id: str
    code: PlanCode
    display_name: str
    version: int
    monthly_price_amount: str | None
    annual_price_amount: str | None
    currency: Literal["AUD"]
    included_user_limit: int | None
    modules: list[ModuleCode]
    status: Literal["active", "retired"]
