from dataclasses import dataclass
from typing import Literal
from uuid import UUID

from fastapi import Depends

from revenueos.auth import AuthenticatedUser, get_current_user
from revenueos.errors import PublicAPIError

Role = Literal["admin", "manager", "member"]


@dataclass(frozen=True)
class TenantContext:
    organisation_id: UUID
    user_id: UUID
    role: Role

    @classmethod
    def from_authenticated_user(cls, user: AuthenticatedUser) -> "TenantContext":
        return cls(
            organisation_id=user.organisation_id,
            user_id=user.user_id,
            role=user.role,
        )

    def can_manage(self) -> bool:
        return self.role in {"admin", "manager"}


def get_tenant_context(
    authenticated_user: AuthenticatedUser = Depends(get_current_user),
) -> TenantContext:
    """Derive tenant context only from the verified authentication adapter."""

    return TenantContext.from_authenticated_user(authenticated_user)


def require_manager(
    context: TenantContext = Depends(get_tenant_context),
) -> TenantContext:
    if not context.can_manage():
        raise PublicAPIError("forbidden", "You do not have permission to perform this action.", 403)
    return context
