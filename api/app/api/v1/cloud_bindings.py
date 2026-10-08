from __future__ import annotations

from fastapi import APIRouter, Header

from app.core.errors import CloudBindingConflictApiError
from app.models.cloud_binding import (
    CloudBindingCredentialRequest,
    CloudBindingEnsureRequest,
    CloudBindingResponse,
)
from app.repositories.cloud_bindings import CloudBindingConflictError
from app.repositories.events import AlertaRepository
from app.security.credentials import parse_device_authorization
from app.services.cloud_binding_service import CloudBindingService
from app.services.device_auth import DeviceAuthService


def create_cloud_binding_router(repository: AlertaRepository) -> APIRouter:
    router = APIRouter(prefix="/devices")
    auth = DeviceAuthService(repository)
    service = CloudBindingService(repository)

    def device_secret(authorization: str | None) -> str:
        return parse_device_authorization(authorization)

    @router.get(
        "/{device_id}/cloud-binding",
        response_model=CloudBindingResponse,
    )
    def get_cloud_binding(
        device_id: str,
        authorization: str | None = Header(default=None, alias="Authorization"),
    ) -> CloudBindingResponse:
        secret = device_secret(authorization)
        auth.authenticate_status(device_id, secret)
        return service.get(device_id)

    @router.put(
        "/{device_id}/cloud-binding",
        response_model=CloudBindingResponse,
    )
    def ensure_cloud_binding(
        device_id: str,
        request: CloudBindingEnsureRequest,
        authorization: str | None = Header(default=None, alias="Authorization"),
    ) -> CloudBindingResponse:
        secret = device_secret(authorization)
        auth.authenticate(device_id, secret)
        try:
            return service.ensure(device_id, request)
        except CloudBindingConflictError as exc:
            raise CloudBindingConflictApiError() from exc

    @router.post(
        "/{device_id}/cloud-binding/rotate",
        response_model=CloudBindingResponse,
    )
    def rotate_cloud_binding(
        device_id: str,
        request: CloudBindingCredentialRequest,
        authorization: str | None = Header(default=None, alias="Authorization"),
    ) -> CloudBindingResponse:
        secret = device_secret(authorization)
        auth.authenticate(device_id, secret)
        return service.rotate(device_id, request)

    @router.delete(
        "/{device_id}/cloud-binding",
        response_model=CloudBindingResponse,
    )
    def revoke_cloud_binding(
        device_id: str,
        authorization: str | None = Header(default=None, alias="Authorization"),
    ) -> CloudBindingResponse:
        secret = device_secret(authorization)
        auth.authenticate(device_id, secret)
        return service.revoke(device_id)

    return router
