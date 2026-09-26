from __future__ import annotations

from fastapi import APIRouter, Depends, Header

from app.models.mobile_snapshot import MobileSnapshotV1
from app.models.responses import SnapshotAcceptedResponse
from app.repositories.devices import DevicesRepository
from app.security.credentials import parse_device_authorization
from app.services.snapshot_service import AuthenticatedDevice, SnapshotService


def create_snapshot_router(
    repository: DevicesRepository,
) -> APIRouter:
    router = APIRouter(prefix="/api/v1/devices")
    service = SnapshotService(repository)

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

    return router
