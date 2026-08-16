from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Annotated, Literal
from uuid import UUID

from pydantic import ConfigDict, Field, StringConstraints

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
    provider_family: Literal["mock"]
    supported_capabilities: list[ConnectorCapability]
    authentication_type: Literal["mock_local"]
    execution_risk_classes: list[ActionRiskClass]
    configuration_schema_version: int
    execution_mode: Literal["simulation"] = "simulation"
    available: bool
    simulation_only: Literal[True] = True


class IntegrationCatalogResponse(APIModel):
    connectors: list[ConnectorDefinitionResponse]
    execution_mode: Literal["simulation"] = "simulation"
    external_actions_enabled: Literal[False] = False


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
    metadata_version: int
    execution_mode: Literal["simulation"] = "simulation"
    simulation_only: Literal[True] = True
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
    execution_mode: Literal["simulation"] = "simulation"
    simulation_only: Literal[True] = True


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
    action: Literal["update_opportunity", "update_contact"]


class TaskExecutionPreview(StrictIntegrationModel):
    kind: Literal["task"]
    title: str
    owner_user_id: UUID | None
    due_at: datetime | None
    opportunity_id: UUID
    context: str
    action: Literal["create_task"] = "create_task"


ExecutionPreviewContent = Annotated[
    EmailExecutionPreview | CalendarExecutionPreview | CRMExecutionPreview | TaskExecutionPreview,
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
    execution_mode: Literal["simulation"] = "simulation"
    simulation_only: Literal[True] = True
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
    execution_mode: Literal["simulation"] = "simulation"
    simulation_only: Literal[True] = True
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
