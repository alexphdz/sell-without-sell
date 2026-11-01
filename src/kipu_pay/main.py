"""FastAPI application entrypoint."""

from __future__ import annotations

import uuid
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from kipu_pay.core.config import Settings, get_settings
from kipu_pay.core.exceptions import KipuError
from kipu_pay.core.logging import clear_request_id, configure_logging, get_logger, set_request_id
from kipu_pay.core.models import HealthResponse
from kipu_pay.core.utils import safe_request_id

logger = get_logger(__name__)


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Attach or propagate a safe request ID to every request."""

    async def dispatch(self, request: Request, call_next):
        raw = request.headers.get("x-request-id")
        rid = safe_request_id(raw) or str(uuid.uuid4())
        set_request_id(rid)
        response = await call_next(request)
        response.headers["x-request-id"] = rid
        clear_request_id()
        return response


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan: startup and shutdown."""
    settings = get_settings()
    configure_logging(log_level=settings.log_level, json_format=settings.app_env != "local")
    logger.info("application_startup", version=settings.app_version, env=settings.app_env)
    yield
    logger.info("application_shutdown")


def create_app(settings: Settings | None = None) -> FastAPI:
    """Application factory."""
    if settings is None:
        settings = get_settings()

    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        docs_url="/docs" if settings.app_env == "local" else None,
        redoc_url="/redoc" if settings.app_env == "local" else None,
        lifespan=lifespan,
    )

    app.add_middleware(RequestIDMiddleware)

    @app.exception_handler(KipuError)
    async def _kipu_error_handler(request: Request, exc: KipuError) -> JSONResponse:
        logger.warning(
            "application_error",
            code=exc.code,
            status_code=exc.status_code,
            path=request.url.path,
        )
        return JSONResponse(
            status_code=exc.status_code,
            content=exc.to_dict(),
            headers={"x-request-id": request.headers.get("x-request-id", "-")},
        )

    @app.exception_handler(Exception)
    async def _unexpected_error_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("unexpected_error", path=request.url.path)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": {
                    "code": "internal_error",
                    "message": "An unexpected error occurred.",
                }
            },
            headers={"x-request-id": request.headers.get("x-request-id", "-")},
        )

    from kipu_pay.api.router import router as participant_router

    app.include_router(participant_router)

    @app.get("/v1/health", response_model=HealthResponse)
    @app.get("/health", response_model=HealthResponse)
    async def health() -> HealthResponse:
        """Liveness probe; does not require database."""
        return HealthResponse(
            status="ok",
            team=settings.team_name,
            version=settings.app_version,
            models=[],
        )

    return app


app = create_app()
