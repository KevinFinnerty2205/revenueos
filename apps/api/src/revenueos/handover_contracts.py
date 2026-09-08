from __future__ import annotations

from datetime import date, datetime
from typing import Annotated, Literal, Self
from uuid import UUID

from pydantic import Field, StringConstraints, field_validator, model_validator

from revenueos.contracts import APIModel
from revenueos.domain import ClosedWonHandoverStatus, HandoverAuthorityType, HandoverSourceType

HandoverSectionKey = Literal[
    "executive_summary",
    "customer_objectives",
    "why_they_bought",
    "commercial_scope",
    "key_stakeholders",
    "commitments",
    "success_criteria",
    "implementation_expectations",
    "risks",
    "open_items",
    "timeline",
    "next_actions",
]
HandoverRiskKind = Literal["observed_risk", "seller_concern", "system_inference"]
HandoverActionStatus = Literal["open", "in_progress", "completed", "cancelled"]
BoundedClaim = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2_000)]
BoundedLabel = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=240)]

SECTION_KEYS: tuple[HandoverSectionKey, ...] = (
    "executive_summary",
    "customer_objectives",
    "why_they_bought",
    "commercial_scope",
    "key_stakeholders",
    "commitments",
    "success_criteria",
    "implementation_expectations",
    "risks",
    "open_items",
    "timeline",
    "next_actions",
)
SECTION_ITEM_LIMITS: dict[HandoverSectionKey, int] = {
    "executive_summary": 5,
    "customer_objectives": 20,
    "why_they_bought": 12,
    "commercial_scope": 20,
    "key_stakeholders": 30,
    "commitments": 30,
    "success_criteria": 20,
    "implementation_expectations": 30,
    "risks": 30,
    "open_items": 30,
    "timeline": 30,
    "next_actions": 30,
}
MAX_HANDOVER_ITEMS = 120


class HandoverItem(APIModel):
    id: UUID
    text: BoundedClaim
    authority_type: HandoverAuthorityType
    source_ids: list[UUID] = Field(default_factory=list, max_length=8)
    confirmed_by_user_id: UUID | None = None
    confirmed_at: datetime | None = None
    owner: Annotated[str | None, StringConstraints(strip_whitespace=True, min_length=1, max_length=160)] = None
    due_date: date | None = None
    action_status: HandoverActionStatus | None = None
    risk_kind: HandoverRiskKind | None = None

    @field_validator("source_ids")
    @classmethod
    def unique_sources(cls, value: list[UUID]) -> list[UUID]:
        if len(value) != len(set(value)):
            raise ValueError("A handover item cannot cite the same source twice.")
        return value

    @model_validator(mode="after")
    def coherent_authority(self) -> Self:
        if (
            self.authority_type
            in {
                HandoverAuthorityType.CUSTOMER_EVIDENCE,
                HandoverAuthorityType.COMMERCIAL_RECORD,
                HandoverAuthorityType.CUSTOMER_FACING_APPROVED,
                HandoverAuthorityType.SYSTEM_DERIVED,
            }
            and not self.source_ids
        ):
            raise ValueError("Source-backed handover items require at least one pinned source.")
        confirmed = self.confirmed_by_user_id is not None and self.confirmed_at is not None
        if self.authority_type == HandoverAuthorityType.SELLER_CONFIRMED and not confirmed:
            raise ValueError("Seller-confirmed handover items require a confirming actor and timestamp.")
        if self.authority_type != HandoverAuthorityType.SELLER_CONFIRMED and (
            self.confirmed_by_user_id is not None or self.confirmed_at is not None
        ):
            raise ValueError("Only seller-confirmed handover items carry confirmation metadata.")
        if self.confirmed_at is not None and self.confirmed_at.utcoffset() is None:
            raise ValueError("confirmedAt must include a timezone.")
        return self


