"""C3-C heartbeat API; no snapshot writer or operational Cloud collector."""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Header, HTTPException, Response

from app.core.errors import PersistenceUnavailableApiError
from app.models.source_authority import Source
from app.models.source_heartbeat import SourceHeartbeatRequest, SourceHeartbeatResponse
from app.repositories.devices import PersistenceUnavailableError
from app.repositories.source_authority import SourceHeartbeatRepository
from app.repositories.events import AlertaRepository
from app.security.credentials import (
    parse_device_authorization,
    parse_cloud_binding_authorization,
)
from app.services.cloud_binding_service import CloudBindingService
from app.services.device_auth import DeviceAuthService


def create_source_heartbeat_router(repository: AlertaRepository) -> APIRouter:
    router = APIRouter()
    devices = DeviceAuthService(repository)
    clouds = CloudBindingService(repository)

    def record(
        device_id: str,
        source: Source,
        payload: SourceHeartbeatRequest,
        *,
        cloud_binding_id: UUID | None = None,
    ) -> SourceHeartbeatResponse:
        try:
            return repository.record_source_heartbeat(
                device_id, source, payload, cloud_binding_id=cloud_binding_id,
            )
        except PersistenceUnavailableError as exc:
            raise PersistenceUnavailableApiError() from exc

    @router.post(
        "/devices/{device_id}/source-heartbeat",
        response_model=SourceHeartbeatResponse,
        responses={401: {"description": "Desktop inválido."},
                   422: {"description": "Heartbeat inválido."},
                   503: {"description": "Persistência indisponível."}},
    )
    def desktop_heartbeat(
        device_id: str,
        payload: SourceHeartbeatRequest,
        response: Response,
        authorization: str | None = Header(default=None, alias="Authorization"),
    ) -> SourceHeartbeatResponse:
        secret = parse_device_authorization(authorization)
        devices.authenticate(device_id, secret)
        if (
            payload.persistent_state_ready is not None
            or payload.last_candidate_generated_at is not None
        ):
            raise HTTPException(status_code=422, detail="desktop heartbeat fields invalid")
        response.headers["Cache-Control"] = "no-store"
        return record(device_id, Source.DESKTOP, payload)

    @router.post(
        "/cloud-bindings/{cloud_binding_id}/source-heartbeat",
        response_model=SourceHeartbeatResponse,
        responses={403: {"description": "CloudBinding inválido."},
                   422: {"description": "Heartbeat inválido."},
                   503: {"description": "Persistência indisponível."}},
    )
    def cloud_heartbeat(
        cloud_binding_id: UUID,
        payload: SourceHeartbeatRequest,
        response: Response,
        authorization: str | None = Header(default=None, alias="Authorization"),
    ) -> SourceHeartbeatResponse:
        credential = parse_cloud_binding_authorization(authorization)
        binding = clouds.authenticate_cloud_binding(cloud_binding_id, credential)
        if payload.persistent_state_ready is None:
            raise HTTPException(status_code=422, detail="persistent state status required")
        response.headers["Cache-Control"] = "no-store"
        return record(
            binding.device_id, Source.CLOUD, payload,
            cloud_binding_id=binding.cloud_binding_id,
        )

    return router
