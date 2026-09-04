from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import ConfigDict, Field, StringConstraints, field_validator, model_validator

from revenueos.contracts import APIModel, to_camel

SellingProfileState = Literal["draft", "approved", "superseded", "retired"]
SellingProfileStatus = Literal["empty", "draft", "current", "retired"]

CompanyDescription = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2_000)]
OfferingName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]
OfferingDescription = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=800)]
OfferingPoint = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)]
IdempotencyKey = Annotated[str, StringConstraints(strip_whitespace=True, min_length=8, max_length=200)]


class StrictSellingProfileModel(APIModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        extra="forbid",
        frozen=True,
        str_strip_whitespace=True,
    )


class SellingOffering(StrictSellingProfileModel):
    name: OfferingName
    description: OfferingDescription
    who_normally_buys: tuple[OfferingPoint, ...] = Field(default=(), max_length=8)
    problems_solved: tuple[OfferingPoint, ...] = Field(default=(), max_length=8)
    intended_outcomes: tuple[OfferingPoint, ...] = Field(default=(), max_length=8)
    differentiators: tuple[OfferingPoint, ...] = Field(default=(), max_length=8)
    competitors_alternatives: tuple[OfferingPoint, ...] = Field(default=(), max_length=8)
    approved_proof: tuple[OfferingPoint, ...] = Field(default=(), max_length=8)
    approved_claims: tuple[OfferingPoint, ...] = Field(default=(), max_length=8)

    @field_validator(
        "who_normally_buys",
        "problems_solved",
        "intended_outcomes",
        "differentiators",
        "competitors_alternatives",
        "approved_proof",
        "approved_claims",
    )
    @classmethod
    def unique_points(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if len({point.casefold() for point in value}) != len(value):
            raise ValueError("Offering points must be unique within each field.")
        return value


class SellingProfileContent(StrictSellingProfileModel):
    company_description: CompanyDescription
    offerings: tuple[SellingOffering, ...] = Field(min_length=1, max_length=8)

    @model_validator(mode="after")
    def unique_offerings(self) -> SellingProfileContent:
        names = [offering.name.casefold() for offering in self.offerings]
        if len(names) != len(set(names)):
            raise ValueError("Offering names must be unique.")
        return self


class SellingProfileRevisionResponse(StrictSellingProfileModel):
    id: UUID
    profile_id: UUID
    revision_number: int
    state: SellingProfileState
    lock_version: int
    content: SellingProfileContent
    content_fingerprint: str
    created_by_user_id: UUID
    approved_by_user_id: UUID | None
    created_at: datetime
    updated_at: datetime
    approved_at: datetime | None
    superseded_at: datetime | None
    retired_at: datetime | None


class SellingProfileManagementResponse(StrictSellingProfileModel):
    status: SellingProfileStatus
    can_manage: bool
    draft: SellingProfileRevisionResponse | None
    current: SellingProfileRevisionResponse | None
    history: tuple[SellingProfileRevisionResponse, ...]
    authority: Literal["organisation_approved"] = "organisation_approved"
    authority_note: str = (
        "This profile is organisation-approved context. It is not customer Evidence or proof about a specific buyer."
    )


class SellingProfileContextResponse(StrictSellingProfileModel):
    schema_version: Literal[1] = 1
    available: bool
    authority: Literal["organisation_approved"] = "organisation_approved"
    customer_evidence: Literal[False] = False
    profile_id: UUID | None
    revision_id: UUID | None
    revision_number: int | None
    content: SellingProfileContent | None
    approved_at: datetime | None
    message: str


class SellingProfileDraftCreate(StrictSellingProfileModel):
    idempotency_key: IdempotencyKey
    content: SellingProfileContent


class SellingProfileDraftUpdate(StrictSellingProfileModel):
    expected_lock_version: int = Field(ge=1)
    content: SellingProfileContent


class SellingProfileApproveRequest(StrictSellingProfileModel):
    expected_lock_version: int = Field(ge=1)
