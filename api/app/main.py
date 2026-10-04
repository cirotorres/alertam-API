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
from app.infrastructure.web_push import WebPushGateway
from app.core.logging import (
    HttpRequestLoggingMiddleware,
    configure_logging,
)
from app.repositories.events import AlertaRepository, StoredManeuverEvent
from app.repositories.tracking import StoredVesselTrackingEvent
from app.repositories.factory import create_devices_repository
from app.services.anchorage_entry import AnchorageEntryEvent
from app.services.push_dispatch_service import (
    AnchoragePushDispatchService,
    PushDispatchService,
    PushGateway,
)
from app.services.tracking_push_dispatch_service import (
    TrackingPushDispatchService,
)
from app.services.vessel_photo_service import (
    VesselPhotoLookup,
    VesselPhotoService,
)


def create_app(
    repository: AlertaRepository | None = None,
    *,
    settings: Settings | None = None,
    stale_after_seconds: int | None = None,
    clock: Callable[[], datetime] | None = None,
    vessel_photo_service: VesselPhotoLookup | None = None,
    dispatch_event: Callable[[StoredManeuverEvent], None] | None = None,
    dispatch_tracking_event: Callable[
        [StoredVesselTrackingEvent], None
    ] | None = None,
    dispatch_anchorage_entry: Callable[
        [AnchorageEntryEvent], None
    ] | None = None,
    web_push_gateway: PushGateway | None = None,
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

    resolved_photo_service = vessel_photo_service or VesselPhotoService(
        timeout=resolved_settings.vessel_photo_timeout_seconds,
        user_agent=resolved_settings.vessel_photo_user_agent,
    )

    resolved_dispatch_event = dispatch_event
    resolved_dispatch_tracking_event = dispatch_tracking_event
    resolved_dispatch_anchorage_entry = dispatch_anchorage_entry
    if resolved_settings.web_push_enabled and (
        resolved_dispatch_event is None
        or resolved_dispatch_tracking_event is None
        or resolved_dispatch_anchorage_entry is None
    ):
        resolved_gateway = web_push_gateway or WebPushGateway(
            vapid_private_key=resolved_settings.vapid_private_key,
            vapid_subject=resolved_settings.vapid_subject,
        )
        if resolved_dispatch_event is None:
            push_dispatcher = PushDispatchService(
                devices_repository,
                resolved_gateway,
                foreground_fresh_seconds=(
                    resolved_settings.push_foreground_fresh_seconds
                ),
                clock=clock,
            )
            resolved_dispatch_event = push_dispatcher.dispatch_event
        if resolved_dispatch_tracking_event is None:
            tracking_push_dispatcher = TrackingPushDispatchService(
                devices_repository,
                resolved_gateway,
                foreground_fresh_seconds=(
                    resolved_settings.push_foreground_fresh_seconds
                ),
                clock=clock,
            )
            resolved_dispatch_tracking_event = (
                tracking_push_dispatcher.dispatch_event
            )
        if resolved_dispatch_anchorage_entry is None:
            anchorage_push_dispatcher = AnchoragePushDispatchService(
                devices_repository,
                resolved_gateway,
                foreground_fresh_seconds=(
                    resolved_settings.push_foreground_fresh_seconds
                ),
                clock=clock,
            )
            resolved_dispatch_anchorage_entry = (
                anchorage_push_dispatcher.dispatch_event
            )

    application.include_router(
        create_v1_router(
            devices_repository,
            stale_after_seconds=resolved_stale_after,
            cookie_secure=resolved_settings.environment == "production",
            vessel_photo_service=resolved_photo_service,
            web_push_enabled=resolved_settings.web_push_enabled,
            vapid_public_key=resolved_settings.vapid_public_key,
            clock=clock,
            dispatch_event=resolved_dispatch_event,
            dispatch_tracking_event=resolved_dispatch_tracking_event,
            dispatch_anchorage_entry=resolved_dispatch_anchorage_entry,
        )
    )

    application.add_middleware(HttpRequestLoggingMiddleware)

    allowed_origins = resolved_settings.allowed_origins_list
    if allowed_origins:
        application.add_middleware(
            CORSMiddleware,
            allow_origins=allowed_origins,
            allow_credentials=False,
            allow_methods=[
                "GET",
                "POST",
                "PUT",
                "PATCH",
                "DELETE",
                "OPTIONS",
            ],
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
            loc = error.get("loc")
            error_type = error.get("type")
            ctx = error.get("ctx") or {}
            unsupported_schema = (
                loc == ("body", "schema_version")
                and error_type == "literal_error"
            ) or (
                loc == ("body",)
                and error_type == "union_tag_invalid"
                and "schema_version" in str(ctx.get("discriminator", ""))
            )
            if unsupported_schema:
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
