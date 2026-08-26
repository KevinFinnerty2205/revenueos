from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Annotated, Literal
from uuid import UUID

from pydantic import ConfigDict, Field, StringConstraints, model_validator

from revenueos.contracts import APIModel, to_camel
from revenueos.domain import (
    ActionRiskClass,
    ConnectionStatus,
    ConnectorCapability,
    ConnectorKey,
    ExecutionStatus,
)

SafeMessage = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)]


class StrictIntegrationModel(APIModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        extra="forbid",
        frozen=True,
    )


class ConnectorDefinitionResponse(APIModel):
    connector_key: ConnectorKey
    display_name: str
    provider_family: Literal["mock", "crm"]
    supported_capabilities: list[ConnectorCapability]
    authentication_type: Literal["mock_local", "oauth2_authorisation_code"]
    execution_risk_classes: list[ActionRiskClass]
    configuration_schema_version: int
    execution_mode: Literal["simulation", "live"] = "simulation"
    available: bool
    simulation_only: bool = True


class IntegrationCatalogResponse(APIModel):
    connectors: list[ConnectorDefinitionResponse]
    execution_mode: Literal["simulation", "mixed"]
    external_actions_enabled: bool


class ConnectionCreateRequest(StrictIntegrationModel):
    connector_key: ConnectorKey


class OrganisationConnectionResponse(APIModel):
    id: UUID
    connector_key: ConnectorKey
    display_name: str
    connection_status: ConnectionStatus
    supported_capabilities: list[ConnectorCapability]
    capability_state: list[ConnectorCapability]
    created_by_user_id: UUID
    connected_at: datetime
    last_verified_at: datetime | None
    revoked_at: datetime | None
    external_account_id: str | None
    external_account_name: str | None
    granted_scopes: list[str]
    metadata_version: int
    execution_mode: Literal["simulation", "live"] = "simulation"
    simulation_only: bool = True
    created_at: datetime
    updated_at: datetime


class ConnectionListResponse(APIModel):
    items: list[OrganisationConnectionResponse]
    total: int


class ActionExecutionOptionResponse(APIModel):
    connection_id: UUID
    connector_key: ConnectorKey
    connector_display_name: str
    capability: ConnectorCapability
    risk_class: ActionRiskClass
    execution_mode: Literal["simulation", "live"] = "simulation"
    simulation_only: bool = True


class ActionExecutionOptionListResponse(APIModel):
    items: list[ActionExecutionOptionResponse]
    total: int


class ConnectionHealthResponse(APIModel):
    connection: OrganisationConnectionResponse
    healthy: bool
    checked_at: datetime
    safe_message: SafeMessage


class EmailExecutionPreview(StrictIntegrationModel):
    kind: Literal["email"]
    sender_name: str | None = Field(default=None, exclude_if=lambda value: value is None)
    sender_email: str | None = Field(default=None, exclude_if=lambda value: value is None)
    recipient_name: str | None = Field(default=None, exclude_if=lambda value: value is None)
    recipient: str
    subject: str
    body: str
    action: Literal["send_email"] = "send_email"


class CalendarParticipantPreview(StrictIntegrationModel):
    contact_id: UUID
    display_name: str
    email: str


class CalendarExecutionPreview(StrictIntegrationModel):
    kind: Literal["calendar"]
    event: str
    participant_contact_ids: tuple[UUID, ...]
    participants: tuple[CalendarParticipantPreview, ...]
    scheduled_at: datetime
    timezone: str
    purpose: str
    action: Literal["create_calendar_event"] = "create_calendar_event"


class CRMExecutionPreview(StrictIntegrationModel):
    kind: Literal["crm"]
    target_type: Literal["opportunity", "contact"]
    target_id: UUID
    field: str
    current_external_value: str | Decimal | None
    expected_external_value: str | Decimal | None
    new_value: str | Decimal | None
    field_authority: Literal["crm_authoritative", "revenueos_authoritative", "review_before_sync"] | None = None
    external_updated_at: datetime | None = None
    action: Literal["update_opportunity", "update_contact"]


class CRMActivityExecutionPreview(StrictIntegrationModel):
    kind: Literal["crm_activity"]
    interaction_id: UUID
    occurred_at: datetime
    title: str
    summary: str
    agreed_next_steps: tuple[str, ...]
    raw_transcript_included: Literal[False] = False
    action: Literal["create_activity"] = "create_activity"


class TaskExecutionPreview(StrictIntegrationModel):
    kind: Literal["task"]
    title: str
    owner_user_id: UUID | None
    due_at: datetime | None
    opportunity_id: UUID
    context: str
    action: Literal["create_task"] = "create_task"


ExecutionPreviewContent = Annotated[
    EmailExecutionPreview
    | CalendarExecutionPreview
    | CRMExecutionPreview
    | CRMActivityExecutionPreview
    | TaskExecutionPreview,
    Field(discriminator="kind"),
]


class ExecutionPreviewResponse(APIModel):
    id: UUID
    action_proposal_id: UUID
    action_version: int
    connection_id: UUID
    connector_key: ConnectorKey
    connector_display_name: str
    capability: ConnectorCapability
    risk_class: ActionRiskClass
    execution_mode: Literal["simulation", "live"] = "simulation"
    simulation_only: bool = True
    readiness: Literal["ready"] = "ready"
    summary: str
    confirmation_label: str
    preview_fingerprint: str
    content: ExecutionPreviewContent
    expires_at: datetime
    created_at: datetime


