from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.core.errors import (
    InvalidDeviceCredentialsError,
    OutOfOrderSnapshotError,
    PersistenceUnavailableApiError,
    SequenceReuseMismatchError,
)
from app.models.mobile_snapshot import MobileSnapshotV1
from app.repositories.devices import (
    DeviceAuthRecord,
    PersistenceUnavailableError,
)
from app.repositories.memory import MemoryDeviceRepository
from app.security.credentials import hash_secret
from app.services.snapshot_service import SnapshotService


FIXTURE = Path(__file__).parents[1] / "fixtures" / "mobile_snapshot_v1.json"
DEVICE_ID = "pecem-01"
DEVICE_SECRET = "device-secret"


def _snapshot() -> MobileSnapshotV1:
    return MobileSnapshotV1.model_validate(
        json.loads(FIXTURE.read_text(encoding="utf-8"))
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


def _with_vessel_state(
    snapshot: MobileSnapshotV1,
    *,
    sequence: int,
    status: str,
    section: str,
) -> MobileSnapshotV1:
    vessel = snapshot.vessels[0].model_copy(
        update={"status": status, "section": section}
    )
    return snapshot.model_copy(
        update={"sequence": sequence, "vessels": [vessel]}
    )


def test_first_snapshot_is_silent_anchorage_baseline():
    repo = _repo()
    dispatched = []
    service = SnapshotService(
        repo,
        dispatch_anchorage_entry=dispatched.append,
    )

    service.accept_snapshot(
        DEVICE_ID,
        DEVICE_SECRET,
        _with_vessel_state(
            _snapshot(),
            sequence=1,
            status="FUNDEADO",
            section="FUNDEADO",
        ),
    )

    assert dispatched == []


@pytest.mark.parametrize(
    ("previous_status", "previous_section"),
    [
        ("PREVISTO", "PREVISTO"),
        ("DESATRACANDO", "ATRACADO"),
        ("ATRACADO", "ATRACADO"),
    ],
)
def test_transition_from_any_other_section_to_fundeado_dispatches_once(
    previous_status: str,
    previous_section: str,
):
    repo = _repo()
    dispatched = []
    service = SnapshotService(
        repo,
        dispatch_anchorage_entry=dispatched.append,
    )
    baseline = _with_vessel_state(
        _snapshot(),
        sequence=1,
        status=previous_status,
        section=previous_section,
    )
    entered = _with_vessel_state(
        _snapshot(),
        sequence=2,
        status="FUNDEADO",
        section="FUNDEADO",
    )
    still_anchored = _with_vessel_state(
        _snapshot(),
        sequence=3,
        status="FUNDEADO",
        section="FUNDEADO",
    )

    service.accept_snapshot(DEVICE_ID, DEVICE_SECRET, baseline)
    service.accept_snapshot(DEVICE_ID, DEVICE_SECRET, entered)
    service.accept_snapshot(DEVICE_ID, DEVICE_SECRET, entered)
    service.accept_snapshot(DEVICE_ID, DEVICE_SECRET, still_anchored)

    assert len(dispatched) == 1
    assert dispatched[0].device_id == DEVICE_ID
    assert dispatched[0].vessel_name == "NAVIO A"
    assert dispatched[0].vessel_imo == "1234567"
    assert dispatched[0].previous_section == previous_section


def test_new_vessel_appearing_fundeado_after_baseline_dispatches():
    repo = _repo()
    dispatched = []
    service = SnapshotService(
        repo,
        dispatch_anchorage_entry=dispatched.append,
    )
    empty = _snapshot().model_copy(
        update={"sequence": 1, "vessels": []}
    )
    new_fundeado = _with_vessel_state(
        _snapshot(),
        sequence=2,
        status="FUNDEADO",
        section="FUNDEADO",
    )

    service.accept_snapshot(DEVICE_ID, DEVICE_SECRET, empty)
    service.accept_snapshot(DEVICE_ID, DEVICE_SECRET, new_fundeado)

    assert len(dispatched) == 1
    assert dispatched[0].previous_section is None
