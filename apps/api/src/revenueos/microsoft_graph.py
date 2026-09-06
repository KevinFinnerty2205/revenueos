from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import cast
from urllib.parse import urlencode, urlsplit

import httpx
import jwt
from jwt import PyJWK
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from revenueos.action_contracts import FollowUpEmailPayload, PersonalizedOutreachPayload
from revenueos.config import Settings
from revenueos.credential_store import ConnectorCredential, CredentialStore
from revenueos.domain import ConnectorKey
from revenueos.integration_contracts import EmailExecutionPreview, ExecutionPreviewContent
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
from revenueos.models import ProviderOutboundOperation

MICROSOFT_SCOPES = (
    "openid",
    "offline_access",
    "User.Read",
    "Mail.Send",
    "Mail.Read",
    "Calendars.ReadBasic",
)
MICROSOFT_GRAPH_SCOPES = frozenset({"User.Read", "Mail.Send", "Mail.Read", "Calendars.ReadBasic"})
_CONSUMER_TENANT_ID = "9188040d-6c67-4c5b-b112-36a304b66dad"
_EMAIL = re.compile(r"[^\s@]+@[^\s@]+\.[^\s@]+")


class MicrosoftAPIError(Exception):
    def __init__(
        self,
        code: str,
        *,
        retryable: bool = False,
        uncertain: bool = False,
        retry_after_seconds: int | None = None,
        status_code: int | None = None,
    ) -> None:
        super().__init__(code)
        self.code = code
        self.retryable = retryable
        self.uncertain = uncertain
        self.retry_after_seconds = retry_after_seconds
        self.status_code = status_code


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="ignore")


class _TokenResponse(_StrictModel):
    access_token: str = Field(min_length=1, max_length=16_384)
    refresh_token: str | None = Field(default=None, min_length=1, max_length=16_384)
    expires_in: int = Field(gt=0, le=86_400)
    scope: str = Field(min_length=1, max_length=2_048)
    id_token: str | None = Field(default=None, min_length=1, max_length=16_384)


class MicrosoftProfile(_StrictModel):
    id: str = Field(min_length=1, max_length=128)
    display_name: str = Field(alias="displayName", min_length=1, max_length=200)
    mail: str | None = Field(default=None, max_length=320)
    user_principal_name: str = Field(alias="userPrincipalName", min_length=1, max_length=320)

    @property
    def email(self) -> str:
        return self.mail or self.user_principal_name


@dataclass(frozen=True)
class MicrosoftOAuthResult:
    credential: ConnectorCredential
    profile: MicrosoftProfile
    tenant_id: str


