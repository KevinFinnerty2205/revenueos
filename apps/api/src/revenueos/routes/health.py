from fastapi import APIRouter, Depends, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncEngine

from revenueos.config import Settings, get_settings
from revenueos.contracts import DependencyCheck, HealthResponse, ReadyResponse
from revenueos.database import database_is_ready

router = APIRouter(tags=["system"])


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse(status="healthy")


@router.get(
    "/ready",
    response_model=ReadyResponse,
    responses={503: {"model": ReadyResponse}},
)
async def ready(
    request: Request,
    response: Response,
    settings: Settings = Depends(get_settings),
) -> ReadyResponse:
    engine: AsyncEngine | None = request.app.state.engine
    database_ready = await database_is_ready(engine)
    database_check = DependencyCheck(
        status="ready" if database_ready else "unavailable",
        detail="Database connection succeeded." if database_ready else "Persistence is unavailable.",
    )

    if settings.auth_mode == "mock":
        auth_ready = settings.mock_auth_enabled and settings.environment != "production"
        auth_check = DependencyCheck(
            status="ready" if auth_ready else "misconfigured",
            detail=(
                "Clearly labelled development authentication is active."
                if auth_ready
                else "Development authentication is disabled or prohibited."
            ),
        )
    else:
        auth_check = DependencyCheck(
            status="unavailable",
            detail=(
                "Clerk configuration is present but token verification is not connected."
                if settings.clerk_configuration_complete
                else "Clerk verification configuration is incomplete."
            ),
        )
        auth_ready = False

    is_ready = database_ready and auth_ready
    if not is_ready:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    return ReadyResponse(
        status="ready" if is_ready else "not_ready",
        environment=settings.environment,
        dependencies={"database": database_check, "authentication": auth_check},
        request_id=request.state.request_id,
    )
