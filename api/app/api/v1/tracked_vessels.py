from __future__ import annotations

from datetime import datetime
from typing import Callable
from uuid import UUID

from fastapi import APIRouter, Depends, Response, status

from app.api.v1.mobile_auth import MobileInstallationAuth
from app.models.tracked_vessel import (
    TrackedVesselCreateRequest,
    TrackedVesselResponse,
)
from app.repositories.events import AlertaRepository
from app.services.mobile_session_service import MobileSessionPrincipal
from app.services.tracked_vessel_service import TrackedVesselService


def create_tracked_vessels_router(
    repository: AlertaRepository,
    *,
    clock: Callable[[], datetime] | None = None,
) -> APIRouter:
    router = APIRouter(prefix="/mobile/tracked-vessels")
    auth = MobileInstallationAuth(repository, clock=clock)
    service = TrackedVesselService(repository)

    @router.get("", response_model=list[TrackedVesselResponse])
    def list_tracked_vessels(
        principal: MobileSessionPrincipal = Depends(auth),
    ) -> list[TrackedVesselResponse]:
        return service.list(principal)

    @router.post("", response_model=TrackedVesselResponse)
    def start_tracking(
        request: TrackedVesselCreateRequest,
        principal: MobileSessionPrincipal = Depends(auth),
    ) -> TrackedVesselResponse:
        return service.start(principal, request)

    @router.delete(
        "/{tracked_vessel_id}",
        status_code=status.HTTP_204_NO_CONTENT,
    )
    def stop_tracking(
        tracked_vessel_id: UUID,
        principal: MobileSessionPrincipal = Depends(auth),
    ) -> Response:
        service.stop(principal, tracked_vessel_id)
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    return router
