from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Literal, Protocol

from revenueos.integration_executors import ExecutorConnectionContext

type CRMObjectType = Literal["account", "contact", "opportunity"]
type CRMScalar = str | int | Decimal | date | datetime | bool | None


@dataclass(frozen=True)
class CRMProviderRecord:
    """Allow-listed provider record; raw provider responses never cross this boundary."""

    object_type: CRMObjectType
    external_object_id: str
    fields: dict[str, CRMScalar]
    external_version: str
    modified_at: datetime
    owner_external_id: str | None = None
    related_account_external_id: str | None = None
    archived: bool = False


@dataclass(frozen=True)
class CRMProviderPage:
    records: tuple[CRMProviderRecord, ...]
    next_cursor: str | None
    high_watermark_at: datetime


@dataclass(frozen=True)
class CRMProviderOwner:
    external_owner_id: str
    display_name: str | None
    email: str | None
    active: bool


@dataclass(frozen=True)
class CRMProviderStage:
    pipeline_id: str
    pipeline_name: str
    stage_id: str
    stage_name: str
    active: bool


class CRMProviderError(Exception):
    def __init__(
        self,
        code: str,
        *,
        retryable: bool = False,
        uncertain: bool = False,
        retry_after_seconds: int | None = None,
    ) -> None:
        super().__init__(code)
        self.code = code
        self.retryable = retryable
        self.uncertain = uncertain
        self.retry_after_seconds = retry_after_seconds


class CRMProviderAdapter(Protocol):
    provider_key: Literal["hubspot", "salesforce"]

    async def validate_connection(self, context: ExecutorConnectionContext) -> None: ...

    async def list_records(
        self,
        context: ExecutorConnectionContext,
        object_type: CRMObjectType,
        *,
        cursor: str | None,
        modified_after: datetime | None,
        limit: int,
    ) -> CRMProviderPage: ...

    async def get_record(
        self,
        context: ExecutorConnectionContext,
        object_type: CRMObjectType,
        external_object_id: str,
    ) -> CRMProviderRecord: ...

    async def create_record(
        self,
        context: ExecutorConnectionContext,
        object_type: CRMObjectType,
        fields: dict[str, CRMScalar],
    ) -> CRMProviderRecord: ...

    async def update_record(
        self,
        context: ExecutorConnectionContext,
        record: CRMProviderRecord,
        fields: dict[str, CRMScalar],
    ) -> CRMProviderRecord: ...

    async def owners(self, context: ExecutorConnectionContext) -> tuple[CRMProviderOwner, ...]: ...

    async def stages(self, context: ExecutorConnectionContext) -> tuple[CRMProviderStage, ...]: ...


@dataclass(frozen=True)
class CRMFieldRule:
    canonical_field: str
    provider_field: str
    value_type: Literal["string", "number", "date", "datetime", "enumeration", "relation", "owner"]
    default_authority: Literal["crm_authoritative", "revenueos_authoritative", "review_before_sync"]


