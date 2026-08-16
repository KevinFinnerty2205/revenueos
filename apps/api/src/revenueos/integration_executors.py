from __future__ import annotations

import hashlib
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Literal, cast
from uuid import UUID

from revenueos.action_contracts import (
    ActionPayload,
    ContactUpdatePayload,
    CreateTaskPayload,
    FollowUpEmailPayload,
    OpportunityUpdatePayload,
    ScheduleInteractionPayload,
)
from revenueos.domain import ActionRiskClass, ConnectorCapability, ConnectorKey
from revenueos.integration_contracts import (
    CalendarExecutionPreview,
    CalendarParticipantPreview,
    CRMExecutionPreview,
    EmailExecutionPreview,
    ExecutionPreviewContent,
    TaskExecutionPreview,
)


@dataclass(frozen=True)
class ConnectorDefinition:
    connector_key: ConnectorKey
    display_name: str
    capabilities: tuple[ConnectorCapability, ...]
    risk_classes: tuple[ActionRiskClass, ...]


CONNECTOR_DEFINITIONS: dict[ConnectorKey, ConnectorDefinition] = {
    ConnectorKey.MOCK_EMAIL: ConnectorDefinition(
        connector_key=ConnectorKey.MOCK_EMAIL,
        display_name="Mock Email",
        capabilities=(ConnectorCapability.SEND_EMAIL,),
        risk_classes=(ActionRiskClass.EXTERNAL_CUSTOMER_FACING,),
    ),
    ConnectorKey.MOCK_CALENDAR: ConnectorDefinition(
        connector_key=ConnectorKey.MOCK_CALENDAR,
        display_name="Mock Calendar",
        capabilities=(ConnectorCapability.CREATE_CALENDAR_EVENT,),
        risk_classes=(ActionRiskClass.EXTERNAL_CUSTOMER_FACING,),
    ),
    ConnectorKey.MOCK_CRM: ConnectorDefinition(
        connector_key=ConnectorKey.MOCK_CRM,
        display_name="Mock CRM",
        capabilities=(ConnectorCapability.UPDATE_OPPORTUNITY, ConnectorCapability.UPDATE_CONTACT),
        risk_classes=(ActionRiskClass.DATA_MUTATION,),
    ),
    ConnectorKey.MOCK_TASK: ConnectorDefinition(
        connector_key=ConnectorKey.MOCK_TASK,
        display_name="Mock Tasks",
        capabilities=(ConnectorCapability.CREATE_TASK,),
        risk_classes=(ActionRiskClass.INTERNAL_LOW_RISK,),
    ),
}


@dataclass(frozen=True)
class ApprovedContactRecipient:
    contact_id: UUID
    display_name: str
    email: str


@dataclass(frozen=True)
class ApprovedActionInput:
    organisation_id: UUID
    action_id: UUID
    action_version: int
    opportunity_id: UUID
    action_type: str
    risk_class: ActionRiskClass
    title: str
    target_entity_type: str | None
    target_entity_id: UUID | None
    payload: ActionPayload
    participant_contacts: tuple[ApprovedContactRecipient, ...] = ()


@dataclass(frozen=True)
class ExecutorResult:
    external_result_id: str
    object_type: str
    object_key: str
    state: dict[str, object]
    safe_message: str


class ExecutionFailure(Exception):
    def __init__(self, code: str, safe_message: str) -> None:
        super().__init__(safe_message)
        self.code = code
        self.safe_message = safe_message


class RetryableExecutionFailure(ExecutionFailure):
    pass


class PermanentExecutionFailure(ExecutionFailure):
    pass


class UnknownExternalStateFailure(ExecutionFailure):
    pass