class MicrosoftGraphClient:
    """Bounded Microsoft identity and Graph adapter; raw provider payloads are never logged."""

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

    def authorisation_url(self, state: str, challenge: str, nonce: str) -> str:
        assert self.settings.microsoft_client_id is not None
        assert self.settings.microsoft_oauth_redirect_uri is not None
        query = urlencode(
            {
                "client_id": self.settings.microsoft_client_id,
                "response_type": "code",
                "redirect_uri": self.settings.microsoft_oauth_redirect_uri,
                "response_mode": "query",
                "scope": " ".join(MICROSOFT_SCOPES),
                "state": state,
                "nonce": nonce,
                "code_challenge": challenge,
                "code_challenge_method": "S256",
                "prompt": "select_account",
            }
        )
        return f"{self.settings.microsoft_authorisation_base_url}?{query}"

    async def exchange_code(
        self,
        code: str,
        code_verifier: str,
        expected_nonce_hash: str,
    ) -> MicrosoftOAuthResult:
        assert self.settings.microsoft_client_id is not None
        assert self.settings.microsoft_client_secret is not None
        assert self.settings.microsoft_oauth_redirect_uri is not None
        response = await self._identity_request(
            self.settings.microsoft_token_base_url,
            data={
                "client_id": self.settings.microsoft_client_id,
                "client_secret": self.settings.microsoft_client_secret.get_secret_value(),
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": self.settings.microsoft_oauth_redirect_uri,
                "scope": " ".join(MICROSOFT_SCOPES),
                "code_verifier": code_verifier,
            },
        )
        token = self._parse(_TokenResponse, response)
        if token.id_token is None:
            raise MicrosoftAPIError("provider_identity_invalid")
        tenant_id = await self._validate_id_token(token.id_token, expected_nonce_hash)
        if tenant_id.casefold() == _CONSUMER_TENANT_ID:
            raise MicrosoftAPIError("microsoft_work_account_required")
        scopes = tuple(sorted(set(token.scope.split())))
        if not MICROSOFT_GRAPH_SCOPES.issubset(scopes):
            raise MicrosoftAPIError("provider_scope_incomplete")
        provisional = ConnectorCredential(
            access_token=token.access_token,
            refresh_token=token.refresh_token or "",
            expires_at=datetime.now(UTC) + timedelta(seconds=token.expires_in),
            scopes=scopes,
            external_account_id="pending",
        )
        if not provisional.refresh_token:
            raise MicrosoftAPIError("provider_refresh_token_missing")
        profile = await self.profile_with_token(provisional.access_token)
        if not _EMAIL.fullmatch(profile.email):
            raise MicrosoftAPIError("provider_identity_invalid")
        return MicrosoftOAuthResult(
            credential=ConnectorCredential(
                access_token=provisional.access_token,
                refresh_token=provisional.refresh_token,
                expires_at=provisional.expires_at,
                scopes=provisional.scopes,
                external_account_id=profile.id,
            ),
            profile=profile,
            tenant_id=tenant_id,
        )

    async def profile_with_token(self, access_token: str) -> MicrosoftProfile:
        response = await self._request(
            "GET",
            f"{self.settings.microsoft_graph_base_url}/me",
            token=access_token,
            params={"$select": "id,displayName,mail,userPrincipalName"},
            write=False,
        )
        return self._parse(MicrosoftProfile, response)

    async def profile(self, context: ExecutorConnectionContext) -> MicrosoftProfile:
        response = await self.graph_request(
            context,
            "GET",
            "/me",
            params={"$select": "id,displayName,mail,userPrincipalName"},
            write=False,
        )
        return self._parse(MicrosoftProfile, response)

    async def send_mail(
        self,
        context: ExecutorConnectionContext,
        *,
        sender_name: str | None,
        sender_email: str,
        recipient_name: str | None,
        recipient_email: str,
        subject: str,
        body: str,
        operation_key: str,
    ) -> None:
        address = {"address": sender_email}
        if sender_name:
            address["name"] = sender_name
        recipient = {"address": recipient_email}
        if recipient_name:
            recipient["name"] = recipient_name
        await self.graph_request(
            context,
            "POST",
            "/me/sendMail",
            json_body={
                "message": {
                    "subject": subject,
                    "body": {"contentType": "Text", "content": body},
                    "from": {"emailAddress": address},
                    "replyTo": [{"emailAddress": address}],
                    "toRecipients": [{"emailAddress": recipient}],
                    "internetMessageHeaders": [{"name": "X-Oryntela-Operation-Id", "value": operation_key}],
                },
                "saveToSentItems": True,
            },
            write=True,
            expected_status=202,
        )

    async def graph_json(
        self,
        context: ExecutorConnectionContext,
        path_or_url: str,
        *,
        params: dict[str, str] | None = None,
        headers: dict[str, str] | None = None,
    ) -> dict[str, object]:
        url = self._graph_url(path_or_url)
        response = await self.graph_request(
            context,
            "GET",
            url,
            params=params,
            headers=headers,
            write=False,
        )
        try:
            value = json.loads(response.content)
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise MicrosoftAPIError("provider_response_invalid") from exc
        if not isinstance(value, dict):
            raise MicrosoftAPIError("provider_response_invalid")
        return cast(dict[str, object], value)

    async def graph_request(
        self,
        context: ExecutorConnectionContext,
        method: str,
        path_or_url: str,
        *,
        params: dict[str, str] | None = None,
        json_body: dict[str, object] | None = None,
        headers: dict[str, str] | None = None,
        write: bool,
        expected_status: int = 200,
    ) -> httpx.Response:
        if context.credential_reference is None:
            raise MicrosoftAPIError("connection_reauthorisation_required")
        try:
            credential = await self.credential_store.get(
                context.organisation_id,
                context.connection_id,
                context.credential_reference,
            )
        except ValueError as exc:
            raise MicrosoftAPIError("connection_reauthorisation_required") from exc
        if credential.expires_at.astimezone(UTC) <= datetime.now(UTC) + timedelta(seconds=60):
            credential = await self._refresh(context)
        try:
            return await self._request(
                method,
                self._graph_url(path_or_url),
                token=credential.access_token,
                params=params,
                json_body=json_body,
                extra_headers=headers,
                write=write,
                expected_status=expected_status,
            )
        except MicrosoftAPIError as exc:
            if exc.code != "connection_reauthorisation_required" or exc.status_code != 401:
                raise
        credential = await self._refresh(context, rejected_access_token=credential.access_token)
        return await self._request(
            method,
            self._graph_url(path_or_url),
            token=credential.access_token,
            params=params,
            json_body=json_body,
            extra_headers=headers,
            write=write,
            expected_status=expected_status,
        )

    async def _refresh(
        self,
        context: ExecutorConnectionContext,
        *,
        rejected_access_token: str | None = None,
    ) -> ConnectorCredential:
        assert context.credential_reference is not None
        try:
            credential = await self.credential_store.get_for_update(
                context.organisation_id,
                context.connection_id,
                context.credential_reference,
            )
        except ValueError as exc:
            raise MicrosoftAPIError("connection_reauthorisation_required") from exc
        if rejected_access_token is not None and credential.access_token != rejected_access_token:
            return credential
        if rejected_access_token is None and credential.expires_at.astimezone(UTC) > datetime.now(UTC) + timedelta(
            seconds=60
        ):
            return credential
        assert self.settings.microsoft_client_id is not None
        assert self.settings.microsoft_client_secret is not None
        try:
            response = await self._identity_request(
                self.settings.microsoft_token_base_url,
                data={
                    "client_id": self.settings.microsoft_client_id,
                    "client_secret": self.settings.microsoft_client_secret.get_secret_value(),
                    "grant_type": "refresh_token",
                    "refresh_token": credential.refresh_token,
                    "scope": " ".join(MICROSOFT_SCOPES),
                },
            )
            token = self._parse(_TokenResponse, response)
        except MicrosoftAPIError as exc:
            if exc.retryable:
                raise
            raise MicrosoftAPIError("connection_reauthorisation_required") from exc
        scopes = tuple(sorted(set(token.scope.split())))
        if not MICROSOFT_GRAPH_SCOPES.issubset(scopes):
            raise MicrosoftAPIError("connection_reauthorisation_required")
        refreshed = ConnectorCredential(
            access_token=token.access_token,
            refresh_token=token.refresh_token or credential.refresh_token,
            expires_at=datetime.now(UTC) + timedelta(seconds=token.expires_in),
            scopes=scopes,
            external_account_id=credential.external_account_id,
        )
        await self.credential_store.put(context.organisation_id, context.connection_id, refreshed)
        return refreshed

    async def _validate_id_token(self, token: str, expected_nonce_hash: str) -> str:
        try:
            header = cast(dict[str, object], jwt.get_unverified_header(token))
            kid = header.get("kid")
            if not isinstance(kid, str) or not kid:
                raise MicrosoftAPIError("provider_identity_invalid")
            configuration = await self._identity_json(self.settings.microsoft_openid_configuration_url)
            jwks_uri = configuration.get("jwks_uri")
            if not isinstance(jwks_uri, str) or not self._microsoft_identity_url(jwks_uri):
                raise MicrosoftAPIError("provider_identity_invalid")
            keys = (await self._identity_json(jwks_uri)).get("keys")
            if not isinstance(keys, list):
                raise MicrosoftAPIError("provider_identity_invalid")
            key_data = next(
                (item for item in keys if isinstance(item, dict) and item.get("kid") == kid),
                None,
            )
            if not isinstance(key_data, dict):
                raise MicrosoftAPIError("provider_identity_invalid")
            unverified = cast(dict[str, object], jwt.decode(token, options={"verify_signature": False}))
            tenant_id = unverified.get("tid")
            if not isinstance(tenant_id, str) or not tenant_id:
                raise MicrosoftAPIError("provider_identity_invalid")
            assert self.settings.microsoft_client_id is not None
            claims = cast(
                dict[str, object],
                jwt.decode(
                    token,
                    key=PyJWK.from_dict(key_data).key,
                    algorithms=["RS256"],
                    audience=self.settings.microsoft_client_id,
                    issuer=f"https://login.microsoftonline.com/{tenant_id}/v2.0",
                    options={"require": ["exp", "iat", "iss", "aud", "nonce", "oid", "tid"]},
                ),
            )
            nonce = claims.get("nonce")
            if not isinstance(nonce, str) or hashlib.sha256(nonce.encode()).hexdigest() != expected_nonce_hash:
                raise MicrosoftAPIError("provider_identity_invalid")
            return tenant_id
        except MicrosoftAPIError:
            raise
        except (jwt.PyJWTError, KeyError, TypeError, ValueError) as exc:
            raise MicrosoftAPIError("provider_identity_invalid") from exc

    async def _identity_json(self, url: str) -> dict[str, object]:
        if not self._microsoft_identity_url(url):
            raise MicrosoftAPIError("provider_identity_invalid")
        response = await self._request("GET", url, write=False)
        try:
            value = json.loads(response.content)
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise MicrosoftAPIError("provider_response_invalid") from exc
        if not isinstance(value, dict):
            raise MicrosoftAPIError("provider_response_invalid")
        return cast(dict[str, object], value)

    async def _identity_request(self, url: str, *, data: dict[str, str]) -> httpx.Response:
        if not self._microsoft_identity_url(url):
            raise MicrosoftAPIError("provider_request_rejected")
        return await self._request("POST", url, data=data, write=False)

    async def _request(
        self,
        method: str,
        url: str,
        *,
        token: str | None = None,
        params: dict[str, str] | None = None,
        data: dict[str, str] | None = None,
        json_body: dict[str, object] | None = None,
        extra_headers: dict[str, str] | None = None,
        write: bool,
        expected_status: int = 200,
    ) -> httpx.Response:
        headers = {"Accept": "application/json"}
        if extra_headers is not None:
            headers.update(extra_headers)
        if token is not None:
            headers["Authorization"] = f"Bearer {token}"
        timeout = httpx.Timeout(
            connect=self.settings.microsoft_connect_timeout_seconds,
            read=self.settings.microsoft_write_timeout_seconds
            if write
            else self.settings.microsoft_read_timeout_seconds,
            write=self.settings.microsoft_write_timeout_seconds,
            pool=self.settings.microsoft_connect_timeout_seconds,
        )
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
                async with httpx.AsyncClient(timeout=timeout, follow_redirects=False) as client:
                    response = await client.request(
                        method,
                        url,
                        params=params,
                        data=data,
                        json=json_body,
                        headers=headers,
                    )
        except httpx.TimeoutException as exc:
            raise MicrosoftAPIError("provider_timeout", retryable=not write, uncertain=write) from exc
        except httpx.RequestError as exc:
            raise MicrosoftAPIError("provider_unavailable", retryable=not write, uncertain=write) from exc
        if len(response.content) > self.settings.microsoft_max_response_bytes:
            raise MicrosoftAPIError("provider_response_too_large", uncertain=write)
        if response.status_code in {401, 403}:
            raise MicrosoftAPIError("connection_reauthorisation_required", status_code=response.status_code)
        if response.status_code == 429:
            retry_after = response.headers.get("Retry-After", "").strip()
            seconds = int(retry_after) if retry_after.isdigit() else None
            raise MicrosoftAPIError("provider_rate_limited", retryable=True, retry_after_seconds=seconds)
        if response.status_code == 410 and not write:
            raise MicrosoftAPIError("provider_cursor_expired", retryable=True)
        if response.status_code >= 500:
            raise MicrosoftAPIError("provider_unavailable", retryable=not write, uncertain=write)
        if response.status_code >= 400:
            raise MicrosoftAPIError("provider_request_rejected")
        if response.status_code != expected_status:
            raise MicrosoftAPIError("provider_response_invalid", uncertain=write)
        return response

    def _graph_url(self, path_or_url: str) -> str:
        if path_or_url.startswith("/"):
            return f"{self.settings.microsoft_graph_base_url}{path_or_url}"
        parsed = urlsplit(path_or_url)
        base = urlsplit(self.settings.microsoft_graph_base_url)
        if parsed.scheme != "https" or parsed.hostname != base.hostname or not parsed.path.startswith("/v1.0/"):
            raise MicrosoftAPIError("provider_cursor_invalid")
        return path_or_url

    @staticmethod
    def _microsoft_identity_url(value: str) -> bool:
        parsed = urlsplit(value)
        return parsed.scheme == "https" and parsed.hostname == "login.microsoftonline.com"

    @staticmethod
    def _parse[T: BaseModel](model: type[T], response: httpx.Response) -> T:
        try:
            return model.model_validate_json(response.content)
        except ValidationError as exc:
            raise MicrosoftAPIError("provider_response_invalid") from exc


