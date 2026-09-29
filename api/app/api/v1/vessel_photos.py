from __future__ import annotations

from datetime import datetime
from typing import Callable

from fastapi import APIRouter, Cookie, Header

from app.api.v1.mobile_session import COOKIE_NAME
from app.core.errors import InvalidViewCredentialsError, VesselNotInSnapshotError
from app.models.vessel_photo import VesselPhotoResponse
from app.repositories.devices import DevicesRepository
from app.security.credentials import parse_bearer_authorization
from app.services.mobile_session_service import MobileSessionService
from app.services.snapshot_read_service import SnapshotReadService
from app.services.vessel_photo_service import VesselPhotoLookup


def create_vessel_photo_router(
    repository: DevicesRepository,
    photo_service: VesselPhotoLookup,
    *,
    clock: Callable[[], datetime] | None = None,
) -> APIRouter:
    router = APIRouter(prefix="/devices")
    read_service = SnapshotReadService(repository, clock=clock)
    session_service = MobileSessionService(repository, clock=clock)

    @router.get(
        "/{device_id}/vessels/{imo}/photo",
        response_model=VesselPhotoResponse,
    )
    def get_vessel_photo(
        device_id: str,
        imo: str,
        authorization: str | None = Header(default=None, alias="Authorization"),
        mobile_session: str | None = Cookie(default=None, alias=COOKIE_NAME),
    ) -> VesselPhotoResponse:
        if authorization is not None:
            view_secret = parse_bearer_authorization(authorization)
            read_service.authenticate_view(device_id, view_secret)
        else:
            principal = session_service.resolve_session(mobile_session)
            if principal.device_id != device_id:
                raise InvalidViewCredentialsError()

        snapshot = read_service.get_authenticated_snapshot(device_id).snapshot
        if not any(vessel.imo == imo for vessel in snapshot.vessels):
            raise VesselNotInSnapshotError()
        return photo_service.get_photo(imo)

    return router
