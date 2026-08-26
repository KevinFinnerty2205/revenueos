from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Annotated, Literal
from uuid import UUID

from pydantic import ConfigDict, Field, StringConstraints, model_validator

from revenueos.contracts import APIModel, to_camel
from revenueos.domain import (
    ActionAudience,
    ActionPriority,
    ActionRejectionReason,
    ActionRiskClass,
    ActionStatus,
    ActionType,
)

ShortText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=240)]
BodyText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=10_000)]
DescriptionText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2_000)]
LabelText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)]
EmailText = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=3,
        max_length=320,
        pattern=r"^[^\s@]+@[^\s@]+\.[^\s@]+$",
    ),
]


class StrictActionModel(APIModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        extra="forbid",
        frozen=True,
    )


class ActionSourceReference(StrictActionModel):
    source_type: Literal[
        "ai_artifact",
        "accepted_evidence",
        "interaction_intelligence",
        "revenue_brain_insight",
        "methodology_projection",
    ]
    source_id: UUID
    item_key: Annotated[
        str,
        StringConstraints(strip_whitespace=True, min_length=1, max_length=120),
    ]
    label: LabelText
    origin: Literal[
        "customer_direct",
        "salesperson_reported",
        "validated_intelligence",
        "revenue_brain",
        "methodology",
    ]


class FollowUpEmailPayload(StrictActionModel):
    kind: Literal["follow_up_email"]
    draft_artifact_id: UUID
    recipient_contact_id: UUID | None
    recipient_email: EmailText | None
    recipient_confirmed: bool = False
    subject: ShortText
    body: BodyText

    @model_validator(mode="after")
    def validate_recipient_pair(self) -> FollowUpEmailPayload:
        if (self.recipient_contact_id is None) != (self.recipient_email is None):
            raise ValueError("Recipient contact and email must be supplied together.")
        if self.recipient_confirmed and self.recipient_contact_id is None:
            raise ValueError("A recipient cannot be confirmed until a validated contact is selected.")
        return self


class PersonalizedOutreachPayload(StrictActionModel):
    kind: Literal["personalized_outreach"]
    outreach_id: UUID
    outreach_version: int = Field(ge=1)
    sender_user_id: UUID
    sender_name: ShortText
    sender_email: EmailText
    recipient_contact_id: UUID
    recipient_name: ShortText
    recipient_email: EmailText
    recipient_trust: Literal["verified", "provider_supplied"]
    recipient_confirmed: Literal[True] = True
    subject: ShortText
    body: BodyText


class RequestedMaterialPayload(StrictActionModel):
    kind: Literal["send_requested_material"]
    material: ShortText
    requested_by: ShortText | None
    recipient_contact_id: UUID | None


class CreateTaskPayload(StrictActionModel):
    kind: Literal["create_task"]
    title: ShortText
    owner_name: ShortText | None
    owner_user_id: UUID | None
    due_at: datetime | None
    context: DescriptionText
    linked_opportunity_id: UUID
    linked_interaction_id: UUID | None


class FollowUpStakeholderPayload(StrictActionModel):
    kind: Literal["follow_up_stakeholder"]
    stakeholder_name: ShortText
    contact_id: UUID | None
    purpose: DescriptionText


class ScheduleInteractionPayload(StrictActionModel):
    kind: Literal["schedule_interaction"]
    interaction_type: Literal[
        "online_meeting",
        "face_to_face_meeting",
        "presentation",
        "workshop",
        "site_visit",
        "executive_lunch",
        "phone_call",
        "conference_interaction",
        "trade_show_interaction",
        "manual_interaction",
    ]
    timeframe: ShortText | None
    participant_contact_ids: tuple[UUID, ...] = Field(max_length=20)
    purpose: DescriptionText
    objective: DescriptionText


class OpportunityUpdatePayload(StrictActionModel):
    kind: Literal["update_opportunity"]
    field: Literal[
        "stage",
        "status",
        "expected_close_date",
        "description",
        "estimated_value",
        "currency",
        "next_step",
    ]
    current_value: str | Decimal | None
    proposed_value: str | Decimal | None
    reason: DescriptionText


class ContactUpdatePayload(StrictActionModel):
    kind: Literal["update_contact"]
    operation: Literal["add", "update"]
    contact_id: UUID | None
    first_name: ShortText
    last_name: ShortText
    email: EmailText | None
    job_title: ShortText | None
    current_values: dict[str, str | None]


class LogInteractionPayload(StrictActionModel):
    kind: Literal["log_interaction"]
    interaction_id: UUID
    occurred_at: datetime
    interaction_type: Literal[
        "online_meeting",
        "face_to_face_meeting",
        "presentation",
        "workshop",
        "site_visit",
        "executive_lunch",
        "phone_call",
        "conference_interaction",
        "trade_show_interaction",
        "manual_interaction",
    ]
    title: ShortText
    summary: DescriptionText
    agreed_next_steps: tuple[LabelText, ...] = Field(max_length=8)


