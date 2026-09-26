from __future__ import annotations

from fastapi import APIRouter, Depends, Header, Response, status

from app.models.access import ViewAccessRequest
from app.repositories.devices import DevicesRepository
from app.security.credentials import parse_device_authorization
from app.services.access_service import AccessService
from app.services.device_auth import AuthenticatedDevice


def create_access_router(
    repository: DevicesRepository,
) -> APIRouter:
    router = APIRouter(prefix="/api/v1/devices")
    service = AccessService(repository)

    def require_device(
        device_id: str,
        authorization: str | None = Header(
            default=None,
            alias="Authorization",
        ),
    ) -> AuthenticatedDevice:
        device_secret = parse_device_authorization(authorization)
        return service.authenticate_device(device_id, device_secret)

    @router.put(
        "/{device_id}/view-access",
        status_code=status.HTTP_204_NO_CONTENT,
    )
    def put_view_access(
        request: ViewAccessRequest,
        device: AuthenticatedDevice = Depends(require_device),
    ) -> Response:
        service.rotate_authenticated_view_secret(
            device,
            request.view_secret,
        )
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    return router
