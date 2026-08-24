from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal, InvalidOperation
from typing import Literal, NoReturn, cast
from urllib.parse import urlencode
from uuid import UUID

import httpx
from pydantic import AliasChoices, BaseModel, ConfigDict, Field, ValidationError

from revenueos.action_contracts import ContactUpdatePayload, LogInteractionPayload, OpportunityUpdatePayload
from revenueos.config import Settings
from revenueos.credential_store import ConnectorCredential, CredentialStore
from revenueos.domain import ConnectorKey, CRMFieldAuthority
from revenueos.integration_contracts import CRMActivityExecutionPreview, CRMExecutionPreview, ExecutionPreviewContent
from revenueos.integration_executors import (
    CONNECTOR_DEFINITIONS,
    ActionExecutor,
    ApprovedActionInput,
    ExecutorConnectionContext,
    ExecutorResult,
    PermanentExecutionFailure,
    RetryableExecutionFailure,
    UnknownExternalStateFailure,
)

HUBSPOT_REQUIRED_SCOPES = (
    "oauth",
    "crm.objects.companies.read",
    "crm.objects.contacts.read",
    "crm.objects.contacts.write",
    "crm.objects.deals.read",
    "crm.objects.deals.write",
    "crm.objects.meetings.read",
    "crm.objects.meetings.write",
    "crm.schemas.companies.read",
    "crm.schemas.contacts.read",
    "crm.schemas.deals.read",
)


class HubSpotAPIError(Exception):
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


class _ProviderModel(BaseModel):
    model_config = ConfigDict(extra="ignore")


class _TokenResponse(_ProviderModel):
    access_token: str
    refresh_token: str | None = None
    expires_in: int = Field(ge=60, le=86_400)
    scopes: list[str] = Field(default_factory=list)
    hub_id: int | str | None = Field(
        default=None,
        validation_alias=AliasChoices("hub_id", "hubId"),
    )


class _TokenMetadata(_ProviderModel):
    active: bool = True
    hub_id: int | str = Field(validation_alias=AliasChoices("hub_id", "hubId", "portalId"))
    hub_domain: str | None = Field(
        default=None,
        validation_alias=AliasChoices("hub_domain", "hubDomain"),
    )
    scopes: list[str] = Field(default_factory=list)


class HubSpotRecord(_ProviderModel):
    id: str
    properties: dict[str, object] = Field(default_factory=dict)
    updated_at: datetime | None = Field(default=None, validation_alias=AliasChoices("updatedAt", "updated_at"))


class _SearchResponse(_ProviderModel):
    results: list[HubSpotRecord] = Field(default_factory=list)
    total: int = 0


class HubSpotPropertyOption(_ProviderModel):
    label: str
    value: str
    hidden: bool = False


class _PropertyModification(_ProviderModel):
    read_only_value: bool = Field(default=False, validation_alias=AliasChoices("readOnlyValue", "read_only_value"))


class HubSpotProperty(_ProviderModel):
    name: str
    label: str
    type: str
    field_type: str = Field(validation_alias=AliasChoices("fieldType", "field_type"))
    options: list[HubSpotPropertyOption] = Field(default_factory=list)
    modification_metadata: _PropertyModification = Field(
        default_factory=_PropertyModification,
        validation_alias=AliasChoices("modificationMetadata", "modification_metadata"),
    )


class _PropertyResponse(_ProviderModel):
    results: list[HubSpotProperty] = Field(default_factory=list)


class HubSpotPipelineStage(_ProviderModel):
    id: str
    label: str


class HubSpotPipeline(_ProviderModel):
    id: str
    label: str
    stages: list[HubSpotPipelineStage] = Field(default_factory=list)


class _PipelineResponse(_ProviderModel):
    results: list[HubSpotPipeline] = Field(default_factory=list)


class _AssociationLabel(_ProviderModel):
    type_id: int = Field(validation_alias=AliasChoices("typeId", "type_id"))
    category: str
    label: str | None = None


class _AssociationResponse(_ProviderModel):
    results: list[_AssociationLabel] = Field(default_factory=list)


@dataclass(frozen=True)
class HubSpotExternalState:
    current_value: str | None
    updated_at: datetime | None
    currency: str | None


