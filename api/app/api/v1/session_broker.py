from __future__ import annotations

from datetime import datetime
from typing import Callable
from uuid import UUID

from fastapi import APIRouter, Header, Response

from app.core.errors import (
    SessionLeaseGenerationConflictApiError,
    SessionLeaseReplayApiError,
    SessionPublisherConflictApiError,
)
from app.models.session_broker import (
    AcceptedSessionLeaseMetadata,
    SessionLeaseConsumeResponse,
    SessionLeaseInvalidateRequest,
    SessionLeasePublishRequest,
    SessionLeaseRevokeRequest,
    SessionPublisherRequest,
    SessionPublisherResponse,
    SessionPublisherRevokeRequest,
)
from app.repositories.events import AlertaRepository
from app.repositories.session_broker import (
    SessionLeaseGenerationConflictError,
    SessionLeaseReplayError,
    SessionPublisherConflictError,
)
from app.security.credentials import (
    parse_cloud_binding_authorization,
    parse_device_authorization,
)
from app.security.session_crypto import SessionCryptoKeyring
from app.services.device_auth import DeviceAuthService
from app.services.session_broker_service import SessionBrokerService


def create_session_broker_router(
    repository: AlertaRepository,
    *,
    crypto: SessionCryptoKeyring | None,
    fingerprint_key: bytes | None,
    clock: Callable[[], datetime] | None = None,
) -> APIRouter:
    router = APIRouter()
    auth = DeviceAuthService(repository)
    service = SessionBrokerService(
        repository,
        crypto=crypto,
        fingerprint_key=fingerprint_key,
        clock=clock,
    )

    @router.put(
        "/devices/{device_id}/webpilot-session-publisher",
        response_model=SessionPublisherResponse,
        responses={
            401: {"description": "Credenciais do Desktop inválidas."},
            403: {"description": "Realm/publisher não autorizado."},
            409: {"description": "Publisher conflitante."},
            503: {"description": "Persistência/segurança indisponível."},
        },
    )
    def ensure_publisher(
        device_id: str,
        request: SessionPublisherRequest,
        authorization: str | None = Header(default=None, alias="Authorization"),
    ) -> SessionPublisherResponse:
        secret = parse_device_authorization(authorization)
        auth.authenticate(device_id, secret)
        try:
            return service.ensure_publisher(device_id, request)
        except SessionPublisherConflictError as exc:
            raise SessionPublisherConflictApiError() from exc

    @router.delete(
        "/devices/{device_id}/webpilot-session-publisher",
        response_model=SessionPublisherResponse,
        responses={
            401: {"description": "Credenciais do Desktop inválidas."},
            403: {"description": "Realm/publisher não autorizado."},
            503: {"description": "Persistência indisponível."},
        },
    )
    def revoke_publisher(
        device_id: str,
        request: SessionPublisherRevokeRequest,
        authorization: str | None = Header(default=None, alias="Authorization"),
    ) -> SessionPublisherResponse:
        secret = parse_device_authorization(authorization)
        auth.authenticate(device_id, secret)
        return service.revoke_publisher(
            device_id,
            request.realm_id,
            request.publisher_id,
        )

    @router.post(
        "/devices/{device_id}/webpilot-session-leases",
        response_model=AcceptedSessionLeaseMetadata,
        responses={
            401: {"description": "Credenciais do Desktop inválidas."},
            403: {"description": "Publisher/realm/scope não autorizado."},
            409: {"description": "Generation em replay ou conflito."},
            503: {"description": "Persistência/segurança indisponível."},
        },
    )
    def publish_lease(
        device_id: str,
        request: SessionLeasePublishRequest,
        authorization: str | None = Header(default=None, alias="Authorization"),
    ) -> AcceptedSessionLeaseMetadata:
        secret = parse_device_authorization(authorization)
        auth.authenticate(device_id, secret)
        try:
            return service.publish(device_id, request)
        except SessionLeaseGenerationConflictError as exc:
            raise SessionLeaseGenerationConflictApiError() from exc
        except SessionLeaseReplayError as exc:
            raise SessionLeaseReplayApiError() from exc

    @router.post(
        "/devices/{device_id}/webpilot-session-leases/revoke",
        response_model=AcceptedSessionLeaseMetadata,
        responses={
            401: {"description": "Credenciais do Desktop inválidas."},
            403: {"description": "Realm não autorizado."},
            404: {"description": "SessionLease não encontrada."},
            503: {"description": "Persistência indisponível."},
        },
    )
    def revoke_lease(
        device_id: str,
        request: SessionLeaseRevokeRequest,
        authorization: str | None = Header(default=None, alias="Authorization"),
    ) -> AcceptedSessionLeaseMetadata:
        secret = parse_device_authorization(authorization)
        auth.authenticate(device_id, secret)
        return service.revoke_lease(
            device_id,
            request.realm_id,
            request.lease_id,
        )

    @router.get(
        "/cloud-bindings/{cloud_binding_id}/webpilot-session-lease",
        response_model=SessionLeaseConsumeResponse,
        responses={
            403: {"description": "CloudBinding não autorizado."},
            404: {"description": "SessionLease não disponível."},
            503: {"description": "Persistência/segurança indisponível."},
        },
    )
    def consume_lease(
        cloud_binding_id: UUID,
        response: Response,
        authorization: str | None = Header(default=None, alias="Authorization"),
    ) -> SessionLeaseConsumeResponse:
        credential = parse_cloud_binding_authorization(authorization)
        result = service.consume(cloud_binding_id, credential)
        response.headers["Cache-Control"] = "no-store"
        return result

    @router.post(
        "/cloud-bindings/{cloud_binding_id}/webpilot-session-lease/invalidate",
        response_model=AcceptedSessionLeaseMetadata,
        responses={
            403: {"description": "CloudBinding não autorizado."},
            404: {"description": "SessionLease não encontrada."},
            503: {"description": "Persistência indisponível."},
        },
    )
    def invalidate_lease(
        cloud_binding_id: UUID,
        request: SessionLeaseInvalidateRequest,
        response: Response,
        authorization: str | None = Header(default=None, alias="Authorization"),
    ) -> AcceptedSessionLeaseMetadata:
        credential = parse_cloud_binding_authorization(authorization)
        result = service.invalidate(
            cloud_binding_id,
            credential,
            request.lease_id,
            request.realm_epoch,
        )
        response.headers["Cache-Control"] = "no-store"
        return result

    return router
