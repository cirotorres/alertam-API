from __future__ import annotations

from datetime import datetime
from typing import Callable

from fastapi import APIRouter

from app.api.v1.access import create_access_router
from app.api.v1.health import create_health_router
from app.api.v1.maneuver_events import create_maneuver_event_router
from app.api.v1.mobile_event_details import create_mobile_event_details_router
from app.api.v1.mobile_events import create_mobile_events_router
from app.api.v1.mobile_session import create_mobile_session_router
from app.api.v1.push import create_push_router
from app.api.v1.snapshots import create_snapshot_router
from app.api.v1.vessel_photos import create_vessel_photo_router
from app.api.v1.vessel_tracking_events import create_vessel_tracking_event_router
from app.api.v1.tracked_vessels import create_tracked_vessels_router
from app.repositories.events import AlertaRepository, StoredManeuverEvent
from app.services.tracked_vessel_projection_service import (
    TrackedVesselProjectionService,
)
from app.services.vessel_photo_service import VesselPhotoLookup


def create_v1_router(
    repository: AlertaRepository,
    *,
    stale_after_seconds: int,
    cookie_secure: bool,
    vessel_photo_service: VesselPhotoLookup,
    web_push_enabled: bool,
    vapid_public_key: str,
    clock: Callable[[], datetime] | None = None,
    dispatch_event: Callable[[StoredManeuverEvent], None] | None = None,
) -> APIRouter:
    router = APIRouter(prefix="/api/v1")
    projection = TrackedVesselProjectionService(repository)
    router.include_router(create_health_router())
    router.include_router(
        create_maneuver_event_router(
            repository,
            dispatch_event=dispatch_event,
            project_event=projection.apply_maneuver_event,
        )
    )
    router.include_router(
        create_vessel_tracking_event_router(
            repository,
            project_event=projection.apply_tracking_event,
        )
    )
    router.include_router(
        create_mobile_events_router(repository, clock=clock)
    )
    router.include_router(
        create_mobile_event_details_router(repository, clock=clock)
    )
    router.include_router(
        create_tracked_vessels_router(repository, clock=clock)
    )
    router.include_router(
        create_push_router(
            repository,
            web_push_enabled=web_push_enabled,
            vapid_public_key=vapid_public_key,
            clock=clock,
        )
    )
    router.include_router(
        create_mobile_session_router(
            repository,
            cookie_secure=cookie_secure,
            clock=clock,
        )
    )
    router.include_router(
        create_snapshot_router(
            repository,
            stale_after_seconds=stale_after_seconds,
            clock=clock,
        )
    )
    router.include_router(
        create_vessel_photo_router(
            repository,
            vessel_photo_service,
            clock=clock,
        )
    )
    router.include_router(create_access_router(repository))
    return router
