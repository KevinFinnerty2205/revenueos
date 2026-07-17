from dataclasses import dataclass
from typing import Literal, Protocol
from uuid import UUID

from fastapi import Depends, Request

from revenueos.config import Settings, get_settings
from revenueos.errors import PublicAPIError

Role = Literal["admin", "manager", "member"]


class AuthenticationError(Exception):
    """Raised when a request has no valid authentication."""


class AuthenticationUnavailableError(Exception):
    """Raised when the configured authentication provider is not ready."""


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
    auth_mode: Literal["mock", "clerk"]


class AuthAdapter(Protocol):
    def authenticate(self, request: Request) -> AuthenticatedUser: ...


class DevelopmentAuthAdapter:
    """Clearly labelled local adapter that is prohibited in production."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def authenticate(self, request: Request) -> AuthenticatedUser:
        del request
        if not self.settings.mock_auth_enabled or self.settings.environment == "production":
            raise AuthenticationUnavailableError("Development authentication is disabled.")
        return AuthenticatedUser(
            user_id=UUID("00000000-0000-4000-8000-000000000001"),
            external_auth_id="user_dev_001",
            display_name="Alex Morgan",
            email="alex@example.test",
            organisation_id=UUID("00000000-0000-4000-8000-000000000002"),
            organisation_name="Example Revenue Team",
            organisation_slug="example-revenue-team",
            role="admin",
            auth_mode="mock",
        )


class ClerkAuthAdapter:
    """Production adapter boundary for future verified Clerk JWT handling."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def authenticate(self, request: Request) -> AuthenticatedUser:
        if not self.settings.clerk_configuration_complete:
            raise AuthenticationUnavailableError("Clerk authentication is not configured.")
        authorisation = request.headers.get("Authorization", "")
        if not authorisation.startswith("Bearer "):
            raise AuthenticationError("Authentication is required.")
        raise AuthenticationUnavailableError("Clerk token verification is not connected in the Sprint 1 foundation.")


def get_auth_adapter(settings: Settings = Depends(get_settings)) -> AuthAdapter:
    if settings.auth_mode == "clerk":
        return ClerkAuthAdapter(settings)
    return DevelopmentAuthAdapter(settings)


def get_current_user(
    request: Request,
    adapter: AuthAdapter = Depends(get_auth_adapter),
) -> AuthenticatedUser:
    try:
        user = adapter.authenticate(request)
    except AuthenticationError as exc:
        raise PublicAPIError("authentication_required", "Authentication is required.", status_code=401) from exc
    except AuthenticationUnavailableError as exc:
        raise PublicAPIError(
            "authentication_unavailable",
            "Authentication is not available in this environment.",
            status_code=503,
        ) from exc
    request.state.auth_user = user
    return user
