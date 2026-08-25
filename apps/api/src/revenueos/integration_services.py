from __future__ import annotations

import hashlib
import json
import logging
import secrets
import uuid
from dataclasses import replace
from datetime import UTC, datetime, time, timedelta
from typing import TYPE_CHECKING, Literal, NoReturn, cast
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
    LogInteractionPayload,
    OpportunityUpdatePayload,
    ScheduleInteractionPayload,
)
from revenueos.action_repositories import ActionRecord, ActionRepository
from revenueos.config import Settings
from revenueos.credential_store import (
    CredentialStore,
    EncryptedDatabaseCredentialStore,
    MockCredentialStore,
)
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
    CRMEntityLinkRequest,
    CRMEntityMappingResponse,
    CRMFieldConfigurationResponse,
    CRMFieldMappingRequest,
    CRMFieldMappingResponse,
    CRMPropertyDefinition,
    CRMSearchResponse,
    CRMSearchResult,
    CRMStageConfigurationResponse,
    CRMStageDefinition,
    CRMStageMappingRequest,
    CRMStageMappingResponse,
    ExecutionAttemptResponse,
    ExecutionConfirmRequest,
    ExecutionPreviewContent,
    ExecutionPreviewResponse,
    IntegrationCatalogResponse,
    OAuthCallbackRequest,
    OAuthStartResponse,
    OrganisationConnectionResponse,
)
from revenueos.integration_executors import (
    CONNECTOR_DEFINITIONS,
    ActionExecutor,
    ActionExecutorRegistry,
    ApprovedActionInput,
    ApprovedContactRecipient,
    ApprovedExternalTarget,
    ExecutionFailure,
    ExecutorConnectionContext,
    PermanentExecutionFailure,
    capability_for_action,
)
from revenueos.integration_repositories import ExecutionRecord, IntegrationRepository
from revenueos.models import (
    ActionExecution,
    Company,
    Contact,
    CRMEntityMapping,
    CRMFieldMapping,
    CRMStageMapping,
    ExecutionPreview,
    IntegrationAuditEvent,
    IntegrationConnection,
    Interaction,
    OAuthConnectionState,
    Opportunity,
    OrganisationMembership,
    User,
)
from revenueos.tenant import TenantContext

if TYPE_CHECKING:
    from revenueos.hubspot_connector import HubSpotClient

logger = logging.getLogger("revenueos.integrations")
_PAYLOAD_ADAPTER: TypeAdapter[ActionPayload] = TypeAdapter(ActionPayload)
_SOURCE_ADAPTER: TypeAdapter[list[ActionSourceReference]] = TypeAdapter(list[ActionSourceReference])