class HandoverContent(APIModel):
    schema_version: Literal[1] = 1
    executive_summary: list[HandoverItem] = Field(
        default_factory=list, max_length=SECTION_ITEM_LIMITS["executive_summary"]
    )
    customer_objectives: list[HandoverItem] = Field(
        default_factory=list, max_length=SECTION_ITEM_LIMITS["customer_objectives"]
    )
    why_they_bought: list[HandoverItem] = Field(default_factory=list, max_length=SECTION_ITEM_LIMITS["why_they_bought"])
    commercial_scope: list[HandoverItem] = Field(
        default_factory=list, max_length=SECTION_ITEM_LIMITS["commercial_scope"]
    )
    key_stakeholders: list[HandoverItem] = Field(
        default_factory=list, max_length=SECTION_ITEM_LIMITS["key_stakeholders"]
    )
    commitments: list[HandoverItem] = Field(default_factory=list, max_length=SECTION_ITEM_LIMITS["commitments"])
    success_criteria: list[HandoverItem] = Field(
        default_factory=list, max_length=SECTION_ITEM_LIMITS["success_criteria"]
    )
    implementation_expectations: list[HandoverItem] = Field(
        default_factory=list, max_length=SECTION_ITEM_LIMITS["implementation_expectations"]
    )
    risks: list[HandoverItem] = Field(default_factory=list, max_length=SECTION_ITEM_LIMITS["risks"])
    open_items: list[HandoverItem] = Field(default_factory=list, max_length=SECTION_ITEM_LIMITS["open_items"])
    timeline: list[HandoverItem] = Field(default_factory=list, max_length=SECTION_ITEM_LIMITS["timeline"])
    next_actions: list[HandoverItem] = Field(default_factory=list, max_length=SECTION_ITEM_LIMITS["next_actions"])

    @model_validator(mode="after")
    def bounded_and_section_specific(self) -> Self:
        all_items: list[HandoverItem] = []
        for key in SECTION_KEYS:
            items = getattr(self, key)
            all_items.extend(items)
            for item in items:
                if key != "next_actions" and (
                    item.owner is not None or item.due_date is not None or item.action_status is not None
                ):
                    raise ValueError("Action owner, due date and status belong only in Next Actions.")
                if key != "risks" and item.risk_kind is not None:
                    raise ValueError("Risk classification belongs only in Risks.")
        if len(all_items) > MAX_HANDOVER_ITEMS:
            raise ValueError(f"A handover can contain at most {MAX_HANDOVER_ITEMS} items.")
        identifiers = [item.id for item in all_items]
        if len(identifiers) != len(set(identifiers)):
            raise ValueError("Every handover item must have a unique id.")
        return self


class HandoverContentUpdate(APIModel):
    expected_handover_version: int = Field(ge=1)
    expected_revision_version: int = Field(ge=1)
    content: HandoverContent


class HandoverLifecycleRequest(APIModel):
    expected_handover_version: int = Field(ge=1)
    expected_revision_version: int = Field(ge=1)
    confirmed: Literal[True]


class HandoverClaimConfirmationRequest(HandoverLifecycleRequest):
    item_id: UUID


class HandoverSourceResponse(APIModel):
    id: UUID
    source_type: HandoverSourceType
    source_id: UUID
    source_version_id: UUID | None
    source_version: int | None
    authority_type: HandoverAuthorityType
    label: BoundedLabel
    source_fingerprint: str
    pinned_at: datetime


class HandoverRevisionSummary(APIModel):
    id: UUID
    revision: int
    status: ClosedWonHandoverStatus
    created_by_user_id: UUID
    submitted_at: datetime | None
    approved_by_user_id: UUID | None
    approved_at: datetime | None
    superseded_at: datetime | None
    retired_at: datetime | None
    retirement_reason: str | None
    created_at: datetime
    updated_at: datetime


class HandoverRevisionResponse(HandoverRevisionSummary):
    handover_id: UUID
    opportunity_id: UUID
    content_schema_version: Literal[1]
    content: HandoverContent
    sources: list[HandoverSourceResponse]
    lock_version: int
    approval_blockers: list[str]


class HandoverWorkspaceResponse(APIModel):
    handover_id: UUID | None
    opportunity_id: UUID
    opportunity_status: Literal["open", "won", "lost", "on_hold"]
    handover_lock_version: int | None
    active_revision: HandoverRevisionResponse | None
    current_approved_revision: HandoverRevisionSummary | None
    history: list[HandoverRevisionSummary]
    can_manage: bool
    can_approve: bool
    entitlement: Literal["create"] = "create"
    credits_required: Literal[False] = False
    ai_drafting: Literal["not_used"] = "not_used"
