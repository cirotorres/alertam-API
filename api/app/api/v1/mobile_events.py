from __future__ import annotations

from datetime import datetime
from typing import Callable

from fastapi import APIRouter, Depends, Query

from app.api.v1.mobile_auth import MobileSessionAuth
from app.core.errors import InvalidEventCursorError
from app.models.maneuver_event import ManeuverEventFeedResponse
from app.repositories.events import AlertaRepository
from app.services.event_feed_service import EventFeedService


def create_mobile_events_router(
    repository: AlertaRepository,
    *,
    clock: Callable[[], datetime] | None = None,
) -> APIRouter:
    router = APIRouter(prefix="/mobile/maneuver-events")
    auth = MobileSessionAuth(repository, clock=clock)
    service = EventFeedService(repository)

    @router.get("", response_model=ManeuverEventFeedResponse)
    def get_maneuver_events(
        after: int | None = Query(default=None, ge=1),
        before: int | None = Query(default=None, ge=1),
        limit: int = Query(default=50, ge=1, le=100),
        device_id: str = Depends(auth),
    ) -> ManeuverEventFeedResponse:
        if after is not None and before is not None:
            raise InvalidEventCursorError()
        return service.get_page(
            device_id,
            after=after,
            before=before,
            limit=limit,
        )

    return router
