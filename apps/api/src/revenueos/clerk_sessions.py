from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal, Protocol, cast

import httpx

from revenueos.config import Settings

SessionRevocationOutcome = Literal["succeeded", "failed", "unknown", "not_required"]


@dataclass(frozen=True)
class SessionRevocationResult:
    outcome: SessionRevocationOutcome
    revoked_session_count: int
    failure_code: str | None = None

    @property
    def confirmed(self) -> bool:
        return self.outcome in {"succeeded", "not_required"}


class SessionRevoker(Protocol):
    async def revoke_active_sessions(
        self,
        external_user_id: str,
        external_organisation_id: str,
    ) -> SessionRevocationResult: ...


class NoopSessionRevoker:
    """Deterministic local/test adapter; it never represents a Clerk operation."""

    async def revoke_active_sessions(
        self,
        external_user_id: str,
        external_organisation_id: str,
    ) -> SessionRevocationResult:
        del external_user_id, external_organisation_id
        return SessionRevocationResult(outcome="not_required", revoked_session_count=0)


class UnavailableSessionRevoker:
    """Fail-closed adapter for an incomplete non-production Clerk configuration."""

    async def revoke_active_sessions(
        self,
        external_user_id: str,
        external_organisation_id: str,
    ) -> SessionRevocationResult:
        del external_user_id, external_organisation_id
        return SessionRevocationResult(
            outcome="failed",
            revoked_session_count=0,
            failure_code="clerk_session_management_unavailable",
        )


