from __future__ import annotations

import base64
import hashlib
import json
import logging
import secrets
import uuid
from collections.abc import Callable, Mapping
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
    PersonalizedOutreachPayload,
    ScheduleInteractionPayload,
)
from revenueos.action_repositories import ActionRecord, ActionRepository
from revenueos.commercial_contracts import ModuleCode
from revenueos.commercial_services import CommercialService
from revenueos.config import Settings
from revenueos.credential_store import (
    CredentialStore,
    EncryptedDatabaseCredentialStore,
    MockCredentialStore,
)
from revenueos.crm_provider import CRMObjectType as CanonicalCRMObjectType
from revenueos.crm_provider import CRMProviderAdapter, CRMProviderError, rules_for
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
    CRMConnectionState,
    CRMEntityMapping,
    CRMFieldMapping,
    CRMStageMapping,
    CRMSyncJob,
    ExecutionPreview,
    IntegrationAuditEvent,
    IntegrationConnection,
    Interaction,
    OAuthConnectionState,
    Opportunity,
    Organisation,
    OrganisationMembership,
    ProviderOutboundOperation,
    User,
)
from revenueos.outreach_repositories import OutreachRepository
from revenueos.outreach_services import evaluate_contactability, validate_personalized_outreach_action
from revenueos.tenant import TenantContext

if TYPE_CHECKING:
    from revenueos.google_workspace import GoogleWorkspaceClient
    from revenueos.hubspot_connector import HubSpotClient
    from revenueos.microsoft_graph import MicrosoftGraphClient
    from revenueos.salesforce_connector import SalesforceClient

logger = logging.getLogger("revenueos.integrations")


