from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Literal
from uuid import UUID

from pydantic import Field, StringConstraints

from revenueos.contracts import APIModel
from revenueos.sales_analytics_contracts import MetricUnit
from revenueos.sales_target_policy import TargetCategory, TargetScope

TargetOrigin = Literal["self_set", "admin_assigned"]
TargetPeriodType = Literal["month", "quarter", "year"]
TargetStatus = Literal["upcoming", "active", "past", "archived"]
TargetListView = Literal["current", "past", "archived", "all"]
TargetProgressState = Literal["available", "upcoming", "unavailable"]

GoalValueText = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=1,
        max_length=24,
        pattern=r"^(0|[1-9][0-9]*)(\.[0-9]{1,2})?$",
    ),
]
CurrencyCode = Annotated[str, StringConstraints(strip_whitespace=True, to_upper=True, pattern=r"^[A-Z]{3}$")]


class SalesTargetMetricPolicyResponse(APIModel):
    metric_id: str
    definition_version: str
    label: str
    description: str
    unit: MetricUnit
    category: TargetCategory
    allowed_scopes: list[TargetScope]
    requires_currency: bool
    display_order: int = Field(ge=1)
    date_semantics: str
    exclusions: list[str]


class SalesTargetOwnerResponse(APIModel):
    user_id: UUID
    display_name: str


class SalesTargetPipelineResponse(APIModel):
    id: UUID
    name: str
    active: bool


class SalesTargetMetadataResponse(APIModel):
    current_user_id: UUID
    current_user_role: Literal["admin", "member"]
    organisation_timezone: str
    metrics: list[SalesTargetMetricPolicyResponse]
    owners: list[SalesTargetOwnerResponse]
    pipelines: list[SalesTargetPipelineResponse]
    can_assign_personal_targets: bool
    can_create_organisation_targets: bool


class SalesTargetCreateRequest(APIModel):
    metric_id: str = Field(min_length=1, max_length=80)
    metric_definition_version: str = Field(min_length=1, max_length=20)
    scope: TargetScope
    origin: TargetOrigin
    owner_user_id: UUID | None = None
    pipeline_id: UUID | None = None
    period_type: TargetPeriodType
    period_anchor: date
    goal_value: GoalValueText
    currency: CurrencyCode | None = None


class SalesTargetRevisionCreateRequest(APIModel):
    goal_value: GoalValueText
    expected_revision_number: int = Field(ge=1)


class SalesTargetArchiveRequest(APIModel):
    confirmed: Literal[True]


class SalesTargetRevisionResponse(APIModel):
    id: UUID
    revision_number: int = Field(ge=1)
    goal_value: Decimal = Field(gt=0)
    created_by_user_id: UUID
    created_by_display_name: str
    created_at: datetime


class SalesTargetProgressResponse(APIModel):
    state: TargetProgressState
    actual_value: Decimal | None = Field(default=None, ge=0)
    target_value: Decimal = Field(gt=0)
    remaining_value: Decimal | None = Field(default=None, ge=0)
    above_target_value: Decimal | None = Field(default=None, ge=0)
    percentage_complete: Decimal | None = Field(default=None, ge=0)
    target_reached: bool | None
    calculated_through: date | None
    generated_at: datetime
    disclosures: list[str]


class SalesTargetResponse(APIModel):
    id: UUID
    metric: SalesTargetMetricPolicyResponse
    scope: TargetScope
    origin: TargetOrigin
    owner_user_id: UUID | None
    owner_display_name: str | None
    pipeline_id: UUID | None
    pipeline_name: str | None
    period_type: TargetPeriodType
    period_start: date
    period_end: date
    period_label: str
    timezone: str
    currency: str | None
    status: TargetStatus
    latest_revision: SalesTargetRevisionResponse
    revisions: list[SalesTargetRevisionResponse]
    progress: SalesTargetProgressResponse
    created_by_user_id: UUID
    created_by_display_name: str
    archived_at: datetime | None
    created_at: datetime
    updated_at: datetime
    can_revise: bool
    can_archive: bool


class SalesTargetListResponse(APIModel):
    items: list[SalesTargetResponse]
    can_assign_personal_targets: bool
    can_create_organisation_targets: bool
    maximum_visible_targets: int = 200
