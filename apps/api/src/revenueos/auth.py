from __future__ import annotations

import asyncio
import hashlib
import re
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from functools import lru_cache
from typing import Literal, Protocol, cast
from uuid import UUID

import jwt
from fastapi import Depends, Request
from jwt import PyJWKClient
from jwt.exceptions import InvalidTokenError, PyJWKClientError
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from revenueos.commercial_services import require_seat_available
from revenueos.config import Settings, get_settings
from revenueos.database import set_tenant_database_context
from revenueos.development import DEVELOPMENT_ORGANISATION_ID, DEVELOPMENT_USER_ID
from revenueos.errors import PublicAPIError
from revenueos.models import Organisation, OrganisationMembership, User

Role = Literal["admin", "member"]
AuthMode = Literal["mock", "clerk"]
IDENTITY_NAMESPACE = UUID("fd2573b7-09a4-4c4a-a2f0-767b4c0ca901")


def identity_organisation_id(external_organisation_id: str) -> UUID:
    return uuid.uuid5(IDENTITY_NAMESPACE, f"organisation:{external_organisation_id}")


def identity_user_id(external_user_id: str) -> UUID:
    return uuid.uuid5(IDENTITY_NAMESPACE, f"user:{external_user_id}")


class AuthenticationError(Exception):
    """Raised when a request has no valid authentication."""


class AuthenticationUnavailableError(Exception):
    """Raised when the configured authentication provider is not ready."""


@dataclass(frozen=True)
class VerifiedIdentity:
    external_auth_id: str
    external_organisation_id: str
    display_name: str
    email: str
    organisation_name: str
    role: Role
    auth_mode: AuthMode


@dataclass(frozen=True)
class AuthenticatedUser:
    user_id: UUID
    external_auth_id: str
    display_name: str
    email: str
    organisation_id: UUID
    organisation_name: str
    organisation_slug: str
    role: Role
    auth_mode: AuthMode


class AuthAdapter(Protocol):
    async def authenticate(self, request: Request) -> VerifiedIdentity: ...


class DevelopmentAuthAdapter:
    """Clearly labelled local adapter that is prohibited in production."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def authenticate(self, request: Request) -> VerifiedIdentity:
        del request
        if not self.settings.mock_auth_enabled or self.settings.environment == "production":
            raise AuthenticationUnavailableError("Development authentication is disabled.")
        return VerifiedIdentity(
            external_auth_id="user_dev_001",
            external_organisation_id="org_dev_001",
            display_name="Alex Morgan",
            email="alex@example.test",
            organisation_name="Example Revenue Team",
            role="admin",
            auth_mode="mock",
        )


@lru_cache(maxsize=8)
def _jwks_client(url: str, timeout_seconds: float) -> PyJWKClient:
    return PyJWKClient(
        url,
        cache_keys=True,
        cache_jwk_set=True,
        lifespan=300,
        timeout=timeout_seconds,
    )


class ClerkAuthAdapter:
    """Verify Clerk session JWTs and return only server-trusted identity claims."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def authenticate(self, request: Request) -> VerifiedIdentity:
        if not self.settings.clerk_configuration_complete:
            raise AuthenticationUnavailableError("Clerk authentication is not configured.")
        authorisation = request.headers.get("Authorization", "")
        if not authorisation.startswith("Bearer "):
            raise AuthenticationError("Authentication is required.")
        token = authorisation.removeprefix("Bearer ").strip()
        if not token or len(token) > 16_384:
            raise AuthenticationError("Authentication is required.")
        assert self.settings.clerk_jwks_url is not None
        assert self.settings.clerk_issuer is not None
        assert self.settings.clerk_audience is not None
        try:
            signing_key = await asyncio.to_thread(
                _jwks_client(
                    self.settings.clerk_jwks_url,
                    self.settings.clerk_jwks_timeout_seconds,
                ).get_signing_key_from_jwt,
                token,
            )
            claims = jwt.decode(
                token,
                signing_key.key,
                algorithms=["RS256"],
                issuer=self.settings.clerk_issuer,
                audience=self.settings.clerk_audience,
                leeway=self.settings.clerk_jwt_leeway_seconds,
                options={"require": ["exp", "iat", "sub"]},
            )
        except PyJWKClientError as exc:
            raise AuthenticationUnavailableError("Clerk signing keys could not be loaded.") from exc
        except InvalidTokenError as exc:
            raise AuthenticationError("Authentication is required.") from exc

        external_user_id = self._required_claim(claims, "sub")
        external_organisation_id = self._required_claim(claims, "org_id")
        provider_role = str(claims.get("org_role", "")).lower()
        role: Role = "admin" if provider_role in {"admin", "org:admin"} else "member"
        fallback_hash = hashlib.sha256(external_user_id.encode()).hexdigest()[:20]
        email = self._optional_claim(claims, "email") or f"{fallback_hash}@identity.invalid"
        display_name = self._optional_claim(claims, "name") or "Private beta user"
        organisation_name = self._optional_claim(claims, "org_name") or "Private beta organisation"
        return VerifiedIdentity(
            external_auth_id=external_user_id,
            external_organisation_id=external_organisation_id,
            display_name=display_name[:200],
            email=email[:320],
            organisation_name=organisation_name[:200],
            role=role,
            auth_mode="clerk",
        )

    @staticmethod
    def _required_claim(claims: dict[str, object], key: str) -> str:
        value = claims.get(key)
        if not isinstance(value, str) or not value.strip() or len(value) > 255:
            raise AuthenticationError("Authentication is required.")
        return value.strip()

    @staticmethod
    def _optional_claim(claims: dict[str, object], key: str) -> str | None:
        value = claims.get(key)
        return value.strip() if isinstance(value, str) and value.strip() else None


