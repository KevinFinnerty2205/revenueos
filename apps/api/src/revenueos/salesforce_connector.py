from __future__ import annotations

import base64
import hashlib
import hmac
import re
from dataclasses import dataclass, replace
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Literal, NoReturn, cast
from urllib.parse import urlencode, urlparse
from uuid import UUID

import httpx
from pydantic import AliasChoices, BaseModel, ConfigDict, Field, ValidationError

from revenueos.action_contracts import ContactUpdatePayload, OpportunityUpdatePayload
from revenueos.config import Settings
from revenueos.credential_store import ConnectorCredential, CredentialStore
from revenueos.crm_provider import (
    CRMObjectType,
    CRMProviderError,
    CRMProviderOwner,
    CRMProviderPage,
    CRMProviderRecord,
    CRMProviderStage,
    CRMScalar,
    canonicalise_fields,
    provider_fields,
    rules_for,
)
from revenueos.domain import ConnectorKey, CRMFieldAuthority
from revenueos.integration_contracts import CRMExecutionPreview, ExecutionPreviewContent
from revenueos.integration_executors import (
    CONNECTOR_DEFINITIONS,
    ActionExecutor,
    ApprovedActionInput,
    ExecutorConnectionContext,
    ExecutorResult,
    PermanentExecutionFailure,
    UnknownExternalStateFailure,
)

SALESFORCE_REQUIRED_SCOPES = ("api", "openid", "refresh_token")
_SALESFORCE_ID = re.compile(r"^[A-Za-z0-9]{15}(?:[A-Za-z0-9]{3})?$")
_OBJECT_NAMES: dict[CRMObjectType, str] = {
    "account": "Account",
    "contact": "Contact",
    "opportunity": "Opportunity",
}


class SalesforceAPIError(CRMProviderError):
    pass


class _ProviderModel(BaseModel):
    model_config = ConfigDict(extra="ignore")


class _TokenResponse(_ProviderModel):
    access_token: str
    refresh_token: str | None = None
    instance_url: str | None = None
    identity_url: str | None = Field(default=None, validation_alias=AliasChoices("id", "identity_url"))
    issued_at: str | None = None
    signature: str | None = None
    scope: str = ""


class SalesforceIdentity(_ProviderModel):
    user_id: str = Field(validation_alias=AliasChoices("user_id", "sub"))
    organization_id: str = Field(validation_alias=AliasChoices("organization_id", "organizationId"))
    preferred_username: str | None = None
    name: str | None = None


@dataclass(frozen=True)
class SalesforceOAuthResult:
    credential: ConnectorCredential
    identity: SalesforceIdentity


@dataclass(frozen=True)
class SalesforceExternalState:
    record: CRMProviderRecord
    current_value: str | None
    currency: str | None


class _SalesforceRecord(_ProviderModel):
    id: str = Field(validation_alias="Id")
    name: str | None = Field(default=None, validation_alias="Name")
    website: str | None = Field(default=None, validation_alias="Website")
    industry: str | None = Field(default=None, validation_alias="Industry")
    owner_id: str | None = Field(default=None, validation_alias="OwnerId")
    system_modstamp: datetime = Field(validation_alias="SystemModstamp")
    last_modified_date: datetime = Field(validation_alias="LastModifiedDate")
    first_name: str | None = Field(default=None, validation_alias="FirstName")
    last_name: str | None = Field(default=None, validation_alias="LastName")
    email: str | None = Field(default=None, validation_alias="Email")
    phone: str | None = Field(default=None, validation_alias="Phone")
    title: str | None = Field(default=None, validation_alias="Title")
    account_id: str | None = Field(default=None, validation_alias="AccountId")
    stage_name: str | None = Field(default=None, validation_alias="StageName")
    amount: Decimal | None = Field(default=None, validation_alias="Amount")
    currency_iso_code: str | None = Field(default=None, validation_alias="CurrencyIsoCode")
    close_date: date | None = Field(default=None, validation_alias="CloseDate")
    description: str | None = Field(default=None, validation_alias="Description")
    next_step: str | None = Field(default=None, validation_alias="NextStep")
    is_deleted: bool = Field(default=False, validation_alias="IsDeleted")
    is_person_account: bool = Field(default=False, validation_alias="IsPersonAccount")


class _QueryResponse(_ProviderModel):
    records: list[_SalesforceRecord] = Field(default_factory=list)
    done: bool
    next_records_url: str | None = Field(default=None, validation_alias="nextRecordsUrl")


class _OwnerRecord(_ProviderModel):
    id: str = Field(validation_alias="Id")
    name: str | None = Field(default=None, validation_alias="Name")
    email: str | None = Field(default=None, validation_alias="Email")
    is_active: bool = Field(validation_alias="IsActive")


class _OwnerQueryResponse(_ProviderModel):
    records: list[_OwnerRecord] = Field(default_factory=list)


class _StageRecord(_ProviderModel):
    api_name: str = Field(validation_alias="ApiName")
    master_label: str = Field(validation_alias="MasterLabel")
    is_active: bool = Field(validation_alias="IsActive")