class ExecutionPreviewRequest(StrictIntegrationModel):
    connection_id: UUID


class ExecutionConfirmRequest(StrictIntegrationModel):
    preview_id: UUID
    connection_id: UUID
    confirmed: Literal[True]


class ExecutionAttemptResponse(APIModel):
    attempt_number: int
    status: str
    safe_failure_code: str | None
    external_result_id: str | None
    started_at: datetime
    completed_at: datetime | None
    duration_ms: int | None


class ActionExecutionResponse(APIModel):
    id: UUID
    action_proposal_id: UUID
    action_version: int
    connection_id: UUID
    connector_key: ConnectorKey
    connector_display_name: str
    capability: ConnectorCapability
    risk_class: ActionRiskClass
    execution_status: ExecutionStatus
    execution_mode: Literal["simulation", "live"] = "simulation"
    simulation_only: bool = True
    confirmed_by_user_id: UUID
    confirmed_at: datetime
    started_at: datetime | None
    completed_at: datetime | None
    failed_at: datetime | None
    safe_failure_code: str | None
    external_result_id: str | None
    attempt_count: int
    retryable: bool
    safe_message: str
    created_at: datetime
    updated_at: datetime


class ActionExecutionListResponse(APIModel):
    items: list[ActionExecutionResponse]
    total: int


class ActionExecutionDetailResponse(ActionExecutionResponse):
    attempts: list[ExecutionAttemptResponse]


class OAuthStartResponse(APIModel):
    authorisation_url: str
    expires_at: datetime


class OAuthCallbackRequest(StrictIntegrationModel):
    state: Annotated[str, StringConstraints(min_length=32, max_length=512)]
    code: Annotated[str, StringConstraints(min_length=1, max_length=2048)] | None = None
    provider_error: Annotated[str, StringConstraints(min_length=1, max_length=120)] | None = None

    @model_validator(mode="after")
    def validate_outcome(self) -> OAuthCallbackRequest:
        if (self.code is None) == (self.provider_error is None):
            raise ValueError("Supply exactly one OAuth callback outcome.")
        return self


CRMObjectType = Literal["company", "contact", "deal"]


class CRMSearchResult(APIModel):
    external_object_type: CRMObjectType
    external_object_id: str
    display_name: str
    secondary_label: str | None
    updated_at: datetime | None


class CRMSearchResponse(APIModel):
    items: list[CRMSearchResult]
    total: int


class CRMEntityLinkRequest(StrictIntegrationModel):
    connection_id: UUID
    external_object_type: CRMObjectType
    external_object_id: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=128)]


class CRMEntityMappingResponse(APIModel):
    id: UUID
    connection_id: UUID
    connector_key: ConnectorKey
    revenueos_entity_type: Literal["company", "contact", "opportunity"]
    revenueos_entity_id: UUID
    external_object_type: CRMObjectType
    external_object_id: str
    external_updated_at: datetime | None
    last_synced_at: datetime | None
    sync_state: Literal["active", "external_missing"]
    created_at: datetime
    updated_at: datetime


class CRMPropertyDefinition(APIModel):
    entity_type: Literal["opportunity", "contact"]
    external_property_name: str
    label: str
    property_type: Literal["string", "number", "date", "datetime", "enumeration"]
    options: list[dict[str, str]]
    read_only: bool


class CRMFieldMappingRequest(StrictIntegrationModel):
    entity_type: Literal["opportunity", "contact"]
    revenueos_field: Literal[
        "stage",
        "expected_close_date",
        "estimated_value",
        "next_step",
        "description",
        "first_name",
        "last_name",
        "email",
        "job_title",
    ]
    external_property_name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=128)]
    authority: Literal["review_before_sync", "crm_authoritative"] = "review_before_sync"


class CRMFieldMappingResponse(APIModel):
    id: UUID
    connection_id: UUID
    entity_type: Literal["opportunity", "contact"]
    revenueos_field: str
    external_property_name: str
    external_property_type: Literal["string", "number", "date", "datetime", "enumeration"]
    authority: Literal["crm_authoritative", "revenueos_authoritative", "review_before_sync"]
    enabled: bool


class CRMFieldConfigurationResponse(APIModel):
    properties: list[CRMPropertyDefinition]
    mappings: list[CRMFieldMappingResponse]


class CRMStageMappingRequest(StrictIntegrationModel):
    revenueos_stage: Literal[
        "qualification",
        "discovery",
        "evaluation",
        "proposal",
        "negotiation",
        "procurement",
        "closed_won",
        "closed_lost",
        "other",
    ]
    external_pipeline_id: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=128)]
    external_stage_id: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=128)]


class CRMStageDefinition(APIModel):
    pipeline_id: str
    pipeline_label: str
    stage_id: str
    stage_label: str


class CRMStageMappingResponse(APIModel):
    revenueos_stage: str
    external_pipeline_id: str
    external_stage_id: str


class CRMStageConfigurationResponse(APIModel):
    available_stages: list[CRMStageDefinition]
    mappings: list[CRMStageMappingResponse]
