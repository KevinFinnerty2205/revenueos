import logging
import time
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from starlette.responses import Response

from revenueos.config import Settings, get_settings
from revenueos.database import create_engine, create_session_factory
from revenueos.errors import (
    PublicAPIError,
    http_error_handler,
    public_api_error_handler,
    unhandled_error_handler,
    validation_error_handler,
)
from revenueos.observability import configure_logging
from revenueos.routes import health, me

logger = logging.getLogger("revenueos.http")


def create_app(settings: Settings | None = None) -> FastAPI:
    app_settings = settings or get_settings()
    configure_logging(app_settings.log_level)
    app_engine = create_engine(app_settings)
    session_factory = create_session_factory(app_engine)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        yield
        if app_engine is not None:
            await app_engine.dispose()

    app = FastAPI(
        title="RevenueOS AI API",
        version="0.1.0",
        description="Versioned Sprint 1 foundation API for RevenueOS AI.",
        docs_url="/docs",
        redoc_url="/redoc",
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
        allow_methods=["GET", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
        expose_headers=["X-Request-ID"],
    )

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
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        request.state.request_id = request_id
        started = time.perf_counter()
        response: Response | None = None
        try:
            response = await call_next(request)
            response.headers["X-Request-ID"] = request_id
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
                },
            )

    app.include_router(health.router)
    app.include_router(me.router)
    return app


app = create_app()