class IntegrationService:
    """Tenant connection, OAuth and focused CRM mapping management."""

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
        self.credential_store = credential_store or self._credential_store()
        self.hubspot_client: HubSpotClient | None = None
        live_executor: ActionExecutor | None = None
        if settings.feature_hubspot_crm_enabled:
            from revenueos.hubspot_connector import HubSpotClient, HubSpotCRMExecutor

            self.hubspot_client = HubSpotClient(settings, self.credential_store)
            live_executor = HubSpotCRMExecutor(self.hubspot_client)
        self.executors = executors or ActionExecutorRegistry(live_executor=live_executor)

    def catalog(self) -> IntegrationCatalogResponse:
        self._require_integrations()
        mock_available = self._mock_connectors_available()
        hubspot_available = self.settings.feature_hubspot_crm_enabled
        definitions = [
            definition
            for definition in CONNECTOR_DEFINITIONS.values()
            if (definition.simulation_only and mock_available)
            or (definition.connector_key == ConnectorKey.HUBSPOT and hubspot_available)
        ]
        return IntegrationCatalogResponse(
            connectors=[
                ConnectorDefinitionResponse(
                    connector_key=definition.connector_key,
                    display_name=definition.display_name,
                    provider_family=definition.provider_family,
                    supported_capabilities=list(definition.capabilities),
                    authentication_type=definition.authentication_type,
                    execution_risk_classes=list(definition.risk_classes),
                    configuration_schema_version=1,
                    execution_mode=definition.execution_mode,
                    available=True,
                    simulation_only=definition.simulation_only,
                )
                for definition in definitions
            ],
            execution_mode="mixed" if hubspot_available else "simulation",
            external_actions_enabled=hubspot_available,
        )

    async def list_connections(self) -> ConnectionListResponse:
        self._require_integrations()
        records = await self.repository.list_connections(self.tenant.organisation_id)
        visible = [
            item
            for item in records
            if (item.connector_key.startswith("mock_") and self._mock_connectors_available())
            or (item.connector_key == ConnectorKey.HUBSPOT.value and self.settings.feature_hubspot_crm_enabled)
        ]
        return ConnectionListResponse(items=[self._connection_response(item) for item in visible], total=len(visible))

    async def get_connection(self, connection_id: UUID) -> OrganisationConnectionResponse:
        self._require_integrations()
        connection = await self._require_connection(connection_id)
        self._require_connector_available(connection.connector_key)
        return self._connection_response(connection)

    async def create_connection(self, request: ConnectionCreateRequest) -> OrganisationConnectionResponse:
        self._require_admin()
        if request.connector_key == ConnectorKey.HUBSPOT:
            raise PublicAPIError(
                "oauth_required",
                "Start the HubSpot authorisation flow to create this connection.",
                409,
            )
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
        self._require_integrations()
        connection = await self._require_connection(connection_id, for_update=True)
        self._require_connector_available(connection.connector_key)
        self._require_active_connection(connection)
        checked_at = datetime.now(UTC)
        definition = CONNECTOR_DEFINITIONS[ConnectorKey(connection.connector_key)]
        try:
            await self.executors.get(ConnectorKey(connection.connector_key)).validate_connection(
                self._connection_context(connection)
            )
        except ExecutionFailure as exc:
            if connection.connector_key == ConnectorKey.HUBSPOT.value:
                connection.connection_status = ConnectionStatus.REAUTHORISATION_REQUIRED.value
                connection.metadata_version += 1
                self._add_audit(connection, "connection_reauthorisation_required", checked_at)
                await self._commit("The HubSpot connection state could not be updated.")
            raise PublicAPIError(exc.code, exc.safe_message, 409) from exc
        connection.last_verified_at = checked_at
        connection.metadata_version += 1
        self._add_audit(connection, "connection_tested", checked_at)
        await self._commit("The connection could not be tested.")
        logger.info("connection_tested", extra=self._connection_log_context(connection))
        refreshed = await self._require_connection(connection_id)
        return ConnectionHealthResponse(
            connection=self._connection_response(refreshed),
            healthy=True,
            checked_at=checked_at,
            safe_message=(
                "Simulation connection verified. No external request was made."
                if definition.simulation_only
                else "HubSpot authorisation and account identity were verified."
            ),
        )

    async def revoke_connection(self, connection_id: UUID) -> OrganisationConnectionResponse:
        self._require_admin()
        self._require_integrations()
        connection = await self._require_connection(connection_id, for_update=True)
        self._require_connector_available(connection.connector_key)
        if connection.connection_status == ConnectionStatus.REVOKED.value:
            return self._connection_response(connection)
        now = datetime.now(UTC)
        if connection.credential_reference is not None:
            if connection.connector_key == ConnectorKey.HUBSPOT.value and self.hubspot_client is not None:
                from revenueos.hubspot_connector import HubSpotAPIError

                try:
                    credential = await self.credential_store.get(
                        self.tenant.organisation_id,
                        connection.id,
                        connection.credential_reference,
                    )
                    await self.hubspot_client.revoke(credential)
                except (ValueError, HubSpotAPIError):
                    # Provider revocation is best effort; local credential deletion always wins.
                    logger.warning(
                        "connection_provider_revocation_failed",
                        extra=self._connection_log_context(connection),
                    )
            await self.credential_store.revoke(
                self.tenant.organisation_id,
                connection.id,
                connection.credential_reference,
            )
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
        await self._commit("The connection could not be revoked.")
        logger.info("connection_revoked", extra=self._connection_log_context(connection))
        return self._connection_response(await self._require_connection(connection_id))

    async def start_hubspot_oauth(self) -> OAuthStartResponse:
        self._require_admin()
        client = self._require_hubspot()
        state = secrets.token_urlsafe(48)
        now = datetime.now(UTC)
        assert self.settings.hubspot_oauth_redirect_uri is not None
        self.repository.add(
            OAuthConnectionState(
                id=uuid.uuid4(),
                organisation_id=self.tenant.organisation_id,
                user_id=self.tenant.user_id,
                connector_key=ConnectorKey.HUBSPOT.value,
                state_hash=hashlib.sha256(state.encode()).hexdigest(),
                redirect_uri=self.settings.hubspot_oauth_redirect_uri,
                expires_at=now + timedelta(seconds=self.settings.hubspot_oauth_state_ttl_seconds),
                consumed_at=None,
                created_at=now,
            )
        )
        await self._commit("The HubSpot authorisation flow could not be started.")
        return OAuthStartResponse(
            authorisation_url=client.authorisation_url(state),
            expires_at=now + timedelta(seconds=self.settings.hubspot_oauth_state_ttl_seconds),
        )

    async def complete_hubspot_oauth(
        self,
        request: OAuthCallbackRequest,
    ) -> OrganisationConnectionResponse:
        self._require_admin()
        client = self._require_hubspot()
        now = datetime.now(UTC)
        state = await self.repository.oauth_state_by_hash(
            self.tenant.organisation_id,
            hashlib.sha256(request.state.encode()).hexdigest(),
            for_update=True,
        )
        if state is None:
            raise PublicAPIError("oauth_state_invalid", "This HubSpot authorisation request is invalid.", 400)
        if state.user_id != self.tenant.user_id:
            raise PublicAPIError("oauth_state_invalid", "This HubSpot authorisation request is invalid.", 400)
        if state.consumed_at is not None:
            raise PublicAPIError("oauth_state_replayed", "This HubSpot authorisation request was already used.", 409)
        if self._as_utc(state.expires_at) <= now:
            raise PublicAPIError("oauth_state_expired", "This HubSpot authorisation request has expired.", 409)
        if state.redirect_uri != self.settings.hubspot_oauth_redirect_uri:
            raise PublicAPIError("oauth_redirect_mismatch", "This HubSpot authorisation request is invalid.", 400)
        state.consumed_at = now
        if request.provider_error is not None:
            await self._commit("The HubSpot authorisation result could not be recorded.")
            raise PublicAPIError(
                "oauth_authorisation_declined",
                "HubSpot authorisation was not completed. No connection was created.",
                400,
            )
        assert request.code is not None
        from revenueos.hubspot_connector import HubSpotAPIError

        try:
            credential, account_name = await client.exchange_code(request.code)
        except HubSpotAPIError as exc:
            await self._commit("The HubSpot authorisation result could not be recorded.")
            raise PublicAPIError(
                exc.code,
                "HubSpot authorisation could not be verified. Start the connection again.",
                409,
            ) from exc
        connection = await self.repository.connection_by_key(
            self.tenant.organisation_id,
            ConnectorKey.HUBSPOT.value,
            for_update=True,
        )
        if (
            connection is not None
            and connection.external_account_id is not None
            and connection.external_account_id != credential.external_account_id
        ):
            try:
                await client.revoke(credential)
            except HubSpotAPIError:
                logger.warning(
                    "connection_rejected_credential_revocation_failed",
                    extra=self._connection_log_context(connection),
                )
            await self._commit("The rejected HubSpot authorisation could not be recorded.")
            logger.warning(
                "connection_account_change_rejected",
                extra=self._connection_log_context(connection),
            )
            raise PublicAPIError(
                "connection_account_changed",
                "Reconnect the same HubSpot account. Changing accounts requires a reviewed mapping reset.",
                409,
            )
        if connection is None:
            connection = IntegrationConnection(
                id=uuid.uuid4(),
                organisation_id=self.tenant.organisation_id,
                connector_key=ConnectorKey.HUBSPOT.value,
                connection_status=ConnectionStatus.ACTIVE.value,
                created_by_user_id=self.tenant.user_id,
                connected_at=now,
                last_verified_at=now,
                revoked_at=None,
                credential_reference=None,
                capability_state_json=[item.value for item in CONNECTOR_DEFINITIONS[ConnectorKey.HUBSPOT].capabilities],
                external_account_id=credential.external_account_id,
                external_account_name=account_name,
                granted_scopes_json=list(credential.scopes),
                metadata_version=1,
                created_at=now,
                updated_at=now,
            )
            self.repository.add(connection)
            event_type = "connection_created"
            await self.repository.flush()
        else:
            connection.connection_status = ConnectionStatus.ACTIVE.value
            connection.created_by_user_id = self.tenant.user_id
            connection.connected_at = now
            connection.last_verified_at = now
            connection.revoked_at = None
            connection.capability_state_json = [
                item.value for item in CONNECTOR_DEFINITIONS[ConnectorKey.HUBSPOT].capabilities
            ]
            connection.external_account_id = credential.external_account_id
            connection.external_account_name = account_name
            connection.granted_scopes_json = list(credential.scopes)
            connection.metadata_version += 1
            event_type = "connection_created"
        connection.credential_reference = await self.credential_store.put(
            self.tenant.organisation_id,
            connection.id,
            credential,
        )
        self._add_audit(connection, event_type, now)
        await self._commit("The HubSpot connection could not be saved.")
        logger.info("connection_created", extra=self._connection_log_context(connection))
        return self._connection_response(await self._require_connection(connection.id))

    async def search_crm_records(
        self,
        connection_id: UUID,
        entity_type: str,
        query: str,
    ) -> CRMSearchResponse:
        connection = await self._require_hubspot_connection(connection_id)
        query = query.strip()
        if len(query) < 2 or len(query) > 120:
            raise PublicAPIError("search_query_invalid", "Enter between 2 and 120 characters.", 422)
        object_type, properties = self._crm_search_shape(entity_type)
        try:
            records = await self._require_hubspot().search_records(
                self._connection_context(connection),
                object_type,
                query,
                properties,
            )
        except Exception as exc:
            self._raise_hubspot_public_error(exc)
        items = [
            CRMSearchResult(
                external_object_type=cast(
                    Literal["company", "contact", "deal"], object_type[:-1] if object_type != "companies" else "company"
                ),
                external_object_id=record.id,
                display_name=self._crm_display_name(entity_type, record.properties),
                secondary_label=self._crm_secondary_label(entity_type, record.properties),
                updated_at=record.updated_at,
            )
            for record in records
        ]
        return CRMSearchResponse(items=items, total=len(items))

    async def get_entity_mapping(
        self,
        connection_id: UUID,
        entity_type: str,
        entity_id: UUID,
    ) -> CRMEntityMappingResponse | None:
        connection = await self._require_hubspot_connection(connection_id)
        mapping = await self.repository.entity_mapping(
            self.tenant.organisation_id,
            connection.id,
            entity_type,
            entity_id,
        )
        return None if mapping is None else self._entity_mapping_response(mapping)

    async def link_entity(
        self,
        entity_type: str,
        entity_id: UUID,
        request: CRMEntityLinkRequest,
    ) -> CRMEntityMappingResponse:
        connection = await self._require_hubspot_connection(request.connection_id)
        expected_object = {"company": "company", "contact": "contact", "opportunity": "deal"}.get(entity_type)
        if expected_object is None or request.external_object_type != expected_object:
            raise PublicAPIError("crm_mapping_invalid", "Select the matching HubSpot object type.", 422)
        await self._require_local_entity(entity_type, entity_id)
        plural = {"company": "companies", "contact": "contacts", "deal": "deals"}[request.external_object_type]
        try:
            record = await self._require_hubspot().get_record(
                self._connection_context(connection),
                plural,
                request.external_object_id,
                (),
            )
        except Exception as exc:
            self._raise_hubspot_public_error(exc)
        now = datetime.now(UTC)
        mapping = await self.repository.entity_mapping(
            self.tenant.organisation_id,
            connection.id,
            entity_type,
            entity_id,
            for_update=True,
        )
        event_type = "mapping_changed"
        if mapping is None:
            event_type = "mapping_created"
            mapping = CRMEntityMapping(
                id=uuid.uuid4(),
                organisation_id=self.tenant.organisation_id,
                connection_id=connection.id,
                revenueos_entity_type=entity_type,
                revenueos_entity_id=entity_id,
                external_object_type=request.external_object_type,
                external_object_id=request.external_object_id,
                external_updated_at=record.updated_at,
                last_synced_at=None,
                sync_state="active",
                created_by_user_id=self.tenant.user_id,
                created_at=now,
                updated_at=now,
            )
            self.repository.add(mapping)
        else:
            mapping.external_object_type = request.external_object_type
            mapping.external_object_id = request.external_object_id
            mapping.external_updated_at = record.updated_at
            mapping.sync_state = "active"
        self._add_audit(connection, event_type, now)
        await self._commit("The CRM record link could not be saved.")
        return self._entity_mapping_response(mapping)

    async def unlink_entity(self, connection_id: UUID, entity_type: str, entity_id: UUID) -> None:
        connection = await self._require_hubspot_connection(connection_id)
        mapping = await self.repository.entity_mapping(
            self.tenant.organisation_id,
            connection.id,
            entity_type,
            entity_id,
            for_update=True,
        )
        if mapping is None:
            return
        await self.repository.delete_entity_mapping(mapping)
        self._add_audit(connection, "mapping_removed", datetime.now(UTC))
        await self._commit("The CRM record link could not be removed.")

    async def field_configuration(
        self,
        connection_id: UUID,
        entity_type: str,
    ) -> CRMFieldConfigurationResponse:
        self._require_admin()
        connection = await self._require_hubspot_connection(connection_id)
        object_type = {"opportunity": "deals", "contact": "contacts"}.get(entity_type)
        if object_type is None:
            raise PublicAPIError("crm_entity_type_invalid", "This CRM entity type is unsupported.", 422)
        try:
            properties = await self._require_hubspot().properties(self._connection_context(connection), object_type)
        except Exception as exc:
            self._raise_hubspot_public_error(exc)
        supported = {"string", "number", "date", "datetime", "enumeration"}
        definitions = [
            CRMPropertyDefinition(
                entity_type=cast(Literal["opportunity", "contact"], entity_type),
                external_property_name=item.name,
                label=item.label,
                property_type=cast(Literal["string", "number", "date", "datetime", "enumeration"], item.type),
                options=[
                    {"label": option.label, "value": option.value} for option in item.options if not option.hidden
                ],
                read_only=item.modification_metadata.read_only_value,
            )
            for item in properties
            if item.type in supported
        ]
        mappings = await self.repository.list_field_mappings(
            self.tenant.organisation_id,
            connection.id,
            entity_type,
        )
        return CRMFieldConfigurationResponse(
            properties=definitions,
            mappings=[self._field_mapping_response(item) for item in mappings],
        )

    async def set_field_mapping(
        self,
        connection_id: UUID,
        request: CRMFieldMappingRequest,
    ) -> CRMFieldMappingResponse:
        self._require_admin()
        configuration = await self.field_configuration(connection_id, request.entity_type)
        selected = next(
            (
                item
                for item in configuration.properties
                if item.external_property_name == request.external_property_name
            ),
            None,
        )
        if selected is None or selected.read_only:
            raise PublicAPIError("crm_property_invalid", "Select a writable HubSpot property.", 422)
        self._validate_field_compatibility(request.revenueos_field, selected.property_type)
        connection = await self._require_hubspot_connection(connection_id)
        mappings = await self.repository.list_field_mappings(
            self.tenant.organisation_id,
            connection.id,
            request.entity_type,
        )
        mapping = next((item for item in mappings if item.revenueos_field == request.revenueos_field), None)
        now = datetime.now(UTC)
        if mapping is None:
            mapping = CRMFieldMapping(
                id=uuid.uuid4(),
                organisation_id=self.tenant.organisation_id,
                connection_id=connection.id,
                entity_type=request.entity_type,
                revenueos_field=request.revenueos_field,
                external_property_name=request.external_property_name,
                external_property_type=selected.property_type,
                authority=request.authority,
                enabled=True,
                configured_by_user_id=self.tenant.user_id,
                created_at=now,
                updated_at=now,
            )
            self.repository.add(mapping)
        else:
            mapping.external_property_name = request.external_property_name
            mapping.external_property_type = selected.property_type
            mapping.authority = request.authority
            mapping.enabled = True
            mapping.configured_by_user_id = self.tenant.user_id
        connection.metadata_version += 1
        self._add_audit(connection, "field_mapping_changed", now)
        await self._commit("The CRM field mapping could not be saved.")
        return self._field_mapping_response(mapping)

    async def stage_configuration(self, connection_id: UUID) -> CRMStageConfigurationResponse:
        self._require_admin()
        connection = await self._require_hubspot_connection(connection_id)
        try:
            pipelines = await self._require_hubspot().pipelines(self._connection_context(connection))
        except Exception as exc:
            self._raise_hubspot_public_error(exc)
        mappings = await self.repository.list_stage_mappings(self.tenant.organisation_id, connection.id)
        return CRMStageConfigurationResponse(
            available_stages=[
                CRMStageDefinition(
                    pipeline_id=pipeline.id,
                    pipeline_label=pipeline.label,
                    stage_id=stage.id,
                    stage_label=stage.label,
                )
                for pipeline in pipelines
                for stage in pipeline.stages
            ],
            mappings=[
                CRMStageMappingResponse(
                    revenueos_stage=item.revenueos_stage,
                    external_pipeline_id=item.external_pipeline_id,
                    external_stage_id=item.external_stage_id,
                )
                for item in mappings
            ],
        )

    async def set_stage_mapping(
        self,
        connection_id: UUID,
        request: CRMStageMappingRequest,
    ) -> CRMStageMappingResponse:
        self._require_admin()
        configuration = await self.stage_configuration(connection_id)
        if not any(
            item.pipeline_id == request.external_pipeline_id and item.stage_id == request.external_stage_id
            for item in configuration.available_stages
        ):
            raise PublicAPIError("crm_stage_invalid", "Select a current HubSpot deal stage.", 422)
        connection = await self._require_hubspot_connection(connection_id)
        mapping = await self.repository.stage_mapping(
            self.tenant.organisation_id,
            connection.id,
            request.revenueos_stage,
        )
        now = datetime.now(UTC)
        if mapping is None:
            mapping = CRMStageMapping(
                id=uuid.uuid4(),
                organisation_id=self.tenant.organisation_id,
                connection_id=connection.id,
                revenueos_stage=request.revenueos_stage,
                external_pipeline_id=request.external_pipeline_id,
                external_stage_id=request.external_stage_id,
                configured_by_user_id=self.tenant.user_id,
                created_at=now,
                updated_at=now,
            )
            self.repository.add(mapping)
        else:
            mapping.external_pipeline_id = request.external_pipeline_id
            mapping.external_stage_id = request.external_stage_id
            mapping.configured_by_user_id = self.tenant.user_id
        connection.metadata_version += 1
        self._add_audit(connection, "stage_mapping_changed", now)
        await self._commit("The CRM stage mapping could not be saved.")
        return CRMStageMappingResponse(
            revenueos_stage=mapping.revenueos_stage,
            external_pipeline_id=mapping.external_pipeline_id,
            external_stage_id=mapping.external_stage_id,
        )

    def _require_integrations(self) -> None:
        if not self.settings.feature_integrations_enabled:
            raise PublicAPIError("feature_unavailable", "This feature is not enabled for the private beta.", 404)

    def _credential_store(self) -> CredentialStore:
        if not self.settings.feature_hubspot_crm_enabled:
            return MockCredentialStore()
        if self.settings.connector_credential_master_key is None:
            raise RuntimeError("HubSpot credential storage is not configured.")
        return EncryptedDatabaseCredentialStore(
            self.session,
            self.settings.connector_credential_master_key.get_secret_value(),
        )

    def _require_hubspot(self) -> HubSpotClient:
        self._require_integrations()
        if not self.settings.feature_hubspot_crm_enabled or self.hubspot_client is None:
            raise PublicAPIError("feature_unavailable", "HubSpot CRM sync is not enabled.", 404)
        return self.hubspot_client

    async def _require_hubspot_connection(self, connection_id: UUID) -> IntegrationConnection:
        self._require_hubspot()
        connection = await self._require_connection(connection_id)
        if connection.connector_key != ConnectorKey.HUBSPOT.value:
            raise PublicAPIError("connection_not_found", "The requested HubSpot connection was not found.", 404)
        self._require_active_connection(connection)
        return connection

    def _require_connector_available(self, connector_key: str) -> None:
        if connector_key == ConnectorKey.HUBSPOT.value:
            self._require_hubspot()
            return
        if connector_key.startswith("mock_"):
            self._require_mock_connectors()
            return
        raise PublicAPIError("connector_unavailable", "The selected connector is unavailable.", 404)

    @staticmethod
    def _connection_context(connection: IntegrationConnection) -> ExecutorConnectionContext:
        definition = CONNECTOR_DEFINITIONS[ConnectorKey(connection.connector_key)]
        return ExecutorConnectionContext(
            organisation_id=connection.organisation_id,
            connection_id=connection.id,
            credential_reference=connection.credential_reference,
            execution_mode=definition.execution_mode,
        )

    async def _require_local_entity(self, entity_type: str, entity_id: UUID) -> None:
        if entity_type == "company":
            record: object | None = await self.session.scalar(
                select(Company).where(
                    Company.organisation_id == self.tenant.organisation_id,
                    Company.id == entity_id,
                )
            )
        elif entity_type == "contact":
            record = await self.session.scalar(
                select(Contact).where(
                    Contact.organisation_id == self.tenant.organisation_id,
                    Contact.id == entity_id,
                )
            )
        elif entity_type == "opportunity":
            record = await self.session.scalar(
                select(Opportunity).where(
                    Opportunity.organisation_id == self.tenant.organisation_id,
                    Opportunity.id == entity_id,
                )
            )
        else:
            raise PublicAPIError("crm_entity_type_invalid", "This CRM entity type is unsupported.", 422)
        if record is None:
            raise PublicAPIError("crm_entity_not_found", "The RevenueOS record was not found.", 404)

    @staticmethod
    def _crm_search_shape(entity_type: str) -> tuple[str, tuple[str, ...]]:
        try:
            return {
                "opportunity": ("deals", ("dealname", "dealstage", "amount")),
                "contact": ("contacts", ("firstname", "lastname", "email")),
                "company": ("companies", ("name", "domain")),
            }[entity_type]
        except KeyError as exc:
            raise PublicAPIError("crm_entity_type_invalid", "This CRM entity type is unsupported.", 422) from exc

    @staticmethod
    def _crm_display_name(entity_type: str, properties: dict[str, object]) -> str:
        if entity_type == "contact":
            value = " ".join(
                part for part in (str(properties.get("firstname") or ""), str(properties.get("lastname") or "")) if part
            )
            return value or str(properties.get("email") or "Unnamed contact")
        key = "dealname" if entity_type == "opportunity" else "name"
        return str(properties.get(key) or "Unnamed record")

    @staticmethod
    def _crm_secondary_label(entity_type: str, properties: dict[str, object]) -> str | None:
        key = {"opportunity": "dealstage", "contact": "email", "company": "domain"}[entity_type]
        value = properties.get(key)
        return str(value) if value not in (None, "") else None

    @staticmethod
    def _validate_field_compatibility(revenueos_field: str, property_type: str) -> None:
        allowed = {
            "stage": {"enumeration"},
            "status": {"enumeration"},
            "expected_close_date": {"date", "datetime"},
            "estimated_value": {"number"},
            "next_step": {"string"},
            "description": {"string"},
            "first_name": {"string"},
            "last_name": {"string"},
            "email": {"string"},
            "job_title": {"string"},
        }
        if property_type not in allowed.get(revenueos_field, set()):
            raise PublicAPIError(
                "crm_field_type_mismatch",
                "The RevenueOS field and HubSpot property types are not compatible.",
                422,
            )

    @staticmethod
    def _entity_mapping_response(mapping: CRMEntityMapping) -> CRMEntityMappingResponse:
        return CRMEntityMappingResponse(
            id=mapping.id,
            connection_id=mapping.connection_id,
            connector_key=ConnectorKey.HUBSPOT,
            revenueos_entity_type=cast(Literal["company", "contact", "opportunity"], mapping.revenueos_entity_type),
            revenueos_entity_id=mapping.revenueos_entity_id,
            external_object_type=cast(Literal["company", "contact", "deal"], mapping.external_object_type),
            external_object_id=mapping.external_object_id,
            external_updated_at=mapping.external_updated_at,
            last_synced_at=mapping.last_synced_at,
            sync_state=cast(Literal["active", "external_missing"], mapping.sync_state),
            created_at=mapping.created_at,
            updated_at=mapping.updated_at,
        )

    @staticmethod
    def _field_mapping_response(mapping: CRMFieldMapping) -> CRMFieldMappingResponse:
        return CRMFieldMappingResponse(
            id=mapping.id,
            connection_id=mapping.connection_id,
            entity_type=cast(Literal["opportunity", "contact"], mapping.entity_type),
            revenueos_field=mapping.revenueos_field,
            external_property_name=mapping.external_property_name,
            external_property_type=cast(
                Literal["string", "number", "date", "datetime", "enumeration"],
                mapping.external_property_type,
            ),
            authority=cast(
                Literal["crm_authoritative", "revenueos_authoritative", "review_before_sync"],
                mapping.authority,
            ),
            enabled=mapping.enabled,
        )

    @staticmethod
    def _raise_hubspot_public_error(error: Exception) -> NoReturn:
        from revenueos.hubspot_connector import HubSpotAPIError

        if not isinstance(error, HubSpotAPIError):
            raise error
        messages = {
            "connection_reauthorisation_required": "Reconnect HubSpot before using CRM sync.",
            "external_object_not_found": "The selected HubSpot record no longer exists.",
            "provider_rate_limited": "HubSpot is temporarily rate limiting this organisation.",
            "provider_timeout": "HubSpot did not respond in time.",
            "provider_unavailable": "HubSpot is temporarily unavailable.",
            "provider_response_invalid": "HubSpot returned an unexpected response.",
        }
        status_code = 429 if error.code == "provider_rate_limited" else 409
        raise PublicAPIError(
            error.code,
            messages.get(error.code, "HubSpot could not complete this request."),
            status_code,
        ) from error

    @staticmethod
    def _as_utc(value: datetime) -> datetime:
        return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)

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
        if connection.connection_status == ConnectionStatus.REAUTHORISATION_REQUIRED.value:
            raise PublicAPIError(
                "connection_reauthorisation_required",
                "Reconnect HubSpot before using CRM sync.",
                409,
            )
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
            external_account_id=connection.external_account_id,
            external_account_name=connection.external_account_name,
            granted_scopes=list(connection.granted_scopes_json),
            metadata_version=connection.metadata_version,
            execution_mode=definition.execution_mode,
            simulation_only=definition.simulation_only,
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
        credential_store: CredentialStore | None = None,
    ) -> None:
        self.session = session
        self.tenant = tenant
        self.settings = settings
        self.repository = IntegrationRepository(session)
        self.action_repository = ActionRepository(session)
        self.credential_store = credential_store or self._credential_store()
        live_executor: ActionExecutor | None = None
        if settings.feature_hubspot_crm_enabled:
            from revenueos.hubspot_connector import HubSpotClient, HubSpotCRMExecutor

            live_executor = HubSpotCRMExecutor(HubSpotClient(settings, self.credential_store))
        self.executors = executors or ActionExecutorRegistry(live_executor=live_executor)

    async def preview(self, action_id: UUID, connection_id: UUID) -> ExecutionPreviewResponse:
        self._require_execution_features()
        action_record = await self._require_approved_action(action_id)
        connection = await self._require_active_connection(connection_id, for_update=True)
        action = await self._action_input(action_record)
        action = await self._bind_external_target(action, connection)
        capability = self._capability(action.action_type)
        executor = self._executor(connection, capability, action.risk_class)
        current_external_state = await self._current_external_state(executor, action, connection)
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
                    execution_mode=definition.execution_mode,
                    simulation_only=definition.simulation_only,
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
        action = await self._bind_external_target(action, connection)
        capability = self._capability(action.action_type)
        if capability.value != preview.capability:
            raise PublicAPIError("execution_preview_tampered", "The execution preview does not match this Action.", 409)
        executor = self._executor(connection, capability, action.risk_class)
        current_external_state = await self._current_external_state(executor, action, connection)
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
                "The Action, connection or external state changed. Review execution again.",
                409,
            )
        await self._enforce_rate_limits(capability, now)
        idempotency_key = self._idempotency_key(
            action,
            connection.id,
            capability,
            executor.definition.execution_mode,
        )
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
            execution_mode=executor.definition.execution_mode,
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

    async def reconcile_execution(self, execution_id: UUID) -> ActionExecutionResponse:
        """Read provider state once; never retries an unknown write blindly."""
        self._require_execution_features()
        record = await self.repository.execution(
            self.tenant.organisation_id,
            execution_id,
            for_update=True,
        )
        if record is None:
            raise PublicAPIError("execution_not_found", "The requested execution was not found.", 404)
        execution = record.execution
        if execution.execution_mode != "live":
            raise PublicAPIError(
                "reconciliation_unavailable", "Simulation executions do not require reconciliation.", 409
            )
        if execution.execution_status != ExecutionStatus.UNKNOWN_EXTERNAL_STATE.value:
            return self._execution_response(record)
        connection = await self._require_active_connection(execution.connection_id, for_update=True)
        action_record = await self.repository.approved_action(
            self.tenant.organisation_id,
            execution.action_id,
            for_update=True,
        )
        if action_record is None or action_record.proposal.approved_version != execution.action_version:
            raise PublicAPIError("action_version_stale", "The approved Action version is unavailable.", 409)
        action = await self._bind_external_target(await self._action_input(action_record), connection)
        capability = ConnectorCapability(execution.capability)
        executor = self._executor(connection, capability, action.risk_class)
        context = ExecutorConnectionContext(
            organisation_id=self.tenant.organisation_id,
            connection_id=connection.id,
            credential_reference=connection.credential_reference,
            execution_mode="live",
        )
        now = datetime.now(UTC)
        external_result_id: str | None = None
        applied = False
        safe_to_retry = False
        try:
            if isinstance(action.payload, LogInteractionPayload):
                from revenueos.hubspot_connector import HubSpotCRMExecutor

                if not isinstance(executor, HubSpotCRMExecutor):
                    raise PermanentExecutionFailure(
                        "connector_unavailable",
                        "The HubSpot reconciliation adapter is unavailable.",
                    )
                result = await executor.reconcile_activity(action, execution.idempotency_key, context)
                if result is None:
                    safe_to_retry = True
                else:
                    applied = True
                    external_result_id = result.external_result_id
            else:
                state = await executor.current_external_state(action, context)
                desired = action.external_target.proposed_external_value if action.external_target is not None else None
                current = getattr(state, "current_value", object())
                if current == desired:
                    applied = True
                    assert action.external_target is not None
                    external_result_id = action.external_target.external_object_id
                else:
                    content = executor.preview_execution(action, state)
                    safe_to_retry = (
                        self._preview_fingerprint(
                            action_record,
                            connection,
                            capability,
                            content.model_dump(mode="json", by_alias=True),
                        )
                        == execution.preview_fingerprint
                    )
        except ExecutionFailure as exc:
            raise PublicAPIError(exc.code, exc.safe_message, 409) from exc
        if applied:
            execution.execution_status = ExecutionStatus.SUCCEEDED.value
            execution.completed_at = now
            execution.failed_at = None
            execution.safe_failure_code = None
            execution.external_result_id = external_result_id
            execution.next_attempt_at = None
        elif safe_to_retry:
            execution.execution_status = ExecutionStatus.FAILED_RETRYABLE.value
            execution.safe_failure_code = "reconciled_not_applied"
            execution.next_attempt_at = now
            execution.max_attempts = max(execution.max_attempts, min(execution.attempt_count + 1, 20))
        else:
            execution.execution_status = ExecutionStatus.FAILED_PERMANENT.value
            execution.safe_failure_code = "reconciled_external_state_changed"
            execution.next_attempt_at = None
        execution.worker_id = None
        execution.lease_expires_at = None
        self._add_execution_audit(
            event_type="execution_reconciled",
            subject_type="execution",
            subject_id=execution.id,
            connection=connection,
            capability=capability,
            risk_class=action.risk_class,
            created_at=now,
        )
        await self._commit("The HubSpot execution could not be reconciled.")
        refreshed = await self.repository.execution(self.tenant.organisation_id, execution.id)
        assert refreshed is not None
        return self._execution_response(refreshed)

    def _require_execution_features(self) -> None:
        if not (
            self.settings.feature_integrations_enabled
            and self.settings.feature_action_execution_enabled
            and self.settings.feature_action_layer_enabled
            and (
                self.settings.feature_hubspot_crm_enabled
                or (self.settings.feature_mock_connectors_enabled and self.settings.environment != "production")
            )
        ):
            raise PublicAPIError("feature_unavailable", "This feature is not enabled for the private beta.", 404)

    def _credential_store(self) -> CredentialStore:
        if not self.settings.feature_hubspot_crm_enabled:
            return MockCredentialStore()
        if self.settings.connector_credential_master_key is None:
            raise RuntimeError("HubSpot credential storage is not configured.")
        return EncryptedDatabaseCredentialStore(
            self.session,
            self.settings.connector_credential_master_key.get_secret_value(),
        )

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
        opportunity = cast(
            Opportunity | None,
            await self.session.scalar(
                select(Opportunity).where(
                    Opportunity.organisation_id == self.tenant.organisation_id,
                    Opportunity.id == proposal.opportunity_id,
                )
            ),
        )
        if opportunity is None:
            raise PublicAPIError("action_target_stale", "The Action target is no longer available.", 409)
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
                or contact.email is None
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
            if len(contacts_by_id) != len(set(payload.participant_contact_ids)) or any(
                contact.email is None for contact in contacts_by_id.values()
            ):
                raise PublicAPIError("calendar_attendees_stale", "A selected calendar participant is unavailable.", 409)
            participant_contacts = tuple(
                ApprovedContactRecipient(
                    contact_id=contact_id,
                    display_name=f"{contacts_by_id[contact_id].first_name} {contacts_by_id[contact_id].last_name}",
                    email=cast(str, contacts_by_id[contact_id].email),
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
        if isinstance(payload, LogInteractionPayload):
            interaction = await self.session.scalar(
                select(Interaction).where(
                    Interaction.organisation_id == self.tenant.organisation_id,
                    Interaction.id == payload.interaction_id,
                    Interaction.opportunity_id == proposal.opportunity_id,
                )
            )
            if interaction is None:
                raise PublicAPIError("action_target_stale", "The approved interaction is unavailable.", 409)
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
            revenueos_currency=opportunity.currency,
        )

    async def _bind_external_target(
        self,
        action: ApprovedActionInput,
        connection: IntegrationConnection,
    ) -> ApprovedActionInput:
        if connection.connector_key != ConnectorKey.HUBSPOT.value:
            return action
        entity_type: str
        entity_id: UUID
        field_name: str | None = None
        proposed: object | None = None
        if isinstance(action.payload, OpportunityUpdatePayload):
            entity_type = "opportunity"
            entity_id = action.opportunity_id
            field_name = action.payload.field
            proposed = action.payload.proposed_value
        elif isinstance(action.payload, ContactUpdatePayload):
            if action.payload.operation != "update" or action.payload.contact_id is None:
                raise PublicAPIError(
                    "contact_mapping_required",
                    "Link an existing HubSpot contact before updating it.",
                    409,
                )
            entity_type = "contact"
            entity_id = action.payload.contact_id
            values: dict[str, object | None] = {
                "first_name": action.payload.first_name,
                "last_name": action.payload.last_name,
                "email": action.payload.email,
                "job_title": action.payload.job_title,
            }
            changes = [
                (name, value) for name, value in values.items() if action.payload.current_values.get(name) != value
            ]
            if len(changes) != 1:
                raise PublicAPIError(
                    "crm_change_not_atomic",
                    "The approved Contact update must change exactly one mapped field.",
                    409,
                )
            field_name, proposed = changes[0]
        elif isinstance(action.payload, LogInteractionPayload):
            entity_type = "opportunity"
            entity_id = action.opportunity_id
        else:
            return action
        mapping = await self.repository.entity_mapping(
            self.tenant.organisation_id,
            connection.id,
            entity_type,
            entity_id,
        )
        if mapping is None or mapping.sync_state != "active":
            raise PublicAPIError(
                "crm_mapping_missing",
                "Connect this RevenueOS record to a HubSpot record before reviewing the Action.",
                409,
            )
        property_name: str | None = None
        property_type: str | None = None
        authority: str | None = None
        proposed_value: str | None = None
        if field_name is not None:
            field_mapping = await self.repository.field_mapping(
                self.tenant.organisation_id,
                connection.id,
                entity_type,
                field_name,
            )
            if field_mapping is None:
                raise PublicAPIError(
                    "crm_field_mapping_missing",
                    "Configure this HubSpot field mapping before reviewing the Action.",
                    409,
                )
            property_name = field_mapping.external_property_name
            property_type = field_mapping.external_property_type
            authority = field_mapping.authority
            if field_name == "stage":
                stage = await self.repository.stage_mapping(
                    self.tenant.organisation_id,
                    connection.id,
                    str(proposed),
                )
                if stage is None:
                    raise PublicAPIError(
                        "crm_stage_mapping_missing",
                        "Configure this RevenueOS-to-HubSpot stage mapping before reviewing the Action.",
                        409,
                    )
                proposed_value = stage.external_stage_id
            elif isinstance(proposed, datetime):
                proposed_value = proposed.astimezone(UTC).isoformat()
            elif proposed is not None:
                proposed_value = str(proposed)
        return replace(
            action,
            external_target=ApprovedExternalTarget(
                mapping_id=mapping.id,
                external_object_type={"opportunity": "deals", "contact": "contacts"}[entity_type],
                external_object_id=mapping.external_object_id,
                external_property_name=property_name,
                external_property_type=property_type,
                field_authority=authority,
                proposed_external_value=proposed_value,
            ),
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
        connection: IntegrationConnection,
    ) -> object | None:
        if executor.definition.execution_mode == "live":
            try:
                return await executor.current_external_state(
                    action,
                    ExecutorConnectionContext(
                        organisation_id=self.tenant.organisation_id,
                        connection_id=connection.id,
                        credential_reference=connection.credential_reference,
                        execution_mode="live",
                    ),
                )
            except ExecutionFailure as exc:
                raise PublicAPIError(exc.code, exc.safe_message, 409) from exc
        try:
            object_key = executor.object_key(action, "preview")
        except PermanentExecutionFailure as exc:
            raise PublicAPIError(exc.code, exc.safe_message, 409) from exc
        mock_object = await self.repository.mock_object(
            self.tenant.organisation_id,
            connection.id,
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
            ConnectorCapability.CREATE_ACTIVITY: self.settings.private_beta_max_crm_executions_per_day,
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
                "The private-beta execution limit has been reached for this capability today.",
                429,
            )
        active = await self.repository.active_execution_count(self.tenant.organisation_id)
        if active >= self.settings.private_beta_max_concurrent_executions:
            raise PublicAPIError(
                "concurrent_execution_limit_reached",
                "Wait for another execution to finish before confirming this one.",
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
            "executionMode": CONNECTOR_DEFINITIONS[ConnectorKey(connection.connector_key)].execution_mode,
        }
        return hashlib.sha256(
            json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
        ).hexdigest()

    @staticmethod
    def _idempotency_key(
        action: ApprovedActionInput,
        connection_id: UUID,
        capability: ConnectorCapability,
        execution_mode: Literal["simulation", "live"],
    ) -> str:
        value = (
            f"execution-v1:{action.organisation_id}:{action.action_id}:{action.action_version}:"
            f"{connection_id}:{capability.value}:{execution_mode}"
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
            ConnectorCapability.UPDATE_OPPORTUNITY: "Update CRM",
            ConnectorCapability.UPDATE_CONTACT: "Update CRM",
            ConnectorCapability.CREATE_ACTIVITY: "Log interaction in CRM",
            ConnectorCapability.CREATE_TASK: "Create task",
        }[capability]
        live_summary = {
            ConnectorCapability.UPDATE_OPPORTUNITY: "Apply this reviewed field update to the linked HubSpot deal.",
            ConnectorCapability.UPDATE_CONTACT: "Apply this reviewed field update to the linked HubSpot contact.",
            ConnectorCapability.CREATE_ACTIVITY: (
                "Log this reviewed interaction summary against the linked HubSpot deal. No transcript is sent."
            ),
        }
        simulation_summary = {
            ConnectorCapability.SEND_EMAIL: "Simulate sending this approved email.",
            ConnectorCapability.CREATE_CALENDAR_EVENT: "Simulate creating this approved calendar event.",
            ConnectorCapability.UPDATE_OPPORTUNITY: "Simulate this approved opportunity update.",
            ConnectorCapability.UPDATE_CONTACT: "Simulate this approved contact update.",
            ConnectorCapability.CREATE_ACTIVITY: "Simulate logging this approved interaction summary.",
            ConnectorCapability.CREATE_TASK: "Simulate creating this approved task.",
        }
        summary = live_summary[capability] if definition.execution_mode == "live" else simulation_summary[capability]
        return ExecutionPreviewResponse(
            id=preview.id,
            action_proposal_id=preview.action_id,
            action_version=preview.action_version,
            connection_id=preview.connection_id,
            connector_key=definition.connector_key,
            connector_display_name=definition.display_name,
            capability=capability,
            risk_class=ActionRiskClass(preview.risk_class),
            execution_mode=definition.execution_mode,
            simulation_only=definition.simulation_only,
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
            ExecutionStatus.SUCCEEDED: "The reviewed HubSpot action completed and was verified.",
        }[status]
        if execution.execution_mode == "live":
            safe_message = {
                ExecutionStatus.QUEUED: "HubSpot update queued. No external change has occurred yet.",
                ExecutionStatus.EXECUTING: "RevenueOS is applying the reviewed HubSpot action.",
                ExecutionStatus.SUCCEEDED: "The reviewed HubSpot action completed and was verified.",
                ExecutionStatus.FAILED_RETRYABLE: "HubSpot did not apply the action; a bounded retry is safe.",
                ExecutionStatus.FAILED_PERMANENT: "The HubSpot action stopped safely and will not be retried.",
                ExecutionStatus.CANCELLED: "The HubSpot action was cancelled before execution.",
                ExecutionStatus.UNKNOWN_EXTERNAL_STATE: (
                    "The HubSpot outcome is unknown. RevenueOS will not retry without reconciliation."
                ),
                ExecutionStatus.SIMULATED_SUCCESS: "The simulation completed. No external action occurred.",
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
            execution_mode=cast(Literal["simulation", "live"], execution.execution_mode),
            simulation_only=definition.simulation_only,
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
            "execution_mode": CONNECTOR_DEFINITIONS[ConnectorKey(connection.connector_key)].execution_mode,
        }


async def membership_is_active(session: AsyncSession, tenant: TenantContext) -> bool:
    return (
        await session.scalar(
            select(OrganisationMembership.user_id)
            .join(User, User.id == OrganisationMembership.user_id)
            .where(
                OrganisationMembership.organisation_id == tenant.organisation_id,
                OrganisationMembership.user_id == tenant.user_id,
                OrganisationMembership.status == "active",
                User.status == "active",
            )
        )
        is not None
    )