class HubSpotClient:
    """Small direct-HTTP adapter with explicit timeouts and no hidden retries."""

    def __init__(
        self,
        settings: Settings,
        credential_store: CredentialStore,
        *,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self.settings = settings
        self.credential_store = credential_store
        self._http_client = http_client

    def authorisation_url(self, state: str) -> str:
        assert self.settings.hubspot_client_id is not None
        assert self.settings.hubspot_oauth_redirect_uri is not None
        query = urlencode(
            {
                "client_id": self.settings.hubspot_client_id,
                "redirect_uri": self.settings.hubspot_oauth_redirect_uri,
                "scope": " ".join(HUBSPOT_REQUIRED_SCOPES),
                "state": state,
            }
        )
        return f"{self.settings.hubspot_authorisation_base_url}?{query}"

    async def exchange_code(self, code: str) -> tuple[ConnectorCredential, str | None]:
        assert self.settings.hubspot_client_id is not None
        assert self.settings.hubspot_client_secret is not None
        assert self.settings.hubspot_oauth_redirect_uri is not None
        response = await self._request(
            "POST",
            "/oauth/2026-03/token",
            data={
                "grant_type": "authorization_code",
                "client_id": self.settings.hubspot_client_id,
                "client_secret": self.settings.hubspot_client_secret.get_secret_value(),
                "redirect_uri": self.settings.hubspot_oauth_redirect_uri,
                "code": code,
            },
            write=False,
            authenticated=False,
        )
        token = self._parse(_TokenResponse, response)
        if not token.refresh_token:
            raise HubSpotAPIError("provider_response_invalid")
        metadata = await self.introspect(token.access_token)
        scopes = tuple(sorted(set(token.scopes or metadata.scopes)))
        missing = sorted(set(HUBSPOT_REQUIRED_SCOPES) - set(scopes))
        if missing:
            raise HubSpotAPIError("missing_required_scope")
        return (
            ConnectorCredential(
                access_token=token.access_token,
                refresh_token=token.refresh_token,
                expires_at=datetime.now(UTC) + timedelta(seconds=token.expires_in),
                scopes=scopes,
                external_account_id=str(metadata.hub_id),
            ),
            metadata.hub_domain,
        )

    async def introspect(self, token: str) -> _TokenMetadata:
        assert self.settings.hubspot_client_id is not None
        assert self.settings.hubspot_client_secret is not None
        response = await self._request(
            "POST",
            "/oauth/2026-03/token/introspect",
            data={
                "client_id": self.settings.hubspot_client_id,
                "client_secret": self.settings.hubspot_client_secret.get_secret_value(),
                "token": token,
                "token_type_hint": "access_token",
            },
            write=False,
            authenticated=False,
        )
        metadata = self._parse(_TokenMetadata, response)
        if not metadata.active:
            raise HubSpotAPIError("connection_reauthorisation_required")
        return metadata

    async def revoke(self, credential: ConnectorCredential) -> None:
        assert self.settings.hubspot_client_id is not None
        assert self.settings.hubspot_client_secret is not None
        await self._request(
            "POST",
            "/oauth/2026-03/token/revoke",
            data={
                "client_id": self.settings.hubspot_client_id,
                "client_secret": self.settings.hubspot_client_secret.get_secret_value(),
                "token": credential.refresh_token,
                "token_type_hint": "refresh_token",
            },
            write=False,
            authenticated=False,
        )

    async def validate_credentials(
        self,
        context: ExecutorConnectionContext,
    ) -> tuple[ConnectorCredential, _TokenMetadata]:
        """Refresh when needed, then verify the token and account identity."""
        if context.credential_reference is None:
            raise HubSpotAPIError("connection_reauthorisation_required")
        try:
            credential = await self.credential_store.get(
                context.organisation_id,
                context.connection_id,
                context.credential_reference,
            )
        except ValueError as exc:
            raise HubSpotAPIError("connection_reauthorisation_required") from exc
        if credential.expires_at.astimezone(UTC) <= datetime.now(UTC) + timedelta(seconds=60):
            credential = await self._refresh(context, credential)
        try:
            metadata = await self.introspect(credential.access_token)
        except HubSpotAPIError as exc:
            if exc.code != "connection_reauthorisation_required":
                raise
            credential = await self._refresh(context, credential)
            metadata = await self.introspect(credential.access_token)
        return credential, metadata

    async def get_record(
        self,
        context: ExecutorConnectionContext,
        object_type: str,
        object_id: str,
        properties: tuple[str, ...],
    ) -> HubSpotRecord:
        response = await self._authenticated_request(
            context,
            "GET",
            f"/crm/objects/2026-03/{object_type}/{object_id}",
            params={"properties": ",".join(properties)},
            write=False,
        )
        return self._parse(HubSpotRecord, response)

    async def update_record(
        self,
        context: ExecutorConnectionContext,
        object_type: str,
        object_id: str,
        properties: dict[str, str],
    ) -> HubSpotRecord:
        response = await self._authenticated_request(
            context,
            "PATCH",
            f"/crm/objects/2026-03/{object_type}/{object_id}",
            json_body={"properties": properties},
            write=True,
        )
        return self._parse(HubSpotRecord, response)

    async def search_records(
        self,
        context: ExecutorConnectionContext,
        object_type: str,
        query: str,
        properties: tuple[str, ...],
        *,
        limit: int = 10,
    ) -> list[HubSpotRecord]:
        response = await self._authenticated_request(
            context,
            "POST",
            f"/crm/objects/2026-03/{object_type}/search",
            json_body={"query": query, "limit": min(limit, 10), "properties": list(properties)},
            write=False,
        )
        return self._parse(_SearchResponse, response).results[:10]

    async def search_by_property(
        self,
        context: ExecutorConnectionContext,
        object_type: str,
        property_name: str,
        value: str,
        properties: tuple[str, ...],
    ) -> list[HubSpotRecord]:
        response = await self._authenticated_request(
            context,
            "POST",
            f"/crm/objects/2026-03/{object_type}/search",
            json_body={
                "filterGroups": [{"filters": [{"propertyName": property_name, "operator": "EQ", "value": value}]}],
                "limit": 2,
                "properties": list(properties),
            },
            write=False,
        )
        return self._parse(_SearchResponse, response).results[:2]

    async def properties(self, context: ExecutorConnectionContext, object_type: str) -> list[HubSpotProperty]:
        response = await self._authenticated_request(
            context,
            "GET",
            f"/crm/properties/2026-03/{object_type}",
            write=False,
        )
        return self._parse(_PropertyResponse, response).results

    async def pipelines(self, context: ExecutorConnectionContext) -> list[HubSpotPipeline]:
        response = await self._authenticated_request(
            context,
            "GET",
            "/crm/pipelines/2026-03/deals",
            write=False,
        )
        return self._parse(_PipelineResponse, response).results

    async def create_meeting(
        self,
        context: ExecutorConnectionContext,
        *,
        properties: dict[str, str],
        deal_id: str,
    ) -> HubSpotRecord:
        association_type = await self._meeting_deal_association_type(context)
        response = await self._authenticated_request(
            context,
            "POST",
            "/crm/objects/2026-03/meetings",
            json_body={
                "properties": properties,
                "associations": [
                    {
                        "to": {"id": deal_id},
                        "types": [
                            {
                                "associationCategory": "HUBSPOT_DEFINED",
                                "associationTypeId": association_type,
                            }
                        ],
                    }
                ],
            },
            write=True,
        )
        return self._parse(HubSpotRecord, response)

    async def _meeting_deal_association_type(self, context: ExecutorConnectionContext) -> int:
        response = await self._authenticated_request(
            context,
            "GET",
            "/crm/associations/2026-03/meetings/deals/labels",
            write=False,
        )
        labels = self._parse(_AssociationResponse, response).results
        for label in labels:
            if label.category == "HUBSPOT_DEFINED" and label.label is None:
                return label.type_id
        raise HubSpotAPIError("association_capability_unavailable")

    async def _authenticated_request(
        self,
        context: ExecutorConnectionContext,
        method: str,
        path: str,
        *,
        params: dict[str, str] | None = None,
        json_body: dict[str, object] | None = None,
        write: bool,
    ) -> httpx.Response:
        if context.credential_reference is None:
            raise HubSpotAPIError("connection_reauthorisation_required")
        try:
            credential = await self.credential_store.get(
                context.organisation_id,
                context.connection_id,
                context.credential_reference,
            )
        except ValueError as exc:
            raise HubSpotAPIError("connection_reauthorisation_required") from exc
        if credential.expires_at.astimezone(UTC) <= datetime.now(UTC) + timedelta(seconds=60):
            credential = await self._refresh(context, credential)
        try:
            return await self._request(
                method,
                path,
                params=params,
                json_body=json_body,
                token=credential.access_token,
                write=write,
                authenticated=True,
            )
        except HubSpotAPIError as exc:
            if exc.code != "connection_reauthorisation_required":
                raise
        credential = await self._refresh(context, credential)
        return await self._request(
            method,
            path,
            params=params,
            json_body=json_body,
            token=credential.access_token,
            write=write,
            authenticated=True,
        )

    async def _refresh(
        self,
        context: ExecutorConnectionContext,
        credential: ConnectorCredential,
    ) -> ConnectorCredential:
        assert self.settings.hubspot_client_id is not None
        assert self.settings.hubspot_client_secret is not None
        try:
            response = await self._request(
                "POST",
                "/oauth/2026-03/token",
                data={
                    "grant_type": "refresh_token",
                    "client_id": self.settings.hubspot_client_id,
                    "client_secret": self.settings.hubspot_client_secret.get_secret_value(),
                    "refresh_token": credential.refresh_token,
                },
                write=False,
                authenticated=False,
            )
            refreshed = self._parse(_TokenResponse, response)
        except HubSpotAPIError as exc:
            raise HubSpotAPIError("connection_reauthorisation_required") from exc
        value = ConnectorCredential(
            access_token=refreshed.access_token,
            refresh_token=refreshed.refresh_token or credential.refresh_token,
            expires_at=datetime.now(UTC) + timedelta(seconds=refreshed.expires_in),
            scopes=tuple(sorted(set(refreshed.scopes or list(credential.scopes)))),
            external_account_id=credential.external_account_id,
        )
        await self.credential_store.put(context.organisation_id, context.connection_id, value)
        return value

    async def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, str] | None = None,
        data: dict[str, str] | None = None,
        json_body: dict[str, object] | None = None,
        token: str | None = None,
        write: bool,
        authenticated: bool,
    ) -> httpx.Response:
        headers = {"Accept": "application/json"}
        if authenticated:
            if token is None:
                raise HubSpotAPIError("connection_reauthorisation_required")
            headers["Authorization"] = f"Bearer {token}"
        timeout = httpx.Timeout(
            connect=self.settings.hubspot_connect_timeout_seconds,
            read=(self.settings.hubspot_write_timeout_seconds if write else self.settings.hubspot_read_timeout_seconds),
            write=self.settings.hubspot_write_timeout_seconds,
            pool=self.settings.hubspot_connect_timeout_seconds,
        )
        url = f"{self.settings.hubspot_api_base_url}{path}"
        try:
            if self._http_client is not None:
                response = await self._http_client.request(
                    method,
                    url,
                    params=params,
                    data=data,
                    json=json_body,
                    headers=headers,
                    timeout=timeout,
                )
            else:
                async with httpx.AsyncClient(timeout=timeout) as client:
                    response = await client.request(
                        method,
                        url,
                        params=params,
                        data=data,
                        json=json_body,
                        headers=headers,
                    )
        except httpx.TimeoutException as exc:
            raise HubSpotAPIError("provider_timeout", retryable=not write, uncertain=write) from exc
        except httpx.RequestError as exc:
            raise HubSpotAPIError("provider_unavailable", retryable=not write, uncertain=write) from exc
        if response.status_code in {401, 403}:
            raise HubSpotAPIError("connection_reauthorisation_required")
        if response.status_code == 429:
            retry_after = response.headers.get("Retry-After", "").strip()
            retry_after_seconds = int(retry_after) if retry_after.isdigit() else None
            raise HubSpotAPIError(
                "provider_rate_limited",
                retryable=True,
                uncertain=False,
                retry_after_seconds=retry_after_seconds,
            )
        if response.status_code == 404:
            raise HubSpotAPIError("external_object_not_found")
        if response.status_code >= 500:
            raise HubSpotAPIError("provider_unavailable", retryable=not write, uncertain=write)
        if response.status_code >= 400:
            raise HubSpotAPIError("provider_request_rejected")
        return response

    @staticmethod
    def _parse[T: BaseModel](model: type[T], response: httpx.Response) -> T:
        try:
            return model.model_validate_json(response.content)
        except ValidationError as exc:
            raise HubSpotAPIError("provider_response_invalid") from exc


