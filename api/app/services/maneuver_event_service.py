from __future__ import annotations

import logging
from typing import Callable

from app.core.errors import (
    EventIdPayloadMismatchError,
    InvalidDeviceCredentialsError,
    PersistenceUnavailableApiError,
)
from app.models.maneuver_event import (
    ManeuverEventAcceptedResponse,
    ManeuverEventIn,
)
from app.repositories.devices import PersistenceUnavailableError
from app.repositories.events import (
    AcceptEventStatus,
    AlertaRepository,
    StoredManeuverEvent,
)
from app.services.device_auth import AuthenticatedDevice, DeviceAuthService


log = logging.getLogger(__name__)


class ManeuverEventService:
    def __init__(
        self,
        repository: AlertaRepository,
        *,
        dispatch_event: Callable[[StoredManeuverEvent], None] | None = None,
        project_event: Callable[[StoredManeuverEvent], None] | None = None,
    ) -> None:
        self._repository = repository
        self._auth = DeviceAuthService(repository)
        self._dispatch_event = dispatch_event
        self._project_event = project_event

    def authenticate_device(
        self,
        device_id: str,
        device_secret: str,
    ) -> AuthenticatedDevice:
        return self._auth.authenticate(device_id, device_secret)

    def accept_event(
        self,
        device_id: str,
        device_secret: str,
        event: ManeuverEventIn,
    ) -> ManeuverEventAcceptedResponse:
        device = self.authenticate_device(device_id, device_secret)
        return self.accept_authenticated_event(device, event)

    def accept_authenticated_event(
        self,
        device: AuthenticatedDevice,
        event: ManeuverEventIn,
    ) -> ManeuverEventAcceptedResponse:
        try:
            result = self._repository.accept_maneuver_event_atomic(
                device.device_id,
                event,
            )
        except PersistenceUnavailableError as exc:
            raise PersistenceUnavailableApiError() from exc

        if result.status in {
            AcceptEventStatus.ACCEPTED,
            AcceptEventStatus.IDEMPOTENT,
        }:
            if result.stored is None:
                raise PersistenceUnavailableApiError()
            self._project(result.stored)
            self._dispatch_safely(result.stored)
            return ManeuverEventAcceptedResponse(
                status=result.status.value,
                ingestion_id=result.stored.ingestion_id,
                received_at=result.stored.ingested_at,
            )

        if result.status is AcceptEventStatus.PAYLOAD_MISMATCH:
            raise EventIdPayloadMismatchError()
        raise InvalidDeviceCredentialsError()

    def _project(self, stored: StoredManeuverEvent) -> None:
        if self._project_event is None:
            return
        try:
            self._project_event(stored)
        except PersistenceUnavailableError as exc:
            raise PersistenceUnavailableApiError() from exc

    def _dispatch_safely(self, stored: StoredManeuverEvent) -> None:
        if self._dispatch_event is None:
            return
        try:
            self._dispatch_event(stored)
        except Exception as exc:  # noqa: BLE001
            log.error(
                "Falha no dispatch pós-persistência de ManeuverEvent "
                "error_type=%s",
                type(exc).__name__,
            )