class ActionExecutor(ABC):
    """Provider-neutral execution port. WO-022 implementations are simulation-only."""

    definition: ConnectorDefinition

    @abstractmethod
    async def validate_connection(self) -> None:
        raise NotImplementedError

    def get_capabilities(self) -> tuple[ConnectorCapability, ...]:
        return self.definition.capabilities

    @abstractmethod
    def validate_action(self, action: ApprovedActionInput) -> None:
        raise NotImplementedError

    @abstractmethod
    def preview_execution(
        self,
        action: ApprovedActionInput,
        current_external_state: object | None,
    ) -> ExecutionPreviewContent:
        raise NotImplementedError

    @abstractmethod
    async def execute(
        self,
        action: ApprovedActionInput,
        *,
        idempotency_key: str,
        current_external_state: object | None,
    ) -> ExecutorResult:
        raise NotImplementedError

    async def get_execution_status(self, external_result_id: str) -> str:
        del external_result_id
        return "simulated_success"

    async def cancel_if_supported(self, external_result_id: str | None) -> bool:
        del external_result_id
        return False

    @abstractmethod
    def object_key(self, action: ApprovedActionInput, idempotency_key: str) -> str:
        raise NotImplementedError


class _MockExecutor(ActionExecutor):
    async def validate_connection(self) -> None:
        return None

    @staticmethod
    def _external_id(prefix: str, idempotency_key: str) -> str:
        value = hashlib.sha256(f"{prefix}:{idempotency_key}".encode()).hexdigest()[:24]
        return f"{prefix}_{value}"


class MockEmailExecutor(_MockExecutor):
    definition = CONNECTOR_DEFINITIONS[ConnectorKey.MOCK_EMAIL]

    def validate_action(self, action: ApprovedActionInput) -> None:
        if not isinstance(action.payload, FollowUpEmailPayload):
            raise PermanentExecutionFailure("unsupported_action", "This connector cannot simulate that Action type.")
        payload = action.payload
        if not payload.recipient_confirmed or payload.recipient_email is None:
            raise PermanentExecutionFailure(
                "recipient_not_confirmed",
                "Confirm a validated Contact recipient in the Action before execution preview.",
            )
        if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", payload.recipient_email):
            raise PermanentExecutionFailure("invalid_recipient", "The approved recipient address is invalid.")
        if not payload.subject.strip() or not payload.body.strip():
            raise PermanentExecutionFailure(
                "invalid_email_content", "The approved email subject and body are required."
            )

    def preview_execution(
        self,
        action: ApprovedActionInput,
        current_external_state: object | None,
    ) -> ExecutionPreviewContent:
        del current_external_state
        self.validate_action(action)
        payload = cast(FollowUpEmailPayload, action.payload)
        assert payload.recipient_email is not None
        return EmailExecutionPreview(
            kind="email",
            recipient=payload.recipient_email,
            subject=payload.subject,
            body=payload.body,
        )

    async def execute(
        self,
        action: ApprovedActionInput,
        *,
        idempotency_key: str,
        current_external_state: object | None,
    ) -> ExecutorResult:
        del current_external_state
        self.validate_action(action)
        return ExecutorResult(
            external_result_id=self._external_id("mock_email", idempotency_key),
            object_type="email",
            object_key=self.object_key(action, idempotency_key),
            state={"simulation": True, "status": "simulated"},
            safe_message="Email simulation completed. No email was sent.",
        )

    def object_key(self, action: ApprovedActionInput, idempotency_key: str) -> str:
        del action
        return f"email:{idempotency_key}"


