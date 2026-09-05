import logging
import time
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.exc import SQLAlchemyError
from starlette.middleware.trustedhost import TrustedHostMiddleware
from starlette.responses import Response

from revenueos.commercial_dependencies import require_commercial_workspace_access
from revenueos.config import Settings, get_settings
from revenueos.database import create_engine, create_session_factory
from revenueos.development import ensure_development_identity
from revenueos.errors import (
    PublicAPIError,
    http_error_handler,
    public_api_error_handler,
    unhandled_error_handler,
    validation_error_handler,
)
from revenueos.observability import configure_logging
from revenueos.routes import (
    accounts,
    actions,
    ask,
    beta,
    billing,
    campaigns,
    commercial,
    companies,
    contacts,
    create,
    credits,
    crm,
    daily,
    events,
    evidence,
    health,
    integrations,
    interactions,
    manager,
    me,
    meetings,
    methodologies,
    opportunities,
    outreach,
    pipelines,
    prospect,
    sales_forecast,
    sales_insights,
    sales_targets,
    selling_profile,
    tasks,
)

logger = logging.getLogger("revenueos.http")
REQUEST_ID_ALLOWED_CHARACTERS = frozenset("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_.:")


def safe_request_id(candidate: str | None) -> str:
    if (
        candidate
        and len(candidate) <= 128
        and all(character in REQUEST_ID_ALLOWED_CHARACTERS for character in candidate)
    ):
        return candidate
    return str(uuid.uuid4())


def create_app(settings: Settings | None = None) -> FastAPI:
    app_settings = settings or get_settings()
    configure_logging(app_settings.log_level)
    app_engine = create_engine(app_settings)
    session_factory = create_session_factory(app_engine)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        if app_settings.environment == "development" and app_settings.mock_auth_enabled and session_factory is not None:
            try:
                await ensure_development_identity(session_factory)
            except SQLAlchemyError:
                logger.warning("development_identity_provisioning_failed")
        yield
        if app_engine is not None:
            await app_engine.dispose()

    app = FastAPI(
        title="RevenueOS AI API",
        version="0.4.0",
        description="Tenant-isolated RevenueOS private beta API.",
        docs_url=None if app_settings.environment == "production" else "/docs",
        redoc_url=None if app_settings.environment == "production" else "/redoc",
        lifespan=lifespan,
    )
    app.state.settings = app_settings
    app.state.engine = app_engine
    app.state.session_factory = session_factory
    app.dependency_overrides[get_settings] = lambda: app_settings
    app.add_middleware(
        CORSMiddleware,
        allow_origins=app_settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["DELETE", "GET", "OPTIONS", "PATCH", "POST", "PUT"],
        allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
        expose_headers=["X-Request-ID"],
    )
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=app_settings.allowed_host_list)

    app.add_exception_handler(PublicAPIError, public_api_error_handler)
    app.add_exception_handler(RequestValidationError, validation_error_handler)
    app.add_exception_handler(Exception, unhandled_error_handler)
    for status_code in (401, 403, 404, 405):
        app.add_exception_handler(status_code, http_error_handler)

    @app.middleware("http")
    async def request_context_middleware(
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        request_id = safe_request_id(request.headers.get("X-Request-ID"))
        request.state.request_id = request_id
        started = time.perf_counter()
        response: Response | None = None
        try:
            response = await call_next(request)
            response.headers["X-Request-ID"] = request_id
            response.headers.setdefault("Cache-Control", "no-store")
            response.headers.setdefault(
                "Content-Security-Policy",
                "default-src 'none'; frame-ancestors 'none'; base-uri 'none'",
            )
            response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=(), payment=()"
            response.headers["Referrer-Policy"] = "no-referrer"
            response.headers["X-Content-Type-Options"] = "nosniff"
            response.headers["X-Frame-Options"] = "DENY"
            if app_settings.environment == "production":
                response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
            return response
        finally:
            duration_ms = round((time.perf_counter() - started) * 1000, 2)
            logger.info(
                "request_completed",
                extra={
                    "request_id": request_id,
                    "method": request.method,
                    "path": request.url.path,
                    "status_code": response.status_code if response is not None else 500,
                    "duration_ms": duration_ms,
                    "organisation_id": str(request.state.auth_user.organisation_id)
                    if getattr(request.state, "auth_user", None) is not None
                    else None,
                    "user_id": str(request.state.auth_user.user_id)
                    if getattr(request.state, "auth_user", None) is not None
                    else None,
                },
            )

    app.include_router(health.router)
    app.include_router(me.router)
    app.include_router(beta.router)
    app.include_router(billing.router)
    app.include_router(commercial.router)
    app.include_router(credits.router)
    commercial_access = [Depends(require_commercial_workspace_access)]
    app.include_router(companies.router, dependencies=commercial_access)
    app.include_router(contacts.router, dependencies=commercial_access)
    app.include_router(crm.router, dependencies=commercial_access)
    app.include_router(daily.router, dependencies=commercial_access)
    app.include_router(evidence.router, dependencies=commercial_access)
    app.include_router(opportunities.router, dependencies=commercial_access)
    app.include_router(pipelines.router, dependencies=commercial_access)
    app.include_router(prospect.router, dependencies=commercial_access)
    app.include_router(sales_insights.router, dependencies=commercial_access)
    app.include_router(sales_forecast.router, dependencies=commercial_access)
    app.include_router(sales_targets.router, dependencies=commercial_access)
    app.include_router(selling_profile.router, dependencies=commercial_access)
    app.include_router(tasks.router, dependencies=commercial_access)
    app.include_router(interactions.router, dependencies=commercial_access)
    app.include_router(manager.router, dependencies=commercial_access)
    app.include_router(meetings.router, dependencies=commercial_access)
    app.include_router(methodologies.router, dependencies=commercial_access)
    app.include_router(accounts.router, dependencies=commercial_access)
    app.include_router(actions.router, dependencies=commercial_access)
    app.include_router(ask.router, dependencies=commercial_access)
    app.include_router(integrations.router, dependencies=commercial_access)
    app.include_router(outreach.router, dependencies=commercial_access)
    app.include_router(campaigns.router, dependencies=commercial_access)
    app.include_router(events.router, dependencies=commercial_access)
    app.include_router(create.router, dependencies=commercial_access)
    return app


app = create_app()
