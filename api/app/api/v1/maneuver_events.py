from __future__ import annotations

from typing import Callable

from fastapi import APIRouter, Depends, Header

from app.models.maneuver_event import (
    ManeuverEventAcceptedResponse,
    ManeuverEventIn,
)
from app.repositories.events import AlertaRepository, StoredManeuverEvent
from app.security.credentials import parse_device_authorization
from app.services.device_auth import AuthenticatedDevice
from app.services.maneuver_event_service import ManeuverEventService


def create_maneuver_event_router(
    repository: AlertaRepository,
    *,
    dispatch_event: Callable[[StoredManeuverEvent], None] | None = None,
    project_event: Callable[[StoredManeuverEvent], None] | None = None,
) -> APIRouter:
    router = APIRouter(prefix="/devices")
    service = ManeuverEventService(
        repository,
        dispatch_event=dispatch_event,
        project_event=project_event,
    )

    def require_device(
        device_id: str,
        authorization: str | None = Header(
            default=None,
            alias="Authorization",
        ),
    ) -> AuthenticatedDevice:
        device_secret = parse_device_authorization(authorization)
        return service.authenticate_device(device_id, device_secret)

    @router.post(
        "/{device_id}/maneuver-events",
        response_model=ManeuverEventAcceptedResponse,
    )
    def post_maneuver_event(
        event: ManeuverEventIn,
        device: AuthenticatedDevice = Depends(require_device),
    ) -> ManeuverEventAcceptedResponse:
        return service.accept_authenticated_event(device, event)

    return router
