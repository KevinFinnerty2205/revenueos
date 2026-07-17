from fastapi import APIRouter, Depends, Request

from revenueos.auth import AuthenticatedUser, get_current_user
from revenueos.contracts import MeResponse, OrganisationSummary, UserSummary
from revenueos.tenant import TenantContext, get_tenant_context

router = APIRouter(prefix="/api/v1", tags=["identity"])


@router.get("/me", response_model=MeResponse)
async def me(
    request: Request,
    user: AuthenticatedUser = Depends(get_current_user),
    tenant: TenantContext = Depends(get_tenant_context),
) -> MeResponse:
    return MeResponse(
        user=UserSummary(
            id=tenant.user_id,
            external_auth_id=user.external_auth_id,
            display_name=user.display_name,
            email=user.email,
        ),
        organisation=OrganisationSummary(
            id=tenant.organisation_id,
            name=user.organisation_name,
            slug=user.organisation_slug,
        ),
        role=tenant.role,
        auth_mode=user.auth_mode,
        request_id=request.state.request_id,
    )