class ClerkBackendSessionRevoker:
    """Revoke only one exact user's sessions active in one exact organisation."""

    _SESSION_ID = re.compile(r"^sess_[A-Za-z0-9]+$")
    _USER_ID = re.compile(r"^user_[A-Za-z0-9]+$")
    _ORGANISATION_ID = re.compile(r"^org_[A-Za-z0-9]+$")
    _PAGE_LIMIT = 500

    def __init__(self, settings: Settings, *, http_client: httpx.AsyncClient | None = None) -> None:
        if settings.clerk_secret_key is None:
            raise ValueError("Clerk session management is not configured.")
        self._base_url = settings.clerk_api_base_url.rstrip("/")
        self._secret_key = settings.clerk_secret_key.get_secret_value()
        self._connect_timeout_seconds = settings.clerk_api_connect_timeout_seconds
        self._read_timeout_seconds = settings.clerk_api_read_timeout_seconds
        self._max_response_bytes = settings.clerk_api_max_response_bytes
        self._max_batches = settings.clerk_session_revoke_max_batches
        self._http_client = http_client

    @property
    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._secret_key}",
            "Accept": "application/json",
            "User-Agent": "Oryntela-API/1.0",
        }

    async def revoke_active_sessions(
        self,
        external_user_id: str,
        external_organisation_id: str,
    ) -> SessionRevocationResult:
        if self._USER_ID.fullmatch(external_user_id) is None:
            return SessionRevocationResult(
                outcome="failed",
                revoked_session_count=0,
                failure_code="clerk_user_identity_invalid",
            )
        if self._ORGANISATION_ID.fullmatch(external_organisation_id) is None:
            return SessionRevocationResult(
                outcome="failed",
                revoked_session_count=0,
                failure_code="clerk_organisation_identity_invalid",
            )
        if self._http_client is not None:
            return await self._revoke_with_client(
                self._http_client,
                external_user_id,
                external_organisation_id,
            )
        timeout = httpx.Timeout(
            connect=self._connect_timeout_seconds,
            read=self._read_timeout_seconds,
            write=self._read_timeout_seconds,
            pool=self._connect_timeout_seconds,
        )
        async with httpx.AsyncClient(
            base_url=self._base_url,
            timeout=timeout,
            headers=self._headers,
        ) as client:
            return await self._revoke_with_client(client, external_user_id, external_organisation_id)

    async def _revoke_with_client(
        self,
        client: httpx.AsyncClient,
        external_user_id: str,
        external_organisation_id: str,
    ) -> SessionRevocationResult:
        revoked_ids: set[str] = set()
        for _ in range(self._max_batches):
            listed = await self._list_active_sessions(
                client,
                external_user_id,
                external_organisation_id,
            )
            if isinstance(listed, SessionRevocationResult):
                return SessionRevocationResult(
                    outcome=listed.outcome,
                    revoked_session_count=len(revoked_ids),
                    failure_code=listed.failure_code,
                )
            if not listed:
                return SessionRevocationResult(
                    outcome="succeeded",
                    revoked_session_count=len(revoked_ids),
                )
            for session_id in listed:
                result = await self._revoke_session(client, session_id)
                if isinstance(result, SessionRevocationResult):
                    return SessionRevocationResult(
                        outcome=result.outcome,
                        revoked_session_count=len(revoked_ids),
                        failure_code=result.failure_code,
                    )
                if result:
                    revoked_ids.add(session_id)
        remaining = await self._list_active_sessions(
            client,
            external_user_id,
            external_organisation_id,
        )
        if isinstance(remaining, SessionRevocationResult):
            return SessionRevocationResult(
                outcome=remaining.outcome,
                revoked_session_count=len(revoked_ids),
                failure_code=remaining.failure_code,
            )
        if not remaining:
            return SessionRevocationResult(
                outcome="succeeded",
                revoked_session_count=len(revoked_ids),
            )
        return SessionRevocationResult(
            outcome="unknown",
            revoked_session_count=len(revoked_ids),
            failure_code="clerk_active_sessions_remain",
        )

    async def _list_active_sessions(
        self,
        client: httpx.AsyncClient,
        external_user_id: str,
        external_organisation_id: str,
    ) -> list[str] | SessionRevocationResult:
        try:
            response = await client.get(
                "sessions",
                headers=self._headers,
                params={
                    "user_id": external_user_id,
                    "status": "active",
                    "limit": self._PAGE_LIMIT,
                    "offset": 0,
                },
            )
        except (httpx.ConnectError, httpx.ConnectTimeout, httpx.PoolTimeout):
            return SessionRevocationResult("failed", 0, "clerk_session_list_unavailable")
        except (httpx.ReadTimeout, httpx.WriteTimeout, httpx.RemoteProtocolError):
            return SessionRevocationResult("failed", 0, "clerk_session_list_incomplete")
        if not response.is_success:
            return SessionRevocationResult("failed", 0, self._http_failure_code(response.status_code, "list"))
        if len(response.content) > self._max_response_bytes:
            return SessionRevocationResult("failed", 0, "clerk_session_list_too_large")
        try:
            payload = cast(object, response.json())
        except ValueError:
            return SessionRevocationResult("failed", 0, "clerk_session_list_invalid")
        raw_sessions: object = payload
        if isinstance(payload, dict):
            raw_sessions = payload.get("data")
        if not isinstance(raw_sessions, list):
            return SessionRevocationResult("failed", 0, "clerk_session_list_invalid")
        session_ids: list[str] = []
        seen_session_ids: set[str] = set()
        for raw_session in raw_sessions:
            if not isinstance(raw_session, dict):
                return SessionRevocationResult("failed", 0, "clerk_session_identity_invalid")
            session_id = raw_session.get("id")
            returned_user_id = raw_session.get("user_id")
            status = raw_session.get("status")
            last_active_organisation_id = raw_session.get("last_active_organization_id")
            if (
                not isinstance(session_id, str)
                or self._SESSION_ID.fullmatch(session_id) is None
                or returned_user_id != external_user_id
                or status != "active"
                or (
                    last_active_organisation_id is not None
                    and (
                        not isinstance(last_active_organisation_id, str)
                        or self._ORGANISATION_ID.fullmatch(last_active_organisation_id) is None
                    )
                )
            ):
                return SessionRevocationResult("failed", 0, "clerk_session_identity_invalid")
            if last_active_organisation_id == external_organisation_id and session_id not in seen_session_ids:
                session_ids.append(session_id)
                seen_session_ids.add(session_id)
        return session_ids

    async def _revoke_session(
        self,
        client: httpx.AsyncClient,
        session_id: str,
    ) -> bool | SessionRevocationResult:
        try:
            response = await client.post(f"sessions/{session_id}/revoke", headers=self._headers)
        except (httpx.ConnectError, httpx.ConnectTimeout, httpx.PoolTimeout):
            return SessionRevocationResult("failed", 0, "clerk_session_revoke_unavailable")
        except (httpx.ReadTimeout, httpx.WriteTimeout, httpx.RemoteProtocolError):
            return SessionRevocationResult("unknown", 0, "clerk_session_revoke_outcome_unknown")
        if response.is_success:
            return True
        if response.status_code == 404:
            return False
        outcome: SessionRevocationOutcome = "unknown" if response.status_code >= 500 else "failed"
        return SessionRevocationResult(outcome, 0, self._http_failure_code(response.status_code, "revoke"))

    @staticmethod
    def _http_failure_code(status_code: int, operation: Literal["list", "revoke"]) -> str:
        if status_code in {401, 403}:
            return "clerk_session_management_unauthorised"
        if status_code == 429:
            return "clerk_session_management_rate_limited"
        if status_code >= 500:
            return f"clerk_session_{operation}_provider_failure"
        return f"clerk_session_{operation}_rejected"


def create_session_revoker(settings: Settings) -> SessionRevoker:
    if settings.auth_mode != "clerk":
        return NoopSessionRevoker()
    if settings.clerk_secret_key is None:
        return UnavailableSessionRevoker()
    return ClerkBackendSessionRevoker(settings)