class StakeholderUpdatePayload(StrictActionModel):
    kind: Literal["update_stakeholder"]
    contact_id: UUID | None
    stakeholder_name: ShortText
    role: Literal[
        "economic_buyer_candidate",
        "decision_maker",
        "champion",
        "technical_buyer",
        "procurement",
        "legal_security",
        "blocker",
        "participant",
        "unknown",
    ]
    current_role: ShortText | None
    reason: DescriptionText


class RecordDecisionPayload(StrictActionModel):
    kind: Literal["add_decision"]
    decision: DescriptionText
    owner_name: ShortText | None


class RecordCommitmentPayload(StrictActionModel):
    kind: Literal["add_commitment"]
    commitment: DescriptionText
    owner_name: ShortText | None
    due_at: datetime | None


class RecordRiskPayload(StrictActionModel):
    kind: Literal["add_risk"]
    risk: DescriptionText
    severity: Literal["high", "normal", "low"]
    owner_name: ShortText | None


class UpdateTimelinePayload(StrictActionModel):
    kind: Literal["update_timeline"]
    current_value: ShortText | None
    proposed_value: ShortText
    reason: DescriptionText


class UpdateProcurementPayload(StrictActionModel):
    kind: Literal["update_procurement"]
    current_value: ShortText | None
    proposed_value: ShortText
    reason: DescriptionText


class UpdateSecurityLegalPayload(StrictActionModel):
    kind: Literal["update_security_legal"]
    area: Literal["security", "legal", "security_and_legal"]
    current_value: ShortText | None
    proposed_value: ShortText
    reason: DescriptionText


class CreateReminderPayload(StrictActionModel):
    kind: Literal["create_reminder"]
    reminder: DescriptionText
    due_at: datetime | None


class NotifyInternalPayload(StrictActionModel):
    kind: Literal["notify_internal"]
    recipient_user_id: UUID | None
    reason: DescriptionText
    severity: Literal["high", "normal", "low"]


class PrepareNextInteractionPayload(StrictActionModel):
    kind: Literal["prepare_next_interaction"]
    objective: DescriptionText
    preparation_notes: tuple[LabelText, ...] = Field(max_length=8)


class ResolveOpenQuestionPayload(StrictActionModel):
    kind: Literal["resolve_open_question"]
    question: DescriptionText
    owner_name: ShortText | None


class ReviewConflictPayload(StrictActionModel):
    kind: Literal["review_conflict"]
    subject: ShortText
    conflicting_claims: tuple[DescriptionText, ...] = Field(min_length=2, max_length=5)


class OtherActionPayload(StrictActionModel):
    kind: Literal["other"]
    instruction: DescriptionText


ActionPayload = Annotated[
    FollowUpEmailPayload
    | PersonalizedOutreachPayload
    | RequestedMaterialPayload
    | CreateTaskPayload
    | FollowUpStakeholderPayload
    | ScheduleInteractionPayload
    | OpportunityUpdatePayload
    | ContactUpdatePayload
    | LogInteractionPayload
    | StakeholderUpdatePayload
    | RecordDecisionPayload
    | RecordCommitmentPayload
    | RecordRiskPayload
    | UpdateTimelinePayload
    | UpdateProcurementPayload
    | UpdateSecurityLegalPayload
    | CreateReminderPayload
    | NotifyInternalPayload
    | PrepareNextInteractionPayload
    | ResolveOpenQuestionPayload
    | ReviewConflictPayload
    | OtherActionPayload,
    Field(discriminator="kind"),
]


class ActionProposalResponse(APIModel):
    id: UUID
    organisation_id: UUID
    opportunity_id: UUID | None
    interaction_id: UUID | None
    action_type: ActionType
    status: ActionStatus
    priority: ActionPriority
    audience: ActionAudience
    risk_class: ActionRiskClass
    current_version: int
    approved_version: int | None
    title: str
    description: str
    proposed_due_at: datetime | None
    target_entity_type: str | None
    target_entity_id: UUID | None
    proposed_payload: ActionPayload
    source_refs: list[ActionSourceReference]
    provenance_summary: str
    generated_at: datetime
    version_created_at: datetime
    created_by_user_id: UUID
    reviewed_by_user_id: UUID | None
    reviewed_at: datetime | None
    approved_at: datetime | None
    rejected_at: datetime | None
    rejection_reason_code: ActionRejectionReason | None
    supersedes_action_id: UUID | None
    completed_by_user_id: UUID | None
    completed_at: datetime | None
    execution_state: Literal["not_executed"] = "not_executed"
    send_ready: bool = False


class ActionListResponse(APIModel):
    items: list[ActionProposalResponse]
    total: int


class ActionGenerationResponse(APIModel):
    actions: list[ActionProposalResponse]
    created_count: int
    reused_count: int
    superseded_count: int
    proposal_limit: int
    provider_composition_used: Literal[False] = False
    external_actions_executed: Literal[False] = False


class ActionEditRequest(APIModel):
    expected_version: int = Field(ge=1)
    title: ShortText
    description: DescriptionText
    proposed_due_at: datetime | None
    proposed_payload: ActionPayload


class ActionReviewRequest(APIModel):
    expected_version: int = Field(ge=1)


class ActionRejectRequest(ActionReviewRequest):
    reason_code: ActionRejectionReason
