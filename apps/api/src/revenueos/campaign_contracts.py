from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal, Self
from uuid import UUID

from pydantic import ConfigDict, Field, StringConstraints, model_validator

from revenueos.contracts import APIModel, to_camel
from revenueos.domain import (
    CampaignApprovalMode,
    CampaignEnrollmentState,
    CampaignOutcome,
    CampaignState,
    CampaignStepState,
    SequenceStepObjective,
)
from revenueos.outreach_contracts import OutreachResponse

CampaignName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=160)]
CampaignPurpose = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=300)]


class StrictCampaignModel(APIModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True, extra="forbid")


class CampaignSequenceStepInput(StrictCampaignModel):
    delay_days: int = Field(ge=0, le=30)
    objective: SequenceStepObjective
    content_strategy: Literal[
        "source_backed_value",
        "truthful_follow_up",
        "source_backed_new_angle",
        "respectful_close",
    ]
    enabled: bool = True


class CampaignDraftFields(StrictCampaignModel):
    name: CampaignName
    purpose: CampaignPurpose
    approval_mode: CampaignApprovalMode = CampaignApprovalMode.REVIEW_EACH_SEND
    source_type: Literal["manual_contacts", "target_market", "event_attendees"] = "manual_contacts"
    event_id: UUID | None = None
    event_stage: Literal["pre_event", "post_event"] | None = None
    sender_timezone: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=64)] = (
        "Australia/Sydney"
    )
    send_days: list[int] = Field(default_factory=lambda: [1, 2, 3, 4, 5], min_length=1, max_length=7)
    send_window_start_minutes: int = Field(default=510, ge=0, le=1438)
    send_window_end_minutes: int = Field(default=1020, ge=1, le=1439)
    stop_on_active_opportunity: bool = True
    steps: list[CampaignSequenceStepInput] = Field(min_length=1, max_length=4)
    contact_ids: list[UUID] = Field(min_length=1, max_length=50)

    @model_validator(mode="after")
    def validate_campaign(self) -> Self:
        if len(set(self.contact_ids)) != len(self.contact_ids):
            raise ValueError("Campaign Contacts must be unique.")
        if len(set(self.send_days)) != len(self.send_days) or any(day < 1 or day > 7 for day in self.send_days):
            raise ValueError("Send days must contain unique ISO weekdays from 1 to 7.")
        if self.send_window_start_minutes >= self.send_window_end_minutes:
            raise ValueError("The send window start must be before its end.")
        if self.steps[0].delay_days != 0:
            raise ValueError("The first sequence step must have a zero-day delay.")
        if any(step.delay_days < 1 for step in self.steps[1:]):
            raise ValueError("Every follow-up step must wait at least one calendar day.")
        final_positions = [
            index for index, step in enumerate(self.steps) if step.objective is SequenceStepObjective.FINAL_FOLLOW_UP
        ]
        if final_positions and final_positions != [len(self.steps) - 1]:
            raise ValueError("Final follow-up may appear only as the last step.")
        if self.source_type == "event_attendees":
            if self.event_id is None or self.event_stage is None:
                raise ValueError("Event attendee campaigns require an Event and a pre- or post-Event stage.")
        elif self.event_id is not None or self.event_stage is not None:
            raise ValueError("Event context is only accepted for an Event attendee campaign.")
        return self


class CampaignCreateRequest(CampaignDraftFields):
    pass


class CampaignUpdateRequest(CampaignDraftFields):
    expected_version: int = Field(ge=1)


class CampaignLaunchRequest(StrictCampaignModel):
    expected_version: int = Field(ge=1)
    confirmed: Literal[True]
    auto_send_confirmed: bool = False


class CampaignConfirmedRequest(StrictCampaignModel):
    confirmed: Literal[True]


class CampaignOutcomeRequest(StrictCampaignModel):
    outcome: CampaignOutcome


class CampaignSequenceStepResponse(APIModel):
    id: UUID
    step_order: int
    delay_days: int
    objective: SequenceStepObjective
    content_strategy: str
    enabled: bool


class CampaignAudienceItemResponse(APIModel):
    id: UUID
    contact_id: UUID | None
    company_id: UUID | None
    recipient_name: str
    recipient_email: str | None
    recipient_trust: Literal["verified", "provider_supplied", "unknown"]
    eligible: bool
    eligibility_code: str
    eligibility_reason: str


class CampaignMetricsResponse(APIModel):
    recipients: int
    active: int
    completed: int
    stopped: int
    blocked: int
    needs_attention: int
    messages_sent: int
    messages_ready_for_review: int
    messages_failed: int
    replies_reported: int
    meetings_reported: int


class CampaignListItemResponse(APIModel):
    id: UUID
    name: str
    purpose: str
    state: CampaignState
    approval_mode: CampaignApprovalMode
    owner_user_id: UUID
    audience_count: int
    eligible_count: int
    blocked_count: int
    current_version: int
    launched_at: datetime | None
    updated_at: datetime


class CampaignListResponse(APIModel):
    items: list[CampaignListItemResponse]
    total: int
    can_create: bool
    simulation_only: bool
    production_mailbox_available: Literal[False] = False


class CampaignResponse(APIModel):
    id: UUID
    version_id: UUID
    version: int
    name: str
    purpose: str
    state: CampaignState
    approval_mode: CampaignApprovalMode
    owner_user_id: UUID
    sender_user_id: UUID
    source_type: Literal["manual_contacts", "target_market", "event_attendees"]
    event_id: UUID | None = None
    event_stage: Literal["pre_event", "post_event"] | None = None
    sender_timezone: str
    send_days: list[int]
    send_window_start_minutes: int
    send_window_end_minutes: int
    stop_on_active_opportunity: bool
    policy_version: int | None
    audience_count: int
    eligible_count: int
    blocked_count: int
    steps: list[CampaignSequenceStepResponse]
    audience: list[CampaignAudienceItemResponse]
    metrics: CampaignMetricsResponse
    can_manage: bool
    can_launch: bool
    campaign_auto_send_allowed: bool
    simulation_only: bool
    production_mailbox_available: Literal[False] = False
    launch_warning: str | None
    needs_attention_reason: str | None
    launched_at: datetime | None
    created_at: datetime
    updated_at: datetime


class CampaignEnrollmentStepResponse(APIModel):
    id: UUID
    step_order: int
    objective: SequenceStepObjective
    scheduled_at: datetime
    state: CampaignStepState
    safe_status_code: str | None
    outreach_message_id: UUID | None
    prepared_at: datetime | None
    sent_at: datetime | None


class CampaignEnrollmentResponse(APIModel):
    id: UUID
    campaign_id: UUID
    contact_id: UUID | None
    company_id: UUID | None
    recipient_name: str
    recipient_email: str
    recipient_trust: Literal["verified", "provider_supplied"]
    state: CampaignEnrollmentState
    current_step_order: int
    next_scheduled_at: datetime | None
    stop_reason: str | None
    outcome: CampaignOutcome | None
    outcome_provenance: Literal["seller_reported"] | None
    steps: list[CampaignEnrollmentStepResponse]
    current_outreach: OutreachResponse | None
    created_at: datetime
    updated_at: datetime


class CampaignEnrollmentListResponse(APIModel):
    items: list[CampaignEnrollmentResponse]
    total: int