class _StageQueryResponse(_ProviderModel):
    records: list[_StageRecord] = Field(default_factory=list)


class _CreateResponse(_ProviderModel):
    id: str
    success: bool


class _DescribeField(_ProviderModel):
    name: str


class _DescribeResponse(_ProviderModel):
    fields: list[_DescribeField] = Field(default_factory=list)


def validate_salesforce_instance_url(value: str) -> str:
    """Accept only an HTTPS Salesforce origin returned by OAuth."""
    parsed = urlparse(value)
    host = (parsed.hostname or "").casefold()
    if (
        parsed.scheme != "https"
        or not host.endswith(".salesforce.com")
        or parsed.port is not None
        or parsed.username is not None
        or parsed.password is not None
        or parsed.path not in ("", "/")
        or parsed.params
        or parsed.query
        or parsed.fragment
    ):
        raise SalesforceAPIError("provider_instance_url_invalid")
    return f"https://{host}"


class SalesforceClient:
    """Direct REST adapter for a Salesforce External Client App."""

    provider_key = "salesforce"

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

    def authorisation_url(self, state: str, code_challenge: str) -> str:
        assert self.settings.salesforce_client_id is not None
        assert self.settings.salesforce_oauth_redirect_uri is not None
        query = urlencode(
            {
                "response_type": "code",
                "client_id": self.settings.salesforce_client_id,
                "redirect_uri": self.settings.salesforce_oauth_redirect_uri,
                "scope": " ".join(SALESFORCE_REQUIRED_SCOPES),
                "state": state,
                "code_challenge": code_challenge,
                "code_challenge_method": "S256",
            }
        )
        return f"{self.settings.salesforce_authorisation_base_url}?{query}"

    async def exchange_code(self, code: str, code_verifier: str) -> SalesforceOAuthResult:
        assert self.settings.salesforce_client_id is not None
        assert self.settings.salesforce_client_secret is not None
        assert self.settings.salesforce_oauth_redirect_uri is not None
        response = await self._oauth_request(
            self.settings.salesforce_token_url,
            {
                "grant_type": "authorization_code",
                "client_id": self.settings.salesforce_client_id,
                "client_secret": self.settings.salesforce_client_secret.get_secret_value(),
                "redirect_uri": self.settings.salesforce_oauth_redirect_uri,
                "code": code,
                "code_verifier": code_verifier,
            },
        )
        token = self._parse(_TokenResponse, response)
        if not token.refresh_token or not token.instance_url or not token.identity_url:
            raise SalesforceAPIError("provider_response_invalid")
        self._verify_token_signature(token)
        api_base_url = validate_salesforce_instance_url(token.instance_url)
        scopes = tuple(sorted(set(token.scope.split())))
        if set(SALESFORCE_REQUIRED_SCOPES) - set(scopes):
            raise SalesforceAPIError("missing_required_scope")
        temporary = ConnectorCredential(
            access_token=token.access_token,
            refresh_token=token.refresh_token,
            expires_at=datetime.now(UTC) + timedelta(hours=2),
            scopes=scopes,
            external_account_id="pending",
            api_base_url=api_base_url,
        )
        identity = await self._userinfo(temporary)
        identity_org, identity_user = self._identity_path(token.identity_url)
        if identity.organization_id != identity_org or identity.user_id != identity_user:
            raise SalesforceAPIError("provider_identity_mismatch")
        return SalesforceOAuthResult(
            credential=ConnectorCredential(
                access_token=temporary.access_token,
                refresh_token=temporary.refresh_token,
                expires_at=temporary.expires_at,
                scopes=temporary.scopes,
                external_account_id=identity.organization_id,
                api_base_url=api_base_url,
            ),
            identity=identity,
        )

    async def revoke(self, credential: ConnectorCredential) -> None:
        await self._oauth_request(
            self.settings.salesforce_revoke_url,
            {"token": credential.refresh_token},
            allow_empty=True,
        )

    async def validate_credentials(
        self,
        context: ExecutorConnectionContext,
    ) -> tuple[ConnectorCredential, SalesforceIdentity]:
        credential = await self._credential(context)
        if credential.expires_at.astimezone(UTC) <= datetime.now(UTC) + timedelta(seconds=60):
            credential = await self._refresh(context, force=False)
        try:
            identity = await self._userinfo(credential)
        except SalesforceAPIError as exc:
            if exc.code != "connection_reauthorisation_required":
                raise
            credential = await self._refresh(context, force=True)
            identity = await self._userinfo(credential)
        if identity.organization_id != credential.external_account_id:
            raise SalesforceAPIError("provider_identity_mismatch")
        return credential, identity

    async def validate_connection(self, context: ExecutorConnectionContext) -> None:
        credential, identity = await self.validate_credentials(context)
        if (
            context.external_tenant_id is not None and context.external_tenant_id != identity.organization_id
        ) or credential.external_account_id != identity.organization_id:
            raise SalesforceAPIError("provider_identity_mismatch")

    async def list_records(
        self,
        context: ExecutorConnectionContext,
        object_type: CRMObjectType,
        *,
        cursor: str | None,
        modified_after: datetime | None,
        limit: int,
    ) -> CRMProviderPage:
        del limit
        if cursor is not None:
            path = self._validate_query_cursor(cursor)
            response = await self._authenticated_request(context, "GET", path, write=False)
        else:
            object_name = _OBJECT_NAMES[object_type]
            include_person_account = object_type == "account" and await self._supports_field(
                context,
                object_name,
                "IsPersonAccount",
            )
            include_currency = object_type == "opportunity" and await self._supports_field(
                context,
                object_name,
                "CurrencyIsoCode",
            )
            selected = self._selected_fields(
                object_type,
                include_person_account=include_person_account,
                include_currency=include_currency,
            )
            where = ""
            if modified_after is not None:
                watermark = modified_after.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
                where = f" WHERE SystemModstamp >= {watermark}"
            query = f"SELECT {','.join(selected)} FROM {object_name}{where} ORDER BY SystemModstamp, Id"
            response = await self._authenticated_request(
                context,
                "GET",
                f"/services/data/{self.settings.salesforce_api_version}/queryAll",
                params={"q": query},
                extra_headers={"Sforce-Query-Options": "batchSize=200"},
                write=False,
            )
        parsed = self._parse(_QueryResponse, response)
        records = tuple(self._normalise_record(object_type, item) for item in parsed.records)
        high_watermark = max(
            (item.system_modstamp.astimezone(UTC) for item in parsed.records),
            default=modified_after or datetime.now(UTC),
        )
        return CRMProviderPage(
            records=records,
            next_cursor=None if parsed.done else self._validate_query_cursor(parsed.next_records_url or ""),
            high_watermark_at=high_watermark,
        )

    async def get_record(
        self,
        context: ExecutorConnectionContext,
        object_type: CRMObjectType,
        external_object_id: str,
    ) -> CRMProviderRecord:
        self._validate_id(external_object_id)
        include_person_account = object_type == "account" and await self._supports_field(
            context,
            _OBJECT_NAMES[object_type],
            "IsPersonAccount",
        )
        include_currency = object_type == "opportunity" and await self._supports_field(
            context,
            _OBJECT_NAMES[object_type],
            "CurrencyIsoCode",
        )
        response = await self._authenticated_request(
            context,
            "GET",
            f"/services/data/{self.settings.salesforce_api_version}/sobjects/"
            f"{_OBJECT_NAMES[object_type]}/{external_object_id}",
            params={
                "fields": ",".join(
                    self._selected_fields(
                        object_type,
                        include_person_account=include_person_account,
                        include_currency=include_currency,
                    )
                )
            },
            write=False,
        )
        return self._normalise_record(object_type, self._parse(_SalesforceRecord, response))

    async def search_records(
        self,
        context: ExecutorConnectionContext,
        object_type: CRMObjectType,
        query_text: str,
        *,
        limit: int = 10,
    ) -> tuple[CRMProviderRecord, ...]:
        escaped = query_text.replace("\\", "\\\\").replace("'", "\\'").replace("%", "\\%").replace("_", "\\_")
        object_name = _OBJECT_NAMES[object_type]
        include_person_account = object_type == "account" and await self._supports_field(
            context,
            object_name,
            "IsPersonAccount",
        )
        include_currency = object_type == "opportunity" and await self._supports_field(
            context,
            object_name,
            "CurrencyIsoCode",
        )
        selected = self._selected_fields(
            object_type,
            include_person_account=include_person_account,
            include_currency=include_currency,
        )
        conditions = [f"Name LIKE '%{escaped}%'"]
        if object_type == "contact":
            conditions.append(f"Email LIKE '%{escaped}%'")
        soql = (
            f"SELECT {','.join(selected)} FROM {object_name} WHERE "
            f"({' OR '.join(conditions)}) ORDER BY LastModifiedDate DESC LIMIT {min(max(limit, 1), 10)}"
        )
        response = await self._authenticated_request(
            context,
            "GET",
            f"/services/data/{self.settings.salesforce_api_version}/query",
            params={"q": soql},
            write=False,
        )
        parsed = self._parse(_QueryResponse, response)
        return tuple(self._normalise_record(object_type, item) for item in parsed.records)

    async def create_record(
        self,
        context: ExecutorConnectionContext,
        object_type: CRMObjectType,
        fields: dict[str, CRMScalar],
    ) -> CRMProviderRecord:
        await self._require_currency_capability(context, object_type, fields)
        payload = self._provider_payload(object_type, fields)
        response = await self._authenticated_request(
            context,
            "POST",
            f"/services/data/{self.settings.salesforce_api_version}/sobjects/{_OBJECT_NAMES[object_type]}",
            json_body=payload,
            write=True,
        )
        created = self._parse(_CreateResponse, response)
        if not created.success:
            raise SalesforceAPIError("provider_request_rejected")
        try:
            return await self.get_record(context, object_type, created.id)
        except CRMProviderError as exc:
            raise SalesforceAPIError(
                "provider_create_verification_unknown",
                uncertain=True,
                external_object_id=created.id,
            ) from exc

    async def update_record(
        self,
        context: ExecutorConnectionContext,
        record: CRMProviderRecord,
        fields: dict[str, CRMScalar],
    ) -> CRMProviderRecord:
        self._validate_id(record.external_object_id)
        await self._require_currency_capability(context, record.object_type, fields)
        payload = self._provider_payload(record.object_type, fields)
        await self._authenticated_request(
            context,
            "PATCH",
            f"/services/data/{self.settings.salesforce_api_version}/sobjects/"
            f"{_OBJECT_NAMES[record.object_type]}/{record.external_object_id}",
            json_body=payload,
            extra_headers={
                "If-Unmodified-Since": record.modified_at.astimezone(UTC).strftime("%a, %d %b %Y %H:%M:%S GMT")
            },
            write=True,
            allow_empty=True,
        )
        try:
            return await self.get_record(context, record.object_type, record.external_object_id)
        except CRMProviderError as exc:
            raise SalesforceAPIError(
                "provider_update_verification_unknown",
                uncertain=True,
                external_object_id=record.external_object_id,
            ) from exc

    async def owners(self, context: ExecutorConnectionContext) -> tuple[CRMProviderOwner, ...]:
        query = "SELECT Id,Name,Email,IsActive FROM User WHERE UserType = 'Standard' ORDER BY Name LIMIT 200"
        response = await self._authenticated_request(
            context,
            "GET",
            f"/services/data/{self.settings.salesforce_api_version}/query",
            params={"q": query},
            write=False,
        )
        parsed = self._parse(_OwnerQueryResponse, response)
        return tuple(CRMProviderOwner(item.id, item.name, item.email, item.is_active) for item in parsed.records)

    async def stages(self, context: ExecutorConnectionContext) -> tuple[CRMProviderStage, ...]:
        query = "SELECT ApiName,MasterLabel,IsActive FROM OpportunityStage ORDER BY SortOrder LIMIT 200"
        response = await self._authenticated_request(
            context,
            "GET",
            f"/services/data/{self.settings.salesforce_api_version}/query",
            params={"q": query},
            write=False,
        )
        parsed = self._parse(_StageQueryResponse, response)
        return tuple(
            CRMProviderStage("default", "Salesforce", item.api_name, item.master_label, item.is_active)
            for item in parsed.records
        )

    async def _credential(self, context: ExecutorConnectionContext) -> ConnectorCredential:
        if context.credential_reference is None:
            raise SalesforceAPIError("connection_reauthorisation_required")
        try:
            credential = await self.credential_store.get(
                context.organisation_id,
                context.connection_id,
                context.credential_reference,
            )
        except ValueError as exc:
            raise SalesforceAPIError("connection_reauthorisation_required") from exc
        if credential.api_base_url is None:
            raise SalesforceAPIError("connection_reauthorisation_required")
        validate_salesforce_instance_url(credential.api_base_url)
        return credential

    async def _authenticated_request(
        self,
        context: ExecutorConnectionContext,
        method: str,
        path: str,
        *,
        params: dict[str, str] | None = None,
        json_body: dict[str, object] | None = None,
        extra_headers: dict[str, str] | None = None,
        write: bool,
        allow_empty: bool = False,
    ) -> httpx.Response:
        credential = await self._credential(context)
        if credential.expires_at.astimezone(UTC) <= datetime.now(UTC) + timedelta(seconds=60):
            credential = await self._refresh(context, force=False)
        try:
            return await self._api_request(
                credential,
                method,
                path,
                params=params,
                json_body=json_body,
                extra_headers=extra_headers,
                write=write,
                allow_empty=allow_empty,
            )
        except SalesforceAPIError as exc:
            if exc.code != "connection_reauthorisation_required":
                raise
        credential = await self._refresh(context, force=True)
        return await self._api_request(
            credential,
            method,
            path,
            params=params,
            json_body=json_body,
            extra_headers=extra_headers,
            write=write,
            allow_empty=allow_empty,
        )

    async def _refresh(
        self,
        context: ExecutorConnectionContext,
        *,
        force: bool,
    ) -> ConnectorCredential:
        if context.credential_reference is None:
            raise SalesforceAPIError("connection_reauthorisation_required")
        try:
            current = await self.credential_store.get_for_update(
                context.organisation_id,
                context.connection_id,
                context.credential_reference,
            )
        except ValueError as exc:
            raise SalesforceAPIError("connection_reauthorisation_required") from exc
        if not force and current.expires_at.astimezone(UTC) > datetime.now(UTC) + timedelta(seconds=60):
            return current
        assert self.settings.salesforce_client_id is not None
        assert self.settings.salesforce_client_secret is not None
        try:
            response = await self._oauth_request(
                self.settings.salesforce_token_url,
                {
                    "grant_type": "refresh_token",
                    "client_id": self.settings.salesforce_client_id,
                    "client_secret": self.settings.salesforce_client_secret.get_secret_value(),
                    "refresh_token": current.refresh_token,
                },
            )
            token = self._parse(_TokenResponse, response)
        except SalesforceAPIError as exc:
            raise SalesforceAPIError("connection_reauthorisation_required") from exc
        api_base_url = (
            validate_salesforce_instance_url(token.instance_url)
            if token.instance_url is not None
            else current.api_base_url
        )
        refreshed = ConnectorCredential(
            access_token=token.access_token,
            refresh_token=token.refresh_token or current.refresh_token,
            expires_at=datetime.now(UTC) + timedelta(hours=2),
            scopes=current.scopes,
            external_account_id=current.external_account_id,
            api_base_url=api_base_url,
            schema_version=current.schema_version,
            schema_capabilities=current.schema_capabilities,
        )
        await self.credential_store.put(context.organisation_id, context.connection_id, refreshed)
        return refreshed

    async def _userinfo(self, credential: ConnectorCredential) -> SalesforceIdentity:
        response = await self._api_request(
            credential,
            "GET",
            "/services/oauth2/userinfo",
            write=False,
        )
        return self._parse(SalesforceIdentity, response)

    async def _api_request(
        self,
        credential: ConnectorCredential,
        method: str,
        path: str,
        *,
        params: dict[str, str] | None = None,
        json_body: dict[str, object] | None = None,
        extra_headers: dict[str, str] | None = None,
        write: bool,
        allow_empty: bool = False,
    ) -> httpx.Response:
        if credential.api_base_url is None:
            raise SalesforceAPIError("connection_reauthorisation_required")
        base_url = validate_salesforce_instance_url(credential.api_base_url)
        if not path.startswith("/") or path.startswith("//"):
            raise SalesforceAPIError("provider_cursor_invalid")
        headers = {"Accept": "application/json", "Authorization": f"Bearer {credential.access_token}"}
        if extra_headers:
            headers.update(extra_headers)
        response = await self._send(
            method,
            f"{base_url}{path}",
            params=params,
            json_body=json_body,
            headers=headers,
            write=write,
        )
        self._raise_for_status(response, write=write)
        if not allow_empty and len(response.content) > self.settings.crm_sync_max_response_bytes:
            raise SalesforceAPIError("provider_response_too_large")
        return response

    async def _oauth_request(
        self,
        url: str,
        data: dict[str, str],
        *,
        allow_empty: bool = False,
    ) -> httpx.Response:
        response = await self._send(
            "POST",
            url,
            data=data,
            headers={"Accept": "application/json"},
            write=False,
        )
        self._raise_for_status(response, write=False)
        if not allow_empty and len(response.content) > self.settings.crm_sync_max_response_bytes:
            raise SalesforceAPIError("provider_response_too_large")
        return response

    async def _send(
        self,
        method: str,
        url: str,
        *,
        params: dict[str, str] | None = None,
        data: dict[str, str] | None = None,
        json_body: dict[str, object] | None = None,
        headers: dict[str, str],
        write: bool,
    ) -> httpx.Response:
        timeout = httpx.Timeout(
            connect=self.settings.salesforce_connect_timeout_seconds,
            read=(
                self.settings.salesforce_write_timeout_seconds
                if write
                else self.settings.salesforce_read_timeout_seconds
            ),
            write=self.settings.salesforce_write_timeout_seconds,
            pool=self.settings.salesforce_connect_timeout_seconds,
        )
        try:
            if self._http_client is not None:
                return await self._http_client.request(
                    method,
                    url,
                    params=params,
                    data=data,
                    json=json_body,
                    headers=headers,
                    timeout=timeout,
                )
            async with httpx.AsyncClient(timeout=timeout) as client:
                return await client.request(
                    method,
                    url,
                    params=params,
                    data=data,
                    json=json_body,
                    headers=headers,
                )
        except httpx.TimeoutException as exc:
            raise SalesforceAPIError("provider_timeout", retryable=not write, uncertain=write) from exc
        except httpx.RequestError as exc:
            raise SalesforceAPIError("provider_unavailable", retryable=not write, uncertain=write) from exc

    @staticmethod
    def _raise_for_status(response: httpx.Response, *, write: bool) -> None:
        if response.status_code in {401, 403}:
            if b"REQUEST_LIMIT_EXCEEDED" in response.content:
                raise SalesforceAPIError("provider_rate_limited", retryable=True)
            raise SalesforceAPIError("connection_reauthorisation_required")
        if response.status_code == 404:
            raise SalesforceAPIError("external_object_not_found")
        if response.status_code == 412:
            raise SalesforceAPIError("stale_external_state")
        if response.status_code == 429:
            retry_after = response.headers.get("Retry-After", "").strip()
            raise SalesforceAPIError(
                "provider_rate_limited",
                retryable=True,
                retry_after_seconds=int(retry_after) if retry_after.isdigit() else None,
            )
        if response.status_code >= 500:
            raise SalesforceAPIError("provider_unavailable", retryable=not write, uncertain=write)
        if response.status_code >= 400:
            raise SalesforceAPIError("provider_request_rejected")

    def _verify_token_signature(self, token: _TokenResponse) -> None:
        if token.identity_url is None or token.issued_at is None or token.signature is None:
            raise SalesforceAPIError("provider_response_invalid")
        assert self.settings.salesforce_client_secret is not None
        digest = hmac.new(
            self.settings.salesforce_client_secret.get_secret_value().encode(),
            f"{token.identity_url}{token.issued_at}".encode(),
            hashlib.sha256,
        ).digest()
        expected = base64.b64encode(digest).decode()
        if not hmac.compare_digest(expected, token.signature):
            raise SalesforceAPIError("provider_signature_invalid")

    @staticmethod
    def _identity_path(value: str) -> tuple[str, str]:
        parsed = urlparse(value)
        parts = [part for part in parsed.path.split("/") if part]
        if (
            parsed.scheme != "https"
            or parsed.hostname not in {"login.salesforce.com", "test.salesforce.com"}
            or len(parts) != 3
            or parts[0] != "id"
            or not _SALESFORCE_ID.fullmatch(parts[1])
            or not _SALESFORCE_ID.fullmatch(parts[2])
        ):
            raise SalesforceAPIError("provider_identity_invalid")
        return parts[1], parts[2]

    async def _supports_field(
        self,
        context: ExecutorConnectionContext,
        object_name: str,
        field_name: str,
    ) -> bool:
        credential = await self._credential(context)
        capability = f"{object_name}.{field_name}"
        described_marker = f"described:{object_name}"
        if (
            credential.schema_version == self.settings.salesforce_api_version
            and described_marker in credential.schema_capabilities
        ):
            return capability in credential.schema_capabilities
        response = await self._authenticated_request(
            context,
            "GET",
            f"/services/data/{self.settings.salesforce_api_version}/sobjects/{object_name}/describe",
            write=False,
        )
        described = self._parse(_DescribeResponse, response)
        allowed_capabilities = {
            "Account": {"IsPersonAccount"},
            "Opportunity": {"CurrencyIsoCode"},
        }.get(object_name, set())
        supported = {f"{object_name}.{field.name}" for field in described.fields if field.name in allowed_capabilities}
        if context.credential_reference is None:
            raise SalesforceAPIError("connection_reauthorisation_required")
        try:
            current = await self.credential_store.get_for_update(
                context.organisation_id,
                context.connection_id,
                context.credential_reference,
            )
        except ValueError as exc:
            raise SalesforceAPIError("connection_reauthorisation_required") from exc
        existing_capabilities = (
            set(current.schema_capabilities)
            if current.schema_version == self.settings.salesforce_api_version
            else set()
        )
        existing_capabilities.add(described_marker)
        existing_capabilities.update(supported)
        capabilities = tuple(sorted(existing_capabilities))
        await self.credential_store.put(
            context.organisation_id,
            context.connection_id,
            replace(
                current,
                schema_version=self.settings.salesforce_api_version,
                schema_capabilities=capabilities,
            ),
        )
        return capability in capabilities

    def _selected_fields(
        self,
        object_type: CRMObjectType,
        *,
        include_person_account: bool = False,
        include_currency: bool = False,
    ) -> tuple[str, ...]:
        fields = [
            field
            for field in provider_fields(self.provider_key, object_type)
            if field != "CurrencyIsoCode" or include_currency
        ]
        for required in ("Id", "SystemModstamp", "LastModifiedDate", "IsDeleted"):
            if required not in fields:
                fields.append(required)
        if include_person_account and "IsPersonAccount" not in fields:
            fields.append("IsPersonAccount")
        return tuple(fields)

    async def _require_currency_capability(
        self,
        context: ExecutorConnectionContext,
        object_type: CRMObjectType,
        fields: dict[str, CRMScalar],
    ) -> None:
        if object_type != "opportunity" or not {"estimated_value", "currency"}.intersection(fields):
            return
        if not await self._supports_field(context, "Opportunity", "CurrencyIsoCode"):
            raise SalesforceAPIError("provider_currency_capability_required")

    def _normalise_record(
        self,
        object_type: CRMObjectType,
        record: _SalesforceRecord,
    ) -> CRMProviderRecord:
        if object_type == "account" and record.is_person_account:
            raise SalesforceAPIError("provider_person_account_unsupported")
        values: dict[str, object] = {
            "Name": record.name,
            "Website": record.website,
            "Industry": record.industry,
            "OwnerId": record.owner_id,
            "FirstName": record.first_name,
            "LastName": record.last_name,
            "Email": record.email,
            "Phone": record.phone,
            "Title": record.title,
            "AccountId": record.account_id,
            "StageName": record.stage_name,
            "Amount": record.amount,
            "CurrencyIsoCode": record.currency_iso_code,
            "CloseDate": record.close_date,
            "Description": record.description,
            "NextStep": record.next_step,
        }
        return CRMProviderRecord(
            object_type=object_type,
            external_object_id=record.id,
            fields=canonicalise_fields(self.provider_key, object_type, values),
            external_version=record.system_modstamp.astimezone(UTC).isoformat(),
            modified_at=record.system_modstamp.astimezone(UTC),
            owner_external_id=record.owner_id,
            related_account_external_id=record.account_id,
            archived=record.is_deleted,
        )

    def _provider_payload(
        self,
        object_type: CRMObjectType,
        fields: dict[str, CRMScalar],
    ) -> dict[str, object]:
        rules = {rule.canonical_field: rule.provider_field for rule in rules_for(self.provider_key, object_type)}
        payload: dict[str, object] = {}
        for field, value in fields.items():
            provider_field = rules.get(field)
            if provider_field is None:
                continue
            if isinstance(value, (date, datetime)):
                payload[provider_field] = value.isoformat()
            elif isinstance(value, Decimal):
                if not value.is_finite():
                    raise SalesforceAPIError("provider_value_invalid")
                payload[provider_field] = format(value, "f")
            elif value is None or isinstance(value, (str, int, bool, float)):
                payload[provider_field] = value
        if not payload:
            raise SalesforceAPIError("provider_value_invalid")
        return payload

    def _validate_query_cursor(self, value: str) -> str:
        prefix = f"/services/data/{self.settings.salesforce_api_version}/query/"
        if not value.startswith(prefix) or "//" in value or urlparse(value).scheme or len(value) > 2048:
            raise SalesforceAPIError("provider_cursor_invalid")
        return value

    @staticmethod
    def _validate_id(value: str) -> None:
        if not _SALESFORCE_ID.fullmatch(value):
            raise SalesforceAPIError("external_object_id_invalid")

    @staticmethod
    def _parse[T: BaseModel](model: type[T], response: httpx.Response) -> T:
        try:
            return model.model_validate_json(response.content)
        except ValidationError as exc:
            raise SalesforceAPIError("provider_response_invalid") from exc


