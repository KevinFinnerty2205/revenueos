from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Annotated, Literal
from uuid import UUID

from pydantic import Field, HttpUrl, StringConstraints, TypeAdapter, field_validator, model_validator

from revenueos.contracts import APIModel

CRMEntityType = Literal["account", "contact", "opportunity"]
CRMMode = Literal["unconfigured", "native", "external"]
CRMFieldType = Literal["short_text", "number", "date", "boolean", "single_select", "url"]
CRMFieldAuthority = Literal["revenueos_authoritative", "crm_authoritative", "review_before_sync"]
CRMChangeSource = Literal[
    "manual_user_entry",
    "crm_import",
    "prospect_promotion",
    "event_promotion",
    "external_crm",
    "reviewed_action",
    "system",
]
FieldKey = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        to_lower=True,
        min_length=1,
        max_length=64,
        pattern=r"^[a-z][a-z0-9_]*$",
    ),
]
Label = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]
Option = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=80)]


class CRMAvailabilityResponse(APIModel):
    module_key: Literal["crm"] = "crm"
    state: Literal["available", "not_in_plan", "setup_required", "temporarily_unavailable"]
    enabled: bool
    can_manage: bool
    mode: CRMMode
    external_provider: Literal["hubspot"] | None = None
    external_connected: bool
    custom_fields_read_only: bool
    message: str


class CRMEntitlementUpdate(APIModel):
    enabled: bool


class CRMSettingsUpdate(APIModel):
    mode: Literal["native", "external"]
    confirmed: Literal[True]


class CRMMemberResponse(APIModel):
    user_id: UUID
    display_name: str
    active: bool


class CRMCustomFieldCreate(APIModel):
    entity_type: CRMEntityType
    field_key: FieldKey
    label: Label
    field_type: CRMFieldType
    options: list[Option] = Field(default_factory=list, max_length=50)
    display_order: int = Field(default=0, ge=0, le=24)

    @field_validator("options")
    @classmethod
    def options_must_be_unique(cls, value: list[str]) -> list[str]:
        if len({item.casefold() for item in value}) != len(value):
            raise ValueError("Custom field options must be unique.")
        return value

    @model_validator(mode="after")
    def options_match_type(self) -> CRMCustomFieldCreate:
        if self.field_type == "single_select" and not self.options:
            raise ValueError("A single-select field requires at least one option.")
        if self.field_type != "single_select" and self.options:
            raise ValueError("Only single-select fields accept options.")
        return self


class CRMCustomFieldUpdate(APIModel):
    label: Label | None = None
    options: list[Option] | None = Field(default=None, max_length=50)
    display_order: int | None = Field(default=None, ge=0, le=24)

    @field_validator("options")
    @classmethod
    def options_must_be_unique(cls, value: list[str] | None) -> list[str] | None:
        if value is not None and len({item.casefold() for item in value}) != len(value):
            raise ValueError("Custom field options must be unique.")
        return value

    @model_validator(mode="after")
    def at_least_one_field(self) -> CRMCustomFieldUpdate:
        if not self.model_fields_set:
            raise ValueError("At least one field must be supplied.")
        return self


class CRMCustomFieldDefinitionResponse(APIModel):
    id: UUID
    entity_type: CRMEntityType
    field_key: str
    label: str
    field_type: CRMFieldType
    options: list[str]
    active: bool
    display_order: int
    created_by_user_id: UUID
    archived_at: datetime | None
    created_at: datetime
    updated_at: datetime


class CRMCustomFieldValueUpdate(APIModel):
    value: object | None
    expected_record_updated_at: datetime | None = None

    @field_validator("expected_record_updated_at")
    @classmethod
    def expected_time_requires_timezone(cls, value: datetime | None) -> datetime | None:
        if value is not None and value.utcoffset() is None:
            return value.replace(tzinfo=UTC)
        return value


class CRMCustomFieldValueResponse(APIModel):
    definition: CRMCustomFieldDefinitionResponse
    value: str | Decimal | date | bool | None
    source: CRMChangeSource | None
    changed_by_user_id: UUID | None
    updated_at: datetime | None
    editable: bool


class CRMRecordChangeResponse(APIModel):
    id: UUID
    field_key: str
    old_value: object | None
    new_value: object | None
    source: CRMChangeSource
    changed_by_user_id: UUID
    changed_by_name: str
    changed_at: datetime


class CRMActivityItemResponse(APIModel):
    id: str
    activity_type: Literal["interaction", "outreach", "action", "event", "opportunity"]
    title: str
    detail: str | None
    occurred_at: datetime
    href: str | None
    source_label: str


class CRMCoreFieldResponse(APIModel):
    key: str
    label: str
    value: str | None
    authority: CRMFieldAuthority


class CRMRecordResponse(APIModel):
    entity_type: CRMEntityType
    entity_id: UUID
    title: str
    owner_user_id: UUID
    owner_name: str
    archived_at: datetime | None
    record_updated_at: datetime
    mode: CRMMode
    crm_enabled: bool
    can_manage: bool
    custom_fields_read_only: bool
    field_authority: dict[str, CRMFieldAuthority]
    core_fields: list[CRMCoreFieldResponse]
    custom_fields: list[CRMCustomFieldValueResponse]
    history: list[CRMRecordChangeResponse]
    activity: list[CRMActivityItemResponse]


class CRMArchiveResponse(APIModel):
    entity_type: CRMEntityType
    entity_id: UUID
    archived_at: datetime | None


def validate_custom_url(value: str) -> str:
    return str(TypeAdapter(HttpUrl).validate_python(value))
