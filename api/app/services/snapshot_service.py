from __future__ import annotations

import logging
from collections.abc import Callable

from app.core.errors import (
    InvalidDeviceCredentialsError,
    OutOfOrderSnapshotError,
    PersistenceUnavailableApiError,
    SequenceReuseMismatchError,
)
from app.models.mobile_snapshot import MobileSnapshot
from app.models.responses import SnapshotAcceptedResponse
from app.repositories.devices import (
    AcceptSnapshotStatus,
    DevicesRepository,
    PersistenceUnavailableError,
    SnapshotCandidate,
)
from app.services.anchorage_entry import (
    AnchorageEntryEvent,
    detect_anchorage_entries,
)
from app.services.device_auth import AuthenticatedDevice, DeviceAuthService

log = logging.getLogger(__name__)


class SnapshotService:
    def __init__(
        self,
        repository: DevicesRepository,
        *,
        dispatch_anchorage_entry: Callable[[AnchorageEntryEvent], None] | None = None,
    ) -> None:
        self._repository = repository
        self._auth = DeviceAuthService(repository)
        self._dispatch_anchorage_entry = dispatch_anchorage_entry

    def _dispatch_anchorage_entries(
        self,
        device_id: str,
        previous,
        snapshot: MobileSnapshot,
    ) -> None:
        if self._dispatch_anchorage_entry is None:
            return
        for entry in detect_anchorage_entries(device_id, previous, snapshot):
            try:
                self._dispatch_anchorage_entry(entry)
            except Exception as exc:  # noqa: BLE001
                log.error(
                    "Falha no dispatch pós-persistência de entrada no fundeio "
                    "error_type=%s",
                    type(exc).__name__,
                )

    def authenticate_device(
        self,
        device_id: str,
        device_secret: str,
    ) -> AuthenticatedDevice:
        return self._auth.authenticate(device_id, device_secret)

    def accept_snapshot(
        self,
        device_id: str,
        device_secret: str,
        snapshot: MobileSnapshot,
    ) -> SnapshotAcceptedResponse:
        device = self.authenticate_device(device_id, device_secret)
        return self.accept_authenticated_snapshot(device, snapshot)

    def accept_authenticated_snapshot(
        self,
        device: AuthenticatedDevice,
        snapshot: MobileSnapshot,
    ) -> SnapshotAcceptedResponse:
        previous = self._repository.get_snapshot(device.device_id)
        candidate = SnapshotCandidate(
            device_id=device.device_id,
            snapshot=snapshot.model_dump(mode="json"),
            snapshot_schema_version=snapshot.schema_version,
            boot_id=snapshot.boot_id,
            sequence=snapshot.sequence,
            generated_at=snapshot.generated_at,
        )

        try:
            result = self._repository.accept_snapshot_atomic(candidate)
        except PersistenceUnavailableError as exc:
            raise PersistenceUnavailableApiError() from exc

        if result.status in {
            AcceptSnapshotStatus.ACCEPTED,
            AcceptSnapshotStatus.IDEMPOTENT,
        }:
            if result.received_at is None:
                raise PersistenceUnavailableApiError()
            if result.status is AcceptSnapshotStatus.ACCEPTED:
                self._dispatch_anchorage_entries(
                    device.device_id,
                    previous,
                    snapshot,
                )
            return SnapshotAcceptedResponse(received_at=result.received_at)

        if result.status is AcceptSnapshotStatus.OUT_OF_ORDER:
            raise OutOfOrderSnapshotError()
        if result.status is AcceptSnapshotStatus.SEQUENCE_REUSE_MISMATCH:
            raise SequenceReuseMismatchError()

        raise InvalidDeviceCredentialsError()