def get_auth_adapter(settings: Settings = Depends(get_settings)) -> AuthAdapter:
    if settings.auth_mode == "clerk":
        return ClerkAuthAdapter(settings)
    return DevelopmentAuthAdapter(settings)


async def get_current_user(
    request: Request,
    adapter: AuthAdapter = Depends(get_auth_adapter),
) -> AuthenticatedUser:
    try:
        identity = await adapter.authenticate(request)
    except AuthenticationError as exc:
        raise PublicAPIError("authentication_required", "Authentication is required.", status_code=401) from exc
    except AuthenticationUnavailableError as exc:
        raise PublicAPIError(
            "authentication_unavailable",
            "Authentication is not available in this environment.",
            status_code=503,
        ) from exc

    if identity.auth_mode == "mock":
        user = AuthenticatedUser(
            user_id=DEVELOPMENT_USER_ID,
            external_auth_id=identity.external_auth_id,
            display_name=identity.display_name,
            email=identity.email,
            organisation_id=DEVELOPMENT_ORGANISATION_ID,
            organisation_name=identity.organisation_name,
            organisation_slug="example-revenue-team",
            role="admin",
            auth_mode="mock",
        )
        request.state.auth_user = user
        return user

    session_factory = cast(
        async_sessionmaker[AsyncSession] | None,
        request.app.state.session_factory,
    )
    if session_factory is None:
        raise PublicAPIError(
            "persistence_unavailable",
            "Persistence is not configured for this environment.",
            status_code=503,
        )
    async with session_factory() as session:
        try:
            user = await _resolve_identity(
                session,
                identity,
                allow_provisioning=request.app.state.settings.identity_jit_provisioning_enabled,
            )
        except AuthenticationError as exc:
            await session.rollback()
            raise PublicAPIError(
                "authentication_required",
                "Authentication is required.",
                status_code=401,
            ) from exc
        except AuthenticationUnavailableError as exc:
            await session.rollback()
            raise PublicAPIError(
                "authentication_unavailable",
                "Authentication is not available in this environment.",
                status_code=503,
            ) from exc
        except SQLAlchemyError as exc:
            await session.rollback()
            raise PublicAPIError(
                "authentication_unavailable",
                "Authentication is not available in this environment.",
                status_code=503,
            ) from exc
    request.state.auth_user = user
    return user


async def _resolve_identity(
    session: AsyncSession,
    identity: VerifiedIdentity,
    *,
    allow_provisioning: bool = True,
) -> AuthenticatedUser:
    organisation_id = identity_organisation_id(identity.external_organisation_id)
    await set_tenant_database_context(session, organisation_id)
    organisation = await session.scalar(
        select(Organisation).where(
            Organisation.id == organisation_id,
            Organisation.external_auth_id == identity.external_organisation_id,
        )
    )
    is_new_organisation = organisation is None
    user = await session.scalar(select(User).where(User.external_auth_id == identity.external_auth_id))
    if not allow_provisioning and (organisation is None or user is None):
        raise AuthenticationError("The authenticated organisation or user has not been provisioned.")
    if organisation is None:
        organisation = Organisation(
            id=organisation_id,
            external_auth_id=identity.external_organisation_id,
            name=identity.organisation_name,
            slug=_organisation_slug(identity.external_organisation_id),
        )
        session.add(organisation)
    if user is None:
        user = User(
            id=identity_user_id(identity.external_auth_id),
            external_auth_id=identity.external_auth_id,
            email=identity.email,
            display_name=identity.display_name,
            status="active",
        )
        session.add(user)
    try:
        await session.flush()
    except IntegrityError:
        await session.rollback()
        await set_tenant_database_context(session, organisation_id)
        organisation = await session.scalar(
            select(Organisation).where(
                Organisation.id == organisation_id,
                Organisation.external_auth_id == identity.external_organisation_id,
            )
        )
        user = await session.scalar(select(User).where(User.external_auth_id == identity.external_auth_id))

    if organisation is None or user is None or user.status != "active":
        raise AuthenticationError("The authenticated user is inactive or unavailable.")
    membership = await session.get(OrganisationMembership, (organisation.id, user.id))
    if membership is None:
        if not allow_provisioning:
            raise AuthenticationError("The authenticated membership has not been provisioned.")
        try:
            await require_seat_available(session, organisation.id, now=datetime.now(UTC))
        except PublicAPIError as exc:
            if not is_new_organisation:
                raise AuthenticationError("The organisation cannot activate another member.") from exc
        membership = OrganisationMembership(
            organisation_id=organisation.id,
            user_id=user.id,
            role=identity.role,
            status="active",
        )
        session.add(membership)
    elif membership.status != "active":
        raise AuthenticationError("The authenticated membership is disabled.")
    elif allow_provisioning and membership.role != identity.role and identity.auth_mode == "clerk":
        membership.role = identity.role

    if identity.auth_mode == "clerk":
        user.email = identity.email
        user.display_name = identity.display_name
        if allow_provisioning:
            organisation.name = identity.organisation_name
    await session.commit()
    return AuthenticatedUser(
        user_id=user.id,
        external_auth_id=user.external_auth_id,
        display_name=user.display_name,
        email=user.email,
        organisation_id=organisation.id,
        organisation_name=organisation.name,
        organisation_slug=organisation.slug,
        role="admin" if membership.role == "admin" else "member",
        auth_mode=identity.auth_mode,
    )


def _organisation_slug(external_organisation_id: str) -> str:
    readable = re.sub(r"[^a-z0-9]+", "-", external_organisation_id.lower()).strip("-")[:48]
    suffix = hashlib.sha256(external_organisation_id.encode()).hexdigest()[:12]
    return f"{readable or 'organisation'}-{suffix}"
