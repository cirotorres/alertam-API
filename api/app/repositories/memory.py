from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
from threading import Lock
from typing import Callable, Iterable

from app.repositories.devices import (
    AcceptSnapshotResult,
    AcceptSnapshotStatus,
    DeviceAlreadyExistsError,
    DeviceAuthRecord,
    SnapshotCandidate,
    StoredSnapshot,
)


DeviceRecord = DeviceAuthRecord


class MemoryDeviceRepository:
    """Repository efêmero para desenvolvimento e testes sem Supabase."""

    def __init__(
        self,
        *,
        devices: Iterable[DeviceAuthRecord] = (),
        snapshots: Iterable[StoredSnapshot] = (),
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._devices = {item.device_id: item for item in devices}
        self._snapshots = {item.device_id: item for item in snapshots}
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._lock = Lock()

    def create_device(self, record: DeviceAuthRecord) -> None:
        if record.device_id in self._devices:
            raise DeviceAlreadyExistsError(record.device_id)
        self._devices[record.device_id] = record

    def put_device(self, record: DeviceAuthRecord) -> None:
        self._devices[record.device_id] = record

    def get_device_auth(self, device_id: str) -> DeviceAuthRecord | None:
        return self._devices.get(device_id)

    def get_snapshot(self, device_id: str) -> StoredSnapshot | None:
        return self._snapshots.get(device_id)

    def put_snapshot(self, snapshot: StoredSnapshot) -> None:
        self._snapshots[snapshot.device_id] = snapshot

    def rotate_view_secret_hash(
        self,
        device_id: str,
        view_secret_hash: str,
    ) -> bool:
        current = self._devices.get(device_id)
        if current is None:
            return False
        self._devices[device_id] = replace(
            current,
            view_secret_hash=view_secret_hash,
        )
        return True

    def accept_snapshot_atomic(
        self,
        candidate: SnapshotCandidate,
    ) -> AcceptSnapshotResult:
        with self._lock:
            if candidate.device_id not in self._devices:
                return AcceptSnapshotResult(
                    status=AcceptSnapshotStatus.DEVICE_NOT_FOUND,
                )

            current = self._snapshots.get(candidate.device_id)
            if current is not None and current.boot_id == candidate.boot_id:
                if candidate.sequence < current.sequence:
                    return AcceptSnapshotResult(
                        status=AcceptSnapshotStatus.OUT_OF_ORDER,
                        received_at=current.received_at,
                    )
                if candidate.sequence == current.sequence:
                    if current.snapshot == candidate.snapshot:
                        return AcceptSnapshotResult(
                            status=AcceptSnapshotStatus.IDEMPOTENT,
                            received_at=current.received_at,
                        )
                    return AcceptSnapshotResult(
                        status=AcceptSnapshotStatus.SEQUENCE_REUSE_MISMATCH,
                        received_at=current.received_at,
                    )

            received_at = self._clock()
            self._snapshots[candidate.device_id] = StoredSnapshot(
                device_id=candidate.device_id,
                snapshot=candidate.snapshot,
                snapshot_schema_version=candidate.snapshot_schema_version,
                boot_id=candidate.boot_id,
                sequence=candidate.sequence,
                generated_at=candidate.generated_at,
                received_at=received_at,
            )
            return AcceptSnapshotResult(
                status=AcceptSnapshotStatus.ACCEPTED,
                received_at=received_at,
            )
