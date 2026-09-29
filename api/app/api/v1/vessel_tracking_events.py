from __future__ import annotations

from fastapi import APIRouter, Depends, Header

from app.models.vessel_tracking_event import (
    VesselTrackingEventAcceptedResponse,
    VesselTrackingEventIn,
)
from app.repositories.events import AlertaRepository
from app.security.credentials import parse_device_authorization
from app.services.device_auth import AuthenticatedDevice
from app.services.vessel_tracking_event_service import VesselTrackingEventService


def create_vessel_tracking_event_router(
    repository: AlertaRepository,
) -> APIRouter:
    router = APIRouter(prefix="/devices")
    service = VesselTrackingEventService(repository)

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
        "/{device_id}/vessel-tracking-events",
        response_model=VesselTrackingEventAcceptedResponse,
    )
    def post_vessel_tracking_event(
        event: VesselTrackingEventIn,
        device: AuthenticatedDevice = Depends(require_device),
    ) -> VesselTrackingEventAcceptedResponse:
        return service.accept_authenticated_event(device, event)

    return router
