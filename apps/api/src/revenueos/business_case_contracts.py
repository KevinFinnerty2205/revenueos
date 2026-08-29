from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Literal, Self
from uuid import UUID

from pydantic import Field, StringConstraints, field_validator, model_validator

from revenueos.contracts import APIModel

ModelState = Literal["active", "archived"]
ModelVersionState = Literal["draft", "approved", "archived"]
BusinessCaseState = Literal["draft", "calculated", "needs_review", "approved", "archived"]
BusinessCaseReviewState = Literal["pending", "approved", "needs_review"]
ScenarioName = Literal["base", "conservative", "upside"]
InputValueType = Literal["integer", "decimal", "currency", "percentage", "hours", "days", "minutes", "count"]
ValueUnit = Literal[
    "count",
    "currency",
    "currency_per_year",
    "currency_per_hour",
    "percentage",
    "hours",
    "hours_per_year",
    "minutes",
    "days",
    "months",
    "years",
    "dimensionless",
]
InputOrigin = Literal[
    "validated_customer_evidence",
    "salesperson_reported",
    "organisation_assumption",
    "approved_company_data",
    "prospect_public",
    "user_entered",
    "unknown",
]
SourcePolicy = Literal["reviewed_manual", "customer_or_manual", "approved_org_only", "public_or_manual"]

Key = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=64, pattern=r"^[a-z][a-z0-9_]*$")
]
Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
Title = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=240)]
Description = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=800)]
ShortText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)]
DecimalText = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=80, pattern=r"^-?(0|[1-9][0-9]*)(\.[0-9]+)?$"),
]
FormulaText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)]
CurrencyCode = Annotated[str, StringConstraints(strip_whitespace=True, to_upper=True, pattern=r"^[A-Z]{3}$")]
IdempotencyKey = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=200, pattern=r"^[A-Za-z0-9._:-]+$"),
]


class ScenarioPreset(APIModel):
    conservative: Decimal | None = Field(default=None, max_digits=28)
    base: Decimal | None = Field(default=None, max_digits=28)
    upside: Decimal | None = Field(default=None, max_digits=28)

    @model_validator(mode="after")
    def at_least_one_value(self) -> Self:
        if self.conservative is None and self.base is None and self.upside is None:
            raise ValueError("A scenario preset must contain at least one explicit value.")
        return self


class ValueModelInputDefinition(APIModel):
    key: Key
    label: Name
    description: Description
    value_type: InputValueType
    unit: ValueUnit
    required: bool = True
    minimum: Decimal | None = Field(default=None, max_digits=28)
    maximum: Decimal | None = Field(default=None, max_digits=28)
    decimal_precision: int = Field(default=2, ge=0, le=6)
    default_value: Decimal | None = Field(default=None, max_digits=28)
    default_origin: Literal["organisation_assumption", "approved_company_data"] | None = None
    default_source_reference: ShortText | None = None
    review_expires_on: date | None = None
    max_source_age_days: int | None = Field(default=None, ge=1, le=3650)
    assumption_locked: bool = False
    source_policy: SourcePolicy = "reviewed_manual"
    customer_facing: bool = True
    material: bool = False
    sensitivity_eligible: bool = False
    scenario_preset: ScenarioPreset | None = None
    display_order: int = Field(ge=1, le=30)

    @model_validator(mode="after")
    def coherent_definition(self) -> Self:
        if self.minimum is not None and self.maximum is not None and self.minimum > self.maximum:
            raise ValueError("minimum cannot be greater than maximum.")
        values = [self.default_value]
        if self.scenario_preset is not None:
            values.extend(
                [
                    self.scenario_preset.conservative,
                    self.scenario_preset.base,
                    self.scenario_preset.upside,
                ]
            )
        for value in values:
            if value is not None and self.minimum is not None and value < self.minimum:
                raise ValueError("Default and scenario values must satisfy the approved minimum.")
            if value is not None and self.maximum is not None and value > self.maximum:
                raise ValueError("Default and scenario values must satisfy the approved maximum.")
        if (self.default_value is None) != (self.default_origin is None):
            raise ValueError("Default values require a visible approved origin.")
        if self.assumption_locked and self.default_value is None:
            raise ValueError("A locked assumption requires an approved default value.")
        if self.source_policy == "approved_org_only" and self.default_value is None:
            raise ValueError("Approved-organisation-only inputs require an approved default value.")
        if self.scenario_preset is not None and not self.sensitivity_eligible:
            raise ValueError("Scenario presets require a sensitivity-eligible input.")
        expected_units: dict[str, set[str]] = {
            "integer": {"count", "dimensionless"},
            "count": {"count"},
            "decimal": {"dimensionless"},
            "currency": {"currency", "currency_per_year", "currency_per_hour"},
            "percentage": {"percentage"},
            "hours": {"hours", "hours_per_year"},
            "days": {"days"},
            "minutes": {"minutes"},
        }
        if self.unit not in expected_units[self.value_type]:
            raise ValueError(f"Unit `{self.unit}` is not valid for input type `{self.value_type}`.")
        if self.value_type in {"integer", "count"} and self.decimal_precision != 0:
            raise ValueError("Integer and count inputs must use zero decimal places.")
        return self


