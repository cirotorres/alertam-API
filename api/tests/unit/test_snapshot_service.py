from __future__ import annotations

import json
from pathlib import Path
from typing import get_type_hints

import pytest

from app.core.errors import (
    InvalidDeviceCredentialsError,
    OutOfOrderSnapshotError,
    PersistenceUnavailableApiError,
    SequenceReuseMismatchError,
)
from app.models.mobile_snapshot import MobileSnapshot, MobileSnapshotV1, MobileSnapshotV2
from app.repositories.devices import (
    DeviceAuthRecord,
    PersistenceUnavailableError,
)
from app.repositories.memory import MemoryDeviceRepository
from app.security.credentials import hash_secret
from app.services.snapshot_service import SnapshotService


FIXTURE = Path(__file__).parents[1] / "fixtures" / "mobile_snapshot_v1.json"
V2_FIXTURE = Path(__file__).parents[1] / "fixtures" / "mobile_snapshot_v2_webpilot.json"
DEVICE_ID = "pecem-01"
DEVICE_SECRET = "device-secret"


def _snapshot() -> MobileSnapshotV1:
    return MobileSnapshotV1.model_validate(
        json.loads(FIXTURE.read_text(encoding="utf-8"))
    )


def _snapshot_v2() -> MobileSnapshotV2:
    return MobileSnapshotV2.model_validate(
        json.loads(V2_FIXTURE.read_text(encoding="utf-8"))
    )

def _repo() -> MemoryDeviceRepository:
    repo = MemoryDeviceRepository()
    repo.create_device(
        DeviceAuthRecord(
            device_id=DEVICE_ID,
            device_secret_hash=hash_secret(DEVICE_SECRET),
        )
    )
    return repo


def test_invalid_device_secret_is_rejected_before_persistence():
    service = SnapshotService(_repo())

    with pytest.raises(InvalidDeviceCredentialsError):
        service.accept_snapshot(
            DEVICE_ID,
            "wrong-secret",
            _snapshot(),
        )


def test_missing_device_is_indistinguishable_from_wrong_secret():
    service = SnapshotService(MemoryDeviceRepository())

    with pytest.raises(InvalidDeviceCredentialsError):
        service.accept_snapshot(
            DEVICE_ID,
            DEVICE_SECRET,
            _snapshot(),
        )

def test_valid_snapshot_is_accepted_without_returning_snapshot_body():
    service = SnapshotService(_repo())

    accepted = service.accept_snapshot(
        DEVICE_ID,
        DEVICE_SECRET,
        _snapshot(),
    )

    assert accepted.ok is True
    assert accepted.received_at is not None
    assert not hasattr(accepted, "snapshot")


def test_idempotent_retry_returns_same_received_at():
    service = SnapshotService(_repo())

    first = service.accept_snapshot(
        DEVICE_ID,
        DEVICE_SECRET,
        _snapshot(),
    )
    repeated = service.accept_snapshot(
        DEVICE_ID,
        DEVICE_SECRET,
        _snapshot(),
    )

    assert repeated.ok is True
    assert repeated.received_at == first.received_at

def test_lower_sequence_maps_to_out_of_order_error():
    repo = _repo()
    service = SnapshotService(repo)
    newer_payload = _snapshot().model_copy(update={"sequence": 2})
    service.accept_snapshot(DEVICE_ID, DEVICE_SECRET, newer_payload)

    with pytest.raises(OutOfOrderSnapshotError):
        service.accept_snapshot(
            DEVICE_ID,
            DEVICE_SECRET,
            _snapshot(),
        )


def test_reused_sequence_with_different_payload_maps_to_conflict():
    repo = _repo()
    service = SnapshotService(repo)
    first = _snapshot()
    service.accept_snapshot(DEVICE_ID, DEVICE_SECRET, first)
    changed = first.model_copy(
        update={
            "port": first.port.model_copy(update={"name": "PORTO ALTERADO"})
        }
    )

    with pytest.raises(SequenceReuseMismatchError):
        service.accept_snapshot(
            DEVICE_ID,
            DEVICE_SECRET,
            changed,
        )

class BrokenRepository(MemoryDeviceRepository):
    def accept_snapshot_atomic(self, candidate):
        raise PersistenceUnavailableError()


def test_repository_failure_maps_to_503_application_error():
    repo = BrokenRepository()
    repo.create_device(
        DeviceAuthRecord(
            device_id=DEVICE_ID,
            device_secret_hash=hash_secret(DEVICE_SECRET),
        )
    )
    service = SnapshotService(repo)

    with pytest.raises(PersistenceUnavailableApiError) as exc:
        service.accept_snapshot(
            DEVICE_ID,
            DEVICE_SECRET,
            _snapshot(),
        )

    assert exc.value.status_code == 503


def test_valid_v2_snapshot_is_accepted_and_persisted_with_schema_2():
    repo = _repo()
    service = SnapshotService(repo)

    accepted = service.accept_snapshot(
        DEVICE_ID,
        DEVICE_SECRET,
        _snapshot_v2(),
    )

    assert accepted.ok is True
    stored = repo.get_snapshot(DEVICE_ID)
    assert stored is not None
    assert stored.snapshot_schema_version == 2
    assert stored.snapshot["schema_version"] == 2
    assert "atmosphere" in stored.snapshot


def test_snapshot_service_type_hints_expose_mobile_snapshot_union():
    accept_hints = get_type_hints(
        SnapshotService.accept_snapshot,
        include_extras=True,
    )
    authenticated_hints = get_type_hints(
        SnapshotService.accept_authenticated_snapshot,
        include_extras=True,
    )

    assert accept_hints["snapshot"] == MobileSnapshot
    assert authenticated_hints["snapshot"] == MobileSnapshot
