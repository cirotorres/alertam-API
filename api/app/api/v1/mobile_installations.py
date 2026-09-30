from datetime import datetime
from typing import Callable
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Response, status

from app.models.mobile_installation import (
    MobileInstallationAdminItem,
    MobileInstallationsAdminResponse,
)
from app.repositories.devices import DevicesRepository, MobileInstallationRecord
from app.security.credentials import parse_device_authorization
from app.services.device_auth import AuthenticatedDevice
from app.services.mobile_installation_admin_service import (
    MobileInstallationAdminService,
)


def _item(record: MobileInstallationRecord) -> MobileInstallationAdminItem:
    return MobileInstallationAdminItem(
        installation_id=record.installation_id,
        display_code=record.display_code,
        platform=record.platform,
        active=record.active,
        created_at=record.created_at,
        last_seen_at=record.last_seen_at,
        revoked_at=record.revoked_at,
    )


def create_mobile_installations_router(
    repository: DevicesRepository,
    *,
    clock: Callable[[], datetime] | None = None,
) -> APIRouter:
    router = APIRouter(prefix="/devices")
    service = MobileInstallationAdminService(repository, clock=clock)

    def require_device(
        device_id: str,
        authorization: str | None = Header(
            default=None,
            alias="Authorization",
        ),
    ) -> AuthenticatedDevice:
        device_secret = parse_device_authorization(authorization)
        return service.authenticate(device_id, device_secret)

    @router.get(
        "/{device_id}/mobile-installations",
        response_model=MobileInstallationsAdminResponse,
    )
    def list_mobile_installations(
        device: AuthenticatedDevice = Depends(require_device),
    ) -> MobileInstallationsAdminResponse:
        snapshot = service.list_for_device(device)
        return MobileInstallationsAdminResponse(
            active_count=snapshot.active_count,
            active=[_item(item) for item in snapshot.active],
            recently_revoked=[
                _item(item) for item in snapshot.recently_revoked
            ],
        )

    @router.delete(
        "/{device_id}/mobile-installations/{installation_id}",
        status_code=status.HTTP_204_NO_CONTENT,
        response_class=Response,
    )
    def revoke_mobile_installation(
        installation_id: UUID,
        device: AuthenticatedDevice = Depends(require_device),
    ) -> Response:
        service.revoke(device, installation_id)
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    return router
