from __future__ import annotations

import hashlib
import json
import logging
import uuid
from datetime import UTC, datetime, time, timedelta
from typing import cast
from uuid import UUID

from pydantic import TypeAdapter, ValidationError
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from revenueos.action_contracts import (
    ActionPayload,
    ActionSourceReference,
    ContactUpdatePayload,
    CreateTaskPayload,
    FollowUpEmailPayload,
    OpportunityUpdatePayload,
    ScheduleInteractionPayload,
)
from revenueos.action_repositories import ActionRecord, ActionRepository
from revenueos.config import Settings
from revenueos.credential_store import CredentialStore, MockCredentialStore
from revenueos.database import set_tenant_database_context
from revenueos.domain import (
    ActionRiskClass,
    ActionStatus,
    ConnectionStatus,
    ConnectorCapability,
    ConnectorKey,
    ExecutionStatus,
)
from revenueos.errors import PublicAPIError
from revenueos.integration_contracts import (
    ActionExecutionDetailResponse,
    ActionExecutionListResponse,
    ActionExecutionOptionListResponse,
    ActionExecutionOptionResponse,
    ActionExecutionResponse,
    ConnectionCreateRequest,
    ConnectionHealthResponse,
    ConnectionListResponse,
    ConnectorDefinitionResponse,
    ExecutionAttemptResponse,
    ExecutionConfirmRequest,
    ExecutionPreviewContent,
    ExecutionPreviewResponse,
    IntegrationCatalogResponse,
    OrganisationConnectionResponse,
)
from revenueos.integration_executors import (
    CONNECTOR_DEFINITIONS,
    ActionExecutor,
    ActionExecutorRegistry,
    ApprovedActionInput,
    ApprovedContactRecipient,
    ExecutionFailure,
    PermanentExecutionFailure,
    capability_for_action,
)
from revenueos.integration_repositories import ExecutionRecord, IntegrationRepository
from revenueos.models import (
    ActionExecution,
    Contact,
    ExecutionPreview,
    IntegrationAuditEvent,
    IntegrationConnection,
    Opportunity,
    OrganisationMembership,
)
from revenueos.tenant import TenantContext

logger = logging.getLogger("revenueos.integrations")
_PAYLOAD_ADAPTER: TypeAdapter[ActionPayload] = TypeAdapter(ActionPayload)
_SOURCE_ADAPTER: TypeAdapter[list[ActionSourceReference]] = TypeAdapter(list[ActionSourceReference])


