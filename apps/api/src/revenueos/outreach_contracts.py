from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import ConfigDict, Field, StringConstraints

from revenueos.contracts import APIModel, to_camel
from revenueos.domain import OutreachContactability, OutreachPurpose, OutreachState, SuppressionReason

Subject = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
Body = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=10_000)]
OfferingName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]
ValueProposition = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=1_000)]
ApprovedCTA = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=300)]


class StrictOutreachModel(APIModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True, extra="forbid")


class EngageAvailabilityResponse(APIModel):
    module_key: Literal["engage"] = "engage"
    state: Literal["available", "not_in_plan", "temporarily_unavailable"]
    enabled: bool
    can_manage: bool
    message: str


class EngageEntitlementUpdate(StrictOutreachModel):
    enabled: bool


class OutreachPolicyUpdate(StrictOutreachModel):
    outbound_enabled: bool
    provider_supplied_email_allowed: bool
    cooldown_hours: int = Field(ge=0, le=720)
    max_daily_sends_user: int = Field(ge=1, le=500)
    max_daily_sends_org: int = Field(ge=1, le=2_000)
    require_opt_out_mechanism: bool = False
    offering_name: OfferingName
    value_proposition: ValueProposition
    approved_cta: ApprovedCTA


class OutreachPolicyResponse(APIModel):
    configured: bool
    outbound_enabled: bool
    provider_supplied_email_allowed: bool
    cooldown_hours: int
    max_daily_sends_user: int
    max_daily_sends_org: int
    require_opt_out_mechanism: bool
    offering_name: str | None
    value_proposition: str | None
    approved_cta: str | None
    can_manage: bool
    compliance_notice: str


class ContactabilityResponse(APIModel):
    state: OutreachContactability
    allowed: bool
    reason: str
    trust_state: Literal["verified", "provider_supplied", "unknown"]
    permission_assessed_separately: Literal[True] = True


class OutreachSourceResponse(APIModel):
    id: UUID
    source_type: Literal[
        "prospect_observation",
        "prospect_person_observation",
        "approved_seller_context",
    ]
    source_id: UUID
    label: str
    trust_state: Literal["verified", "provider_supplied", "approved"]
    publisher: str | None
    published_at: datetime | None
    url: str | None


class OutreachVersionResponse(APIModel):
    id: UUID
    version: int
    subject: str
    body: str
    sender_name: str
    sender_email: str
    recipient_name: str
    recipient_email: str
    recipient_trust: Literal["verified", "provider_supplied"]
    creation_type: Literal["generated", "user_edited"]
    composer_version: str
    personalization_used: bool
    sources: list[OutreachSourceResponse]
    warnings: list[str]
    created_at: datetime


class OutreachExecutionSummary(APIModel):
    id: UUID
    status: Literal[
        "queued",
        "sending",
        "submitted",
        "sent",
        "failed",
        "unknown_delivery_state",
        "cancelled",
        "simulated",
    ]
    simulation_only: bool
    safe_message: str
    created_at: datetime
    completed_at: datetime | None


class OutreachResponse(APIModel):
    id: UUID
    action_id: UUID
    contact_id: UUID | None
    purpose: OutreachPurpose
    state: OutreachState
    current_version: int
    approved_version: int | None
    version: OutreachVersionResponse
    contactability: ContactabilityResponse
    relationship_warning: str | None
    execution: OutreachExecutionSummary | None
    created_at: datetime
    updated_at: datetime


class OutreachHistoryItem(APIModel):
    id: UUID
    purpose: OutreachPurpose
    subject: str
    status: str
    simulation_only: bool
    created_at: datetime
    completed_at: datetime | None


class ContactOutreachWorkspaceResponse(APIModel):
    availability: EngageAvailabilityResponse
    contact_id: UUID
    contact_name: str
    company_id: UUID
    company_name: str
    job_title: str | None
    email: str | None
    email_trust: Literal["verified", "provider_supplied", "unknown"]
    permission_status: Literal["assessed_by_organisation_policy", "not_assessed"]
    contactability: ContactabilityResponse
    policy_configured: bool
    production_mailbox_available: Literal[False] = False
    simulation_available: bool
    history: list[OutreachHistoryItem]


class OutreachCreateRequest(StrictOutreachModel):
    purpose: OutreachPurpose


class OutreachEditRequest(StrictOutreachModel):
    expected_version: int = Field(ge=1)
    subject: Subject
    body: Body


class OutreachApproveRequest(StrictOutreachModel):
    expected_version: int = Field(ge=1)


class ContactSuppressionRequest(StrictOutreachModel):
    reason: SuppressionReason


class ContactSuppressionResponse(APIModel):
    id: UUID
    contact_id: UUID | None
    reason: SuppressionReason
    active: bool
    created_at: datetime
    revoked_at: datetime | None
