from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Annotated, ClassVar
from uuid import UUID

from pydantic import (
    EmailStr,
    Field,
    HttpUrl,
    StringConstraints,
    field_validator,
    model_validator,
)

from revenueos.contracts import APIModel
from revenueos.domain import (
    CompanyStatus,
    OpportunityStage,
    OpportunityStatus,
    TaskPriority,
    TaskStatus,
)

Name200 = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
Name100 = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]
OptionalText120 = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]
OptionalText150 = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=150)]
OptionalPhone = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=50)]
Description = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=10_000)]
CurrencyCode = Annotated[str, StringConstraints(strip_whitespace=True, to_upper=True, pattern=r"^[A-Z]{3}$")]


class Page[T](APIModel):
    items: list[T]
    page: int
    page_size: int
    total: int
    pages: int


class UpdateRequest(APIModel):
    required_when_present: ClassVar[frozenset[str]] = frozenset()

    @model_validator(mode="after")
    def validate_update_fields(self) -> UpdateRequest:
        if not self.model_fields_set:
            raise ValueError("At least one field must be supplied.")
        for field_name in self.required_when_present:
            if field_name in self.model_fields_set and getattr(self, field_name) is None:
                raise ValueError(f"{field_name} cannot be null.")
        return self


class CompanyCreate(APIModel):
    name: Name200
    website: HttpUrl | None = None
    industry: OptionalText120 | None = None
    employee_count: int | None = Field(default=None, ge=0, le=2_147_483_647)
    status: CompanyStatus = CompanyStatus.PROSPECT
    owner_user_id: UUID | None = None


class CompanyUpdate(UpdateRequest):
    required_when_present = frozenset({"name", "status", "owner_user_id"})

    name: Name200 | None = None
    website: HttpUrl | None = None
    industry: OptionalText120 | None = None
    employee_count: int | None = Field(default=None, ge=0, le=2_147_483_647)
    status: CompanyStatus | None = None
    owner_user_id: UUID | None = None


class CompanyResponse(APIModel):
    id: UUID
    organisation_id: UUID
    name: str
    website: str | None
    industry: str | None
    employee_count: int | None
    status: CompanyStatus
    owner_user_id: UUID
    created_at: datetime
    updated_at: datetime


class ContactCreate(APIModel):
    company_id: UUID
    first_name: Name100
    last_name: Name100
    email: EmailStr
    phone: OptionalPhone | None = None
    job_title: OptionalText150 | None = None
    linkedin_url: HttpUrl | None = None
    owner_user_id: UUID | None = None


class ContactUpdate(UpdateRequest):
    required_when_present = frozenset({"company_id", "first_name", "last_name", "email", "owner_user_id"})

    company_id: UUID | None = None
    first_name: Name100 | None = None
    last_name: Name100 | None = None
    email: EmailStr | None = None
    phone: OptionalPhone | None = None
    job_title: OptionalText150 | None = None
    linkedin_url: HttpUrl | None = None
    owner_user_id: UUID | None = None


class ContactResponse(APIModel):
    id: UUID
    organisation_id: UUID
    company_id: UUID
    first_name: str
    last_name: str
    email: str
    phone: str | None
    job_title: str | None
    linkedin_url: str | None
    owner_user_id: UUID
    created_at: datetime
    updated_at: datetime


class OpportunityCreate(APIModel):
    company_id: UUID | None = None
    name: Name200
    stage: OpportunityStage = OpportunityStage.DISCOVERY
    status: OpportunityStatus = OpportunityStatus.OPEN
    estimated_value: Decimal | None = Field(default=None, ge=0, max_digits=18, decimal_places=2)
    currency: CurrencyCode | None = None
    expected_close_date: date | None = None
    owner_user_id: UUID | None = None
    description: Description | None = None

    @model_validator(mode="after")
    def validate_value_currency(self) -> OpportunityCreate:
        if (self.estimated_value is None) != (self.currency is None):
            raise ValueError("estimatedValue and currency must be supplied together.")
        return self


class OpportunityUpdate(UpdateRequest):
    required_when_present = frozenset(
        {
            "name",
            "stage",
            "status",
            "owner_user_id",
        }
    )

    company_id: UUID | None = None
    name: Name200 | None = None
    stage: OpportunityStage | None = None
    status: OpportunityStatus | None = None
    estimated_value: Decimal | None = Field(default=None, ge=0, max_digits=18, decimal_places=2)
    currency: CurrencyCode | None = None
    expected_close_date: date | None = None
    owner_user_id: UUID | None = None
    description: Description | None = None
    expected_updated_at: datetime | None = None

    @model_validator(mode="after")
    def validate_value_currency(self) -> OpportunityUpdate:
        if "expected_updated_at" in self.model_fields_set:
            value = self.expected_updated_at
            if value is None:
                raise ValueError("expectedUpdatedAt cannot be null.")
            if value.utcoffset() is None:
                self.expected_updated_at = value.replace(tzinfo=UTC)
        changed = self.model_fields_set - {"expected_updated_at"}
        if not changed:
            raise ValueError("At least one opportunity field must be supplied.")
        if ("estimated_value" in changed) != ("currency" in changed):
            raise ValueError("estimatedValue and currency must be updated together.")
        if "estimated_value" in changed and ((self.estimated_value is None) != (self.currency is None)):
            raise ValueError("estimatedValue and currency must be supplied together.")
        return self


class OpportunityResponse(APIModel):
    id: UUID
    organisation_id: UUID
    company_id: UUID | None
    name: str
    stage: OpportunityStage
    status: OpportunityStatus
    estimated_value: Decimal | None
    currency: str | None
    expected_close_date: date | None
    owner_user_id: UUID
    description: str | None
    created_at: datetime
    updated_at: datetime


class TaskCreate(APIModel):
    company_id: UUID | None = None
    contact_id: UUID | None = None
    opportunity_id: UUID | None = None
    title: Name200
    description: Description | None = None
    status: TaskStatus = TaskStatus.OPEN
    priority: TaskPriority = TaskPriority.MEDIUM
    due_at: datetime | None = None
    assigned_user_id: UUID | None = None

    @field_validator("due_at")
    @classmethod
    def due_at_must_include_timezone(cls, value: datetime | None) -> datetime | None:
        if value is not None and value.utcoffset() is None:
            raise ValueError("due_at must include a timezone.")
        return value


class TaskUpdate(UpdateRequest):
    required_when_present = frozenset({"title", "status", "priority"})

    company_id: UUID | None = None
    contact_id: UUID | None = None
    opportunity_id: UUID | None = None
    title: Name200 | None = None
    description: Description | None = None
    status: TaskStatus | None = None
    priority: TaskPriority | None = None
    due_at: datetime | None = None
    assigned_user_id: UUID | None = None

    @field_validator("due_at")
    @classmethod
    def due_at_must_include_timezone(cls, value: datetime | None) -> datetime | None:
        if value is not None and value.utcoffset() is None:
            raise ValueError("due_at must include a timezone.")
        return value


class TaskResponse(APIModel):
    id: UUID
    organisation_id: UUID
    company_id: UUID | None
    contact_id: UUID | None
    opportunity_id: UUID | None
    title: str
    description: str | None
    status: TaskStatus
    priority: TaskPriority
    due_at: datetime | None
    assigned_user_id: UUID | None
    created_by_user_id: UUID
    created_at: datetime
    updated_at: datetime
