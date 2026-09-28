from __future__ import annotations

from datetime import datetime
from typing import Callable
from uuid import UUID

from fastapi import APIRouter, Depends

from app.api.v1.mobile_auth import MobileSessionAuth
from app.models.maneuver_event import ManeuverEventDetailResponse
from app.repositories.events import AlertaRepository
from app.services.event_detail_service import EventDetailService


def create_mobile_event_details_router(
    repository: AlertaRepository,
    *,
    clock: Callable[[], datetime] | None = None,
) -> APIRouter:
    router = APIRouter(prefix="/mobile/events")
    auth = MobileSessionAuth(repository, clock=clock)
    service = EventDetailService(repository)

    @router.get(
        "/{event_id}/detail",
        response_model=ManeuverEventDetailResponse,
    )
    def get_maneuver_event_detail(
        event_id: UUID,
        device_id: str = Depends(auth),
    ) -> ManeuverEventDetailResponse:
        return service.get_detail(device_id, event_id)

    return router