class MockCalendarExecutor(_MockExecutor):
    definition = CONNECTOR_DEFINITIONS[ConnectorKey.MOCK_CALENDAR]

    @staticmethod
    def _scheduled_at(payload: ScheduleInteractionPayload) -> datetime:
        if payload.timeframe is None:
            raise PermanentExecutionFailure(
                "calendar_time_not_exact",
                "Add an exact date, time and timezone to the Action before execution preview.",
            )
        try:
            scheduled_at = datetime.fromisoformat(payload.timeframe.replace("Z", "+00:00"))
        except ValueError as exc:
            raise PermanentExecutionFailure(
                "calendar_time_not_exact",
                "Add an ISO date, time and timezone to the Action before execution preview.",
            ) from exc
        if scheduled_at.tzinfo is None:
            raise PermanentExecutionFailure(
                "calendar_timezone_missing",
                "Add an explicit timezone to the calendar Action before execution preview.",
            )
        return scheduled_at

    def validate_action(self, action: ApprovedActionInput) -> None:
        if not isinstance(action.payload, ScheduleInteractionPayload):
            raise PermanentExecutionFailure("unsupported_action", "This connector cannot simulate that Action type.")
        self._scheduled_at(action.payload)
        if not action.payload.participant_contact_ids:
            raise PermanentExecutionFailure(
                "calendar_attendees_missing",
                "Select at least one validated Contact participant before execution preview.",
            )
        if tuple(item.contact_id for item in action.participant_contacts) != action.payload.participant_contact_ids:
            raise PermanentExecutionFailure(
                "calendar_attendees_stale",
                "A selected calendar participant is unavailable.",
            )

    def preview_execution(
        self,
        action: ApprovedActionInput,
        current_external_state: object | None,
    ) -> ExecutionPreviewContent:
        del current_external_state
        self.validate_action(action)
        payload = cast(ScheduleInteractionPayload, action.payload)
        scheduled_at = self._scheduled_at(payload)
        return CalendarExecutionPreview(
            kind="calendar",
            event=action.title,
            participant_contact_ids=payload.participant_contact_ids,
            participants=tuple(
                CalendarParticipantPreview(
                    contact_id=item.contact_id,
                    display_name=item.display_name,
                    email=item.email,
                )
                for item in action.participant_contacts
            ),
            scheduled_at=scheduled_at,
            timezone=str(scheduled_at.tzinfo),
            purpose=payload.purpose,
        )

    async def execute(
        self,
        action: ApprovedActionInput,
        *,
        idempotency_key: str,
        current_external_state: object | None,
    ) -> ExecutorResult:
        del current_external_state
        self.validate_action(action)
        return ExecutorResult(
            external_result_id=self._external_id("mock_event", idempotency_key),
            object_type="calendar_event",
            object_key=self.object_key(action, idempotency_key),
            state={"simulation": True, "status": "simulated"},
            safe_message="Calendar simulation completed. No event or invitation was created.",
        )

    def object_key(self, action: ApprovedActionInput, idempotency_key: str) -> str:
        del action
        return f"calendar:{idempotency_key}"


class MockCRMExecutor(_MockExecutor):
    definition = CONNECTOR_DEFINITIONS[ConnectorKey.MOCK_CRM]

    @staticmethod
    def _change(action: ApprovedActionInput) -> tuple[str, object | None, object | None]:
        if isinstance(action.payload, OpportunityUpdatePayload):
            return action.payload.field, action.payload.current_value, action.payload.proposed_value
        if isinstance(action.payload, ContactUpdatePayload) and action.payload.operation == "update":
            candidates: dict[str, object | None] = {
                "first_name": action.payload.first_name,
                "last_name": action.payload.last_name,
                "email": action.payload.email,
                "job_title": action.payload.job_title,
            }
            changed = [
                (field, action.payload.current_values.get(field), value)
                for field, value in candidates.items()
                if action.payload.current_values.get(field) != value
            ]
            if len(changed) == 1:
                return changed[0]
        raise PermanentExecutionFailure(
            "crm_change_not_atomic",
            "The approved CRM Action must change exactly one supported field.",
        )

    def validate_action(self, action: ApprovedActionInput) -> None:
        if not isinstance(action.payload, (OpportunityUpdatePayload, ContactUpdatePayload)):
            raise PermanentExecutionFailure("unsupported_action", "This connector cannot simulate that Action type.")
        if action.target_entity_id is None:
            raise PermanentExecutionFailure("external_target_missing", "The approved CRM target is unavailable.")
        self._change(action)

    def preview_execution(
        self,
        action: ApprovedActionInput,
        current_external_state: object | None,
    ) -> ExecutionPreviewContent:
        self.validate_action(action)
        field, expected, new_value = self._change(action)
        current = expected if current_external_state is None else current_external_state
        capability: Literal["update_opportunity", "update_contact"] = (
            "update_opportunity" if isinstance(action.payload, OpportunityUpdatePayload) else "update_contact"
        )
        assert action.target_entity_id is not None
        return CRMExecutionPreview(
            kind="crm",
            target_type="opportunity" if capability == "update_opportunity" else "contact",
            target_id=action.target_entity_id,
            field=field,
            current_external_value=cast(str | Decimal | None, current),
            expected_external_value=cast(str | Decimal | None, expected),
            new_value=cast(str | Decimal | None, new_value),
            action=capability,
        )

    async def execute(
        self,
        action: ApprovedActionInput,
        *,
        idempotency_key: str,
        current_external_state: object | None,
    ) -> ExecutorResult:
        self.validate_action(action)
        field, expected, new_value = self._change(action)
        current = expected if current_external_state is None else current_external_state
        if current != expected:
            raise PermanentExecutionFailure(
                "stale_external_state",
                "The simulated external value changed after review. Refresh the preview before retrying.",
            )
        return ExecutorResult(
            external_result_id=self._external_id("mock_crm", idempotency_key),
            object_type="crm_record_field",
            object_key=self.object_key(action, idempotency_key),
            state={"field": field, "current_value": new_value, "simulation": True},
            safe_message="CRM simulation completed. The RevenueOS record and no real CRM were changed.",
        )

    def object_key(self, action: ApprovedActionInput, idempotency_key: str) -> str:
        del idempotency_key
        field, _, _ = self._change(action)
        assert action.target_entity_id is not None
        return f"{action.target_entity_type}:{action.target_entity_id}:{field}"