class IntegrationService:
    """Tenant connection management for the simulation-only connector registry."""

    def __init__(
        self,
        session: AsyncSession,
        tenant: TenantContext,
        settings: Settings,
        *,
        executors: ActionExecutorRegistry | None = None,
        credential_store: CredentialStore | None = None,
    ) -> None:
        self.session = session
        self.tenant = tenant
        self.settings = settings
        self.repository = IntegrationRepository(session)
        self.executors = executors or ActionExecutorRegistry()
        self.credential_store = credential_store or MockCredentialStore()

    def catalog(self) -> IntegrationCatalogResponse:
        self._require_integrations()
        available = self._mock_connectors_available()
        return IntegrationCatalogResponse(
            connectors=[
                ConnectorDefinitionResponse(
                    connector_key=definition.connector_key,
                    display_name=definition.display_name,
                    provider_family="mock",
                    supported_capabilities=list(definition.capabilities),
                    authentication_type="mock_local",
                    execution_risk_classes=list(definition.risk_classes),
                    configuration_schema_version=1,
                    available=available,
                )
                for definition in CONNECTOR_DEFINITIONS.values()
            ]
            if available
            else []
        )

    async def list_connections(self) -> ConnectionListResponse:
        self._require_integrations()
        if not self._mock_connectors_available():
            return ConnectionListResponse(items=[], total=0)
        records = await self.repository.list_connections(self.tenant.organisation_id)
        return ConnectionListResponse(items=[self._connection_response(item) for item in records], total=len(records))

    async def get_connection(self, connection_id: UUID) -> OrganisationConnectionResponse:
        self._require_mock_connectors()
        return self._connection_response(await self._require_connection(connection_id))

    async def create_connection(self, request: ConnectionCreateRequest) -> OrganisationConnectionResponse:
        self._require_admin()
        self._require_mock_connectors()
        definition = CONNECTOR_DEFINITIONS[request.connector_key]
        await self.executors.get(request.connector_key).validate_connection()
        now = datetime.now(UTC)
        connection = await self.repository.connection_by_key(
            self.tenant.organisation_id,
            request.connector_key.value,
            for_update=True,
        )
        event_type = "connection_created"
        if connection is None:
            connection = IntegrationConnection(
                id=uuid.uuid4(),
                organisation_id=self.tenant.organisation_id,
                connector_key=request.connector_key.value,
                connection_status=ConnectionStatus.ACTIVE.value,
                created_by_user_id=self.tenant.user_id,
                connected_at=now,
                last_verified_at=now,
                revoked_at=None,
                credential_reference=None,
                capability_state_json=[item.value for item in definition.capabilities],
                metadata_version=1,
                created_at=now,
                updated_at=now,
            )
            self.repository.add(connection)
        elif connection.connection_status == ConnectionStatus.REVOKED.value:
            connection.connection_status = ConnectionStatus.ACTIVE.value
            connection.created_by_user_id = self.tenant.user_id
            connection.connected_at = now
            connection.last_verified_at = now
            connection.revoked_at = None
            connection.credential_reference = None
            connection.capability_state_json = [item.value for item in definition.capabilities]
            connection.metadata_version += 1
        else:
            return self._connection_response(connection)
        self._add_audit(connection, event_type, now)
        await self._commit("The simulation connection could not be created.")
        logger.info("connection_created", extra=self._connection_log_context(connection))
        return self._connection_response(await self._require_connection(connection.id))

    async def test_connection(self, connection_id: UUID) -> ConnectionHealthResponse:
        self._require_admin()
        self._require_mock_connectors()
        connection = await self._require_connection(connection_id, for_update=True)
        self._require_active_connection(connection)
        checked_at = datetime.now(UTC)
        await self.executors.get(ConnectorKey(connection.connector_key)).validate_connection()
        connection.last_verified_at = checked_at
        connection.metadata_version += 1
        self._add_audit(connection, "connection_tested", checked_at)
        await self._commit("The simulation connection could not be tested.")
        logger.info("connection_tested", extra=self._connection_log_context(connection))
        refreshed = await self._require_connection(connection_id)
        return ConnectionHealthResponse(
            connection=self._connection_response(refreshed),
            healthy=True,
            checked_at=checked_at,
            safe_message="Simulation connection verified. No external request was made.",
        )

    async def revoke_connection(self, connection_id: UUID) -> OrganisationConnectionResponse:
        self._require_admin()
        self._require_integrations()
        connection = await self._require_connection(connection_id, for_update=True)
        if connection.connection_status == ConnectionStatus.REVOKED.value:
            return self._connection_response(connection)
        now = datetime.now(UTC)
        if connection.credential_reference is not None:
            await self.credential_store.revoke(connection.credential_reference)
        connection.credential_reference = None
        connection.connection_status = ConnectionStatus.REVOKED.value
        connection.capability_state_json = []
        connection.revoked_at = now
        connection.metadata_version += 1
        await self.repository.invalidate_connection_previews(
            self.tenant.organisation_id,
            connection.id,
            now,
        )
        await self.repository.cancel_queued_executions(
            self.tenant.organisation_id,
            connection.id,
            now,
        )
        self._add_audit(connection, "connection_revoked", now)
        await self._commit("The simulation connection could not be revoked.")
        logger.info("connection_revoked", extra=self._connection_log_context(connection))
        return self._connection_response(await self._require_connection(connection_id))

    def _require_integrations(self) -> None:
        if not self.settings.feature_integrations_enabled:
            raise PublicAPIError("feature_unavailable", "This feature is not enabled for the private beta.", 404)

    def _require_mock_connectors(self) -> None:
        self._require_integrations()
        if not self._mock_connectors_available():
            raise PublicAPIError(
                "mock_connectors_unavailable",
                "Simulation connectors are unavailable in this environment.",
                404,
            )

    def _mock_connectors_available(self) -> bool:
        return self.settings.feature_mock_connectors_enabled and self.settings.environment != "production"

    def _require_admin(self) -> None:
        if not self.tenant.can_manage():
            raise PublicAPIError("forbidden", "You do not have permission to perform this action.", 403)

    async def _require_connection(
        self,
        connection_id: UUID,
        *,
        for_update: bool = False,
    ) -> IntegrationConnection:
        connection = await self.repository.connection(
            self.tenant.organisation_id,
            connection_id,
            for_update=for_update,
        )
        if connection is None:
            raise PublicAPIError("connection_not_found", "The requested connection was not found.", 404)
        return connection

    @staticmethod
    def _require_active_connection(connection: IntegrationConnection) -> None:
        if connection.connection_status != ConnectionStatus.ACTIVE.value:
            raise PublicAPIError("connection_revoked", "This connection has been revoked.", 409)

    def _connection_response(self, connection: IntegrationConnection) -> OrganisationConnectionResponse:
        definition = CONNECTOR_DEFINITIONS[ConnectorKey(connection.connector_key)]
        allowed = set(definition.capabilities)
        try:
            capability_state = [
                capability
                for value in connection.capability_state_json
                if (capability := ConnectorCapability(value)) in allowed
            ]
        except ValueError as exc:
            raise PublicAPIError(
                "connection_capabilities_invalid",
                "The connection capabilities are invalid.",
                409,
            ) from exc
        return OrganisationConnectionResponse(
            id=connection.id,
            connector_key=definition.connector_key,
            display_name=definition.display_name,
            connection_status=ConnectionStatus(connection.connection_status),
            supported_capabilities=list(definition.capabilities),
            capability_state=capability_state,
            created_by_user_id=connection.created_by_user_id,
            connected_at=connection.connected_at,
            last_verified_at=connection.last_verified_at,
            revoked_at=connection.revoked_at,
            metadata_version=connection.metadata_version,
            created_at=connection.created_at,
            updated_at=connection.updated_at,
        )

    def _add_audit(self, connection: IntegrationConnection, event_type: str, created_at: datetime) -> None:
        self.repository.add(
            IntegrationAuditEvent(
                id=uuid.uuid4(),
                organisation_id=self.tenant.organisation_id,
                actor_user_id=self.tenant.user_id,
                event_type=event_type,
                subject_type="connection",
                subject_id=connection.id,
                connector_key=connection.connector_key,
                capability=None,
                risk_class=None,
                attempt_count=None,
                safe_failure_code=None,
                external_result_id=None,
                duration_ms=None,
                created_at=created_at,
            )
        )

    async def _commit(self, message: str) -> None:
        try:
            await self.repository.flush()
            await self.repository.commit()
            await set_tenant_database_context(self.session, self.tenant.organisation_id)
        except IntegrityError as exc:
            await self.repository.rollback()
            raise PublicAPIError("integration_conflict", message, 409) from exc

    @staticmethod
    def _connection_log_context(connection: IntegrationConnection) -> dict[str, object]:
        return {
            "organisation_id": str(connection.organisation_id),
            "connection_id": str(connection.id),
            "connector_key": connection.connector_key,
            "connection_status": connection.connection_status,
        }


