from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Literal
from uuid import UUID

from pydantic import Field, StringConstraints, model_validator

from revenueos.contracts import APIModel

PipelineStageType = Literal["open", "won", "lost"]
PipelineView = Literal["open", "closed"]
StageName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]
Guidance = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=300)]
OutcomeNote = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)]
IdempotencyKey = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=8, max_length=100, pattern=r"^[A-Za-z0-9._:-]+$"),
]


class PipelineStageDraft(APIModel):
    name: StageName
    stage_type: PipelineStageType
    guidance: Guidance | None = None


class PipelineCreate(APIModel):
    name: StageName
    stages: list[PipelineStageDraft] = Field(min_length=3, max_length=12)
    is_default: bool = False

    @model_validator(mode="after")
    def validate_stages(self) -> PipelineCreate:
        if sum(stage.stage_type == "won" for stage in self.stages) != 1:
            raise ValueError("A pipeline needs exactly one Won stage.")
        if sum(stage.stage_type == "lost" for stage in self.stages) != 1:
            raise ValueError("A pipeline needs exactly one Lost stage.")
        if not any(stage.stage_type == "open" for stage in self.stages):
            raise ValueError("A pipeline needs at least one open stage.")
        first_final = next(
            (index for index, stage in enumerate(self.stages) if stage.stage_type != "open"),
            len(self.stages),
        )
        if any(stage.stage_type == "open" for stage in self.stages[first_final:]):
            raise ValueError("Won and Lost stages must be final stages.")
        names = [stage.name.casefold() for stage in self.stages]
        if len(names) != len(set(names)):
            raise ValueError("Stage names must be unique within a pipeline.")
        return self


class PipelineUpdate(APIModel):
    name: StageName | None = None
    is_default: bool | None = None

    @model_validator(mode="after")
    def validate_change(self) -> PipelineUpdate:
        if not self.model_fields_set:
            raise ValueError("Supply a pipeline change.")
        return self


class PipelineOpenStageCreate(APIModel):
    name: StageName
    guidance: Guidance | None = None
    position: int = Field(ge=0, le=9)


class PipelineStageUpdate(APIModel):
    name: StageName | None = None
    guidance: Guidance | None = None
    position: int | None = Field(default=None, ge=0, le=11)

    @model_validator(mode="after")
    def validate_change(self) -> PipelineStageUpdate:
        if not self.model_fields_set:
            raise ValueError("Supply a stage change.")
        return self


class PipelineStageResponse(APIModel):
    id: UUID
    pipeline_id: UUID
    key: str
    name: str
    position: int
    stage_type: PipelineStageType
    guidance: str | None
    active: bool
    archived_at: datetime | None
    current_opportunity_count: int = 0


class PipelineResponse(APIModel):
    id: UUID
    name: str
    is_default: bool
    active: bool
    archived_at: datetime | None
    stages: list[PipelineStageResponse]
    created_at: datetime
    updated_at: datetime


class PipelineValueSummary(APIModel):
    currency: str
    amount: Decimal
    opportunity_count: int


class PipelineSummaryResponse(APIModel):
    open_opportunity_count: int
    needs_attention_count: int
    close_dates_this_month_count: int
    unvalued_opportunity_count: int
    values: list[PipelineValueSummary]


class PipelineCardResponse(APIModel):
    opportunity_id: UUID
    opportunity_name: str
    company_id: UUID | None
    company_name: str | None
    pipeline_id: UUID
    pipeline_name: str
    stage_id: UUID
    stage_name: str
    stage_type: PipelineStageType
    status: Literal["open", "won", "lost", "on_hold"]
    estimated_value: Decimal | None
    currency: str | None
    expected_close_date: date | None
    actual_close_date: date | None
    owner_user_id: UUID
    owner_name: str
    stage_entered_at: datetime | None
    stage_tracking_started_at: datetime | None
    days_in_stage: int | None
    next_action: str | None
    attention_reasons: list[str] = Field(max_length=2)
    outcome_reason: str | None
    outcome_provenance: Literal["seller_reported"] | None


class PipelineBoardResponse(APIModel):
    pipeline: PipelineResponse
    pipelines: list[PipelineResponse]
    view: PipelineView
    summary: PipelineSummaryResponse
    cards: list[PipelineCardResponse]
    stage_changes_allowed: bool
    managed_externally: bool
    authority_message: str | None
    manager_intelligence_available: bool
    generated_at: datetime


class OpportunityStageTransitionRequest(APIModel):
    target_stage_id: UUID
    expected_current_stage_id: UUID
    idempotency_key: IdempotencyKey


LossReason = Literal[
    "price",
    "competitor",
    "no_decision",
    "budget",
    "timing",
    "requirements_fit",
    "procurement",
    "relationship",
    "other",
    "unknown",
]
WinReason = Literal[
    "solution_fit",
    "commercial",
    "relationship",
    "implementation",
    "existing_customer",
    "other",
    "unknown",
]


class OpportunityCloseWonRequest(APIModel):
    expected_current_stage_id: UUID
    actual_close_date: date
    final_amount: Decimal | None = Field(default=None, ge=0, max_digits=18, decimal_places=2)
    outcome_reason: WinReason | None = None
    outcome_note: OutcomeNote | None = None
    idempotency_key: IdempotencyKey


class OpportunityCloseLostRequest(APIModel):
    expected_current_stage_id: UUID
    actual_close_date: date
    final_amount: Decimal | None = Field(default=None, ge=0, max_digits=18, decimal_places=2)
    outcome_reason: LossReason
    outcome_note: OutcomeNote | None = None
    idempotency_key: IdempotencyKey


class OpportunityReopenRequest(APIModel):
    target_stage_id: UUID
    expected_current_stage_id: UUID
    idempotency_key: IdempotencyKey


class OpportunityStageEventResponse(APIModel):
    id: UUID
    from_pipeline_id: UUID | None
    to_pipeline_id: UUID
    from_stage_id: UUID | None
    to_stage_id: UUID
    from_stage_name: str | None
    to_stage_name: str
    from_stage_type: PipelineStageType | None
    to_stage_type: PipelineStageType
    changed_by_user_id: UUID | None
    changed_by_name: str | None
    changed_at: datetime
    source: Literal["system_initial", "migration_baseline", "manual", "external_crm"]
    is_baseline: bool
    previous_stage_entered_at: datetime | None
    outcome_reason: str | None
    outcome_note: str | None
    outcome_provenance: Literal["seller_reported"] | None
    actual_close_date: date | None
    final_amount: Decimal | None
    final_currency: str | None


class OpportunityPipelineResponse(APIModel):
    opportunity_id: UUID
    status: Literal["open", "won", "lost", "on_hold"]
    pipeline: PipelineResponse
    stage: PipelineStageResponse
    stage_entered_at: datetime | None
    stage_tracking_started_at: datetime | None
    days_in_stage: int | None
    actual_close_date: date | None
    outcome_reason: str | None
    outcome_note: str | None
    outcome_provenance: Literal["seller_reported"] | None
    available_pipelines: list[PipelineResponse]
    history: list[OpportunityStageEventResponse]
    stage_changes_allowed: bool
    managed_externally: bool
    authority_message: str | None
