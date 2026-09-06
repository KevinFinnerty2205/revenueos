from __future__ import annotations

import base64
import hashlib
import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from email.headerregistry import Address
from email.message import EmailMessage
from email.policy import SMTP
from typing import cast
from urllib.parse import quote, urlencode, urlsplit

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

GOOGLE_GMAIL_SEND_SCOPE = "https://www.googleapis.com/auth/gmail.send"
GOOGLE_GMAIL_READ_SCOPE = "https://www.googleapis.com/auth/gmail.readonly"
GOOGLE_CALENDAR_READ_SCOPE = "https://www.googleapis.com/auth/calendar.events.readonly"
GOOGLE_SCOPES = (
    "openid",
    "email",
    "profile",
    GOOGLE_GMAIL_SEND_SCOPE,
    GOOGLE_GMAIL_READ_SCOPE,
    GOOGLE_CALENDAR_READ_SCOPE,
)
GOOGLE_API_SCOPES = frozenset(GOOGLE_SCOPES[3:])
_EMAIL = re.compile(r"[^\s@]+@[^\s@]+\.[^\s@]+")
_HEADER_LINE_BREAK = re.compile(r"[\r\n]")


class GoogleAPIError(Exception):
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
    scope: str | None = Field(default=None, max_length=4_096)
    id_token: str | None = Field(default=None, min_length=1, max_length=16_384)


class GoogleProfile(_StrictModel):
    sub: str = Field(min_length=1, max_length=128)
    email: str = Field(min_length=3, max_length=320)
    email_verified: bool
    name: str = Field(min_length=1, max_length=200)
    hd: str = Field(min_length=1, max_length=253)


class _GmailSendResponse(_StrictModel):
    id: str = Field(min_length=1, max_length=255)
    thread_id: str = Field(alias="threadId", min_length=1, max_length=255)


@dataclass(frozen=True)
class GoogleOAuthResult:
    credential: ConnectorCredential
    profile: GoogleProfile


@dataclass(frozen=True)
class GoogleSendResult:
    message_id: str
    thread_id: str
    internet_message_id: str