class ValueModelOutputDefinition(APIModel):
    key: Key
    label: Name
    description: Description
    formula: FormulaText
    unit: ValueUnit
    display_precision: int = Field(default=2, ge=0, le=6)
    customer_facing: bool = True
    highlight: bool = False
    scenario_sensitive: bool = True
    display_order: int = Field(ge=1, le=30)


class ValueModelDefinition(APIModel):
    inputs: list[ValueModelInputDefinition] = Field(min_length=1, max_length=30)
    outputs: list[ValueModelOutputDefinition] = Field(min_length=1, max_length=30)
    customer_disclaimer: ShortText | None = None

    @model_validator(mode="after")
    def unique_keys_and_order(self) -> Self:
        input_keys = [item.key for item in self.inputs]
        output_keys = [item.key for item in self.outputs]
        if len(input_keys) != len(set(input_keys)):
            raise ValueError("Input keys must be unique.")
        if len(output_keys) != len(set(output_keys)):
            raise ValueError("Output keys must be unique.")
        if set(input_keys) & set(output_keys):
            raise ValueError("Input and output keys must not overlap.")
        if len({item.display_order for item in self.inputs}) != len(self.inputs):
            raise ValueError("Input display order values must be unique.")
        if len({item.display_order for item in self.outputs}) != len(self.outputs):
            raise ValueError("Output display order values must be unique.")
        if not any(item.highlight for item in self.outputs):
            raise ValueError("At least one output must be highlighted for review.")
        return self


class ValueModelCreateRequest(APIModel):
    name: Name
    description: Description
    definition: ValueModelDefinition
    idempotency_key: IdempotencyKey


class ValueModelVersionCreateRequest(APIModel):
    name: Name | None = None
    description: Description | None = None
    definition: ValueModelDefinition
    idempotency_key: IdempotencyKey


class ValueModelApprovalRequest(APIModel):
    confirmed: Literal[True]


class ValueModelArchiveRequest(APIModel):
    confirmed: Literal[True]


class ValueModelVersionResponse(APIModel):
    id: UUID
    version: int = Field(ge=1)
    state: ModelVersionState
    definition: ValueModelDefinition
    formula_engine_version: Literal["bounded_decimal_v1"]
    fingerprint: str
    approved_by_user_id: UUID | None
    approved_at: datetime | None
    created_by_user_id: UUID
    created_at: datetime


class ValueModelResponse(APIModel):
    id: UUID
    name: str
    description: str
    state: ModelState
    latest_version: ValueModelVersionResponse
    can_manage: bool
    created_at: datetime
    updated_at: datetime


class ValueModelListResponse(APIModel):
    items: list[ValueModelResponse]
    can_manage: bool
    max_active_models: int = 50


class BusinessCaseCreateRequest(APIModel):
    account_id: UUID
    opportunity_id: UUID | None = None
    model_version_id: UUID
    currency: CurrencyCode
    title: Title | None = None
    idempotency_key: IdempotencyKey


class BusinessCaseInputValue(APIModel):
    key: Key
    value: DecimalText
    origin: InputOrigin
    source_id: UUID | None = None
    observed_at: datetime | None = None

    @field_validator("observed_at")
    @classmethod
    def observed_at_has_timezone(cls, value: datetime | None) -> datetime | None:
        if value is not None and value.utcoffset() is None:
            raise ValueError("observedAt must include a timezone.")
        return value