class HubSpotCRMExecutor(ActionExecutor):
    definition = CONNECTOR_DEFINITIONS[ConnectorKey.HUBSPOT]

    def __init__(self, client: HubSpotClient) -> None:
        self.client = client

    async def validate_connection(self, context: ExecutorConnectionContext | None = None) -> None:
        if context is None or context.credential_reference is None:
            raise PermanentExecutionFailure(
                "connection_reauthorisation_required",
                "Reconnect HubSpot before using CRM sync.",
            )
        try:
            credential, metadata = await self.client.validate_credentials(context)
        except HubSpotAPIError as exc:
            raise PermanentExecutionFailure(
                "connection_reauthorisation_required",
                "Reconnect HubSpot before using CRM sync.",
            ) from exc
        if str(metadata.hub_id) != credential.external_account_id:
            raise PermanentExecutionFailure(
                "connection_account_changed",
                "The HubSpot account identity no longer matches this connection.",
            )

    def validate_action(self, action: ApprovedActionInput) -> None:
        target = action.external_target
        if target is None:
            raise PermanentExecutionFailure(
                "crm_mapping_missing",
                "Connect this RevenueOS record to a CRM record before reviewing the update.",
            )
        if isinstance(action.payload, OpportunityUpdatePayload):
            if target.external_object_type != "deals" or target.external_property_name is None:
                raise PermanentExecutionFailure("crm_mapping_invalid", "The CRM opportunity mapping is invalid.")
            if target.field_authority == CRMFieldAuthority.CRM_AUTHORITATIVE.value:
                raise PermanentExecutionFailure(
                    "crm_field_authoritative",
                    "HubSpot is the source of truth for this field, so RevenueOS will not overwrite it.",
                )
            if action.payload.field == "estimated_value" and action.revenueos_currency is None:
                raise PermanentExecutionFailure(
                    "currency_context_missing",
                    "The RevenueOS opportunity needs a currency before its amount can be updated.",
                )
        elif isinstance(action.payload, ContactUpdatePayload):
            if action.payload.operation != "update":
                raise PermanentExecutionFailure(
                    "contact_mapping_required",
                    "Link an existing HubSpot contact before updating it. Contact creation is not enabled.",
                )
            if target.external_object_type != "contacts" or target.external_property_name is None:
                raise PermanentExecutionFailure("crm_mapping_invalid", "The CRM contact mapping is invalid.")
            if target.field_authority == CRMFieldAuthority.CRM_AUTHORITATIVE.value:
                raise PermanentExecutionFailure(
                    "crm_field_authoritative",
                    "HubSpot is the source of truth for this field, so RevenueOS will not overwrite it.",
                )
        elif isinstance(action.payload, LogInteractionPayload):
            if target.external_object_type != "deals":
                raise PermanentExecutionFailure("crm_mapping_invalid", "The CRM opportunity mapping is invalid.")
        else:
            raise PermanentExecutionFailure("unsupported_action", "HubSpot cannot execute this approved Action.")

    async def current_external_state(
        self,
        action: ApprovedActionInput,
        context: ExecutorConnectionContext,
    ) -> object | None:
        self.validate_action(action)
        if isinstance(action.payload, LogInteractionPayload):
            return None
        assert action.external_target is not None
        property_name = cast(str, action.external_target.external_property_name)
        properties = [property_name]
        if isinstance(action.payload, OpportunityUpdatePayload) and action.payload.field == "estimated_value":
            properties.append("deal_currency_code")
        try:
            record = await self.client.get_record(
                context,
                action.external_target.external_object_type,
                action.external_target.external_object_id,
                tuple(properties),
            )
        except HubSpotAPIError as exc:
            self._raise_execution_failure(exc)
        current = self._normalise_value(
            record.properties.get(property_name),
            action.external_target.external_property_type,
        )
        currency = self._string_value(record.properties.get("deal_currency_code"))
        if (
            isinstance(action.payload, OpportunityUpdatePayload)
            and action.payload.field == "estimated_value"
            and currency is not None
            and action.revenueos_currency != currency.upper()
        ):
            raise PermanentExecutionFailure(
                "currency_mismatch",
                "HubSpot and RevenueOS use different currencies for this opportunity. No conversion was made.",
            )
        return HubSpotExternalState(current_value=current, updated_at=record.updated_at, currency=currency)

    def preview_execution(
        self,
        action: ApprovedActionInput,
        current_external_state: object | None,
    ) -> ExecutionPreviewContent:
        self.validate_action(action)
        if isinstance(action.payload, LogInteractionPayload):
            return CRMActivityExecutionPreview(
                kind="crm_activity",
                interaction_id=action.payload.interaction_id,
                occurred_at=action.payload.occurred_at,
                title=action.payload.title,
                summary=action.payload.summary,
                agreed_next_steps=action.payload.agreed_next_steps,
            )
        if not isinstance(current_external_state, HubSpotExternalState):
            raise PermanentExecutionFailure("external_state_unavailable", "The current CRM value could not be read.")
        assert action.external_target is not None
        capability: Literal["update_opportunity", "update_contact"] = (
            "update_opportunity" if isinstance(action.payload, OpportunityUpdatePayload) else "update_contact"
        )
        field = (
            action.payload.field
            if isinstance(action.payload, OpportunityUpdatePayload)
            else self._contact_field(action)
        )
        return CRMExecutionPreview(
            kind="crm",
            target_type="opportunity" if capability == "update_opportunity" else "contact",
            target_id=cast(UUID, action.target_entity_id),
            field=field,
            current_external_value=current_external_state.current_value,
            expected_external_value=current_external_state.current_value,
            new_value=action.external_target.proposed_external_value,
            field_authority=cast(
                Literal["crm_authoritative", "revenueos_authoritative", "review_before_sync"],
                action.external_target.field_authority,
            ),
            external_updated_at=current_external_state.updated_at,
            action=capability,
        )

    async def execute(
        self,
        action: ApprovedActionInput,
        *,
        idempotency_key: str,
        current_external_state: object | None,
        context: ExecutorConnectionContext | None = None,
    ) -> ExecutorResult:
        if context is None:
            raise PermanentExecutionFailure("connection_unavailable", "The HubSpot connection is unavailable.")
        self.validate_action(action)
        if isinstance(action.payload, LogInteractionPayload):
            return await self._create_activity(action, idempotency_key, context)
        if not isinstance(current_external_state, HubSpotExternalState):
            raise PermanentExecutionFailure("external_state_unavailable", "The current CRM value could not be read.")
        assert action.external_target is not None
        desired = action.external_target.proposed_external_value
        if current_external_state.current_value == desired:
            return ExecutorResult(
                external_result_id=action.external_target.external_object_id,
                object_type=action.external_target.external_object_type,
                object_key=self.object_key(action, idempotency_key),
                state={"reconciled": True},
                safe_message="HubSpot already contains the approved value. RevenueOS reconciled the result.",
            )
        property_name = cast(str, action.external_target.external_property_name)
        try:
            record = await self.client.update_record(
                context,
                action.external_target.external_object_type,
                action.external_target.external_object_id,
                {property_name: desired or ""},
            )
        except HubSpotAPIError as exc:
            if exc.uncertain:
                return await self._reconcile_uncertain_update(action, idempotency_key, context, current_external_state)
            self._raise_execution_failure(exc)
        applied = self._normalise_value(
            record.properties.get(property_name),
            action.external_target.external_property_type,
        )
        if applied != desired:
            refreshed = await self.current_external_state(action, context)
            if not isinstance(refreshed, HubSpotExternalState) or refreshed.current_value != desired:
                raise UnknownExternalStateFailure(
                    "unknown_external_state",
                    "HubSpot accepted the request but the final value could not be verified.",
                )
        return ExecutorResult(
            external_result_id=record.id,
            object_type=action.external_target.external_object_type,
            object_key=self.object_key(action, idempotency_key),
            state={"verified": True},
            safe_message="HubSpot was updated and the final mapped value was verified.",
        )

    async def _reconcile_uncertain_update(
        self,
        action: ApprovedActionInput,
        idempotency_key: str,
        context: ExecutorConnectionContext,
        expected: HubSpotExternalState,
    ) -> ExecutorResult:
        try:
            refreshed = await self.current_external_state(action, context)
        except (RetryableExecutionFailure, PermanentExecutionFailure):
            raise UnknownExternalStateFailure(
                "unknown_external_state",
                "The HubSpot outcome is unknown. RevenueOS will not retry until it can reconcile the record.",
            ) from None
        assert action.external_target is not None
        if (
            isinstance(refreshed, HubSpotExternalState)
            and refreshed.current_value == action.external_target.proposed_external_value
        ):
            return ExecutorResult(
                external_result_id=action.external_target.external_object_id,
                object_type=action.external_target.external_object_type,
                object_key=self.object_key(action, idempotency_key),
                state={"reconciled": True},
                safe_message="HubSpot applied the approved value; RevenueOS reconciled the uncertain response.",
            )
        if isinstance(refreshed, HubSpotExternalState) and refreshed.current_value == expected.current_value:
            raise RetryableExecutionFailure(
                "provider_timeout_not_applied",
                "HubSpot did not apply the update. RevenueOS may retry it safely.",
            )
        raise UnknownExternalStateFailure(
            "unknown_external_state",
            "The HubSpot record changed unexpectedly. RevenueOS will not retry this update.",
        )

    async def _create_activity(
        self,
        action: ApprovedActionInput,
        idempotency_key: str,
        context: ExecutorConnectionContext,
    ) -> ExecutorResult:
        payload = cast(LogInteractionPayload, action.payload)
        assert action.external_target is not None
        marker = f"RevenueOS execution {hashlib.sha256(idempotency_key.encode()).hexdigest()[:24]}"
        existing = await self._find_activity(context, marker)
        if len(existing) == 1:
            return ExecutorResult(
                external_result_id=existing[0].id,
                object_type="meetings",
                object_key=self.object_key(action, idempotency_key),
                state={"reconciled": True},
                safe_message="The HubSpot activity already exists. RevenueOS reconciled it without a duplicate.",
            )
        if len(existing) > 1:
            raise UnknownExternalStateFailure(
                "activity_reconciliation_ambiguous",
                "More than one matching HubSpot activity exists. RevenueOS will not create another.",
            )
        body = payload.summary
        if payload.agreed_next_steps:
            body += "\n\nAgreed next steps:\n" + "\n".join(f"• {item}" for item in payload.agreed_next_steps)
        try:
            record = await self.client.create_meeting(
                context,
                properties={
                    "hs_timestamp": payload.occurred_at.astimezone(UTC).isoformat(),
                    "hs_meeting_title": payload.title,
                    "hs_meeting_body": body,
                    "hs_internal_meeting_notes": marker,
                },
                deal_id=action.external_target.external_object_id,
            )
        except HubSpotAPIError as exc:
            if exc.uncertain:
                try:
                    matches = await self._find_activity(context, marker)
                except (RetryableExecutionFailure, PermanentExecutionFailure):
                    raise UnknownExternalStateFailure(
                        "unknown_external_state",
                        "The HubSpot activity outcome is unknown. RevenueOS will not create another.",
                    ) from None
                if len(matches) == 1:
                    record = matches[0]
                else:
                    raise UnknownExternalStateFailure(
                        "unknown_external_state",
                        "The HubSpot activity outcome is unknown. RevenueOS will not create another.",
                    ) from None
            else:
                self._raise_execution_failure(exc)
        return ExecutorResult(
            external_result_id=record.id,
            object_type="meetings",
            object_key=self.object_key(action, idempotency_key),
            state={"verified": True},
            safe_message="The reviewed interaction summary was logged in HubSpot. No transcript was sent.",
        )

    async def reconcile_activity(
        self,
        action: ApprovedActionInput,
        idempotency_key: str,
        context: ExecutorConnectionContext,
    ) -> ExecutorResult | None:
        """Read-only recovery check; never creates another activity."""
        if not isinstance(action.payload, LogInteractionPayload):
            raise PermanentExecutionFailure("unsupported_action", "This is not a HubSpot activity Action.")
        matches = await self._find_activity(
            context,
            f"RevenueOS execution {hashlib.sha256(idempotency_key.encode()).hexdigest()[:24]}",
        )
        if not matches:
            return None
        if len(matches) > 1:
            raise UnknownExternalStateFailure(
                "activity_reconciliation_ambiguous",
                "More than one matching HubSpot activity exists. RevenueOS will not retry.",
            )
        return ExecutorResult(
            external_result_id=matches[0].id,
            object_type="meetings",
            object_key=self.object_key(action, idempotency_key),
            state={"reconciled": True},
            safe_message="The HubSpot activity was found and reconciled without creating a duplicate.",
        )

    async def _find_activity(
        self,
        context: ExecutorConnectionContext,
        marker: str,
    ) -> list[HubSpotRecord]:
        try:
            return await self.client.search_by_property(
                context,
                "meetings",
                "hs_internal_meeting_notes",
                marker,
                ("hs_internal_meeting_notes",),
            )
        except HubSpotAPIError as exc:
            self._raise_execution_failure(exc)

    def object_key(self, action: ApprovedActionInput, idempotency_key: str) -> str:
        self.validate_action(action)
        assert action.external_target is not None
        if isinstance(action.payload, LogInteractionPayload):
            return f"hubspot:meeting:{hashlib.sha256(idempotency_key.encode()).hexdigest()[:24]}"
        return (
            f"hubspot:{action.external_target.external_object_type}:"
            f"{action.external_target.external_object_id}:{action.external_target.external_property_name}"
        )

    @staticmethod
    def _contact_field(action: ApprovedActionInput) -> str:
        payload = cast(ContactUpdatePayload, action.payload)
        candidates = {
            "first_name": payload.first_name,
            "last_name": payload.last_name,
            "email": payload.email,
            "job_title": payload.job_title,
        }
        changed = [field for field, value in candidates.items() if payload.current_values.get(field) != value]
        if len(changed) != 1:
            raise PermanentExecutionFailure(
                "crm_change_not_atomic",
                "The approved Contact update must change exactly one mapped field.",
            )
        return changed[0]

    @staticmethod
    def _normalise_value(value: object, property_type: str | None) -> str | None:
        raw = HubSpotCRMExecutor._string_value(value)
        if raw is None or raw == "":
            return None
        if property_type == "number":
            try:
                return format(Decimal(raw), "f")
            except InvalidOperation:
                return raw
        if property_type == "date" and "T" in raw:
            return raw.split("T", 1)[0]
        return raw

    @staticmethod
    def _string_value(value: object) -> str | None:
        if value is None:
            return None
        if isinstance(value, (str, int, float, Decimal)):
            return str(value)
        return None

    @staticmethod
    def _raise_execution_failure(error: HubSpotAPIError) -> NoReturn:
        safe_messages = {
            "connection_reauthorisation_required": "Reconnect HubSpot before using CRM sync.",
            "external_object_not_found": "The linked HubSpot record no longer exists.",
            "provider_rate_limited": "HubSpot is temporarily rate limiting this organisation.",
            "provider_unavailable": "HubSpot is temporarily unavailable.",
            "provider_timeout": "HubSpot did not respond in time.",
            "provider_request_rejected": "HubSpot rejected the mapped CRM change.",
            "provider_response_invalid": "HubSpot returned an unexpected response.",
            "association_capability_unavailable": "HubSpot activity association is unavailable.",
        }
        message = safe_messages.get(error.code, "The HubSpot connector could not complete this request.")
        if error.uncertain:
            raise UnknownExternalStateFailure("unknown_external_state", message)
        if error.retryable:
            raise RetryableExecutionFailure(
                error.code,
                message,
                retry_after_seconds=error.retry_after_seconds,
            )
        raise PermanentExecutionFailure(error.code, message)
