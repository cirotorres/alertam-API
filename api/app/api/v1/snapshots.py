from __future__ import annotations

from datetime import datetime
from typing import Callable

from fastapi import APIRouter, Cookie, Depends, Header

from app.api.v1.mobile_session import COOKIE_NAME
from app.models.mobile_snapshot import MobileSnapshotV1
from app.models.read_snapshot import SnapshotReadResponse
from app.models.responses import SnapshotAcceptedResponse
from app.repositories.devices import DevicesRepository
from app.security.credentials import (
    parse_bearer_authorization,
    parse_device_authorization,
)
from app.services.device_auth import AuthenticatedDevice
from app.services.mobile_session_service import MobileSessionService
from app.services.snapshot_read_service import SnapshotReadService
from app.services.snapshot_service import SnapshotService


def create_snapshot_router(
    repository: DevicesRepository,
    *,
    stale_after_seconds: int = 120,
    clock: Callable[[], datetime] | None = None,
) -> APIRouter:
    router = APIRouter(prefix="/devices")
    service = SnapshotService(repository)
    read_service = SnapshotReadService(
        repository,
        stale_after_seconds=stale_after_seconds,
        clock=clock,
    )
    session_service = MobileSessionService(repository, clock=clock)

    def require_device(
        device_id: str,
        authorization: str | None = Header(
            default=None,
            alias="Authorization",
        ),
    ) -> AuthenticatedDevice:
        device_secret = parse_device_authorization(authorization)
        return service.authenticate_device(
            device_id,
            device_secret,
        )

    @router.post(
        "/{device_id}/snapshot",
        response_model=SnapshotAcceptedResponse,
    )
    def post_snapshot(
        snapshot: MobileSnapshotV1,
        device: AuthenticatedDevice = Depends(require_device),
    ) -> SnapshotAcceptedResponse:
        return service.accept_authenticated_snapshot(
            device,
            snapshot,
        )

    @router.get(
        "/{device_id}/snapshot",
        response_model=SnapshotReadResponse,
    )
    def get_snapshot(
        device_id: str,
        authorization: str | None = Header(
            default=None,
            alias="Authorization",
        ),
        mobile_session: str | None = Cookie(
            default=None,
            alias=COOKIE_NAME,
        ),
    ) -> SnapshotReadResponse:
        if authorization is not None:
            view_secret = parse_bearer_authorization(authorization)
            return read_service.get_snapshot(device_id, view_secret)

        principal = session_service.resolve_session(mobile_session)
        if principal.device_id != device_id:
            from app.core.errors import InvalidViewCredentialsError

            raise InvalidViewCredentialsError()
        return read_service.get_authenticated_snapshot(device_id)

    return router