class ScenarioOverride(APIModel):
    key: Key
    value: DecimalText


class BusinessCaseScenarioRequest(APIModel):
    name: Literal["conservative", "upside"]
    overrides: list[ScenarioOverride] = Field(min_length=1, max_length=30)

    @field_validator("overrides")
    @classmethod
    def unique_overrides(cls, values: list[ScenarioOverride]) -> list[ScenarioOverride]:
        if len({item.key for item in values}) != len(values):
            raise ValueError("A scenario can override each input only once.")
        return values


class SensitivityRequest(APIModel):
    input_key: Key
    values: list[DecimalText] = Field(min_length=2, max_length=5)

    @field_validator("values")
    @classmethod
    def unique_values(cls, values: list[str]) -> list[str]:
        if len(set(values)) != len(values):
            raise ValueError("Sensitivity values must be unique.")
        return values


class BusinessCaseCalculateRequest(APIModel):
    inputs: list[BusinessCaseInputValue] = Field(min_length=1, max_length=30)
    scenarios: list[BusinessCaseScenarioRequest] = Field(default_factory=list, max_length=2)
    sensitivity: SensitivityRequest | None = None
    idempotency_key: IdempotencyKey

    @model_validator(mode="after")
    def unique_inputs_and_scenarios(self) -> Self:
        if len({item.key for item in self.inputs}) != len(self.inputs):
            raise ValueError("Each input may be supplied only once.")
        if len({item.name for item in self.scenarios}) != len(self.scenarios):
            raise ValueError("Each scenario may be supplied only once.")
        return self


class CalculationInputResponse(APIModel):
    key: str
    label: str
    value: str
    calculation_value: str
    unit: ValueUnit
    origin: InputOrigin
    source_id: UUID | None
    source_label: str
    assumption: bool
    material: bool
    customer_facing: bool
    observed_at: datetime
    freshness: Literal["current", "stale", "unknown", "deleted_source"]


class CalculationOutputResponse(APIModel):
    key: str
    label: str
    description: str
    unit: ValueUnit
    exact_value: str | None
    display_value: str | None
    unavailable_reason: Literal["division_by_zero", "non_positive_denominator", "dependency_unavailable"] | None
    formula: str
    input_dependencies: list[str]
    output_dependencies: list[str]
    customer_facing: bool
    highlight: bool


class ScenarioCalculationResponse(APIModel):
    name: ScenarioName
    overrides: list[ScenarioOverride]
    outputs: list[CalculationOutputResponse]


class SensitivityRowResponse(APIModel):
    input_value: str
    outputs: list[CalculationOutputResponse]


class SensitivityResponse(APIModel):
    input_key: str
    rows: list[SensitivityRowResponse]


class BusinessCaseVersionResponse(APIModel):
    id: UUID
    version: int = Field(ge=1)
    currency: str
    model_version_id: UUID
    model_version: int
    formula_engine_version: Literal["bounded_decimal_v1"]
    model_fingerprint: str
    calculation_fingerprint: str
    inputs: list[CalculationInputResponse]
    scenarios: list[ScenarioCalculationResponse]
    sensitivity: SensitivityResponse | None
    review_state: BusinessCaseReviewState
    approved_by_user_id: UUID | None
    approved_at: datetime | None
    created_by_user_id: UUID
    created_at: datetime


class BusinessCaseResponse(APIModel):
    id: UUID
    title: str
    account_id: UUID
    account_name: str
    opportunity_id: UUID | None
    opportunity_name: str | None
    model_id: UUID
    model_name: str
    model_version_id: UUID
    model_version: int
    model_definition: ValueModelDefinition
    currency: str
    state: BusinessCaseState
    current_version: BusinessCaseVersionResponse | None
    created_by_user_id: UUID
    created_at: datetime
    updated_at: datetime


class BusinessCaseListResponse(APIModel):
    items: list[BusinessCaseResponse]
    can_create: bool
    max_active_cases_per_account: int = 20


class BusinessCaseApprovalRequest(APIModel):
    confirmed: Literal[True]


class BusinessCaseArchiveRequest(APIModel):
    confirmed: Literal[True]
