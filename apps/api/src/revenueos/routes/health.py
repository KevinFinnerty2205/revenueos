import asyncio

from fastapi import APIRouter, Depends, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncEngine

from revenueos.config import Settings, get_settings
from revenueos.contracts import DependencyCheck, HealthResponse, ReadyResponse
from revenueos.database import database_is_ready, database_migration_version

router = APIRouter(tags=["system"])
EXPECTED_MIGRATION_HEAD = "0032_integration_execution"


@router.get("/health", response_model=HealthResponse)
@router.get("/health/live", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse(status="healthy")


@router.get(
    "/ready",
    response_model=ReadyResponse,
    responses={503: {"model": ReadyResponse}},
)
@router.get(
    "/health/ready",
    response_model=ReadyResponse,
    responses={503: {"model": ReadyResponse}},
)
async def ready(
    request: Request,
    response: Response,
    settings: Settings = Depends(get_settings),
) -> ReadyResponse:
    engine: AsyncEngine | None = request.app.state.engine
    try:
        database_ready = await asyncio.wait_for(database_is_ready(engine), timeout=2.0)
    except TimeoutError:
        database_ready = False
    database_check = DependencyCheck(
        status="ready" if database_ready else "unavailable",
        detail="Database connection succeeded." if database_ready else "Persistence is unavailable.",
    )

    migration_version = None
    if database_ready:
        try:
            migration_version = await asyncio.wait_for(database_migration_version(engine), timeout=2.0)
        except TimeoutError:
            migration_version = None
    migration_ready = migration_version == EXPECTED_MIGRATION_HEAD
    if migration_version is None and settings.environment in {"development", "test"}:
        migration_ready = True
    migration_check = DependencyCheck(
        status="ready" if migration_ready else "misconfigured",
        detail=(
            "Database migration is compatible."
            if migration_ready
            else "Database migration is not compatible with this release."
        ),
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
        auth_ready = settings.clerk_configuration_complete
        auth_check = DependencyCheck(
            status="ready" if auth_ready else "misconfigured",
            detail=(
                "Clerk JWT verification is configured."
                if auth_ready
                else "Clerk verification configuration is incomplete."
            ),
        )

    provider_ready = settings.ai_provider_name == "mock" or (
        settings.feature_openai_provider_enabled
        and settings.openai_api_key is not None
        and settings.openai_model is not None
    )
    provider_check = DependencyCheck(
        status="ready" if provider_ready else "misconfigured",
        detail=(
            "Selected AI provider configuration is valid."
            if provider_ready
            else "Selected AI provider configuration is unavailable."
        ),
    )
    worker_ready = settings.worker_heartbeat_interval_seconds < settings.worker_lease_duration_seconds
    worker_check = DependencyCheck(
        status="ready" if worker_ready else "misconfigured",
        detail="Worker configuration is valid." if worker_ready else "Worker configuration is invalid.",
    )

    is_ready = database_ready and migration_ready and auth_ready and provider_ready and worker_ready
    if not is_ready:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    return ReadyResponse(
        status="ready" if is_ready else "not_ready",
        environment=settings.environment,
        dependencies={
            "database": database_check,
            "migration": migration_check,
            "authentication": auth_check,
            "aiProvider": provider_check,
            "worker": worker_check,
        },
        request_id=request.state.request_id,
    )
