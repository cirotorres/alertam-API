import json
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

from app.models.vessel_tracking_event import VesselTrackingEventIn
from app.repositories.devices import DeviceAuthRecord
from app.repositories.memory import MemoryDeviceRepository
from app.repositories.tracking import AcceptTrackingEventStatus


FIXTURE = Path(__file__).parents[1] / "fixtures" / "vessel_tracking_event_v1.json"
NOW = datetime(2026, 9, 28, 16, 0, tzinfo=timezone.utc)


def event(**overrides):
    body = json.loads(FIXTURE.read_text(encoding="utf-8"))
    body.update(overrides)
    return VesselTrackingEventIn.model_validate(body)


def repo():
    repository = MemoryDeviceRepository(clock=lambda: NOW)
    repository.create_device(DeviceAuthRecord("pecem-01", "hash"))
    repository.create_device(DeviceAuthRecord("other-01", "hash"))
    return repository


def test_accept_tracking_event_is_idempotent_and_preserves_metadata():
    repository = repo()
    item = event()

    first = repository.accept_vessel_tracking_event_atomic("pecem-01", item)
    repeated = repository.accept_vessel_tracking_event_atomic("pecem-01", item)

    assert first.status is AcceptTrackingEventStatus.ACCEPTED
    assert repeated.status is AcceptTrackingEventStatus.IDEMPOTENT
    assert first.stored is not None
    assert repeated.stored == first.stored
    assert first.stored.ingestion_id == 1
    assert first.stored.ingested_at == NOW


def test_same_tracking_event_id_with_changed_payload_is_conflict():
    repository = repo()
    first = event()
    changed = event(vessel_name="OUTRO NAVIO")

    repository.accept_vessel_tracking_event_atomic("pecem-01", first)
    result = repository.accept_vessel_tracking_event_atomic("pecem-01", changed)

    assert result.status is AcceptTrackingEventStatus.PAYLOAD_MISMATCH
    assert result.stored is not None
    assert result.stored.event.vessel_name == "NAVIO A"


def test_tracking_event_is_scoped_to_existing_device():
    repository = repo()
    result = repository.accept_vessel_tracking_event_atomic("missing", event())

    assert result.status is AcceptTrackingEventStatus.DEVICE_NOT_FOUND
    assert result.stored is None


def test_concurrent_identical_tracking_events_create_one_stored_event():
    repository = repo()
    item = event()

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(
            lambda _: repository.accept_vessel_tracking_event_atomic("pecem-01", item),
            range(2),
        ))

    assert {result.status for result in results} == {
        AcceptTrackingEventStatus.ACCEPTED,
        AcceptTrackingEventStatus.IDEMPOTENT,
    }
    assert {result.stored.ingestion_id for result in results if result.stored} == {1}