class SalesforceCRMExecutor(ActionExecutor):
    definition = CONNECTOR_DEFINITIONS[ConnectorKey.SALESFORCE]

    def __init__(self, client: SalesforceClient) -> None:
        self.client = client

    async def validate_connection(self, context: ExecutorConnectionContext | None = None) -> None:
        if context is None:
            raise PermanentExecutionFailure(
                "connection_reauthorisation_required",
                "Reconnect Salesforce before using CRM sync.",
            )
        try:
            await self.client.validate_connection(context)
        except SalesforceAPIError as exc:
            raise PermanentExecutionFailure(
                "connection_reauthorisation_required",
                "Reconnect Salesforce before using CRM sync.",
            ) from exc

    def validate_action(self, action: ApprovedActionInput) -> None:
        target = action.external_target
        if target is None or target.external_property_name is None:
            raise PermanentExecutionFailure(
                "crm_mapping_missing",
                "Connect this Oryntela record to a Salesforce record before reviewing the update.",
            )
        if isinstance(action.payload, OpportunityUpdatePayload):
            expected_type = "opportunity"
            if action.payload.field == "estimated_value" and action.revenueos_currency is None:
                raise PermanentExecutionFailure(
                    "currency_context_missing",
                    "The Oryntela opportunity needs a currency before its amount can be updated.",
                )
        elif isinstance(action.payload, ContactUpdatePayload):
            if action.payload.operation != "update":
                raise PermanentExecutionFailure(
                    "contact_mapping_required",
                    "Use reviewed CRM writeback to create a Salesforce contact.",
                )
            expected_type = "contact"
        else:
            raise PermanentExecutionFailure("unsupported_action", "Salesforce cannot execute this approved Action.")
        if target.external_object_type != expected_type:
            raise PermanentExecutionFailure("crm_mapping_invalid", "The Salesforce CRM mapping is invalid.")
        if target.field_authority == CRMFieldAuthority.CRM_AUTHORITATIVE.value:
            raise PermanentExecutionFailure(
                "crm_field_authoritative",
                "Salesforce is the source of truth for this field, so Oryntela will not overwrite it.",
            )

    async def current_external_state(
        self,
        action: ApprovedActionInput,
        context: ExecutorConnectionContext,
    ) -> SalesforceExternalState:
        self.validate_action(action)
        assert action.external_target is not None
        assert action.external_target.external_property_name is not None
        object_type = cast(CRMObjectType, action.external_target.external_object_type)
        try:
            record = await self.client.get_record(
                context,
                object_type,
                action.external_target.external_object_id,
            )
        except SalesforceAPIError as exc:
            raise_salesforce_execution_failure(exc)
        canonical_field = self._canonical_field(object_type, action.external_target.external_property_name)
        current = self._string_value(record.fields.get(canonical_field))
        currency = self._string_value(record.fields.get("currency"))
        if isinstance(action.payload, OpportunityUpdatePayload) and action.payload.field == "estimated_value":
            if currency is None:
                raise PermanentExecutionFailure(
                    "currency_context_unavailable",
                    "Salesforce did not expose an explicit opportunity currency, so no amount update was prepared.",
                )
            if action.revenueos_currency == currency.upper():
                return SalesforceExternalState(record, current, currency)
            raise PermanentExecutionFailure(
                "currency_mismatch",
                "Salesforce and Oryntela use different currencies for this opportunity. No conversion was made.",
            )
        return SalesforceExternalState(record, current, currency)

    def preview_execution(
        self,
        action: ApprovedActionInput,
        current_external_state: object | None,
    ) -> ExecutionPreviewContent:
        self.validate_action(action)
        if not isinstance(current_external_state, SalesforceExternalState):
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
            external_updated_at=current_external_state.record.modified_at,
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
        if context is None or not isinstance(current_external_state, SalesforceExternalState):
            raise PermanentExecutionFailure("connection_unavailable", "The Salesforce connection is unavailable.")
        self.validate_action(action)
        assert action.external_target is not None
        assert action.external_target.external_property_name is not None
        desired = action.external_target.proposed_external_value
        if current_external_state.current_value == desired:
            return ExecutorResult(
                external_result_id=action.external_target.external_object_id,
                object_type=action.external_target.external_object_type,
                object_key=self.object_key(action, idempotency_key),
                state={"reconciled": True},
                safe_message="Salesforce already contains the approved value. Oryntela reconciled the result.",
            )
        object_type = cast(CRMObjectType, action.external_target.external_object_type)
        canonical_field = self._canonical_field(object_type, action.external_target.external_property_name)
        try:
            record = await self.client.update_record(
                context,
                current_external_state.record,
                {canonical_field: desired},
            )
        except SalesforceAPIError as exc:
            if exc.uncertain:
                return await self._reconcile_uncertain(action, idempotency_key, context, canonical_field, desired)
            raise_salesforce_execution_failure(exc)
        if self._string_value(record.fields.get(canonical_field)) != desired:
            raise UnknownExternalStateFailure(
                "unknown_external_state",
                "Salesforce accepted the request but the final value could not be verified.",
            )
        return ExecutorResult(
            external_result_id=record.external_object_id,
            object_type=object_type,
            object_key=self.object_key(action, idempotency_key),
            state={"verified": True, "external_version": record.external_version},
            safe_message="The reviewed Salesforce update was applied and verified.",
        )

    async def _reconcile_uncertain(
        self,
        action: ApprovedActionInput,
        idempotency_key: str,
        context: ExecutorConnectionContext,
        canonical_field: str,
        desired: str | None,
    ) -> ExecutorResult:
        assert action.external_target is not None
        object_type = cast(CRMObjectType, action.external_target.external_object_type)
        try:
            record = await self.client.get_record(context, object_type, action.external_target.external_object_id)
        except SalesforceAPIError as exc:
            raise UnknownExternalStateFailure(
                "unknown_external_state",
                "Salesforce may have accepted the request. Oryntela could not yet reconcile it.",
            ) from exc
        if self._string_value(record.fields.get(canonical_field)) != desired:
            raise UnknownExternalStateFailure(
                "unknown_external_state",
                "Salesforce may have accepted the request. Review its current value before retrying.",
            )
        return ExecutorResult(
            external_result_id=record.external_object_id,
            object_type=object_type,
            object_key=self.object_key(action, idempotency_key),
            state={"reconciled": True, "external_version": record.external_version},
            safe_message="Oryntela reconciled the reviewed Salesforce update after an uncertain response.",
        )

    def object_key(self, action: ApprovedActionInput, idempotency_key: str) -> str:
        del idempotency_key
        self.validate_action(action)
        assert action.external_target is not None
        return (
            f"salesforce:{action.external_target.external_object_type}:"
            f"{action.external_target.external_object_id}:{action.external_target.external_property_name}"
        )

    @staticmethod
    def _canonical_field(object_type: CRMObjectType, provider_field: str) -> str:
        for rule in rules_for("salesforce", object_type):
            if rule.provider_field == provider_field:
                return rule.canonical_field
        raise PermanentExecutionFailure("crm_mapping_invalid", "The Salesforce CRM field mapping is invalid.")

    @staticmethod
    def _contact_field(action: ApprovedActionInput) -> str:
        if not isinstance(action.payload, ContactUpdatePayload):
            raise PermanentExecutionFailure("crm_mapping_invalid", "The Salesforce CRM field mapping is invalid.")
        changed = [
            field
            for field in ("first_name", "last_name", "email", "job_title")
            if action.payload.current_values.get(field) != getattr(action.payload, field)
        ]
        if len(changed) != 1:
            raise PermanentExecutionFailure(
                "crm_change_not_atomic",
                "The reviewed CRM update must change exactly one supported field.",
            )
        return changed[0]

    @staticmethod
    def _string_value(value: CRMScalar) -> str | None:
        if value is None:
            return None
        if isinstance(value, datetime):
            return value.astimezone(UTC).isoformat()
        return str(value)


def raise_salesforce_execution_failure(error: SalesforceAPIError) -> NoReturn:
    """Import-light bridge used by the reviewed Action executor."""
    from revenueos.integration_executors import (
        PermanentExecutionFailure,
        RetryableExecutionFailure,
        UnknownExternalStateFailure,
    )

    if error.uncertain:
        raise UnknownExternalStateFailure(
            "unknown_external_state",
            "Salesforce may have accepted the request. Oryntela will reconcile before another write.",
        ) from error
    if error.retryable:
        raise RetryableExecutionFailure(
            error.code,
            "Salesforce is temporarily unavailable. Oryntela will retry safely.",
            retry_after_seconds=error.retry_after_seconds,
        ) from error
    raise PermanentExecutionFailure(error.code, "Salesforce rejected the reviewed CRM update.") from error