CRM_FIELD_RULES: dict[str, dict[CRMObjectType, tuple[CRMFieldRule, ...]]] = {
    "hubspot": {
        "account": (
            CRMFieldRule("name", "name", "string", "crm_authoritative"),
            CRMFieldRule("domain", "domain", "string", "review_before_sync"),
            CRMFieldRule("industry", "industry", "string", "crm_authoritative"),
            CRMFieldRule("owner", "hubspot_owner_id", "owner", "crm_authoritative"),
        ),
        "contact": (
            CRMFieldRule("first_name", "firstname", "string", "crm_authoritative"),
            CRMFieldRule("last_name", "lastname", "string", "crm_authoritative"),
            CRMFieldRule("email", "email", "string", "review_before_sync"),
            CRMFieldRule("phone", "phone", "string", "crm_authoritative"),
            CRMFieldRule("job_title", "jobtitle", "string", "crm_authoritative"),
            CRMFieldRule("account", "associatedcompanyid", "relation", "crm_authoritative"),
            CRMFieldRule("owner", "hubspot_owner_id", "owner", "crm_authoritative"),
        ),
        "opportunity": (
            CRMFieldRule("name", "dealname", "string", "crm_authoritative"),
            CRMFieldRule("account", "associatedcompanyid", "relation", "crm_authoritative"),
            CRMFieldRule("stage", "dealstage", "enumeration", "review_before_sync"),
            CRMFieldRule("estimated_value", "amount", "number", "crm_authoritative"),
            CRMFieldRule("currency", "hs_currency_code", "enumeration", "review_before_sync"),
            CRMFieldRule("expected_close_date", "closedate", "date", "crm_authoritative"),
            CRMFieldRule("owner", "hubspot_owner_id", "owner", "crm_authoritative"),
            CRMFieldRule("description", "description", "string", "review_before_sync"),
            CRMFieldRule("next_step", "hs_next_step", "string", "review_before_sync"),
        ),
    },
    "salesforce": {
        "account": (
            CRMFieldRule("name", "Name", "string", "crm_authoritative"),
            CRMFieldRule("domain", "Website", "string", "review_before_sync"),
            CRMFieldRule("industry", "Industry", "string", "crm_authoritative"),
            CRMFieldRule("owner", "OwnerId", "owner", "crm_authoritative"),
        ),
        "contact": (
            CRMFieldRule("first_name", "FirstName", "string", "crm_authoritative"),
            CRMFieldRule("last_name", "LastName", "string", "crm_authoritative"),
            CRMFieldRule("email", "Email", "string", "review_before_sync"),
            CRMFieldRule("phone", "Phone", "string", "crm_authoritative"),
            CRMFieldRule("job_title", "Title", "string", "crm_authoritative"),
            CRMFieldRule("account", "AccountId", "relation", "crm_authoritative"),
            CRMFieldRule("owner", "OwnerId", "owner", "crm_authoritative"),
        ),
        "opportunity": (
            CRMFieldRule("name", "Name", "string", "crm_authoritative"),
            CRMFieldRule("account", "AccountId", "relation", "crm_authoritative"),
            CRMFieldRule("stage", "StageName", "enumeration", "review_before_sync"),
            CRMFieldRule("estimated_value", "Amount", "number", "crm_authoritative"),
            CRMFieldRule("currency", "CurrencyIsoCode", "enumeration", "review_before_sync"),
            CRMFieldRule("expected_close_date", "CloseDate", "date", "crm_authoritative"),
            CRMFieldRule("owner", "OwnerId", "owner", "crm_authoritative"),
            CRMFieldRule("description", "Description", "string", "review_before_sync"),
            CRMFieldRule("next_step", "NextStep", "string", "review_before_sync"),
        ),
    },
}

# These remain inside Oryntela and are never accepted from or sent to a CRM.
ORYNTELA_ONLY_FIELDS = frozenset(
    {
        "intelligence",
        "evidence",
        "methodology",
        "suppression",
        "consent",
        "recording",
        "transcript",
        "ai_artifact",
        "forecast_judgment",
    }
)


def rules_for(provider_key: str, object_type: CRMObjectType) -> tuple[CRMFieldRule, ...]:
    try:
        return CRM_FIELD_RULES[provider_key][object_type]
    except KeyError as exc:
        raise ValueError("Unsupported CRM provider or object type.") from exc


def provider_fields(provider_key: str, object_type: CRMObjectType) -> tuple[str, ...]:
    return tuple(rule.provider_field for rule in rules_for(provider_key, object_type))


def canonicalise_fields(
    provider_key: str,
    object_type: CRMObjectType,
    provider_values: dict[str, object],
) -> dict[str, CRMScalar]:
    """Drop unknown/custom fields and retain only bounded scalar values."""
    result: dict[str, CRMScalar] = {}
    for rule in rules_for(provider_key, object_type):
        value = provider_values.get(rule.provider_field)
        if isinstance(value, str):
            result[rule.canonical_field] = value.strip()[:2048] or None
        elif value is None or isinstance(value, (bool, int, Decimal, date, datetime)):
            result[rule.canonical_field] = value
    return result