class GoogleWorkspaceClient:
    """Bounded Google OAuth, Gmail and Calendar adapter with allow-listed endpoints."""

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
        assert self.settings.google_client_id is not None
        assert self.settings.google_oauth_redirect_uri is not None
        query = urlencode(
            {
                "client_id": self.settings.google_client_id,
                "response_type": "code",
                "redirect_uri": self.settings.google_oauth_redirect_uri,
                "scope": " ".join(GOOGLE_SCOPES),
                "state": state,
                "nonce": nonce,
                "code_challenge": challenge,
                "code_challenge_method": "S256",
                "access_type": "offline",
                "include_granted_scopes": "false",
                "prompt": "consent select_account",
                "hd": "*",
            }
        )
        return f"{self.settings.google_authorisation_base_url}?{query}"

    async def exchange_code(
        self,
        code: str,
        code_verifier: str,
        expected_nonce_hash: str,
    ) -> GoogleOAuthResult:
        assert self.settings.google_client_id is not None
        assert self.settings.google_client_secret is not None
        assert self.settings.google_oauth_redirect_uri is not None
        response = await self._identity_request(
            self.settings.google_token_base_url,
            data={
                "client_id": self.settings.google_client_id,
                "client_secret": self.settings.google_client_secret.get_secret_value(),
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": self.settings.google_oauth_redirect_uri,
                "code_verifier": code_verifier,
            },
        )
        token = self._parse(_TokenResponse, response)
        if token.id_token is None:
            raise GoogleAPIError("provider_identity_invalid")
        profile = await self._validate_id_token(token.id_token, expected_nonce_hash)
        scopes = tuple(sorted(set((token.scope or "").split())))
        if not GOOGLE_API_SCOPES.issubset(scopes):
            raise GoogleAPIError("provider_scope_incomplete")
        if token.refresh_token is None:
            raise GoogleAPIError("provider_refresh_token_missing")
        return GoogleOAuthResult(
            credential=ConnectorCredential(
                access_token=token.access_token,
                refresh_token=token.refresh_token,
                expires_at=datetime.now(UTC) + timedelta(seconds=token.expires_in),
                scopes=scopes,
                external_account_id=profile.sub,
            ),
            profile=profile,
        )

    async def profile(self, context: ExecutorConnectionContext) -> GoogleProfile:
        response = await self.google_request(
            context,
            "GET",
            "https://openidconnect.googleapis.com/v1/userinfo",
            write=False,
        )
        return self._parse(GoogleProfile, response)

    async def revoke(self, credential: ConnectorCredential) -> None:
        token = credential.refresh_token or credential.access_token
        await self._identity_request(self.settings.google_revoke_url, data={"token": token})

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
    ) -> GoogleSendResult:
        self._validate_headers(sender_name, sender_email, recipient_name, recipient_email, subject)
        internet_message_id = f"<oryntela-{operation_key}@mail.oryntela.invalid>"
        message = EmailMessage(policy=SMTP)
        message["From"] = Address(display_name=sender_name or "", addr_spec=sender_email)
        message["To"] = Address(display_name=recipient_name or "", addr_spec=recipient_email)
        message["Subject"] = subject
        message["Reply-To"] = Address(display_name=sender_name or "", addr_spec=sender_email)
        message["Message-ID"] = internet_message_id
        message["X-Oryntela-Operation-Id"] = operation_key
        message.set_content(body, subtype="plain", charset="utf-8")
        raw = base64.urlsafe_b64encode(message.as_bytes()).decode("ascii").rstrip("=")
        response = await self.google_request(
            context,
            "POST",
            f"{self.settings.google_gmail_base_url}/users/me/messages/send",
            json_body={"raw": raw},
            write=True,
        )
        result = self._parse(_GmailSendResponse, response)
        return GoogleSendResult(
            message_id=result.id,
            thread_id=result.thread_id,
            internet_message_id=internet_message_id,
        )

    async def google_json(
        self,
        context: ExecutorConnectionContext,
        url: str,
        *,
        params: dict[str, str] | None = None,
    ) -> dict[str, object]:
        response = await self.google_request(context, "GET", url, params=params, write=False)
        try:
            value = json.loads(response.content)
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise GoogleAPIError("provider_response_invalid") from exc
        if not isinstance(value, dict):
            raise GoogleAPIError("provider_response_invalid")
        return cast(dict[str, object], value)

    async def google_request(
        self,
        context: ExecutorConnectionContext,
        method: str,
        url: str,
        *,
        params: dict[str, str] | None = None,
        json_body: dict[str, object] | None = None,
        write: bool,
    ) -> httpx.Response:
        self._require_google_url(url)
        if context.credential_reference is None:
            raise GoogleAPIError("connection_reauthorisation_required")
        try:
            credential = await self.credential_store.get(
                context.organisation_id,
                context.connection_id,
                context.credential_reference,
            )
        except ValueError as exc:
            raise GoogleAPIError("connection_reauthorisation_required") from exc
        if credential.expires_at.astimezone(UTC) <= datetime.now(UTC) + timedelta(seconds=60):
            credential = await self._refresh(context)
        try:
            return await self._request(
                method,
                url,
                token=credential.access_token,
                params=params,
                json_body=json_body,
                write=write,
            )
        except GoogleAPIError as exc:
            if exc.code != "connection_reauthorisation_required" or exc.status_code != 401:
                raise
        credential = await self._refresh(context, rejected_access_token=credential.access_token)
        return await self._request(
            method,
            url,
            token=credential.access_token,
            params=params,
            json_body=json_body,
            write=write,
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
            raise GoogleAPIError("connection_reauthorisation_required") from exc
        if rejected_access_token is not None and credential.access_token != rejected_access_token:
            return credential
        if rejected_access_token is None and credential.expires_at.astimezone(UTC) > datetime.now(UTC) + timedelta(
            seconds=60
        ):
            return credential
        assert self.settings.google_client_id is not None
        assert self.settings.google_client_secret is not None
        try:
            response = await self._identity_request(
                self.settings.google_token_base_url,
                data={
                    "client_id": self.settings.google_client_id,
                    "client_secret": self.settings.google_client_secret.get_secret_value(),
                    "grant_type": "refresh_token",
                    "refresh_token": credential.refresh_token,
                },
            )
            token = self._parse(_TokenResponse, response)
        except GoogleAPIError as exc:
            if exc.retryable:
                raise
            raise GoogleAPIError("connection_reauthorisation_required") from exc
        scopes = tuple(sorted(set((token.scope or "").split()))) or credential.scopes
        if not GOOGLE_API_SCOPES.issubset(scopes):
            raise GoogleAPIError("connection_reauthorisation_required")
        refreshed = ConnectorCredential(
            access_token=token.access_token,
            refresh_token=token.refresh_token or credential.refresh_token,
            expires_at=datetime.now(UTC) + timedelta(seconds=token.expires_in),
            scopes=scopes,
            external_account_id=credential.external_account_id,
        )
        await self.credential_store.put(context.organisation_id, context.connection_id, refreshed)
        return refreshed

    async def _validate_id_token(self, token: str, expected_nonce_hash: str) -> GoogleProfile:
        try:
            header = cast(dict[str, object], jwt.get_unverified_header(token))
            kid = header.get("kid")
            if not isinstance(kid, str) or not kid:
                raise GoogleAPIError("provider_identity_invalid")
            configuration = await self._identity_json(self.settings.google_openid_configuration_url)
            jwks_uri = configuration.get("jwks_uri")
            if not isinstance(jwks_uri, str) or not self._google_identity_url(jwks_uri):
                raise GoogleAPIError("provider_identity_invalid")
            keys = (await self._identity_json(jwks_uri)).get("keys")
            if not isinstance(keys, list):
                raise GoogleAPIError("provider_identity_invalid")
            key_data = next(
                (item for item in keys if isinstance(item, dict) and item.get("kid") == kid),
                None,
            )
            if not isinstance(key_data, dict):
                raise GoogleAPIError("provider_identity_invalid")
            assert self.settings.google_client_id is not None
            claims = cast(
                dict[str, object],
                jwt.decode(
                    token,
                    key=PyJWK.from_dict(key_data).key,
                    algorithms=["RS256"],
                    audience=self.settings.google_client_id,
                    issuer=("accounts.google.com", "https://accounts.google.com"),
                    options={"require": ["exp", "iat", "iss", "aud", "nonce", "sub", "email"]},
                ),
            )
            nonce = claims.get("nonce")
            if not isinstance(nonce, str) or hashlib.sha256(nonce.encode()).hexdigest() != expected_nonce_hash:
                raise GoogleAPIError("provider_identity_invalid")
            if not claims.get("hd"):
                raise GoogleAPIError("google_workspace_account_required")
            profile = GoogleProfile.model_validate(claims)
            if not profile.email_verified or not _EMAIL.fullmatch(profile.email):
                raise GoogleAPIError("provider_identity_invalid")
            return profile
        except GoogleAPIError:
            raise
        except (jwt.PyJWTError, ValidationError, KeyError, TypeError, ValueError) as exc:
            raise GoogleAPIError("provider_identity_invalid") from exc

    async def _identity_json(self, url: str) -> dict[str, object]:
        if not self._google_identity_url(url):
            raise GoogleAPIError("provider_identity_invalid")
        response = await self._request("GET", url, write=False)
        try:
            value = json.loads(response.content)
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise GoogleAPIError("provider_response_invalid") from exc
        if not isinstance(value, dict):
            raise GoogleAPIError("provider_response_invalid")
        return cast(dict[str, object], value)

    async def _identity_request(self, url: str, *, data: dict[str, str]) -> httpx.Response:
        if not self._google_identity_url(url):
            raise GoogleAPIError("provider_request_rejected")
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
        write: bool,
    ) -> httpx.Response:
        headers = {"Accept": "application/json"}
        if token is not None:
            headers["Authorization"] = f"Bearer {token}"
        timeout = httpx.Timeout(
            connect=self.settings.google_connect_timeout_seconds,
            read=(self.settings.google_write_timeout_seconds if write else self.settings.google_read_timeout_seconds),
            write=self.settings.google_write_timeout_seconds,
            pool=self.settings.google_connect_timeout_seconds,
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
            raise GoogleAPIError("provider_timeout", retryable=not write, uncertain=write) from exc
        except httpx.RequestError as exc:
            raise GoogleAPIError("provider_unavailable", retryable=not write, uncertain=write) from exc
        if len(response.content) > self.settings.google_max_response_bytes:
            raise GoogleAPIError("provider_response_too_large", uncertain=write)
        if response.status_code == 401:
            raise GoogleAPIError("connection_reauthorisation_required", status_code=401)
        if response.status_code == 403:
            raise GoogleAPIError("provider_permission_denied", status_code=403)
        if response.status_code == 404 and not write:
            raise GoogleAPIError("provider_cursor_expired", retryable=True, status_code=404)
        if response.status_code == 410 and not write:
            raise GoogleAPIError("provider_cursor_expired", retryable=True, status_code=410)
        if response.status_code == 429:
            retry_after = response.headers.get("Retry-After", "").strip()
            seconds = int(retry_after) if retry_after.isdigit() else None
            raise GoogleAPIError("provider_rate_limited", retryable=True, retry_after_seconds=seconds)
        if response.status_code >= 500:
            raise GoogleAPIError("provider_unavailable", retryable=not write, uncertain=write)
        if response.status_code >= 400:
            raise GoogleAPIError("provider_request_rejected")
        if response.status_code not in {200, 201}:
            raise GoogleAPIError("provider_response_invalid", uncertain=write)
        return response

    def _require_google_url(self, value: str) -> None:
        parsed = urlsplit(value)
        allowed = {
            ("openidconnect.googleapis.com", "/v1/userinfo"),
            ("gmail.googleapis.com", "/gmail/v1/"),
            ("www.googleapis.com", "/calendar/v3/"),
        }
        if parsed.scheme != "https" or not any(
            parsed.hostname == hostname and parsed.path.startswith(path) for hostname, path in allowed
        ):
            raise GoogleAPIError("provider_cursor_invalid")

    @staticmethod
    def _google_identity_url(value: str) -> bool:
        parsed = urlsplit(value)
        return parsed.scheme == "https" and parsed.hostname in {
            "accounts.google.com",
            "oauth2.googleapis.com",
            "www.googleapis.com",
        }

    @staticmethod
    def _validate_headers(
        sender_name: str | None,
        sender_email: str,
        recipient_name: str | None,
        recipient_email: str,
        subject: str,
    ) -> None:
        values = (sender_name or "", sender_email, recipient_name or "", recipient_email, subject)
        if any(_HEADER_LINE_BREAK.search(value) for value in values):
            raise GoogleAPIError("invalid_email_header")
        if not _EMAIL.fullmatch(sender_email) or not _EMAIL.fullmatch(recipient_email):
            raise GoogleAPIError("invalid_email_header")
        if len(subject) > 500 or len(sender_name or "") > 200 or len(recipient_name or "") > 200:
            raise GoogleAPIError("invalid_email_header")

    @staticmethod
    def _parse[T: BaseModel](model: type[T], response: httpx.Response) -> T:
        try:
            return model.model_validate_json(response.content)
        except ValidationError as exc:
            raise GoogleAPIError("provider_response_invalid") from exc


class GoogleEmailExecutor(ActionExecutor):
    definition = CONNECTOR_DEFINITIONS[ConnectorKey.GOOGLE_WORKSPACE]

    def __init__(self, session: AsyncSession, client: GoogleWorkspaceClient) -> None:
        self.session = session
        self.client = client

    async def validate_connection(self, context: ExecutorConnectionContext | None = None) -> None:
        if context is None or context.credential_reference is None:
            raise PermanentExecutionFailure(
                "connection_reauthorisation_required",
                "Reconnect Google Workspace to continue.",
            )
        try:
            profile = await self.client.profile(context)
        except GoogleAPIError as exc:
            if exc.retryable:
                raise RetryableExecutionFailure(
                    exc.code,
                    "Google is temporarily unavailable. Oryntela will retry safely.",
                    retry_after_seconds=exc.retry_after_seconds,
                ) from exc
            raise PermanentExecutionFailure(
                "connection_reauthorisation_required",
                "Google Workspace needs to be reconnected.",
            ) from exc
        if (
            profile.sub != context.external_account_id
            or profile.email.casefold() != (context.external_account_email or "").casefold()
            or profile.hd.casefold() != (context.external_tenant_id or "").casefold()
        ):
            raise PermanentExecutionFailure(
                "connection_account_changed",
                "The Google Workspace account identity no longer matches this connection.",
            )

    def validate_action(self, action: ApprovedActionInput) -> None:
        if not isinstance(action.payload, (FollowUpEmailPayload, PersonalizedOutreachPayload)):
            raise PermanentExecutionFailure("unsupported_action", "Google Workspace cannot execute this Action.")
        payload = action.payload
        if not payload.recipient_confirmed or payload.recipient_email is None:
            raise PermanentExecutionFailure("recipient_not_confirmed", "Confirm the exact Contact recipient first.")
        if not _EMAIL.fullmatch(payload.recipient_email):
            raise PermanentExecutionFailure("invalid_recipient", "The approved recipient address is invalid.")
        if not payload.subject.strip() or not payload.body.strip():
            raise PermanentExecutionFailure("invalid_email_content", "The approved subject and body are required.")
        if _HEADER_LINE_BREAK.search(payload.subject):
            raise PermanentExecutionFailure("invalid_email_header", "The approved email headers are invalid.")

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
            raise PermanentExecutionFailure("connection_unavailable", "The Google mailbox is unavailable.")
        self.validate_action(action)
        payload = cast(FollowUpEmailPayload | PersonalizedOutreachPayload, action.payload)
        assert payload.recipient_email is not None
        if (
            isinstance(payload, PersonalizedOutreachPayload)
            and payload.sender_email.casefold() != context.external_account_email.casefold()
        ):
            raise PermanentExecutionFailure(
                "sender_identity_mismatch",
                "The approved From address does not match the connected Google Workspace mailbox.",
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
                "mailbox_operation_receipt_missing",
                "The durable mailbox send receipt is missing.",
            )
        if operation.state in {"accepted", "reconciled"}:
            return self._result(operation)
        if operation.state == "unknown":
            raise UnknownExternalStateFailure(
                "google_send_outcome_unknown",
                "Google may have accepted this email. Oryntela will not send it again until reconciled.",
            )
        if operation.state != "submitting":
            raise PermanentExecutionFailure(
                "mailbox_operation_receipt_invalid",
                "The durable mailbox send receipt is not ready for submission.",
            )
        operation.safe_failure_code = None
        try:
            result = await self.client.send_mail(
                context,
                sender_name=(payload.sender_name if isinstance(payload, PersonalizedOutreachPayload) else None),
                sender_email=context.external_account_email,
                recipient_name=(payload.recipient_name if isinstance(payload, PersonalizedOutreachPayload) else None),
                recipient_email=payload.recipient_email,
                subject=payload.subject,
                body=payload.body,
                operation_key=idempotency_key,
            )
        except GoogleAPIError as exc:
            operation.safe_failure_code = exc.code
            if exc.uncertain:
                operation.state = "unknown"
                raise UnknownExternalStateFailure(
                    "google_send_outcome_unknown",
                    "Google may have accepted this email. Oryntela will not send it again until reconciled.",
                ) from exc
            operation.state = "failed"
            if exc.retryable:
                raise RetryableExecutionFailure(
                    exc.code,
                    "Google is temporarily unavailable. Oryntela will retry safely.",
                    retry_after_seconds=exc.retry_after_seconds,
                ) from exc
            if exc.code == "connection_reauthorisation_required":
                raise PermanentExecutionFailure(exc.code, "Reconnect Google Workspace to continue sending.") from exc
            raise PermanentExecutionFailure(exc.code, "Google rejected the approved email request.") from exc
        operation.provider_message_id = result.message_id
        operation.conversation_id = result.thread_id
        operation.internet_message_id = result.internet_message_id
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
            external_result_id=operation.provider_message_id or f"google_submission_{operation.id}",
            object_type="email",
            object_key=f"email:{operation.idempotency_key}",
            state={"provider": "google_workspace", "status": operation.state},
            safe_message="Google accepted the email for processing; recipient delivery is not yet proven.",
        )


def gmail_message_url(settings: Settings, message_id: str) -> str:
    return f"{settings.google_gmail_base_url}/users/me/messages/{quote(message_id, safe='')}"
