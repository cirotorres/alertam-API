from fastapi import APIRouter, Header

from app.models.device_status import DeviceStatusResponse
from app.repositories.devices import DevicesRepository
from app.security.credentials import parse_device_authorization
from app.services.device_auth import DeviceAuthService


def create_device_status_router(repository: DevicesRepository) -> APIRouter:
    router = APIRouter(prefix="/devices")
    service = DeviceAuthService(repository)

    @router.get(
        "/{device_id}/status",
        response_model=DeviceStatusResponse,
    )
    def get_device_status(
        device_id: str,
        authorization: str | None = Header(
            default=None,
            alias="Authorization",
        ),
    ) -> DeviceStatusResponse:
        device_secret = parse_device_authorization(authorization)
        status = service.authenticate_status(device_id, device_secret)
        return DeviceStatusResponse(
            device_id=status.device_id,
            enabled=status.enabled,
        )

    return router
