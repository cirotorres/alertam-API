from __future__ import annotations

from datetime import datetime
from typing import Callable

from fastapi import APIRouter, Depends, Header

from app.models.mobile_snapshot import MobileSnapshotV1
from app.models.read_snapshot import SnapshotReadResponse
from app.models.responses import SnapshotAcceptedResponse
from app.repositories.devices import DevicesRepository
from app.security.credentials import (
    parse_bearer_authorization,
    parse_device_authorization,
)
from app.services.device_auth import AuthenticatedDevice
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
    ) -> SnapshotReadResponse:
        view_secret = parse_bearer_authorization(authorization)
        return read_service.get_snapshot(device_id, view_secret)

    return router