class MicrosoftEmailExecutor(ActionExecutor):
    definition = CONNECTOR_DEFINITIONS[ConnectorKey.MICROSOFT_365]

    def __init__(self, session: AsyncSession, client: MicrosoftGraphClient) -> None:
        self.session = session
        self.client = client

    async def validate_connection(self, context: ExecutorConnectionContext | None = None) -> None:
        if context is None or context.credential_reference is None:
            raise PermanentExecutionFailure(
                "connection_reauthorisation_required",
                "Reconnect Microsoft 365 to continue.",
            )
        try:
            profile = await self.client.profile(context)
        except MicrosoftAPIError as exc:
            if exc.retryable:
                raise RetryableExecutionFailure(
                    exc.code,
                    "Microsoft is temporarily unavailable. RevenueOS will retry safely.",
                    retry_after_seconds=exc.retry_after_seconds,
                ) from exc
            raise PermanentExecutionFailure(
                "connection_reauthorisation_required",
                "Microsoft 365 needs to be reconnected.",
            ) from exc
        if (
            profile.id != context.external_account_id
            or profile.email.casefold() != (context.external_account_email or "").casefold()
        ):
            raise PermanentExecutionFailure(
                "connection_account_changed",
                "The Microsoft account identity no longer matches this connection.",
            )

    def validate_action(self, action: ApprovedActionInput) -> None:
        if not isinstance(action.payload, (FollowUpEmailPayload, PersonalizedOutreachPayload)):
            raise PermanentExecutionFailure("unsupported_action", "Microsoft 365 cannot execute this Action.")
        payload = action.payload
        if not payload.recipient_confirmed or payload.recipient_email is None:
            raise PermanentExecutionFailure("recipient_not_confirmed", "Confirm the exact Contact recipient first.")
        if not _EMAIL.fullmatch(payload.recipient_email):
            raise PermanentExecutionFailure("invalid_recipient", "The approved recipient address is invalid.")
        if not payload.subject.strip() or not payload.body.strip():
            raise PermanentExecutionFailure("invalid_email_content", "The approved subject and body are required.")

    def preview_execution(
        self,
        action: ApprovedActionInput,
        current_external_state: object | None,
    ) -> ExecutionPreviewContent:
        del current_external_state
        self.validate_action(action)
        payload = cast(FollowUpEmailPayload | PersonalizedOutreachPayload, action.payload)
        assert payload.recipient_email is not None
        return EmailExecutionPreview(
            kind="email",
            sender_name=payload.sender_name if isinstance(payload, PersonalizedOutreachPayload) else None,
            sender_email=payload.sender_email if isinstance(payload, PersonalizedOutreachPayload) else None,
            recipient_name=payload.recipient_name if isinstance(payload, PersonalizedOutreachPayload) else None,
            recipient=payload.recipient_email,
            subject=payload.subject,
            body=payload.body,
        )

    async def current_external_state(
        self,
        action: ApprovedActionInput,
        context: ExecutorConnectionContext,
    ) -> object | None:
        del action, context
        return None

    async def execute(
        self,
        action: ApprovedActionInput,
        *,
        idempotency_key: str,
        current_external_state: object | None,
        context: ExecutorConnectionContext | None = None,
    ) -> ExecutorResult:
        del current_external_state
        if context is None or context.external_account_email is None:
            raise PermanentExecutionFailure("connection_unavailable", "The Microsoft mailbox is unavailable.")
        self.validate_action(action)
        payload = cast(FollowUpEmailPayload | PersonalizedOutreachPayload, action.payload)
        assert payload.recipient_email is not None
        if (
            isinstance(payload, PersonalizedOutreachPayload)
            and payload.sender_email.casefold() != context.external_account_email.casefold()
        ):
            raise PermanentExecutionFailure(
                "sender_identity_mismatch",
                "The approved From address does not match the connected Microsoft mailbox.",
            )
        operation = await self.session.scalar(
            select(ProviderOutboundOperation)
            .where(
                ProviderOutboundOperation.organisation_id == context.organisation_id,
                ProviderOutboundOperation.connection_id == context.connection_id,
                ProviderOutboundOperation.idempotency_key == idempotency_key,
            )
            .with_for_update()
        )
        now = datetime.now(UTC)
        if operation is None:
            raise PermanentExecutionFailure(
                "microsoft_operation_receipt_missing",
                "The durable Microsoft send receipt is missing.",
            )
        if operation.state in {"accepted", "reconciled"}:
            return self._result(operation)
        if operation.state == "unknown":
            raise UnknownExternalStateFailure(
                "microsoft_send_outcome_unknown",
                "Microsoft may have accepted this email. RevenueOS will not send it again until reconciled.",
            )
        if operation.state != "submitting":
            raise PermanentExecutionFailure(
                "microsoft_operation_receipt_invalid",
                "The durable Microsoft send receipt is not ready for submission.",
            )
        operation.safe_failure_code = None
        try:
            await self.client.send_mail(
                context,
                sender_name=(payload.sender_name if isinstance(payload, PersonalizedOutreachPayload) else None),
                sender_email=context.external_account_email,
                recipient_name=(payload.recipient_name if isinstance(payload, PersonalizedOutreachPayload) else None),
                recipient_email=payload.recipient_email,
                subject=payload.subject,
                body=payload.body,
                operation_key=idempotency_key,
            )
        except MicrosoftAPIError as exc:
            operation.safe_failure_code = exc.code
            if exc.uncertain:
                operation.state = "unknown"
                raise UnknownExternalStateFailure(
                    "microsoft_send_outcome_unknown",
                    "Microsoft may have accepted this email. RevenueOS will not send it again until reconciled.",
                ) from exc
            operation.state = "failed"
            if exc.retryable:
                raise RetryableExecutionFailure(
                    exc.code,
                    "Microsoft is temporarily unavailable. RevenueOS will retry safely.",
                    retry_after_seconds=exc.retry_after_seconds,
                ) from exc
            if exc.code == "connection_reauthorisation_required":
                raise PermanentExecutionFailure(exc.code, "Reconnect Microsoft 365 to continue sending.") from exc
            raise PermanentExecutionFailure(exc.code, "Microsoft rejected the approved email request.") from exc
        operation.state = "accepted"
        operation.submitted_at = now
        operation.safe_failure_code = None
        return self._result(operation)

    def object_key(self, action: ApprovedActionInput, idempotency_key: str) -> str:
        del action
        return f"email:{idempotency_key}"

    @staticmethod
    def _result(operation: ProviderOutboundOperation) -> ExecutorResult:
        return ExecutorResult(
            external_result_id=operation.provider_message_id or f"m365_submission_{operation.id}",
            object_type="email",
            object_key=f"email:{operation.idempotency_key}",
            state={"provider": "microsoft_365", "status": operation.state},
            safe_message="Microsoft accepted the email for processing; recipient delivery is not yet proven.",
        )