def _commercial_module_for_connector(connector_key: str) -> ModuleCode:
    if connector_key in {
        ConnectorKey.HUBSPOT.value,
        ConnectorKey.SALESFORCE.value,
        ConnectorKey.MOCK_CRM.value,
    }:
        return "crm"
    if connector_key in {
        ConnectorKey.MOCK_EMAIL.value,
        ConnectorKey.MICROSOFT_365.value,
        ConnectorKey.GOOGLE_WORKSPACE.value,
    }:
        return "engage"
    return "core"


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
        self.salesforce_client: SalesforceClient | None = None
        self.microsoft_client: MicrosoftGraphClient | None = None
        self.google_client: GoogleWorkspaceClient | None = None
        live_executor: ActionExecutor | None = None
        live_executors: list[ActionExecutor] = []
        if settings.feature_hubspot_crm_enabled:
            from revenueos.hubspot_connector import HubSpotClient, HubSpotCRMExecutor

            self.hubspot_client = HubSpotClient(settings, self.credential_store)
            live_executor = HubSpotCRMExecutor(self.hubspot_client)
        if settings.feature_salesforce_crm_enabled:
            from revenueos.salesforce_connector import SalesforceClient, SalesforceCRMExecutor

            self.salesforce_client = SalesforceClient(settings, self.credential_store)
            live_executors.append(SalesforceCRMExecutor(self.salesforce_client))
        if settings.feature_microsoft_365_enabled:
            from revenueos.microsoft_graph import MicrosoftEmailExecutor, MicrosoftGraphClient

            self.microsoft_client = MicrosoftGraphClient(settings, self.credential_store)
            live_executors.append(MicrosoftEmailExecutor(session, self.microsoft_client))
        if settings.feature_google_workspace_enabled:
            from revenueos.google_workspace import GoogleEmailExecutor, GoogleWorkspaceClient

            self.google_client = GoogleWorkspaceClient(settings, self.credential_store)
            live_executors.append(GoogleEmailExecutor(session, self.google_client))
        self.executors = executors or ActionExecutorRegistry(
            live_executor=live_executor,
            live_executors=tuple(live_executors),
        )

    def catalog(self) -> IntegrationCatalogResponse:
        self._require_integrations()
        mock_available = self._mock_connectors_available()
        hubspot_available = self.settings.feature_hubspot_crm_enabled
        salesforce_available = self.settings.feature_salesforce_crm_enabled
        definitions = [
            definition
            for definition in CONNECTOR_DEFINITIONS.values()
            if (definition.simulation_only and mock_available)
            or (definition.connector_key == ConnectorKey.HUBSPOT and hubspot_available)
            or (definition.connector_key == ConnectorKey.SALESFORCE and salesforce_available)
            or definition.connector_key in {ConnectorKey.MICROSOFT_365, ConnectorKey.GOOGLE_WORKSPACE}
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
                    available=(
                        self.settings.feature_microsoft_365_enabled
                        if definition.connector_key == ConnectorKey.MICROSOFT_365
                        else (
                            self.settings.feature_google_workspace_enabled
                            if definition.connector_key == ConnectorKey.GOOGLE_WORKSPACE
                            else (salesforce_available if definition.connector_key == ConnectorKey.SALESFORCE else True)
                        )
                    ),
                    simulation_only=definition.simulation_only,
                )
                for definition in definitions
            ],
            execution_mode=(
                "mixed"
                if hubspot_available
                or salesforce_available
                or self.settings.feature_microsoft_365_enabled
                or self.settings.feature_google_workspace_enabled
                else "simulation"
            ),
            external_actions_enabled=(
                hubspot_available
                or salesforce_available
                or self.settings.feature_microsoft_365_enabled
                or self.settings.feature_google_workspace_enabled
            ),
        )

    async def list_connections(self) -> ConnectionListResponse:
        self._require_integrations()
        records = await self.repository.list_connections(self.tenant.organisation_id)
        visible = [
            item
            for item in records
            if (item.connector_key.startswith("mock_") and self._mock_connectors_available())
            or (item.connector_key == ConnectorKey.HUBSPOT.value and self.settings.feature_hubspot_crm_enabled)
            or (item.connector_key == ConnectorKey.SALESFORCE.value and self.settings.feature_salesforce_crm_enabled)
            or (
                item.connector_key == ConnectorKey.MICROSOFT_365.value
                and (self.tenant.can_manage() or item.created_by_user_id == self.tenant.user_id)
            )
            or (
                item.connector_key == ConnectorKey.GOOGLE_WORKSPACE.value
                and (self.tenant.can_manage() or item.created_by_user_id == self.tenant.user_id)
            )
        ]
        return ConnectionListResponse(items=[self._connection_response(item) for item in visible], total=len(visible))

    async def get_connection(self, connection_id: UUID) -> OrganisationConnectionResponse:
        self._require_integrations()
        connection = await self._require_connection(connection_id)
        self._require_connector_available(connection.connector_key)
        return self._connection_response(connection)

    async def create_connection(self, request: ConnectionCreateRequest) -> OrganisationConnectionResponse:
        self._require_admin()
        if request.connector_key in {
            ConnectorKey.HUBSPOT,
            ConnectorKey.SALESFORCE,
            ConnectorKey.MICROSOFT_365,
            ConnectorKey.GOOGLE_WORKSPACE,
        }:
            raise PublicAPIError(
                "oauth_required",
                "Start the provider authorisation flow to create this connection.",
                409,
            )
        await self._require_connector_entitlement(request.connector_key.value)
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
        self._require_integrations()
        connection = await self._require_connection(connection_id, for_update=True)
        mailbox_keys = {
            ConnectorKey.MICROSOFT_365.value,
            ConnectorKey.GOOGLE_WORKSPACE.value,
        }
        if connection.connector_key not in mailbox_keys:
            self._require_admin()
        elif connection.created_by_user_id != self.tenant.user_id and not self.tenant.can_manage():
            raise PublicAPIError("forbidden", "You cannot test another seller's mailbox.", 403)
        if connection.connector_key in mailbox_keys:
            await CommercialService(self.session, self.settings).require_module_write(
                self.tenant.organisation_id,
                "core",
            )
        else:
            await self._require_connector_entitlement(connection.connector_key)
        self._require_connector_available(connection.connector_key)
        self._require_active_connection(connection)
        checked_at = datetime.now(UTC)
        definition = CONNECTOR_DEFINITIONS[ConnectorKey(connection.connector_key)]
        try:
            await self.executors.get(ConnectorKey(connection.connector_key)).validate_connection(
                self._connection_context(connection)
            )
        except ExecutionFailure as exc:
            if connection.connector_key in {
                ConnectorKey.HUBSPOT.value,
                ConnectorKey.SALESFORCE.value,
                ConnectorKey.MICROSOFT_365.value,
                ConnectorKey.GOOGLE_WORKSPACE.value,
            }:
                connection.connection_status = ConnectionStatus.REAUTHORISATION_REQUIRED.value
                connection.metadata_version += 1
                self._add_audit(connection, "connection_reauthorisation_required", checked_at)
                await self._commit("The connection state could not be updated.")
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
                else (
                    f"{definition.display_name} mailbox and calendar authorisation were verified."
                    if connection.connector_key in mailbox_keys
                    else f"{definition.display_name} authorisation and account identity were verified."
                )
            ),
        )

    async def revoke_connection(self, connection_id: UUID) -> OrganisationConnectionResponse:
        self._require_integrations()
        connection = await self._require_connection(connection_id, for_update=True)
        mailbox_keys = {
            ConnectorKey.MICROSOFT_365.value,
            ConnectorKey.GOOGLE_WORKSPACE.value,
        }
        if connection.connector_key not in mailbox_keys:
            self._require_admin()
        elif connection.created_by_user_id != self.tenant.user_id and not self.tenant.can_manage():
            raise PublicAPIError("forbidden", "You cannot disconnect another seller's mailbox.", 403)
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
            if connection.connector_key == ConnectorKey.SALESFORCE.value and self.salesforce_client is not None:
                from revenueos.salesforce_connector import SalesforceAPIError

                try:
                    credential = await self.credential_store.get(
                        self.tenant.organisation_id,
                        connection.id,
                        connection.credential_reference,
                    )
                    await self.salesforce_client.revoke(credential)
                except (ValueError, SalesforceAPIError):
                    logger.warning(
                        "connection_provider_revocation_failed",
                        extra=self._connection_log_context(connection),
                    )
            if connection.connector_key == ConnectorKey.GOOGLE_WORKSPACE.value and self.google_client is not None:
                from revenueos.google_workspace import GoogleAPIError

                try:
                    credential = await self.credential_store.get(
                        self.tenant.organisation_id,
                        connection.id,
                        connection.credential_reference,
                    )
                    await self.google_client.revoke(credential)
                except (ValueError, GoogleAPIError):
                    # Google revocation is best effort; local deletion and queued-work cancellation always win.
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
        crm_state = await self.session.scalar(
            select(CRMConnectionState).where(
                CRMConnectionState.organisation_id == self.tenant.organisation_id,
                CRMConnectionState.connection_id == connection.id,
            )
        )
        if crm_state is not None:
            crm_state.connector_enabled = False
            crm_state.writeback_enabled = False
            crm_state.lifecycle = "disabled"
            crm_state.health_status = "unavailable"
            crm_jobs = (
                await self.session.scalars(
                    select(CRMSyncJob).where(
                        CRMSyncJob.organisation_id == self.tenant.organisation_id,
                        CRMSyncJob.connection_id == connection.id,
                        CRMSyncJob.status.in_(("queued", "running", "paused")),
                    )
                )
            ).all()
            for job in crm_jobs:
                job.status = "cancelled"
                job.worker_id = None
                job.lease_expires_at = None
                job.completed_at = now
                job.updated_at = now
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
        await self._require_crm_connector_write()
        client = self._require_hubspot()
        await self._require_primary_external_crm_available(ConnectorKey.HUBSPOT)
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

    async def _start_mailbox_oauth(
        self,
        *,
        connector_key: ConnectorKey,
        redirect_uri: str,
        state_ttl_seconds: int,
        provider_name: str,
        authorisation_url: Callable[[str, str, str], str],
    ) -> OAuthStartResponse:
        self._require_integrations()
        await CommercialService(self.session, self.settings).require_module_write(
            self.tenant.organisation_id,
            "core",
        )
        await self._require_primary_mailbox_available(connector_key)
        store = self._require_encrypted_credential_store()
        state_value = secrets.token_urlsafe(48)
        verifier = secrets.token_urlsafe(64)
        challenge = hashlib.sha256(verifier.encode()).digest()
        challenge_value = base64.urlsafe_b64encode(challenge).rstrip(b"=").decode("ascii")
        nonce_value = secrets.token_urlsafe(32)
        state_id = uuid.uuid4()
        pkce_nonce, encrypted_verifier = store.encrypt_oauth_state_secret(
            self.tenant.organisation_id,
            state_id,
            verifier,
        )
        now = datetime.now(UTC)
        expires_at = now + timedelta(seconds=state_ttl_seconds)
        self.repository.add(
            OAuthConnectionState(
                id=state_id,
                organisation_id=self.tenant.organisation_id,
                user_id=self.tenant.user_id,
                connector_key=connector_key.value,
                state_hash=hashlib.sha256(state_value.encode()).hexdigest(),
                redirect_uri=redirect_uri,
                expires_at=expires_at,
                consumed_at=None,
                pkce_verifier_encrypted=encrypted_verifier,
                pkce_nonce=pkce_nonce,
                oidc_nonce_hash=hashlib.sha256(nonce_value.encode()).hexdigest(),
                created_at=now,
            )
        )
        await self._commit(f"The {provider_name} authorisation flow could not be started.")
        return OAuthStartResponse(
            authorisation_url=authorisation_url(state_value, challenge_value, nonce_value),
            expires_at=expires_at,
        )

    async def _consume_mailbox_oauth_state(
        self,
        request: OAuthCallbackRequest,
        *,
        connector_key: ConnectorKey,
        redirect_uri: str,
        provider_name: str,
    ) -> tuple[OAuthConnectionState, datetime]:
        now = datetime.now(UTC)
        state = await self.repository.oauth_state_by_hash(
            self.tenant.organisation_id,
            hashlib.sha256(request.state.encode()).hexdigest(),
            for_update=True,
        )
        invalid_message = f"This {provider_name} authorisation request is invalid."
        if state is None or state.connector_key != connector_key.value or state.user_id != self.tenant.user_id:
            raise PublicAPIError("oauth_state_invalid", invalid_message, 400)
        if state.consumed_at is not None:
            raise PublicAPIError(
                "oauth_state_replayed",
                f"This {provider_name} authorisation request was already used.",
                409,
            )
        if self._as_utc(state.expires_at) <= now:
            raise PublicAPIError(
                "oauth_state_expired",
                f"This {provider_name} authorisation request has expired.",
                409,
            )
        if state.redirect_uri != redirect_uri:
            raise PublicAPIError("oauth_redirect_mismatch", invalid_message, 400)
        state.consumed_at = now
        return state, now

    async def start_microsoft_oauth(self) -> OAuthStartResponse:
        client = self._require_microsoft()
        assert self.settings.microsoft_oauth_redirect_uri is not None
        return await self._start_mailbox_oauth(
            connector_key=ConnectorKey.MICROSOFT_365,
            redirect_uri=self.settings.microsoft_oauth_redirect_uri,
            state_ttl_seconds=self.settings.microsoft_oauth_state_ttl_seconds,
            provider_name="Microsoft",
            authorisation_url=client.authorisation_url,
        )

    async def complete_microsoft_oauth(
        self,
        request: OAuthCallbackRequest,
    ) -> OrganisationConnectionResponse:
        self._require_integrations()
        await CommercialService(self.session, self.settings).require_module_write(
            self.tenant.organisation_id,
            "core",
        )
        client = self._require_microsoft()
        store = self._require_encrypted_credential_store()
        assert self.settings.microsoft_oauth_redirect_uri is not None
        state, now = await self._consume_mailbox_oauth_state(
            request,
            connector_key=ConnectorKey.MICROSOFT_365,
            redirect_uri=self.settings.microsoft_oauth_redirect_uri,
            provider_name="Microsoft",
        )
        if request.provider_error is not None:
            await self._commit("The Microsoft authorisation result could not be recorded.")
            if request.provider_error == "admin_consent_required":
                raise PublicAPIError(
                    "microsoft_admin_approval_required",
                    "Your Microsoft administrator needs to approve Oryntela before this connection can be completed.",
                    409,
                )
            raise PublicAPIError(
                "oauth_authorisation_declined",
                "Microsoft authorisation was not completed. No connection was created.",
                400,
            )
        assert request.code is not None
        if state.oidc_nonce_hash is None:
            raise PublicAPIError("oauth_state_invalid", "This Microsoft authorisation request is invalid.", 400)
        try:
            verifier = store.decrypt_oauth_state_secret(
                self.tenant.organisation_id,
                state.id,
                state.pkce_nonce,
                state.pkce_verifier_encrypted,
            )
            result = await client.exchange_code(request.code, verifier, state.oidc_nonce_hash)
        except ValueError as exc:
            await self._commit("The Microsoft authorisation state could not be recorded.")
            raise PublicAPIError(
                "oauth_state_invalid", "This Microsoft authorisation request is invalid.", 400
            ) from exc
        except Exception as exc:
            from revenueos.microsoft_graph import MicrosoftAPIError

            await self._commit("The Microsoft authorisation result could not be recorded.")
            if isinstance(exc, MicrosoftAPIError):
                messages = {
                    "microsoft_work_account_required": "Connect a Microsoft work or school account.",
                    "provider_scope_incomplete": "Microsoft did not grant every permission required for email and calendar.",
                }
                raise PublicAPIError(
                    exc.code,
                    messages.get(
                        exc.code, "Microsoft authorisation could not be verified. Start the connection again."
                    ),
                    409,
                ) from exc
            raise
        await self._require_primary_mailbox_available(ConnectorKey.MICROSOFT_365)
        connection = await self.repository.connection_by_key_for_user(
            self.tenant.organisation_id,
            ConnectorKey.MICROSOFT_365.value,
            self.tenant.user_id,
            for_update=True,
        )
        if (
            connection is not None
            and connection.connection_status != ConnectionStatus.REVOKED.value
            and (
                connection.external_account_id != result.profile.id or connection.external_tenant_id != result.tenant_id
            )
        ):
            await self._commit("The rejected Microsoft authorisation could not be recorded.")
            raise PublicAPIError(
                "connection_account_changed",
                "Disconnect the existing Microsoft account before connecting a different account.",
                409,
            )
        event_type = "connection_created"
        if connection is None:
            connection = IntegrationConnection(
                id=uuid.uuid4(),
                organisation_id=self.tenant.organisation_id,
                connector_key=ConnectorKey.MICROSOFT_365.value,
                connection_status=ConnectionStatus.ACTIVE.value,
                created_by_user_id=self.tenant.user_id,
                connected_at=now,
                last_verified_at=now,
                revoked_at=None,
                credential_reference=None,
                capability_state_json=[
                    item.value for item in CONNECTOR_DEFINITIONS[ConnectorKey.MICROSOFT_365].capabilities
                ],
                external_account_id=result.profile.id,
                external_account_name=result.profile.display_name,
                external_account_email=result.profile.email,
                external_tenant_id=result.tenant_id,
                granted_scopes_json=list(result.credential.scopes),
                metadata_version=1,
                created_at=now,
                updated_at=now,
            )
            self.repository.add(connection)
            await self.repository.flush()
        else:
            event_type = "connection_tested"
            connection.connection_status = ConnectionStatus.ACTIVE.value
            connection.connected_at = now
            connection.last_verified_at = now
            connection.revoked_at = None
            connection.capability_state_json = [
                item.value for item in CONNECTOR_DEFINITIONS[ConnectorKey.MICROSOFT_365].capabilities
            ]
            connection.external_account_id = result.profile.id
            connection.external_account_name = result.profile.display_name
            connection.external_account_email = result.profile.email
            connection.external_tenant_id = result.tenant_id
            connection.granted_scopes_json = list(result.credential.scopes)
            connection.metadata_version += 1
        connection.credential_reference = await store.put(
            self.tenant.organisation_id,
            connection.id,
            result.credential,
        )
        state.pkce_verifier_encrypted = None
        state.pkce_nonce = None
        self._add_audit(connection, event_type, now)
        await self._commit("The Microsoft connection could not be saved.")
        return self._connection_response(await self._require_connection(connection.id))

    async def start_google_oauth(self) -> OAuthStartResponse:
        client = self._require_google()
        assert self.settings.google_oauth_redirect_uri is not None
        return await self._start_mailbox_oauth(
            connector_key=ConnectorKey.GOOGLE_WORKSPACE,
            redirect_uri=self.settings.google_oauth_redirect_uri,
            state_ttl_seconds=self.settings.google_oauth_state_ttl_seconds,
            provider_name="Google",
            authorisation_url=client.authorisation_url,
        )

    async def complete_google_oauth(
        self,
        request: OAuthCallbackRequest,
    ) -> OrganisationConnectionResponse:
        self._require_integrations()
        await CommercialService(self.session, self.settings).require_module_write(
            self.tenant.organisation_id,
            "core",
        )
        client = self._require_google()
        store = self._require_encrypted_credential_store()
        assert self.settings.google_oauth_redirect_uri is not None
        state, now = await self._consume_mailbox_oauth_state(
            request,
            connector_key=ConnectorKey.GOOGLE_WORKSPACE,
            redirect_uri=self.settings.google_oauth_redirect_uri,
            provider_name="Google",
        )
        if request.provider_error is not None:
            await self._commit("The Google authorisation result could not be recorded.")
            if request.provider_error in {"admin_policy_enforced", "org_internal"}:
                raise PublicAPIError(
                    "google_admin_approval_required",
                    "Your Google Workspace administrator must allow Oryntela before this connection can be completed.",
                    409,
                )
            raise PublicAPIError(
                "oauth_authorisation_declined",
                "Google authorisation was not completed. No connection was created.",
                400,
            )
        assert request.code is not None
        if state.oidc_nonce_hash is None:
            raise PublicAPIError("oauth_state_invalid", "This Google authorisation request is invalid.", 400)
        try:
            verifier = store.decrypt_oauth_state_secret(
                self.tenant.organisation_id,
                state.id,
                state.pkce_nonce,
                state.pkce_verifier_encrypted,
            )
            result = await client.exchange_code(request.code, verifier, state.oidc_nonce_hash)
        except ValueError as exc:
            await self._commit("The Google authorisation state could not be recorded.")
            raise PublicAPIError("oauth_state_invalid", "This Google authorisation request is invalid.", 400) from exc
        except Exception as exc:
            from revenueos.google_workspace import GoogleAPIError

            await self._commit("The Google authorisation result could not be recorded.")
            if isinstance(exc, GoogleAPIError):
                messages = {
                    "google_workspace_account_required": "Connect a managed Google Workspace account.",
                    "provider_scope_incomplete": "Google did not grant every permission required for email and calendar.",
                    "provider_refresh_token_missing": (
                        "Google did not return offline access. Remove the existing Oryntela grant and connect again."
                    ),
                }
                raise PublicAPIError(
                    exc.code,
                    messages.get(exc.code, "Google authorisation could not be verified. Start the connection again."),
                    409,
                ) from exc
            raise
        await self._require_primary_mailbox_available(ConnectorKey.GOOGLE_WORKSPACE)
        connection = await self.repository.connection_by_key_for_user(
            self.tenant.organisation_id,
            ConnectorKey.GOOGLE_WORKSPACE.value,
            self.tenant.user_id,
            for_update=True,
        )
        if (
            connection is not None
            and connection.connection_status != ConnectionStatus.REVOKED.value
            and (
                connection.external_account_id != result.profile.sub
                or connection.external_tenant_id != result.profile.hd
            )
        ):
            try:
                await client.revoke(result.credential)
            except Exception:
                logger.warning(
                    "connection_rejected_credential_revocation_failed",
                    extra=self._connection_log_context(connection),
                )
            await self._commit("The rejected Google authorisation could not be recorded.")
            raise PublicAPIError(
                "connection_account_changed",
                "Disconnect the existing Google account before connecting a different account.",
                409,
            )
        event_type = "connection_created"
        if connection is None:
            connection = IntegrationConnection(
                id=uuid.uuid4(),
                organisation_id=self.tenant.organisation_id,
                connector_key=ConnectorKey.GOOGLE_WORKSPACE.value,
                connection_status=ConnectionStatus.ACTIVE.value,
                created_by_user_id=self.tenant.user_id,
                connected_at=now,
                last_verified_at=now,
                revoked_at=None,
                credential_reference=None,
                capability_state_json=[
                    item.value for item in CONNECTOR_DEFINITIONS[ConnectorKey.GOOGLE_WORKSPACE].capabilities
                ],
                external_account_id=result.profile.sub,
                external_account_name=result.profile.name,
                external_account_email=result.profile.email,
                external_tenant_id=result.profile.hd,
                granted_scopes_json=list(result.credential.scopes),
                metadata_version=1,
                created_at=now,
                updated_at=now,
            )
            self.repository.add(connection)
            await self.repository.flush()
        else:
            event_type = "connection_tested"
            connection.connection_status = ConnectionStatus.ACTIVE.value
            connection.connected_at = now
            connection.last_verified_at = now
            connection.revoked_at = None
            connection.capability_state_json = [
                item.value for item in CONNECTOR_DEFINITIONS[ConnectorKey.GOOGLE_WORKSPACE].capabilities
            ]
            connection.external_account_id = result.profile.sub
            connection.external_account_name = result.profile.name
            connection.external_account_email = result.profile.email
            connection.external_tenant_id = result.profile.hd
            connection.granted_scopes_json = list(result.credential.scopes)
            connection.metadata_version += 1
        connection.credential_reference = await store.put(
            self.tenant.organisation_id,
            connection.id,
            result.credential,
        )
        state.pkce_verifier_encrypted = None
        state.pkce_nonce = None
        self._add_audit(connection, event_type, now)
        await self._commit("The Google Workspace connection could not be saved.")
        return self._connection_response(await self._require_connection(connection.id))

    async def complete_hubspot_oauth(
        self,
        request: OAuthCallbackRequest,
    ) -> OrganisationConnectionResponse:
        self._require_admin()
        await self._require_crm_connector_write()
        client = self._require_hubspot()
        now = datetime.now(UTC)
        state = await self.repository.oauth_state_by_hash(
            self.tenant.organisation_id,
            hashlib.sha256(request.state.encode()).hexdigest(),
            for_update=True,
        )
        if state is None or state.connector_key != ConnectorKey.HUBSPOT.value:
            raise PublicAPIError("oauth_state_invalid", "This HubSpot authorisation request is invalid.", 400)
        if state.user_id != self.tenant.user_id:
            raise PublicAPIError("oauth_state_invalid", "This HubSpot authorisation request is invalid.", 400)
        if state.consumed_at is not None:
            raise PublicAPIError("oauth_state_replayed", "This HubSpot authorisation request was already used.", 409)
        if self._as_utc(state.expires_at) <= now:
            raise PublicAPIError("oauth_state_expired", "This HubSpot authorisation request has expired.", 409)
        if state.redirect_uri != self.settings.hubspot_oauth_redirect_uri:
            raise PublicAPIError("oauth_redirect_mismatch", "This HubSpot authorisation request is invalid.", 400)
        oauth_state_id = state.id
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
        await self._require_primary_external_crm_available(ConnectorKey.HUBSPOT)
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
            try:
                await self.repository.flush()
            except IntegrityError as exc:
                await self._preserve_consumed_oauth_state(
                    oauth_state_id,
                    ConnectorKey.HUBSPOT,
                    now,
                )
                try:
                    await client.revoke(credential)
                except HubSpotAPIError:
                    logger.warning("connection_rejected_credential_revocation_failed")
                raise PublicAPIError(
                    "provider_tenant_already_connected",
                    "This HubSpot account is already connected to another Oryntela organisation.",
                    409,
                ) from exc
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
            try:
                await self.repository.flush()
            except IntegrityError as exc:
                await self._preserve_consumed_oauth_state(
                    oauth_state_id,
                    ConnectorKey.HUBSPOT,
                    now,
                )
                try:
                    await client.revoke(credential)
                except HubSpotAPIError:
                    logger.warning("connection_rejected_credential_revocation_failed")
                raise PublicAPIError(
                    "provider_tenant_already_connected",
                    "This HubSpot account is already connected to another Oryntela organisation.",
                    409,
                ) from exc
        connection.credential_reference = await self.credential_store.put(
            self.tenant.organisation_id,
            connection.id,
            credential,
        )
        crm_state = await self._ensure_crm_connection_state(connection, now)
        await self._seed_default_crm_field_mappings(connection, now)
        await self._queue_initial_crm_sync(connection, crm_state, now)
        self._add_audit(connection, event_type, now)
        await self._commit("The HubSpot connection could not be saved.")
        logger.info("connection_created", extra=self._connection_log_context(connection))
        return self._connection_response(await self._require_connection(connection.id))

    async def start_salesforce_oauth(self) -> OAuthStartResponse:
        self._require_admin()
        await self._require_crm_connector_write()
        client = self._require_salesforce()
        await self._require_primary_external_crm_available(ConnectorKey.SALESFORCE)
        store = self._require_encrypted_credential_store()
        state_value = secrets.token_urlsafe(48)
        verifier = secrets.token_urlsafe(64)
        challenge = hashlib.sha256(verifier.encode()).digest()
        challenge_value = base64.urlsafe_b64encode(challenge).rstrip(b"=").decode("ascii")
        state_id = uuid.uuid4()
        pkce_nonce, encrypted_verifier = store.encrypt_oauth_state_secret(
            self.tenant.organisation_id,
            state_id,
            verifier,
        )
        now = datetime.now(UTC)
        expires_at = now + timedelta(seconds=self.settings.salesforce_oauth_state_ttl_seconds)
        assert self.settings.salesforce_oauth_redirect_uri is not None
        self.repository.add(
            OAuthConnectionState(
                id=state_id,
                organisation_id=self.tenant.organisation_id,
                user_id=self.tenant.user_id,
                connector_key=ConnectorKey.SALESFORCE.value,
                state_hash=hashlib.sha256(state_value.encode()).hexdigest(),
                redirect_uri=self.settings.salesforce_oauth_redirect_uri,
                expires_at=expires_at,
                consumed_at=None,
                pkce_verifier_encrypted=encrypted_verifier,
                pkce_nonce=pkce_nonce,
                oidc_nonce_hash=None,
                created_at=now,
            )
        )
        await self._commit("The Salesforce authorisation flow could not be started.")
        return OAuthStartResponse(
            authorisation_url=client.authorisation_url(state_value, challenge_value),
            expires_at=expires_at,
        )

    async def complete_salesforce_oauth(
        self,
        request: OAuthCallbackRequest,
    ) -> OrganisationConnectionResponse:
        self._require_admin()
        await self._require_crm_connector_write()
        client = self._require_salesforce()
        store = self._require_encrypted_credential_store()
        assert self.settings.salesforce_oauth_redirect_uri is not None
        state, now = await self._consume_mailbox_oauth_state(
            request,
            connector_key=ConnectorKey.SALESFORCE,
            redirect_uri=self.settings.salesforce_oauth_redirect_uri,
            provider_name="Salesforce",
        )
        oauth_state_id = state.id
        if request.provider_error is not None:
            await self._commit("The Salesforce authorisation result could not be recorded.")
            raise PublicAPIError(
                "oauth_authorisation_declined",
                "Salesforce authorisation was not completed. No connection was created.",
                400,
            )
        try:
            verifier = store.decrypt_oauth_state_secret(
                self.tenant.organisation_id,
                state.id,
                state.pkce_nonce,
                state.pkce_verifier_encrypted,
            )
        except ValueError as exc:
            await self._commit("The Salesforce authorisation state could not be recorded.")
            raise PublicAPIError(
                "oauth_state_invalid",
                "This Salesforce authorisation request is invalid.",
                400,
            ) from exc
        assert request.code is not None
        from revenueos.salesforce_connector import SalesforceAPIError

        try:
            result = await client.exchange_code(request.code, verifier)
        except SalesforceAPIError as exc:
            await self._commit("The Salesforce authorisation result could not be recorded.")
            messages = {
                "missing_required_scope": "Salesforce did not grant the required API and offline permissions.",
                "provider_signature_invalid": "Salesforce returned an unverifiable authorisation response.",
                "provider_instance_url_invalid": "Salesforce returned an invalid organisation API address.",
            }
            raise PublicAPIError(
                exc.code,
                messages.get(exc.code, "Salesforce authorisation could not be verified. Start the connection again."),
                409,
            ) from exc
        await self._require_primary_external_crm_available(ConnectorKey.SALESFORCE)
        connection = await self.repository.connection_by_key(
            self.tenant.organisation_id,
            ConnectorKey.SALESFORCE.value,
            for_update=True,
        )
        if (
            connection is not None
            and connection.external_tenant_id is not None
            and connection.external_tenant_id != result.identity.organization_id
        ):
            try:
                await client.revoke(result.credential)
            except SalesforceAPIError:
                logger.warning(
                    "connection_rejected_credential_revocation_failed",
                    extra=self._connection_log_context(connection),
                )
            await self._commit("The rejected Salesforce authorisation could not be recorded.")
            raise PublicAPIError(
                "connection_account_changed",
                "Reconnect the same Salesforce organisation. Changing organisations requires a reviewed reset.",
                409,
            )
        if connection is None:
            connection = IntegrationConnection(
                id=uuid.uuid4(),
                organisation_id=self.tenant.organisation_id,
                connector_key=ConnectorKey.SALESFORCE.value,
                connection_status=ConnectionStatus.ACTIVE.value,
                created_by_user_id=self.tenant.user_id,
                connected_at=now,
                last_verified_at=now,
                revoked_at=None,
                credential_reference=None,
                capability_state_json=[
                    item.value for item in CONNECTOR_DEFINITIONS[ConnectorKey.SALESFORCE].capabilities
                ],
                external_account_id=result.identity.user_id,
                external_account_name=result.identity.name,
                external_account_email=result.identity.preferred_username,
                external_tenant_id=result.identity.organization_id,
                granted_scopes_json=list(result.credential.scopes),
                metadata_version=1,
                created_at=now,
                updated_at=now,
            )
            self.repository.add(connection)
            try:
                await self.repository.flush()
            except IntegrityError as exc:
                await self._preserve_consumed_oauth_state(
                    oauth_state_id,
                    ConnectorKey.SALESFORCE,
                    now,
                )
                try:
                    await client.revoke(result.credential)
                except SalesforceAPIError:
                    logger.warning("connection_rejected_credential_revocation_failed")
                raise PublicAPIError(
                    "provider_tenant_already_connected",
                    "This Salesforce organisation is already connected to another Oryntela organisation.",
                    409,
                ) from exc
        else:
            connection.connection_status = ConnectionStatus.ACTIVE.value
            connection.created_by_user_id = self.tenant.user_id
            connection.connected_at = now
            connection.last_verified_at = now
            connection.revoked_at = None
            connection.capability_state_json = [
                item.value for item in CONNECTOR_DEFINITIONS[ConnectorKey.SALESFORCE].capabilities
            ]
            connection.external_account_id = result.identity.user_id
            connection.external_account_name = result.identity.name
            connection.external_account_email = result.identity.preferred_username
            connection.external_tenant_id = result.identity.organization_id
            connection.granted_scopes_json = list(result.credential.scopes)
            connection.metadata_version += 1
            try:
                await self.repository.flush()
            except IntegrityError as exc:
                await self._preserve_consumed_oauth_state(
                    oauth_state_id,
                    ConnectorKey.SALESFORCE,
                    now,
                )
                try:
                    await client.revoke(result.credential)
                except SalesforceAPIError:
                    logger.warning("connection_rejected_credential_revocation_failed")
                raise PublicAPIError(
                    "provider_tenant_already_connected",
                    "This Salesforce organisation is already connected to another Oryntela organisation.",
                    409,
                ) from exc
        connection.credential_reference = await store.put(
            self.tenant.organisation_id,
            connection.id,
            result.credential,
        )
        state.pkce_verifier_encrypted = None
        state.pkce_nonce = None
        crm_state = await self._ensure_crm_connection_state(connection, now)
        await self._seed_default_crm_field_mappings(connection, now)
        await self._queue_initial_crm_sync(connection, crm_state, now)
        self._add_audit(connection, "connection_created", now)
        await self._commit("The Salesforce connection could not be saved.")
        logger.info("connection_created", extra=self._connection_log_context(connection))
        return self._connection_response(await self._require_connection(connection.id))

    async def search_crm_records(
        self,
        connection_id: UUID,
        entity_type: str,
        query: str,
    ) -> CRMSearchResponse:
        await self._require_crm_connector_write()
        connection = await self._require_crm_connection(connection_id)
        query = query.strip()
        if len(query) < 2 or len(query) > 120:
            raise PublicAPIError("search_query_invalid", "Enter between 2 and 120 characters.", 422)
        canonical_type = self._canonical_crm_object_type(entity_type)
        if connection.connector_key == ConnectorKey.HUBSPOT.value:
            object_type, properties = self._crm_search_shape(entity_type)
            try:
                hubspot_records = await self._require_hubspot().search_records(
                    self._connection_context(connection),
                    object_type,
                    query,
                    properties,
                )
            except Exception as exc:
                self._raise_crm_public_error(connection.connector_key, exc)
            items = [
                CRMSearchResult(
                    external_object_type=cast(
                        Literal["company", "contact", "deal"],
                        object_type[:-1] if object_type != "companies" else "company",
                    ),
                    external_object_id=record.id,
                    display_name=self._crm_display_name(entity_type, record.properties),
                    secondary_label=self._crm_secondary_label(entity_type, record.properties),
                    updated_at=record.updated_at,
                )
                for record in hubspot_records
            ]
        else:
            try:
                salesforce_records = await self._require_salesforce().search_records(
                    self._connection_context(connection),
                    canonical_type,
                    query,
                )
            except Exception as exc:
                self._raise_crm_public_error(connection.connector_key, exc)
            external_type = canonical_type
            items = [
                CRMSearchResult(
                    external_object_type=external_type,
                    external_object_id=record.external_object_id,
                    display_name=self._normalised_crm_display_name(canonical_type, record.fields),
                    secondary_label=self._normalised_crm_secondary_label(canonical_type, record.fields),
                    updated_at=record.modified_at,
                )
                for record in salesforce_records
            ]
        return CRMSearchResponse(items=items, total=len(items))

    async def get_entity_mapping(
        self,
        connection_id: UUID,
        entity_type: str,
        entity_id: UUID,
    ) -> CRMEntityMappingResponse | None:
        connection = await self._require_crm_connection(connection_id)
        mapping = await self.repository.entity_mapping(
            self.tenant.organisation_id,
            connection.id,
            entity_type,
            entity_id,
        )
        return None if mapping is None else self._entity_mapping_response(mapping, connection.connector_key)

    async def link_entity(
        self,
        entity_type: str,
        entity_id: UUID,
        request: CRMEntityLinkRequest,
    ) -> CRMEntityMappingResponse:
        await self._require_crm_connector_write()
        connection = await self._require_crm_connection(request.connection_id)
        expected_object = self._external_object_type(connection.connector_key, entity_type)
        if expected_object is None or request.external_object_type != expected_object:
            raise PublicAPIError("crm_mapping_invalid", "Select the matching provider object type.", 422)
        await self._require_local_entity(entity_type, entity_id)
        try:
            record = await self._crm_adapter(connection).get_record(
                self._connection_context(connection),
                self._canonical_crm_object_type(entity_type),
                request.external_object_id,
            )
        except Exception as exc:
            self._raise_crm_public_error(connection.connector_key, exc)
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
                external_updated_at=record.modified_at,
                last_synced_at=None,
                sync_state="active",
                created_by_user_id=self.tenant.user_id,
                external_version=record.external_version,
                authority_version=1,
                archived_at=None,
                created_at=now,
                updated_at=now,
            )
            self.repository.add(mapping)
        else:
            mapping.external_object_type = request.external_object_type
            mapping.external_object_id = request.external_object_id
            mapping.external_updated_at = record.modified_at
            mapping.external_version = record.external_version
            mapping.sync_state = "active"
            mapping.archived_at = None
        self._add_audit(connection, event_type, now)
        await self._commit("The CRM record link could not be saved.")
        return self._entity_mapping_response(mapping, connection.connector_key)

    async def unlink_entity(self, connection_id: UUID, entity_type: str, entity_id: UUID) -> None:
        await self._require_crm_connector_write()
        connection = await self._require_crm_connection(connection_id)
        mapping = await self.repository.entity_mapping(
            self.tenant.organisation_id,
            connection.id,
            entity_type,
            entity_id,
            for_update=True,
        )
        if mapping is None:
            return
        now = datetime.now(UTC)
        mapping.sync_state = "external_missing"
        mapping.archived_at = now
        self._add_audit(connection, "mapping_removed", now)
        await self._commit("The CRM record link could not be removed.")

    async def field_configuration(
        self,
        connection_id: UUID,
        entity_type: str,
    ) -> CRMFieldConfigurationResponse:
        self._require_admin()
        await self._require_crm_connector_write()
        connection = await self._require_crm_connection(connection_id)
        canonical_type = self._canonical_crm_object_type(entity_type)
        scalar_types = {"string", "number", "date", "datetime", "enumeration"}
        governed = [
            rule for rule in rules_for(connection.connector_key, canonical_type) if rule.value_type in scalar_types
        ]
        if not governed:
            raise PublicAPIError("crm_entity_type_invalid", "This CRM entity type is unsupported.", 422)
        if connection.connector_key == ConnectorKey.HUBSPOT.value:
            object_type = {"company": "companies", "contact": "contacts", "opportunity": "deals"}[entity_type]
            try:
                properties = await self._require_hubspot().properties(self._connection_context(connection), object_type)
            except Exception as exc:
                self._raise_crm_public_error(connection.connector_key, exc)
            allowed_names = {rule.provider_field for rule in governed}
            definitions = [
                CRMPropertyDefinition(
                    entity_type=cast(Literal["company", "opportunity", "contact"], entity_type),
                    external_property_name=item.name,
                    label=item.label,
                    property_type=cast(Literal["string", "number", "date", "datetime", "enumeration"], item.type),
                    options=[
                        {"label": option.label, "value": option.value} for option in item.options if not option.hidden
                    ],
                    read_only=item.modification_metadata.read_only_value,
                )
                for item in properties
                if item.name in allowed_names and item.type in scalar_types
            ]
        else:
            definitions = [
                CRMPropertyDefinition(
                    entity_type=cast(Literal["company", "opportunity", "contact"], entity_type),
                    external_property_name=rule.provider_field,
                    label=rule.canonical_field.replace("_", " ").title(),
                    property_type=cast(Literal["string", "number", "date", "datetime", "enumeration"], rule.value_type),
                    options=[],
                    read_only=False,
                )
                for rule in governed
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
            raise PublicAPIError("crm_property_invalid", "Select a governed, writable CRM field.", 422)
        self._validate_field_compatibility(request.revenueos_field, selected.property_type)
        connection = await self._require_crm_connection(connection_id)
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
                mapping_version=1,
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
            mapping.mapping_version += 1
        state = await self._require_crm_state(connection.id, for_update=True)
        state.mapping_version += 1
        state.lifecycle = "mapping_required"
        state.writeback_enabled = False
        connection.metadata_version += 1
        self._add_audit(connection, "field_mapping_changed", now)
        await self._commit("The CRM field mapping could not be saved.")
        return self._field_mapping_response(mapping)

    async def stage_configuration(self, connection_id: UUID) -> CRMStageConfigurationResponse:
        self._require_admin()
        await self._require_crm_connector_write()
        connection = await self._require_crm_connection(connection_id)
        try:
            stages = await self._crm_adapter(connection).stages(self._connection_context(connection))
        except Exception as exc:
            self._raise_crm_public_error(connection.connector_key, exc)
        mappings = await self.repository.list_stage_mappings(self.tenant.organisation_id, connection.id)
        return CRMStageConfigurationResponse(
            available_stages=[
                CRMStageDefinition(
                    pipeline_id=stage.pipeline_id,
                    pipeline_label=stage.pipeline_name,
                    stage_id=stage.stage_id,
                    stage_label=stage.stage_name,
                )
                for stage in stages
                if stage.active
            ],
            mappings=[
                CRMStageMappingResponse(
                    revenueos_stage=item.revenueos_stage,
                    external_pipeline_id=item.external_pipeline_id,
                    external_stage_id=item.external_stage_id,
                    mapping_version=item.mapping_version,
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
            raise PublicAPIError("crm_stage_invalid", "Select a current provider opportunity stage.", 422)
        connection = await self._require_crm_connection(connection_id)
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
                mapping_version=1,
                created_at=now,
                updated_at=now,
            )
            self.repository.add(mapping)
        else:
            mapping.external_pipeline_id = request.external_pipeline_id
            mapping.external_stage_id = request.external_stage_id
            mapping.configured_by_user_id = self.tenant.user_id
            mapping.mapping_version += 1
        state = await self._require_crm_state(connection.id, for_update=True)
        state.mapping_version += 1
        state.lifecycle = "mapping_required"
        state.writeback_enabled = False
        connection.metadata_version += 1
        self._add_audit(connection, "stage_mapping_changed", now)
        await self._commit("The CRM stage mapping could not be saved.")
        return CRMStageMappingResponse(
            revenueos_stage=mapping.revenueos_stage,
            external_pipeline_id=mapping.external_pipeline_id,
            external_stage_id=mapping.external_stage_id,
            mapping_version=mapping.mapping_version,
        )

    def _require_integrations(self) -> None:
        if not self.settings.feature_integrations_enabled:
            raise PublicAPIError("feature_unavailable", "This feature is not enabled for the private beta.", 404)

    async def _require_crm_connector_write(self) -> None:
        await CommercialService(self.session, self.settings).require_module_write(self.tenant.organisation_id, "crm")

    async def _require_connector_entitlement(self, connector_key: str) -> None:
        await CommercialService(self.session, self.settings).require_module_write(
            self.tenant.organisation_id,
            _commercial_module_for_connector(connector_key),
        )

    def _credential_store(self) -> CredentialStore:
        if not (
            self.settings.feature_hubspot_crm_enabled
            or self.settings.feature_salesforce_crm_enabled
            or self.settings.feature_microsoft_365_enabled
            or self.settings.feature_google_workspace_enabled
        ):
            return MockCredentialStore()
        if self.settings.connector_credential_master_key is None:
            raise RuntimeError("Connector credential storage is not configured.")
        return EncryptedDatabaseCredentialStore(
            self.session,
            self.settings.connector_credential_master_key.get_secret_value(),
        )

    def _require_hubspot(self) -> HubSpotClient:
        self._require_integrations()
        if not self.settings.feature_hubspot_crm_enabled or self.hubspot_client is None:
            raise PublicAPIError("feature_unavailable", "HubSpot CRM sync is not enabled.", 404)
        return self.hubspot_client

    def _require_salesforce(self) -> SalesforceClient:
        self._require_integrations()
        if not self.settings.feature_salesforce_crm_enabled or self.salesforce_client is None:
            raise PublicAPIError("feature_unavailable", "Salesforce CRM sync is not enabled.", 404)
        return self.salesforce_client

    def _require_microsoft(self) -> MicrosoftGraphClient:
        self._require_integrations()
        if not self.settings.feature_microsoft_365_enabled or self.microsoft_client is None:
            raise PublicAPIError(
                "microsoft_setup_required",
                "Microsoft 365 is not configured yet.",
                409,
            )
        return self.microsoft_client

    def _require_google(self) -> GoogleWorkspaceClient:
        self._require_integrations()
        if not self.settings.feature_google_workspace_enabled or self.google_client is None:
            raise PublicAPIError(
                "google_setup_required",
                "Google Workspace is not configured yet.",
                409,
            )
        return self.google_client

    def _require_encrypted_credential_store(self) -> EncryptedDatabaseCredentialStore:
        if not isinstance(self.credential_store, EncryptedDatabaseCredentialStore):
            raise PublicAPIError(
                "provider_setup_required",
                "Encrypted provider credential storage is not configured.",
                409,
            )
        return self.credential_store

    async def _require_hubspot_connection(self, connection_id: UUID) -> IntegrationConnection:
        self._require_hubspot()
        connection = await self._require_connection(connection_id)
        if connection.connector_key != ConnectorKey.HUBSPOT.value:
            raise PublicAPIError("connection_not_found", "The requested HubSpot connection was not found.", 404)
        self._require_active_connection(connection)
        return connection

    async def _require_crm_connection(self, connection_id: UUID) -> IntegrationConnection:
        connection = await self._require_connection(connection_id)
        if connection.connector_key not in {ConnectorKey.HUBSPOT.value, ConnectorKey.SALESFORCE.value}:
            raise PublicAPIError("connection_not_found", "The requested CRM connection was not found.", 404)
        self._require_connector_available(connection.connector_key)
        self._require_active_connection(connection)
        return connection

    async def _require_crm_state(
        self,
        connection_id: UUID,
        *,
        for_update: bool = False,
    ) -> CRMConnectionState:
        statement = select(CRMConnectionState).where(
            CRMConnectionState.organisation_id == self.tenant.organisation_id,
            CRMConnectionState.connection_id == connection_id,
        )
        if for_update:
            statement = statement.with_for_update()
        state = await self.session.scalar(statement)
        if state is None:
            raise PublicAPIError("crm_connection_state_missing", "Reconnect the CRM before continuing.", 409)
        return state

    def _crm_adapter(self, connection: IntegrationConnection) -> CRMProviderAdapter:
        if connection.connector_key == ConnectorKey.HUBSPOT.value:
            from revenueos.hubspot_connector import HubSpotSyncAdapter

            return cast(CRMProviderAdapter, HubSpotSyncAdapter(self._require_hubspot()))
        if connection.connector_key == ConnectorKey.SALESFORCE.value:
            return cast(CRMProviderAdapter, self._require_salesforce())
        raise PublicAPIError("connector_unavailable", "The selected CRM connector is unavailable.", 404)

    @staticmethod
    def _canonical_crm_object_type(entity_type: str) -> CanonicalCRMObjectType:
        if entity_type == "company":
            return "account"
        if entity_type == "contact":
            return "contact"
        if entity_type == "opportunity":
            return "opportunity"
        raise PublicAPIError("crm_entity_type_invalid", "This CRM entity type is unsupported.", 422)

    @staticmethod
    def _external_object_type(connector_key: str, entity_type: str) -> str | None:
        if connector_key == ConnectorKey.HUBSPOT.value:
            return {"company": "company", "contact": "contact", "opportunity": "deal"}.get(entity_type)
        if connector_key == ConnectorKey.SALESFORCE.value:
            return {"company": "account", "contact": "contact", "opportunity": "opportunity"}.get(entity_type)
        return None

    def _require_connector_available(self, connector_key: str) -> None:
        if connector_key == ConnectorKey.HUBSPOT.value:
            self._require_hubspot()
            return
        if connector_key == ConnectorKey.SALESFORCE.value:
            self._require_salesforce()
            return
        if connector_key.startswith("mock_"):
            self._require_mock_connectors()
            return
        if connector_key == ConnectorKey.MICROSOFT_365.value:
            self._require_microsoft()
            return
        if connector_key == ConnectorKey.GOOGLE_WORKSPACE.value:
            self._require_google()
            return
        raise PublicAPIError("connector_unavailable", "The selected connector is unavailable.", 404)

    async def _require_primary_mailbox_available(self, requested: ConnectorKey) -> None:
        existing = await self.session.scalar(
            select(IntegrationConnection).where(
                IntegrationConnection.organisation_id == self.tenant.organisation_id,
                IntegrationConnection.created_by_user_id == self.tenant.user_id,
                IntegrationConnection.connector_key.in_(
                    (ConnectorKey.MICROSOFT_365.value, ConnectorKey.GOOGLE_WORKSPACE.value)
                ),
                IntegrationConnection.connector_key != requested.value,
                IntegrationConnection.connection_status != ConnectionStatus.REVOKED.value,
            )
        )
        if existing is not None:
            definition = CONNECTOR_DEFINITIONS[ConnectorKey(existing.connector_key)]
            raise PublicAPIError(
                "primary_mailbox_already_connected",
                f"Disconnect {definition.display_name} before connecting another primary work mailbox.",
                409,
            )

    async def _require_primary_external_crm_available(self, requested: ConnectorKey) -> None:
        await self.session.scalar(
            select(Organisation.id).where(Organisation.id == self.tenant.organisation_id).with_for_update()
        )
        existing = await self.session.scalar(
            select(IntegrationConnection).where(
                IntegrationConnection.organisation_id == self.tenant.organisation_id,
                IntegrationConnection.connector_key.in_((ConnectorKey.HUBSPOT.value, ConnectorKey.SALESFORCE.value)),
                IntegrationConnection.connector_key != requested.value,
                IntegrationConnection.connection_status != ConnectionStatus.REVOKED.value,
            )
        )
        if existing is not None:
            definition = CONNECTOR_DEFINITIONS[ConnectorKey(existing.connector_key)]
            raise PublicAPIError(
                "primary_crm_already_connected",
                f"Disconnect {definition.display_name} before connecting another external CRM.",
                409,
            )

    async def _preserve_consumed_oauth_state(
        self,
        state_id: UUID,
        connector_key: ConnectorKey,
        consumed_at: datetime,
    ) -> None:
        """Keep callback state one-time even when a global provider identity conflicts."""
        await self.repository.rollback()
        await set_tenant_database_context(self.session, self.tenant.organisation_id)
        state = await self.session.scalar(
            select(OAuthConnectionState)
            .where(
                OAuthConnectionState.organisation_id == self.tenant.organisation_id,
                OAuthConnectionState.id == state_id,
                OAuthConnectionState.connector_key == connector_key.value,
            )
            .with_for_update()
        )
        if state is not None and state.consumed_at is None:
            state.consumed_at = consumed_at
            state.pkce_verifier_encrypted = None
            state.pkce_nonce = None
            await self.repository.commit()
            await set_tenant_database_context(self.session, self.tenant.organisation_id)

    @staticmethod
    def _connection_context(connection: IntegrationConnection) -> ExecutorConnectionContext:
        definition = CONNECTOR_DEFINITIONS[ConnectorKey(connection.connector_key)]
        return ExecutorConnectionContext(
            organisation_id=connection.organisation_id,
            connection_id=connection.id,
            credential_reference=connection.credential_reference,
            execution_mode=definition.execution_mode,
            external_account_id=connection.external_account_id,
            external_account_email=connection.external_account_email,
            external_tenant_id=connection.external_tenant_id,
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
            raise PublicAPIError("crm_entity_not_found", "The Oryntela record was not found.", 404)

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
    def _normalised_crm_display_name(
        object_type: CanonicalCRMObjectType,
        fields: Mapping[str, object],
    ) -> str:
        if object_type == "contact":
            name = " ".join(str(fields.get(key) or "") for key in ("first_name", "last_name")).strip()
            return name or str(fields.get("email") or "Unnamed contact")
        return str(fields.get("name") or "Unnamed record")

    @staticmethod
    def _normalised_crm_secondary_label(
        object_type: CanonicalCRMObjectType,
        fields: Mapping[str, object],
    ) -> str | None:
        key = {"account": "domain", "contact": "email", "opportunity": "stage"}[object_type]
        value = fields.get(key)
        return str(value) if value not in (None, "") else None

    @staticmethod
    def _validate_field_compatibility(revenueos_field: str, property_type: str) -> None:
        allowed = {
            "name": {"string"},
            "domain": {"string"},
            "industry": {"string", "enumeration"},
            "stage": {"enumeration"},
            "status": {"enumeration"},
            "expected_close_date": {"date", "datetime"},
            "estimated_value": {"number"},
            "next_step": {"string"},
            "description": {"string"},
            "first_name": {"string"},
            "last_name": {"string"},
            "email": {"string"},
            "phone": {"string"},
            "job_title": {"string"},
        }
        if property_type not in allowed.get(revenueos_field, set()):
            raise PublicAPIError(
                "crm_field_type_mismatch",
                "The Oryntela field and provider field types are not compatible.",
                422,
            )

    @staticmethod
    def _entity_mapping_response(mapping: CRMEntityMapping, connector_key: str) -> CRMEntityMappingResponse:
        return CRMEntityMappingResponse(
            id=mapping.id,
            connection_id=mapping.connection_id,
            connector_key=ConnectorKey(connector_key),
            revenueos_entity_type=cast(Literal["company", "contact", "opportunity"], mapping.revenueos_entity_type),
            revenueos_entity_id=mapping.revenueos_entity_id,
            external_object_type=cast(
                Literal["account", "company", "contact", "opportunity", "deal"],
                mapping.external_object_type,
            ),
            external_object_id=mapping.external_object_id,
            external_updated_at=mapping.external_updated_at,
            last_synced_at=mapping.last_synced_at,
            sync_state=cast(Literal["active", "external_missing"], mapping.sync_state),
            external_version=mapping.external_version,
            authority_version=mapping.authority_version,
            archived_at=mapping.archived_at,
            created_at=mapping.created_at,
            updated_at=mapping.updated_at,
        )

    @staticmethod
    def _field_mapping_response(mapping: CRMFieldMapping) -> CRMFieldMappingResponse:
        return CRMFieldMappingResponse(
            id=mapping.id,
            connection_id=mapping.connection_id,
            entity_type=cast(Literal["company", "opportunity", "contact"], mapping.entity_type),
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
            mapping_version=mapping.mapping_version,
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
    def _raise_crm_public_error(connector_key: str, error: Exception) -> NoReturn:
        if not isinstance(error, CRMProviderError):
            raise error
        provider_name = CONNECTOR_DEFINITIONS[ConnectorKey(connector_key)].display_name
        messages = {
            "connection_reauthorisation_required": f"Reconnect {provider_name} before using CRM sync.",
            "external_object_not_found": f"The selected {provider_name} record no longer exists.",
            "provider_rate_limited": f"{provider_name} is temporarily rate limiting this organisation.",
            "provider_timeout": f"{provider_name} did not respond in time.",
            "provider_unavailable": f"{provider_name} is temporarily unavailable.",
            "provider_response_invalid": f"{provider_name} returned an unexpected response.",
            "provider_response_too_large": f"{provider_name} returned more data than Oryntela accepts.",
            "stale_external_state": f"The {provider_name} record changed. Refresh before trying again.",
            "provider_person_account_unsupported": (
                "Salesforce Person Accounts are not supported in this connector version. "
                "Use a business Account scope before synchronising."
            ),
            "provider_currency_capability_required": (
                "Salesforce did not expose explicit opportunity currency. Amount writeback remains blocked."
            ),
        }
        status_code = 429 if error.code == "provider_rate_limited" else 409
        raise PublicAPIError(
            error.code,
            messages.get(error.code, f"{provider_name} could not complete this request."),
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
            if connection.connector_key in {
                ConnectorKey.MICROSOFT_365.value,
                ConnectorKey.GOOGLE_WORKSPACE.value,
                ConnectorKey.SALESFORCE.value,
            }:
                definition = CONNECTOR_DEFINITIONS[ConnectorKey(connection.connector_key)]
                raise PublicAPIError(
                    "connection_reauthorisation_required",
                    f"Reconnect {definition.display_name} before continuing.",
                    409,
                )
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
            external_account_email=connection.external_account_email,
            external_tenant_id=connection.external_tenant_id,
            granted_scopes=list(connection.granted_scopes_json),
            metadata_version=connection.metadata_version,
            execution_mode=definition.execution_mode,
            simulation_only=definition.simulation_only,
            created_at=connection.created_at,
            updated_at=connection.updated_at,
        )

    async def _ensure_crm_connection_state(
        self,
        connection: IntegrationConnection,
        now: datetime,
    ) -> CRMConnectionState:
        state = await self.session.scalar(
            select(CRMConnectionState)
            .where(
                CRMConnectionState.organisation_id == self.tenant.organisation_id,
                CRMConnectionState.connection_id == connection.id,
            )
            .with_for_update()
        )
        if state is None:
            state = CRMConnectionState(
                id=uuid.uuid4(),
                organisation_id=self.tenant.organisation_id,
                connection_id=connection.id,
                provider_key=connection.connector_key,
                lifecycle="connected_read_only",
                health_status="healthy",
                connector_enabled=True,
                writeback_enabled=False,
                mapping_version=1,
                records_seen=0,
                records_applied=0,
                conflict_count=0,
                initial_sync_started_at=None,
                initial_sync_completed_at=None,
                last_successful_sync_at=None,
                last_health_checked_at=now,
                last_safe_error_code=None,
                configured_by_user_id=self.tenant.user_id,
                created_at=now,
                updated_at=now,
            )
            self.session.add(state)
            return state
        state.lifecycle = "connected_read_only"
        state.health_status = "healthy"
        state.connector_enabled = True
        state.writeback_enabled = False
        state.last_health_checked_at = now
        state.last_safe_error_code = None
        state.configured_by_user_id = self.tenant.user_id
        paused_jobs = (
            await self.session.scalars(
                select(CRMSyncJob).where(
                    CRMSyncJob.organisation_id == self.tenant.organisation_id,
                    CRMSyncJob.connection_id == connection.id,
                    CRMSyncJob.status == "paused",
                )
            )
        ).all()
        for job in paused_jobs:
            job.status = "queued"
            job.worker_id = None
            job.lease_expires_at = None
            job.completed_at = None
            job.safe_failure_code = None
            job.updated_at = now
        return state

    async def _queue_initial_crm_sync(
        self,
        connection: IntegrationConnection,
        state: CRMConnectionState,
        now: datetime,
    ) -> None:
        idempotency_key = hashlib.sha256(f"initial:{connection.id}:{state.mapping_version}".encode()).hexdigest()
        existing = await self.session.scalar(
            select(CRMSyncJob.id).where(
                CRMSyncJob.organisation_id == self.tenant.organisation_id,
                CRMSyncJob.connection_id == connection.id,
                CRMSyncJob.idempotency_key == idempotency_key,
            )
        )
        if existing is not None or state.initial_sync_completed_at is not None:
            return
        state.lifecycle = "initial_sync"
        state.initial_sync_started_at = now
        self.session.add(
            CRMSyncJob(
                id=uuid.uuid4(),
                organisation_id=self.tenant.organisation_id,
                connection_id=connection.id,
                provider_key=connection.connector_key,
                mode="initial",
                status="queued",
                idempotency_key=idempotency_key,
                requested_by_user_id=self.tenant.user_id,
                attempt_count=0,
                worker_id=None,
                lease_expires_at=None,
                started_at=None,
                completed_at=None,
                safe_failure_code=None,
                created_at=now,
                updated_at=now,
            )
        )
        self._add_audit(connection, "crm_sync_queued", now)

    async def _seed_default_crm_field_mappings(
        self,
        connection: IntegrationConnection,
        now: datetime,
    ) -> None:
        entity_types: dict[CanonicalCRMObjectType, str] = {
            "account": "company",
            "contact": "contact",
            "opportunity": "opportunity",
        }
        for object_type, entity_type in entity_types.items():
            existing = {
                item.revenueos_field
                for item in await self.repository.list_field_mappings(
                    self.tenant.organisation_id,
                    connection.id,
                    entity_type,
                )
            }
            for rule in rules_for(connection.connector_key, object_type):
                if rule.value_type not in {"string", "number", "date", "datetime", "enumeration"}:
                    continue
                if rule.canonical_field in existing:
                    continue
                self.repository.add(
                    CRMFieldMapping(
                        id=uuid.uuid4(),
                        organisation_id=self.tenant.organisation_id,
                        connection_id=connection.id,
                        entity_type=entity_type,
                        revenueos_field=rule.canonical_field,
                        external_property_name=rule.provider_field,
                        external_property_type=rule.value_type,
                        authority=rule.default_authority,
                        enabled=True,
                        configured_by_user_id=self.tenant.user_id,
                        mapping_version=1,
                        created_at=now,
                        updated_at=now,
                    )
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
        live_executors: list[ActionExecutor] = []
        if settings.feature_hubspot_crm_enabled:
            from revenueos.hubspot_connector import HubSpotClient, HubSpotCRMExecutor

            live_executor = HubSpotCRMExecutor(HubSpotClient(settings, self.credential_store))
        if settings.feature_microsoft_365_enabled:
            from revenueos.microsoft_graph import MicrosoftEmailExecutor, MicrosoftGraphClient

            live_executors.append(
                MicrosoftEmailExecutor(session, MicrosoftGraphClient(settings, self.credential_store))
            )
        if settings.feature_google_workspace_enabled:
            from revenueos.google_workspace import GoogleEmailExecutor, GoogleWorkspaceClient

            live_executors.append(GoogleEmailExecutor(session, GoogleWorkspaceClient(settings, self.credential_store)))
        self.executors = executors or ActionExecutorRegistry(
            live_executor=live_executor,
            live_executors=tuple(live_executors),
        )

    async def preview(self, action_id: UUID, connection_id: UUID) -> ExecutionPreviewResponse:
        self._require_execution_features()
        action_record = await self._require_approved_action(action_id)
        connection = await self._require_active_connection(connection_id, for_update=True)
        await self._require_connection_entitlement(connection)
        action = await self._action_input(action_record)
        self._require_outreach_mailbox_binding(action, connection)
        await self._require_mailbox_email_send_safety(action, connection)
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
                await self._require_connection_entitlement(connection)
                self._require_outreach_mailbox_binding(action, connection)
                await self._require_mailbox_email_send_safety(action, connection)
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
        await self._require_connection_entitlement(connection)
        action = await self._action_input(action_record)
        self._require_outreach_mailbox_binding(action, connection)
        await self._require_mailbox_email_send_safety(action, connection)
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
        if connection.connector_key in {
            ConnectorKey.MICROSOFT_365.value,
            ConnectorKey.GOOGLE_WORKSPACE.value,
        }:
            payload = cast(FollowUpEmailPayload | PersonalizedOutreachPayload, action.payload)
            assert payload.recipient_email is not None
            assert connection.external_account_email is not None
            self.session.add(
                ProviderOutboundOperation(
                    id=uuid.uuid4(),
                    organisation_id=self.tenant.organisation_id,
                    connection_id=connection.id,
                    action_id=action.action_id,
                    provider_key=connection.connector_key,
                    idempotency_key=idempotency_key,
                    state="queued",
                    sender_email=connection.external_account_email,
                    recipient_email=payload.recipient_email,
                    created_at=now,
                    updated_at=now,
                )
            )
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
        await self._require_connection_entitlement(connection)
        action_record = await self.repository.approved_action(
            self.tenant.organisation_id,
            execution.action_id,
            for_update=True,
        )
        if action_record is None or action_record.proposal.approved_version != execution.action_version:
            raise PublicAPIError("action_version_stale", "The approved Action version is unavailable.", 409)
        action = await self._action_input(action_record)
        self._require_outreach_mailbox_binding(action, connection)
        action = await self._bind_external_target(action, connection)
        capability = ConnectorCapability(execution.capability)
        executor = self._executor(connection, capability, action.risk_class)
        context = ExecutorConnectionContext(
            organisation_id=self.tenant.organisation_id,
            connection_id=connection.id,
            credential_reference=connection.credential_reference,
            execution_mode="live",
            external_account_id=connection.external_account_id,
            external_account_email=connection.external_account_email,
            external_tenant_id=connection.external_tenant_id,
        )
        now = datetime.now(UTC)
        external_result_id: str | None = None
        applied = False
        safe_to_retry = False
        try:
            if connection.connector_key in {
                ConnectorKey.MICROSOFT_365.value,
                ConnectorKey.GOOGLE_WORKSPACE.value,
            }:
                operation = await self.session.scalar(
                    select(ProviderOutboundOperation)
                    .where(
                        ProviderOutboundOperation.organisation_id == self.tenant.organisation_id,
                        ProviderOutboundOperation.connection_id == connection.id,
                        ProviderOutboundOperation.action_id == execution.action_id,
                        ProviderOutboundOperation.idempotency_key == execution.idempotency_key,
                    )
                    .with_for_update()
                )
                if operation is None or operation.state != "reconciled" or operation.provider_message_id is None:
                    provider_prefix = (
                        "microsoft" if connection.connector_key == ConnectorKey.MICROSOFT_365.value else "google"
                    )
                    raise PublicAPIError(
                        f"{provider_prefix}_send_reconciliation_pending",
                        "The mailbox provider has not supplied strong evidence that this email was sent. "
                        "Oryntela will keep the outcome unknown and will not resend it.",
                        409,
                    )
                applied = True
                external_result_id = operation.provider_message_id
            elif isinstance(action.payload, LogInteractionPayload):
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
        await self._commit("The execution could not be reconciled.")
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
                or self.settings.feature_microsoft_365_enabled
                or self.settings.feature_google_workspace_enabled
                or (self.settings.feature_mock_connectors_enabled and self.settings.environment != "production")
            )
        ):
            raise PublicAPIError("feature_unavailable", "This feature is not enabled for the private beta.", 404)

    async def _require_connection_entitlement(self, connection: IntegrationConnection) -> None:
        await CommercialService(self.session, self.settings).require_module_write(
            self.tenant.organisation_id,
            _commercial_module_for_connector(connection.connector_key),
        )

    def _credential_store(self) -> CredentialStore:
        if not (
            self.settings.feature_hubspot_crm_enabled
            or self.settings.feature_microsoft_365_enabled
            or self.settings.feature_google_workspace_enabled
        ):
            return MockCredentialStore()
        if self.settings.connector_credential_master_key is None:
            raise RuntimeError("Connector credential storage is not configured.")
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
        if proposal.action_type == "personalized_outreach":
            await validate_personalized_outreach_action(
                self.session,
                self.tenant,
                self.settings,
                record,
            )
            return record
        if proposal.opportunity_id is None:
            raise PublicAPIError("action_target_stale", "The Action target is no longer available.", 409)
        opportunity_id = proposal.opportunity_id
        opportunity_statement = select(Opportunity).where(
            Opportunity.organisation_id == self.tenant.organisation_id,
            Opportunity.id == opportunity_id,
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
                opportunity_id,
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
        if isinstance(payload, PersonalizedOutreachPayload):
            return ApprovedActionInput(
                organisation_id=self.tenant.organisation_id,
                action_id=proposal.id,
                action_version=cast(int, proposal.approved_version),
                opportunity_id=None,
                action_type=proposal.action_type,
                risk_class=ActionRiskClass(proposal.risk_class),
                title=record.version.title,
                target_entity_type=record.version.target_entity_type,
                target_entity_id=record.version.target_entity_id,
                payload=payload,
                revenueos_currency=None,
            )
        if proposal.opportunity_id is None:
            raise PublicAPIError("action_target_stale", "The Action target is no longer available.", 409)
        opportunity_id = proposal.opportunity_id
        opportunity = cast(
            Opportunity | None,
            await self.session.scalar(
                select(Opportunity).where(
                    Opportunity.organisation_id == self.tenant.organisation_id,
                    Opportunity.id == opportunity_id,
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
            record.version.target_entity_type != "opportunity" or record.version.target_entity_id != opportunity_id
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
            payload.linked_opportunity_id != opportunity_id
            or record.version.target_entity_type != "opportunity"
            or record.version.target_entity_id != opportunity_id
        ):
            raise PublicAPIError("action_target_stale", "The approved task target is unavailable.", 409)
        if isinstance(payload, LogInteractionPayload):
            interaction = await self.session.scalar(
                select(Interaction).where(
                    Interaction.organisation_id == self.tenant.organisation_id,
                    Interaction.id == payload.interaction_id,
                    Interaction.opportunity_id == opportunity_id,
                )
            )
            if interaction is None:
                raise PublicAPIError("action_target_stale", "The approved interaction is unavailable.", 409)
        return ApprovedActionInput(
            organisation_id=self.tenant.organisation_id,
            action_id=proposal.id,
            action_version=cast(int, proposal.approved_version),
            opportunity_id=opportunity_id,
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
        if connection.connector_key not in {ConnectorKey.HUBSPOT.value, ConnectorKey.SALESFORCE.value}:
            return action
        provider_name = CONNECTOR_DEFINITIONS[ConnectorKey(connection.connector_key)].display_name
        crm_state = await self.session.scalar(
            select(CRMConnectionState).where(
                CRMConnectionState.organisation_id == self.tenant.organisation_id,
                CRMConnectionState.connection_id == connection.id,
            )
        )
        if crm_state is None or not crm_state.connector_enabled or not crm_state.writeback_enabled:
            raise PublicAPIError(
                "crm_writeback_disabled",
                "An administrator must review CRM mappings and enable writeback before external updates.",
                409,
            )
        entity_type: str
        entity_id: UUID
        field_name: str | None = None
        proposed: object | None = None
        if isinstance(action.payload, OpportunityUpdatePayload):
            if action.opportunity_id is None:
                raise PublicAPIError("action_target_stale", "The Action target is no longer available.", 409)
            entity_type = "opportunity"
            entity_id = action.opportunity_id
            field_name = action.payload.field
            proposed = action.payload.proposed_value
        elif isinstance(action.payload, ContactUpdatePayload):
            if action.payload.operation != "update" or action.payload.contact_id is None:
                raise PublicAPIError(
                    "contact_mapping_required",
                    f"Link an existing {provider_name} contact before updating it.",
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
            if action.opportunity_id is None:
                raise PublicAPIError("action_target_stale", "The Action target is no longer available.", 409)
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
                f"Connect this Oryntela record to a {provider_name} record before reviewing the Action.",
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
                    f"Configure this {provider_name} field mapping before reviewing the Action.",
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
                        f"Configure this Oryntela-to-{provider_name} stage mapping before reviewing the Action.",
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
                external_object_type=(
                    {"opportunity": "deals", "contact": "contacts"}[entity_type]
                    if connection.connector_key == ConnectorKey.HUBSPOT.value
                    else {"opportunity": "opportunity", "contact": "contact"}[entity_type]
                ),
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

    def _require_outreach_mailbox_binding(
        self,
        action: ApprovedActionInput,
        connection: IntegrationConnection,
    ) -> None:
        if not isinstance(action.payload, (FollowUpEmailPayload, PersonalizedOutreachPayload)):
            return
        if connection.connector_key not in {
            ConnectorKey.MICROSOFT_365.value,
            ConnectorKey.GOOGLE_WORKSPACE.value,
            ConnectorKey.MOCK_EMAIL.value,
        }:
            return
        if connection.created_by_user_id != self.tenant.user_id:
            raise PublicAPIError(
                "mailbox_owner_mismatch",
                "Select your own connected mailbox.",
                409,
            )
        if connection.connector_key in {
            ConnectorKey.MICROSOFT_365.value,
            ConnectorKey.GOOGLE_WORKSPACE.value,
        }:
            provider_enabled = (
                self.settings.feature_microsoft_365_enabled
                if connection.connector_key == ConnectorKey.MICROSOFT_365.value
                else self.settings.feature_google_workspace_enabled
            )
            definition = CONNECTOR_DEFINITIONS[ConnectorKey(connection.connector_key)]
            if not provider_enabled or not connection.external_account_email:
                raise PublicAPIError(
                    "connection_reauthorisation_required",
                    f"Reconnect {definition.display_name} to continue sending.",
                    409,
                )
            if isinstance(action.payload, PersonalizedOutreachPayload) and (
                action.payload.sender_user_id != self.tenant.user_id
                or action.payload.sender_email.casefold() != connection.external_account_email.casefold()
            ):
                raise PublicAPIError(
                    "sender_identity_mismatch",
                    f"The approved From address must match your connected {definition.display_name} mailbox.",
                    409,
                )
            return
        if self.settings.environment == "production":
            raise PublicAPIError(
                "production_mailbox_unavailable",
                "A production work mailbox connection is required.",
                409,
            )
        if connection.connector_key != ConnectorKey.MOCK_EMAIL.value or (
            isinstance(action.payload, PersonalizedOutreachPayload)
            and action.payload.sender_user_id != self.tenant.user_id
        ):
            raise PublicAPIError(
                "mailbox_owner_mismatch",
                "Select the sender's own email simulation connection.",
                409,
            )

    async def _require_mailbox_email_send_safety(
        self,
        action: ApprovedActionInput,
        connection: IntegrationConnection,
    ) -> None:
        if connection.connector_key not in {
            ConnectorKey.MICROSOFT_365.value,
            ConnectorKey.GOOGLE_WORKSPACE.value,
        } or not isinstance(
            action.payload,
            FollowUpEmailPayload,
        ):
            return
        payload = action.payload
        if payload.recipient_contact_id is None or payload.recipient_email is None:
            raise PublicAPIError(
                "unsupported_recipient",
                "Select the exact canonical Contact recipient before sending.",
                409,
            )
        contact = await self.session.scalar(
            select(Contact).where(
                Contact.organisation_id == self.tenant.organisation_id,
                Contact.id == payload.recipient_contact_id,
            )
        )
        if contact is None or contact.email is None or contact.email.casefold() != payload.recipient_email.casefold():
            raise PublicAPIError("unsupported_recipient", "The approved Contact recipient is unavailable.", 409)
        contactability = await evaluate_contactability(
            OutreachRepository(self.session),
            self.tenant,
            self.settings,
            contact,
            action_id=action.action_id,
            sender_user_id=self.tenant.user_id,
        )
        if not contactability.allowed:
            raise PublicAPIError(contactability.state.value, contactability.reason, 409)

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
                        external_account_id=connection.external_account_id,
                        external_account_email=connection.external_account_email,
                        external_tenant_id=connection.external_tenant_id,
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
            ConnectorCapability.SEND_EMAIL: (
                f"Send this reviewed email through the connected {definition.display_name} work mailbox."
            ),
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
                "Outcome is unknown. Oryntela will not retry without reconciliation."
            ),
            ExecutionStatus.SUCCEEDED: "The reviewed HubSpot action completed and was verified.",
        }[status]
        if execution.execution_mode == "live":
            if execution.connector_key in {
                ConnectorKey.MICROSOFT_365.value,
                ConnectorKey.GOOGLE_WORKSPACE.value,
            }:
                if execution.connector_key == ConnectorKey.MICROSOFT_365.value:
                    safe_message = {
                        ExecutionStatus.QUEUED: "Microsoft email queued. No external send has occurred yet.",
                        ExecutionStatus.EXECUTING: "Oryntela is submitting the reviewed email to Microsoft.",
                        ExecutionStatus.SUCCEEDED: (
                            "Microsoft accepted the reviewed email for processing. Delivery is not guaranteed."
                        ),
                        ExecutionStatus.FAILED_RETRYABLE: (
                            "Microsoft did not accept the email; a bounded retry is safe."
                        ),
                        ExecutionStatus.FAILED_PERMANENT: (
                            "The Microsoft email stopped safely and will not be retried."
                        ),
                        ExecutionStatus.CANCELLED: "The Microsoft email was cancelled before submission.",
                        ExecutionStatus.UNKNOWN_EXTERNAL_STATE: (
                            "The Microsoft send outcome is unknown. Oryntela will not resend without "
                            "strong Sent Items evidence."
                        ),
                        ExecutionStatus.SIMULATED_SUCCESS: "The simulation completed. No external action occurred.",
                    }[status]
                else:
                    safe_message = {
                        ExecutionStatus.QUEUED: "Google Workspace email queued. No external send has occurred yet.",
                        ExecutionStatus.EXECUTING: "Oryntela is submitting the reviewed email to Gmail.",
                        ExecutionStatus.SUCCEEDED: (
                            "Gmail accepted the reviewed email for processing. Delivery is not guaranteed."
                        ),
                        ExecutionStatus.FAILED_RETRYABLE: ("Gmail did not accept the email; a bounded retry is safe."),
                        ExecutionStatus.FAILED_PERMANENT: ("The Gmail email stopped safely and will not be retried."),
                        ExecutionStatus.CANCELLED: "The Gmail email was cancelled before submission.",
                        ExecutionStatus.UNKNOWN_EXTERNAL_STATE: (
                            "The Gmail send outcome is unknown. Oryntela will not resend without strong "
                            "provider evidence."
                        ),
                        ExecutionStatus.SIMULATED_SUCCESS: "The simulation completed. No external action occurred.",
                    }[status]
            else:
                safe_message = {
                    ExecutionStatus.QUEUED: "HubSpot update queued. No external change has occurred yet.",
                    ExecutionStatus.EXECUTING: "Oryntela is applying the reviewed HubSpot action.",
                    ExecutionStatus.SUCCEEDED: "The reviewed HubSpot action completed and was verified.",
                    ExecutionStatus.FAILED_RETRYABLE: "HubSpot did not apply the action; a bounded retry is safe.",
                    ExecutionStatus.FAILED_PERMANENT: "The HubSpot action stopped safely and will not be retried.",
                    ExecutionStatus.CANCELLED: "The HubSpot action was cancelled before execution.",
                    ExecutionStatus.UNKNOWN_EXTERNAL_STATE: (
                        "The HubSpot outcome is unknown. Oryntela will not retry without reconciliation."
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