class MockTaskExecutor(_MockExecutor):
    definition = CONNECTOR_DEFINITIONS[ConnectorKey.MOCK_TASK]

    def validate_action(self, action: ApprovedActionInput) -> None:
        if not isinstance(action.payload, CreateTaskPayload):
            raise PermanentExecutionFailure("unsupported_action", "This connector cannot simulate that Action type.")
        if action.payload.linked_opportunity_id != action.opportunity_id:
            raise PermanentExecutionFailure("invalid_task_target", "The approved task target is invalid.")

    def preview_execution(
        self,
        action: ApprovedActionInput,
        current_external_state: object | None,
    ) -> ExecutionPreviewContent:
        del current_external_state
        self.validate_action(action)
        payload = cast(CreateTaskPayload, action.payload)
        return TaskExecutionPreview(
            kind="task",
            title=payload.title,
            owner_user_id=payload.owner_user_id,
            due_at=payload.due_at,
            opportunity_id=payload.linked_opportunity_id,
            context=payload.context,
        )

    async def execute(
        self,
        action: ApprovedActionInput,
        *,
        idempotency_key: str,
        current_external_state: object | None,
    ) -> ExecutorResult:
        del current_external_state
        self.validate_action(action)
        return ExecutorResult(
            external_result_id=self._external_id("mock_task", idempotency_key),
            object_type="task",
            object_key=self.object_key(action, idempotency_key),
            state={"simulation": True, "status": "simulated"},
            safe_message="Task simulation completed. No external task was created.",
        )

    def object_key(self, action: ApprovedActionInput, idempotency_key: str) -> str:
        del action
        return f"task:{idempotency_key}"


class ActionExecutorRegistry:
    def __init__(self, executors: tuple[ActionExecutor, ...] | None = None) -> None:
        selected = executors or (
            MockEmailExecutor(),
            MockCalendarExecutor(),
            MockCRMExecutor(),
            MockTaskExecutor(),
        )
        self._executors = {item.definition.connector_key: item for item in selected}

    def get(self, connector_key: ConnectorKey) -> ActionExecutor:
        try:
            return self._executors[connector_key]
        except KeyError as exc:
            raise PermanentExecutionFailure(
                "connector_unavailable",
                "The selected connector is unavailable.",
            ) from exc


def capability_for_action(action_type: str) -> ConnectorCapability:
    try:
        return {
            "follow_up_email": ConnectorCapability.SEND_EMAIL,
            "schedule_interaction": ConnectorCapability.CREATE_CALENDAR_EVENT,
            "update_opportunity": ConnectorCapability.UPDATE_OPPORTUNITY,
            "update_contact": ConnectorCapability.UPDATE_CONTACT,
            "create_task": ConnectorCapability.CREATE_TASK,
        }[action_type]
    except KeyError as exc:
        raise PermanentExecutionFailure(
            "action_not_executable",
            "This approved Action type does not have a WO-022 simulation capability.",
        ) from exc
