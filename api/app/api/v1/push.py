from __future__ import annotations

from datetime import datetime
from typing import Callable
from uuid import UUID

from fastapi import APIRouter, Depends, Response, status

from app.api.v1.mobile_auth import MobileSessionAuth
from app.models.push import (
    PushInstallationResponse,
    PushPreferencesPatch,
    PushPreferencesResponse,
    PushSubscriptionIn,
    VapidPublicKeyResponse,
)
from app.repositories.events import AlertaRepository, PushInstallation
from app.services.push_installation_service import PushInstallationService


def create_push_router(
    repository: AlertaRepository,
    *,
    web_push_enabled: bool,
    vapid_public_key: str,
    clock: Callable[[], datetime] | None = None,
) -> APIRouter:
    router = APIRouter(prefix="/mobile/push")
    session_auth = MobileSessionAuth(repository, clock=clock)
    service = PushInstallationService(repository)

    @router.get(
        "/vapid-public-key",
        response_model=VapidPublicKeyResponse,
    )
    def get_vapid_public_key(
        _device_id: str = Depends(session_auth),
    ) -> VapidPublicKeyResponse:
        return VapidPublicKeyResponse(
            enabled=web_push_enabled,
            public_key=vapid_public_key if web_push_enabled else None,
        )

    @router.get(
        "/installations/{installation_id}",
        response_model=PushInstallationResponse,
    )
    def get_installation(
        installation_id: UUID,
        device_id: str = Depends(session_auth),
    ) -> PushInstallationResponse:
        return _to_response(
            service.get_installation(device_id, installation_id)
        )

    @router.put(
        "/installations/{installation_id}",
        response_model=PushInstallationResponse,
    )
    def put_installation(
        installation_id: UUID,
        request: PushSubscriptionIn,
        device_id: str = Depends(session_auth),
    ) -> PushInstallationResponse:
        installation = service.register_installation(
            device_id,
            installation_id,
            endpoint=request.endpoint,
            p256dh=request.keys.p256dh,
            auth=request.keys.auth,
        )
        return _to_response(installation)

    @router.patch(
        "/installations/{installation_id}/preferences",
        response_model=PushInstallationResponse,
    )
    def patch_preferences(
        installation_id: UUID,
        request: PushPreferencesPatch,
        device_id: str = Depends(session_auth),
    ) -> PushInstallationResponse:
        installation = service.update_preferences(
            device_id,
            installation_id,
            request.model_dump(exclude_none=True),
        )
        return _to_response(installation)

    @router.post(
        "/installations/{installation_id}/foreground",
        response_model=PushInstallationResponse,
    )
    def touch_foreground(
        installation_id: UUID,
        device_id: str = Depends(session_auth),
    ) -> PushInstallationResponse:
        return _to_response(
            service.touch_foreground(device_id, installation_id)
        )

    @router.delete(
        "/installations/{installation_id}",
        status_code=status.HTTP_204_NO_CONTENT,
    )
    def delete_installation(
        installation_id: UUID,
        device_id: str = Depends(session_auth),
    ) -> Response:
        service.deactivate_installation(device_id, installation_id)
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    return router


def _to_response(
    installation: PushInstallation,
) -> PushInstallationResponse:
    return PushInstallationResponse(
        installation_id=installation.installation_id,
        active=installation.active,
        preferences=PushPreferencesResponse(
            confirmed=installation.preferences.confirmed,
            updated=installation.preferences.updated,
            completed=installation.preferences.completed,
            cancelled=installation.preferences.cancelled,
            anchored=installation.preferences.anchored,
        ),
        push_enabled_at=installation.push_enabled_at,
        last_seen_at=installation.last_seen_at,
        last_foreground_at=installation.last_foreground_at,
    )
