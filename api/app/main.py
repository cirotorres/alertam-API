from __future__ import annotations

from datetime import datetime
from typing import Callable

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.v1.router import create_v1_router
from app.core.config import Settings
from app.core.errors import ApiError
from app.core.logging import (
    HttpRequestLoggingMiddleware,
    configure_logging,
)
from app.repositories.devices import DevicesRepository
from app.repositories.factory import create_devices_repository


def create_app(
    repository: DevicesRepository | None = None,
    *,
    settings: Settings | None = None,
    stale_after_seconds: int | None = None,
    clock: Callable[[], datetime] | None = None,
) -> FastAPI:
    resolved_settings = settings or Settings()
    resolved_stale_after = (
        stale_after_seconds
        if stale_after_seconds is not None
        else resolved_settings.stale_after_seconds
    )

    configure_logging(resolved_settings.log_level)

    application = FastAPI(
        title="AlertaM Mobile API",
        version="0.1.0",
    )
    devices_repository = (
        repository
        if repository is not None
        else create_devices_repository(resolved_settings)
    )

    application.include_router(
        create_v1_router(
            devices_repository,
            stale_after_seconds=resolved_stale_after,
            cookie_secure=resolved_settings.environment == "production",
            clock=clock,
        )
    )

    application.add_middleware(HttpRequestLoggingMiddleware)

    allowed_origins = resolved_settings.allowed_origins_list
    if allowed_origins:
        application.add_middleware(
            CORSMiddleware,
            allow_origins=allowed_origins,
            allow_credentials=False,
            allow_methods=["GET", "POST", "PUT", "OPTIONS"],
            allow_headers=["Authorization", "Content-Type"],
        )

    @application.exception_handler(ApiError)
    async def handle_api_error(
        _request: Request,
        exc: ApiError,
    ) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.detail},
        )

    @application.exception_handler(RequestValidationError)
    async def handle_validation_error(
        _request: Request,
        exc: RequestValidationError,
    ) -> JSONResponse:
        for error in exc.errors():
            if (
                error.get("loc") == ("body", "schema_version")
                and error.get("type") == "literal_error"
            ):
                return JSONResponse(
                    status_code=422,
                    content={
                        "detail": {
                            "code": "unsupported_snapshot_schema",
                            "message": "Versão de snapshot não suportada.",
                        }
                    },
                )

        return JSONResponse(
            status_code=422,
            content={
                "detail": {
                    "code": "invalid_request_payload",
                    "message": "Payload inválido.",
                }
            },
        )

    return application


app = create_app()
