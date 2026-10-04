from __future__ import annotations

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
from app.services.device_auth import AuthenticatedDevice, DeviceAuthService


class SnapshotService:
    def __init__(self, repository: DevicesRepository) -> None:
        self._repository = repository
        self._auth = DeviceAuthService(repository)

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
            return SnapshotAcceptedResponse(received_at=result.received_at)

        if result.status is AcceptSnapshotStatus.OUT_OF_ORDER:
            raise OutOfOrderSnapshotError()
        if result.status is AcceptSnapshotStatus.SEQUENCE_REUSE_MISMATCH:
            raise SequenceReuseMismatchError()

        raise InvalidDeviceCredentialsError()