class ActionExecutionService:
    """Server-authoritative preview and explicit-confirmation orchestration."""

    def __init__(
        self,
        session: AsyncSession,
        tenant: TenantContext,
        settings: Settings,
        *,
        executors: ActionExecutorRegistry | None = None,
    ) -> None:
        self.session = session
        self.tenant = tenant
        self.settings = settings
        self.repository = IntegrationRepository(session)
        self.action_repository = ActionRepository(session)
        self.executors = executors or ActionExecutorRegistry()

    async def preview(self, action_id: UUID, connection_id: UUID) -> ExecutionPreviewResponse:
        self._require_execution_features()
        action_record = await self._require_approved_action(action_id)
        connection = await self._require_active_connection(connection_id, for_update=True)
        action = await self._action_input(action_record)
        capability = self._capability(action.action_type)
        executor = self._executor(connection, capability, action.risk_class)
        current_external_state = await self._current_external_state(executor, action, connection.id)
        try:
            content = executor.preview_execution(action, current_external_state)
        except ExecutionFailure as exc:
            raise PublicAPIError(exc.code, exc.safe_message, 409) from exc
        now = datetime.now(UTC)
        fingerprint = self._preview_fingerprint(
            action_record,
            connection,
            capability,
            content.model_dump(mode="json", by_alias=True),
        )
        preview = ExecutionPreview(
            id=uuid.uuid4(),
            organisation_id=self.tenant.organisation_id,
            action_id=action.action_id,
            action_version=action.action_version,
            connection_id=connection.id,
            capability=capability.value,
            risk_class=action.risk_class.value,
            preview_fingerprint=fingerprint,
            expires_at=now + timedelta(seconds=self.settings.execution_preview_ttl_seconds),
            confirmed_by_user_id=None,
            confirmed_at=None,
            invalidated_at=None,
            created_at=now,
        )
        self.repository.add(preview)
        self._add_execution_audit(
            event_type="execution_preview_created",
            subject_type="preview",
            subject_id=preview.id,
            connection=connection,
            capability=capability,
            risk_class=action.risk_class,
            created_at=now,
        )
        await self._commit("The execution preview could not be created.")
        logger.info("execution_preview_created", extra=self._execution_log_context(action, connection, capability))
        return self._preview_response(preview, connection, content)

    async def options(self, action_id: UUID) -> ActionExecutionOptionListResponse:
        self._require_execution_features()
        action_record = await self._require_approved_action(action_id)
        action = await self._action_input(action_record)
        capability = self._capability(action.action_type)
        options: list[ActionExecutionOptionResponse] = []
        for connection in await self.repository.list_connections(self.tenant.organisation_id):
            if connection.connection_status != ConnectionStatus.ACTIVE.value:
                continue
            try:
                self._executor(connection, capability, action.risk_class)
            except PublicAPIError:
                continue
            definition = CONNECTOR_DEFINITIONS[ConnectorKey(connection.connector_key)]
            options.append(
                ActionExecutionOptionResponse(
                    connection_id=connection.id,
                    connector_key=definition.connector_key,
                    connector_display_name=definition.display_name,
                    capability=capability,
                    risk_class=action.risk_class,
                )
            )
        return ActionExecutionOptionListResponse(items=options, total=len(options))

    async def confirm(
        self,
        action_id: UUID,
        request: ExecutionConfirmRequest,
    ) -> ActionExecutionResponse:
        self._require_execution_features()
        preview = await self.repository.preview(
            self.tenant.organisation_id,
            request.preview_id,
            for_update=True,
        )
        if preview is None or preview.action_id != action_id or preview.connection_id != request.connection_id:
            raise PublicAPIError("execution_preview_not_found", "The execution preview was not found.", 404)
        existing = await self.repository.execution_by_preview(self.tenant.organisation_id, preview.id)
        if preview.confirmed_at is not None and existing is not None:
            return self._execution_response(existing)
        now = datetime.now(UTC)
        if preview.invalidated_at is not None or self._as_utc(preview.expires_at) <= now:
            raise PublicAPIError(
                "execution_preview_expired",
                "This execution preview is no longer current. Review execution again.",
                409,
            )
        action_record = await self._require_approved_action(action_id, for_update=True)
        if action_record.proposal.approved_version != preview.action_version:
            preview.invalidated_at = now
            await self._commit("The stale preview could not be invalidated.")
            raise PublicAPIError(
                "action_version_stale", "The approved Action version changed. Review execution again.", 409
            )
        connection = await self._require_active_connection(request.connection_id, for_update=True)
        action = await self._action_input(action_record)
        capability = self._capability(action.action_type)
        if capability.value != preview.capability:
            raise PublicAPIError("execution_preview_tampered", "The execution preview does not match this Action.", 409)
        executor = self._executor(connection, capability, action.risk_class)
        current_external_state = await self._current_external_state(executor, action, connection.id)
        try:
            content = executor.preview_execution(action, current_external_state)
        except ExecutionFailure as exc:
            preview.invalidated_at = now
            await self._commit("The stale preview could not be invalidated.")
            raise PublicAPIError(exc.code, exc.safe_message, 409) from exc
        current_fingerprint = self._preview_fingerprint(
            action_record,
            connection,
            capability,
            content.model_dump(mode="json", by_alias=True),
        )
        if current_fingerprint != preview.preview_fingerprint:
            preview.invalidated_at = now
            await self._commit("The stale preview could not be invalidated.")
            raise PublicAPIError(
                "execution_preview_stale",
                "The Action, connection or simulated external state changed. Review execution again.",
                409,
            )
        await self._enforce_rate_limits(capability, now)
        idempotency_key = self._idempotency_key(action, connection.id, capability)
        prior = await self.repository.execution_by_idempotency(self.tenant.organisation_id, idempotency_key)
        if prior is not None:
            preview.confirmed_by_user_id = self.tenant.user_id
            preview.confirmed_at = now
            await self._commit("The duplicate confirmation could not be recorded.")
            return self._execution_response(prior)
        execution = ActionExecution(
            id=uuid.uuid4(),
            organisation_id=self.tenant.organisation_id,
            action_id=action.action_id,
            action_version=action.action_version,
            connection_id=connection.id,
            preview_id=preview.id,
            connector_key=connection.connector_key,
            capability=capability.value,
            risk_class=action.risk_class.value,
            execution_status=ExecutionStatus.QUEUED.value,
            execution_mode="simulation",
            idempotency_key=idempotency_key,
            preview_fingerprint=preview.preview_fingerprint,
            confirmed_by_user_id=self.tenant.user_id,
            confirmed_at=now,
            next_attempt_at=now,
            started_at=None,
            completed_at=None,
            failed_at=None,
            safe_failure_code=None,
            external_result_id=None,
            attempt_count=0,
            max_attempts=self.settings.worker_default_max_attempts,
            worker_id=None,
            lease_expires_at=None,
            created_at=now,
            updated_at=now,
        )
        preview.confirmed_by_user_id = self.tenant.user_id
        preview.confirmed_at = now
        self.repository.add(execution)
        self._add_execution_audit(
            event_type="execution_confirmed",
            subject_type="execution",
            subject_id=execution.id,
            connection=connection,
            capability=capability,
            risk_class=action.risk_class,
            created_at=now,
        )
        try:
            await self._commit("The execution confirmation could not be recorded.")
        except PublicAPIError:
            prior = await self.repository.execution_by_idempotency(self.tenant.organisation_id, idempotency_key)
            if prior is None:
                raise
            return self._execution_response(prior)
        logger.info("execution_confirmed", extra=self._execution_log_context(action, connection, capability))
        record = await self.repository.execution(self.tenant.organisation_id, execution.id)
        assert record is not None
        return self._execution_response(record)

    async def list_for_action(self, action_id: UUID) -> ActionExecutionListResponse:
        self._require_execution_features()
        if await self.action_repository.get_action(self.tenant.organisation_id, action_id) is None:
            raise PublicAPIError("action_not_found", "The requested Action was not found.", 404)
        records = await self.repository.list_action_executions(self.tenant.organisation_id, action_id)
        return ActionExecutionListResponse(
            items=[self._execution_response(item) for item in records],
            total=len(records),
        )

    async def get_execution(self, execution_id: UUID) -> ActionExecutionDetailResponse:
        self._require_execution_features()
        record = await self.repository.execution(self.tenant.organisation_id, execution_id)
        if record is None:
            raise PublicAPIError("execution_not_found", "The requested execution was not found.", 404)
        attempts = await self.repository.attempts(self.tenant.organisation_id, execution_id)
        base = self._execution_response(record)
        return ActionExecutionDetailResponse(
            **base.model_dump(),
            attempts=[
                ExecutionAttemptResponse(
                    attempt_number=item.attempt_number,
                    status=item.status,
                    safe_failure_code=item.safe_failure_code,
                    external_result_id=item.external_result_id,
                    started_at=item.started_at,
                    completed_at=item.completed_at,
                    duration_ms=item.duration_ms,
                )
                for item in attempts
            ],
        )

    def _require_execution_features(self) -> None:
        if not (
            self.settings.feature_integrations_enabled
            and self.settings.feature_action_execution_enabled
            and self.settings.feature_mock_connectors_enabled
            and self.settings.feature_action_layer_enabled
            and self.settings.environment != "production"
        ):
            raise PublicAPIError("feature_unavailable", "This feature is not enabled for the private beta.", 404)

    async def _require_approved_action(
        self,
        action_id: UUID,
        *,
        for_update: bool = False,
    ) -> ActionRecord:
        record = await self.repository.approved_action(
            self.tenant.organisation_id,
            action_id,
            for_update=for_update,
        )
        if record is None:
            existing = await self.action_repository.get_action(self.tenant.organisation_id, action_id)
            if existing is None:
                raise PublicAPIError("action_not_found", "The requested Action was not found.", 404)
            raise PublicAPIError("action_not_approved", "Only an approved Action can be executed.", 409)
        proposal = record.proposal
        if (
            proposal.status != ActionStatus.APPROVED.value
            or proposal.approved_version is None
            or proposal.approved_version != proposal.current_version
        ):
            raise PublicAPIError(
                "action_not_approved", "Only the current approved Action version can be executed.", 409
            )
        opportunity_statement = select(Opportunity).where(
            Opportunity.organisation_id == self.tenant.organisation_id,
            Opportunity.id == proposal.opportunity_id,
        )
        if for_update:
            opportunity_statement = opportunity_statement.with_for_update()
        if await self.session.scalar(opportunity_statement) is None:
            raise PublicAPIError("action_target_stale", "The Action target is no longer available.", 409)
        try:
            references = _SOURCE_ADAPTER.validate_python(record.version.source_refs_json)
        except ValidationError as exc:
            raise PublicAPIError("action_provenance_unavailable", "The Action provenance is invalid.", 409) from exc
        for reference in references:
            if not await self.action_repository.source_is_current(
                self.tenant.organisation_id,
                proposal.opportunity_id,
                reference,
            ):
                raise PublicAPIError(
                    "action_source_stale",
                    "This Action is no longer supported by current validated evidence.",
                    409,
                )
        return record

    async def _action_input(self, record: ActionRecord) -> ApprovedActionInput:
        try:
            payload = _PAYLOAD_ADAPTER.validate_python(record.version.payload_json)
        except ValidationError as exc:
            raise PublicAPIError("action_content_unavailable", "The approved Action content is invalid.", 409) from exc
        proposal = record.proposal
        participant_contacts: tuple[ApprovedContactRecipient, ...] = ()
        if isinstance(payload, FollowUpEmailPayload) and payload.recipient_contact_id is not None:
            contact = await self.session.scalar(
                select(Contact).where(
                    Contact.organisation_id == self.tenant.organisation_id,
                    Contact.id == payload.recipient_contact_id,
                )
            )
            if (
                contact is None
                or payload.recipient_email is None
                or contact.email.casefold() != payload.recipient_email.casefold()
            ):
                raise PublicAPIError("unsupported_recipient", "The approved Contact recipient is unavailable.", 409)
        if isinstance(payload, ScheduleInteractionPayload):
            contacts = list(
                (
                    await self.session.scalars(
                        select(Contact).where(
                            Contact.organisation_id == self.tenant.organisation_id,
                            Contact.id.in_(payload.participant_contact_ids),
                        )
                    )
                ).all()
            )
            contacts_by_id = {contact.id: contact for contact in contacts}
            if len(contacts_by_id) != len(set(payload.participant_contact_ids)):
                raise PublicAPIError("calendar_attendees_stale", "A selected calendar participant is unavailable.", 409)
            participant_contacts = tuple(
                ApprovedContactRecipient(
                    contact_id=contact_id,
                    display_name=f"{contacts_by_id[contact_id].first_name} {contacts_by_id[contact_id].last_name}",
                    email=contacts_by_id[contact_id].email,
                )
                for contact_id in payload.participant_contact_ids
            )
        if isinstance(payload, OpportunityUpdatePayload) and (
            record.version.target_entity_type != "opportunity"
            or record.version.target_entity_id != proposal.opportunity_id
        ):
            raise PublicAPIError("action_target_stale", "The approved Opportunity target is unavailable.", 409)
        if isinstance(payload, ContactUpdatePayload) and payload.operation == "update":
            contact = (
                await self.session.scalar(
                    select(Contact).where(
                        Contact.organisation_id == self.tenant.organisation_id,
                        Contact.id == payload.contact_id,
                    )
                )
                if payload.contact_id is not None
                else None
            )
            if (
                contact is None
                or record.version.target_entity_type != "contact"
                or record.version.target_entity_id != payload.contact_id
            ):
                raise PublicAPIError("action_target_stale", "The approved Contact target is unavailable.", 409)
        if isinstance(payload, CreateTaskPayload) and (
            payload.linked_opportunity_id != proposal.opportunity_id
            or record.version.target_entity_type != "opportunity"
            or record.version.target_entity_id != proposal.opportunity_id
        ):
            raise PublicAPIError("action_target_stale", "The approved task target is unavailable.", 409)
        return ApprovedActionInput(
            organisation_id=self.tenant.organisation_id,
            action_id=proposal.id,
            action_version=cast(int, proposal.approved_version),
            opportunity_id=proposal.opportunity_id,
            action_type=proposal.action_type,
            risk_class=ActionRiskClass(proposal.risk_class),
            title=record.version.title,
            target_entity_type=record.version.target_entity_type,
            target_entity_id=record.version.target_entity_id,
            payload=payload,
            participant_contacts=participant_contacts,
        )

    async def _require_active_connection(
        self,
        connection_id: UUID,
        *,
        for_update: bool = False,
    ) -> IntegrationConnection:
        connection = await self.repository.connection(
            self.tenant.organisation_id,
            connection_id,
            for_update=for_update,
        )
        if connection is None:
            raise PublicAPIError("connection_not_found", "The requested connection was not found.", 404)
        if connection.connection_status != ConnectionStatus.ACTIVE.value:
            raise PublicAPIError("connection_revoked", "This connection has been revoked.", 409)
        return connection

    def _executor(
        self,
        connection: IntegrationConnection,
        capability: ConnectorCapability,
        risk_class: ActionRiskClass,
    ) -> ActionExecutor:
        try:
            state = {ConnectorCapability(item) for item in connection.capability_state_json}
        except ValueError as exc:
            raise PublicAPIError(
                "connection_capabilities_invalid", "The connection capabilities are invalid.", 409
            ) from exc
        executor = self.executors.get(ConnectorKey(connection.connector_key))
        if capability not in state or capability not in executor.get_capabilities():
            raise PublicAPIError(
                "capability_unavailable",
                "The selected connection does not support this approved Action.",
                409,
            )
        if risk_class not in executor.definition.risk_classes:
            raise PublicAPIError(
                "action_risk_mismatch",
                "The approved Action risk class is not valid for this connector capability.",
                409,
            )
        return executor

    @staticmethod
    def _capability(action_type: str) -> ConnectorCapability:
        try:
            return capability_for_action(action_type)
        except PermanentExecutionFailure as exc:
            raise PublicAPIError(exc.code, exc.safe_message, 409) from exc

    async def _current_external_state(
        self,
        executor: ActionExecutor,
        action: ApprovedActionInput,
        connection_id: UUID,
    ) -> object | None:
        try:
            object_key = executor.object_key(action, "preview")
        except PermanentExecutionFailure as exc:
            raise PublicAPIError(exc.code, exc.safe_message, 409) from exc
        mock_object = await self.repository.mock_object(
            self.tenant.organisation_id,
            connection_id,
            object_key,
        )
        if mock_object is None:
            return None
        return mock_object.state_json.get("current_value")

    async def _enforce_rate_limits(self, capability: ConnectorCapability, now: datetime) -> None:
        start = datetime.combine(now.date(), time.min, tzinfo=UTC)
        limit = {
            ConnectorCapability.SEND_EMAIL: self.settings.private_beta_max_email_executions_per_day,
            ConnectorCapability.CREATE_CALENDAR_EVENT: self.settings.private_beta_max_calendar_executions_per_day,
            ConnectorCapability.UPDATE_OPPORTUNITY: self.settings.private_beta_max_crm_executions_per_day,
            ConnectorCapability.UPDATE_CONTACT: self.settings.private_beta_max_crm_executions_per_day,
            ConnectorCapability.CREATE_TASK: self.settings.private_beta_max_task_executions_per_day,
        }.get(capability)
        if limit is None:
            raise PublicAPIError("capability_unavailable", "This capability is unavailable.", 409)
        count = await self.repository.confirmed_count_since(
            self.tenant.organisation_id,
            capability.value,
            start,
        )
        if count >= limit:
            raise PublicAPIError(
                "execution_rate_limit_exceeded",
                "The private-beta simulation limit has been reached for this capability today.",
                429,
            )
        active = await self.repository.active_execution_count(self.tenant.organisation_id)
        if active >= self.settings.private_beta_max_concurrent_executions:
            raise PublicAPIError(
                "concurrent_execution_limit_reached",
                "Wait for another simulation to finish before confirming this one.",
                429,
            )

    @staticmethod
    def _preview_fingerprint(
        action_record: ActionRecord,
        connection: IntegrationConnection,
        capability: ConnectorCapability,
        content: dict[str, object],
    ) -> str:
        value = {
            "schemaVersion": 1,
            "actionId": str(action_record.proposal.id),
            "actionVersion": action_record.proposal.approved_version,
            "actionContentFingerprint": action_record.version.content_fingerprint,
            "connectionId": str(connection.id),
            "connectionMetadataVersion": connection.metadata_version,
            "connectionStatus": connection.connection_status,
            "capabilityState": sorted(connection.capability_state_json),
            "capability": capability.value,
            "preview": content,
            "executionMode": "simulation",
        }
        return hashlib.sha256(
            json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
        ).hexdigest()

    @staticmethod
    def _idempotency_key(
        action: ApprovedActionInput,
        connection_id: UUID,
        capability: ConnectorCapability,
    ) -> str:
        value = (
            f"execution-v1:{action.organisation_id}:{action.action_id}:{action.action_version}:"
            f"{connection_id}:{capability.value}:simulation"
        )
        return hashlib.sha256(value.encode()).hexdigest()

    def _preview_response(
        self,
        preview: ExecutionPreview,
        connection: IntegrationConnection,
        content: ExecutionPreviewContent,
    ) -> ExecutionPreviewResponse:
        capability = ConnectorCapability(preview.capability)
        definition = CONNECTOR_DEFINITIONS[ConnectorKey(connection.connector_key)]
        confirmation_label = {
            ConnectorCapability.SEND_EMAIL: "Send email",
            ConnectorCapability.CREATE_CALENDAR_EVENT: "Create event",
            ConnectorCapability.UPDATE_OPPORTUNITY: "Update opportunity",
            ConnectorCapability.UPDATE_CONTACT: "Update contact",
            ConnectorCapability.CREATE_TASK: "Create task",
        }[capability]
        summary = {
            ConnectorCapability.SEND_EMAIL: "Simulate sending this approved email.",
            ConnectorCapability.CREATE_CALENDAR_EVENT: "Simulate creating this approved calendar event.",
            ConnectorCapability.UPDATE_OPPORTUNITY: "Simulate this approved opportunity update.",
            ConnectorCapability.UPDATE_CONTACT: "Simulate this approved contact update.",
            ConnectorCapability.CREATE_TASK: "Simulate creating this approved task.",
        }[capability]
        return ExecutionPreviewResponse(
            id=preview.id,
            action_proposal_id=preview.action_id,
            action_version=preview.action_version,
            connection_id=preview.connection_id,
            connector_key=definition.connector_key,
            connector_display_name=definition.display_name,
            capability=capability,
            risk_class=ActionRiskClass(preview.risk_class),
            summary=summary,
            confirmation_label=confirmation_label,
            preview_fingerprint=preview.preview_fingerprint,
            content=content,
            expires_at=preview.expires_at,
            created_at=preview.created_at,
        )

    @staticmethod
    def _execution_response(record: ExecutionRecord) -> ActionExecutionResponse:
        execution = record.execution
        status = ExecutionStatus(execution.execution_status)
        definition = CONNECTOR_DEFINITIONS[ConnectorKey(execution.connector_key)]
        safe_message = {
            ExecutionStatus.QUEUED: "Simulation queued. No external action has occurred.",
            ExecutionStatus.EXECUTING: "Simulation is running. No external action will occur.",
            ExecutionStatus.SIMULATED_SUCCESS: "Simulation completed. No external action occurred.",
            ExecutionStatus.FAILED_RETRYABLE: "Simulation failed safely and is eligible for a bounded retry.",
            ExecutionStatus.FAILED_PERMANENT: "Simulation stopped safely and will not be retried.",
            ExecutionStatus.CANCELLED: "Simulation was cancelled before execution.",
            ExecutionStatus.UNKNOWN_EXTERNAL_STATE: (
                "Outcome is unknown. RevenueOS will not retry without reconciliation."
            ),
        }[status]
        return ActionExecutionResponse(
            id=execution.id,
            action_proposal_id=execution.action_id,
            action_version=execution.action_version,
            connection_id=execution.connection_id,
            connector_key=definition.connector_key,
            connector_display_name=definition.display_name,
            capability=ConnectorCapability(execution.capability),
            risk_class=ActionRiskClass(execution.risk_class),
            execution_status=status,
            confirmed_by_user_id=execution.confirmed_by_user_id,
            confirmed_at=execution.confirmed_at,
            started_at=execution.started_at,
            completed_at=execution.completed_at,
            failed_at=execution.failed_at,
            safe_failure_code=execution.safe_failure_code,
            external_result_id=execution.external_result_id,
            attempt_count=execution.attempt_count,
            retryable=status == ExecutionStatus.FAILED_RETRYABLE,
            safe_message=safe_message,
            created_at=execution.created_at,
            updated_at=execution.updated_at,
        )

    def _add_execution_audit(
        self,
        *,
        event_type: str,
        subject_type: str,
        subject_id: UUID,
        connection: IntegrationConnection,
        capability: ConnectorCapability,
        risk_class: ActionRiskClass,
        created_at: datetime,
    ) -> None:
        self.repository.add(
            IntegrationAuditEvent(
                id=uuid.uuid4(),
                organisation_id=self.tenant.organisation_id,
                actor_user_id=self.tenant.user_id,
                event_type=event_type,
                subject_type=subject_type,
                subject_id=subject_id,
                connector_key=connection.connector_key,
                capability=capability.value,
                risk_class=risk_class.value,
                attempt_count=None,
                safe_failure_code=None,
                external_result_id=None,
                duration_ms=None,
                created_at=created_at,
            )
        )

    async def _commit(self, message: str) -> None:
        try:
            await self.repository.flush()
            await self.repository.commit()
            await set_tenant_database_context(self.session, self.tenant.organisation_id)
        except IntegrityError as exc:
            await self.repository.rollback()
            await set_tenant_database_context(self.session, self.tenant.organisation_id)
            raise PublicAPIError("execution_conflict", message, 409) from exc

    @staticmethod
    def _as_utc(value: datetime) -> datetime:
        return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)

    @staticmethod
    def _execution_log_context(
        action: ApprovedActionInput,
        connection: IntegrationConnection,
        capability: ConnectorCapability,
    ) -> dict[str, object]:
        return {
            "organisation_id": str(action.organisation_id),
            "action_id": str(action.action_id),
            "action_version": action.action_version,
            "connection_id": str(connection.id),
            "connector_key": connection.connector_key,
            "capability": capability.value,
            "risk_class": action.risk_class.value,
            "execution_mode": "simulation",
        }


async def membership_is_active(session: AsyncSession, tenant: TenantContext) -> bool:
    membership = await session.get(OrganisationMembership, (tenant.organisation_id, tenant.user_id))
    return membership is not None and membership.status == "active"
