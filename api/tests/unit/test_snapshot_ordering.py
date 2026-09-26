from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID

from app.repositories.devices import (
    AcceptSnapshotStatus,
    DeviceAuthRecord,
    SnapshotCandidate,
)
from app.repositories.memory import MemoryDeviceRepository


BOOT_A = UUID("550e8400-e29b-41d4-a716-446655440000")
BOOT_B = UUID("660e8400-e29b-41d4-a716-446655440000")
BASE_TIME = datetime(2026, 9, 25, 16, 0, tzinfo=timezone.utc)


def _candidate(
    sequence: int,
    *,
    boot_id: UUID = BOOT_A,
    marker: str = "same",
) -> SnapshotCandidate:
    return SnapshotCandidate(
        device_id="pecem-01",
        snapshot={"schema_version": 1, "marker": marker},
        snapshot_schema_version=1,
        boot_id=boot_id,
        sequence=sequence,
        generated_at=BASE_TIME,
    )

def _repo() -> MemoryDeviceRepository:
    times = iter(
        [
            BASE_TIME,
            BASE_TIME + timedelta(seconds=10),
            BASE_TIME + timedelta(seconds=20),
        ]
    )
    repo = MemoryDeviceRepository(clock=lambda: next(times))
    repo.create_device(
        DeviceAuthRecord(
            device_id="pecem-01",
            device_secret_hash="device-hash",
        )
    )
    return repo


def test_missing_device_returns_device_not_found():
    repo = MemoryDeviceRepository(clock=lambda: BASE_TIME)

    result = repo.accept_snapshot_atomic(_candidate(1))

    assert result.status is AcceptSnapshotStatus.DEVICE_NOT_FOUND
    assert result.received_at is None


def test_first_snapshot_is_accepted_and_persisted():
    repo = _repo()

    result = repo.accept_snapshot_atomic(_candidate(1))

    assert result.status is AcceptSnapshotStatus.ACCEPTED
    stored = repo.get_snapshot("pecem-01")
    assert stored.sequence == 1
    assert stored.received_at == result.received_at == BASE_TIME

def test_same_boot_sequence_and_payload_is_idempotent():
    repo = _repo()
    first = repo.accept_snapshot_atomic(_candidate(1))

    repeated = repo.accept_snapshot_atomic(_candidate(1))

    assert repeated.status is AcceptSnapshotStatus.IDEMPOTENT
    assert repeated.received_at == first.received_at
    assert repo.get_snapshot("pecem-01").received_at == first.received_at


def test_same_boot_sequence_with_different_payload_is_conflict():
    repo = _repo()
    repo.accept_snapshot_atomic(_candidate(1, marker="first"))

    result = repo.accept_snapshot_atomic(_candidate(1, marker="different"))

    assert result.status is AcceptSnapshotStatus.SEQUENCE_REUSE_MISMATCH
    assert repo.get_snapshot("pecem-01").snapshot["marker"] == "first"


def test_lower_sequence_from_same_boot_is_out_of_order():
    repo = _repo()
    repo.accept_snapshot_atomic(_candidate(2))

    result = repo.accept_snapshot_atomic(_candidate(1))

    assert result.status is AcceptSnapshotStatus.OUT_OF_ORDER
    assert repo.get_snapshot("pecem-01").sequence == 2

def test_new_boot_can_restart_sequence():
    repo = _repo()
    repo.accept_snapshot_atomic(_candidate(9, boot_id=BOOT_A))

    result = repo.accept_snapshot_atomic(_candidate(1, boot_id=BOOT_B))

    assert result.status is AcceptSnapshotStatus.ACCEPTED
    stored = repo.get_snapshot("pecem-01")
    assert stored.boot_id == BOOT_B
    assert stored.sequence == 1
