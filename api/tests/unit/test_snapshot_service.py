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
from app.services.anchorage_entry import detect_anchorage_entries
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


def test_anchorage_type_hints_preserve_mobile_snapshot_union():
    service_hints = get_type_hints(
        SnapshotService._dispatch_anchorage_entries,
        include_extras=True,
    )
    detector_hints = get_type_hints(
        detect_anchorage_entries,
        include_extras=True,
    )

    assert service_hints["snapshot"] == MobileSnapshot
    assert detector_hints["current"] == MobileSnapshot


def test_v2_transition_to_fundeado_dispatches_anchorage_entry():
    repo = _repo()
    dispatched = []
    service = SnapshotService(
        repo,
        dispatch_anchorage_entry=dispatched.append,
    )
    shared_vessel = _snapshot().vessels[0]
    baseline = _snapshot_v2().model_copy(
        update={
            "sequence": 1,
            "vessels": [
                shared_vessel.model_copy(
                    update={"status": "PREVISTO", "section": "PREVISTO"}
                )
            ],
        }
    )
    entered = _snapshot_v2().model_copy(
        update={
            "sequence": 2,
            "vessels": [
                shared_vessel.model_copy(
                    update={"status": "FUNDEADO", "section": "FUNDEADO"}
                )
            ],
        }
    )

    service.accept_snapshot(DEVICE_ID, DEVICE_SECRET, baseline)
    service.accept_snapshot(DEVICE_ID, DEVICE_SECRET, entered)

    assert len(dispatched) == 1
    assert dispatched[0].vessel_name == entered.vessels[0].name
