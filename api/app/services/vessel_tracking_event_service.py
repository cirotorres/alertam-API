from __future__ import annotations

from typing import Callable

from app.core.errors import (
    EventIdPayloadMismatchError,
    InvalidDeviceCredentialsError,
    PersistenceUnavailableApiError,
)
from app.models.vessel_tracking_event import (
    VesselTrackingEventAcceptedResponse,
    VesselTrackingEventIn,
)
from app.repositories.devices import PersistenceUnavailableError
from app.repositories.events import AlertaRepository
from app.repositories.tracking import (
    AcceptTrackingEventStatus,
    StoredVesselTrackingEvent,
)
from app.services.device_auth import AuthenticatedDevice, DeviceAuthService


class VesselTrackingEventService:
    def __init__(
        self,
        repository: AlertaRepository,
        *,
        project_event: Callable[[StoredVesselTrackingEvent], None] | None = None,
    ) -> None:
        self._repository = repository
        self._auth = DeviceAuthService(repository)
        self._project_event = project_event

    def authenticate_device(
        self,
        device_id: str,
        device_secret: str,
    ) -> AuthenticatedDevice:
        return self._auth.authenticate(device_id, device_secret)

    def accept_authenticated_event(
        self,
        device: AuthenticatedDevice,
        event: VesselTrackingEventIn,
    ) -> VesselTrackingEventAcceptedResponse:
        try:
            result = self._repository.accept_vessel_tracking_event_atomic(
                device.device_id,
                event,
            )
        except PersistenceUnavailableError as exc:
            raise PersistenceUnavailableApiError() from exc

        if result.status in {
            AcceptTrackingEventStatus.ACCEPTED,
            AcceptTrackingEventStatus.IDEMPOTENT,
        }:
            if result.stored is None:
                raise PersistenceUnavailableApiError()
            if self._project_event is not None:
                try:
                    self._project_event(result.stored)
                except PersistenceUnavailableError as exc:
                    raise PersistenceUnavailableApiError() from exc
            return VesselTrackingEventAcceptedResponse(
                status=result.status.value,
                ingestion_id=result.stored.ingestion_id,
                received_at=result.stored.ingested_at,
            )

        if result.status is AcceptTrackingEventStatus.PAYLOAD_MISMATCH:
            raise EventIdPayloadMismatchError()
        raise InvalidDeviceCredentialsError()
