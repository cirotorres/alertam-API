from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

from app.models.maneuver_event import ManeuverEventIn
from app.repositories.devices import DeviceAuthRecord
from app.repositories.events import AcceptEventStatus
from app.repositories.memory import MemoryDeviceRepository


NOW = datetime(2026, 9, 27, 16, 0, tzinfo=timezone.utc)


def event(event_id: str, *, name: str = "NAVIO A") -> ManeuverEventIn:
    return ManeuverEventIn.model_validate({
        "event_id": event_id,
        "maneuver_id": "00000000-0000-4000-8000-000000000201",
        "vessel_identity": "NAME:NAVIO A",
        "vessel_imo": None,
        "vessel_name": name,
        "maneuver_type": "ATRACACAO",
        "event_type": "CONFIRMED",
        "berth": 4,
        "pob": "27/09 10:00",
        "occurred_at": "2026-09-27T10:00:00-03:00",
        "changes": None,
    })


def repo() -> MemoryDeviceRepository:
    repository = MemoryDeviceRepository(clock=lambda: NOW)
    repository.create_device(DeviceAuthRecord("pecem-01", "hash"))
    repository.create_device(DeviceAuthRecord("other-01", "hash"))
    return repository


def test_accept_event_is_idempotent_and_preserves_ingestion_metadata():
    repository = repo()
    item = event("00000000-0000-4000-8000-000000000202")

    first = repository.accept_maneuver_event_atomic("pecem-01", item)
    repeated = repository.accept_maneuver_event_atomic("pecem-01", item)

    assert first.status is AcceptEventStatus.ACCEPTED
    assert repeated.status is AcceptEventStatus.IDEMPOTENT
    assert first.stored is not None
    assert repeated.stored == first.stored
    assert first.stored.ingestion_id == 1
    assert first.stored.ingested_at == NOW


def test_same_event_id_with_different_payload_is_mismatch():
    repository = repo()
    event_id = "00000000-0000-4000-8000-000000000203"
    first = event(event_id)
    changed = event(event_id, name="NAVIO B")

    repository.accept_maneuver_event_atomic("pecem-01", first)
    result = repository.accept_maneuver_event_atomic("pecem-01", changed)

    assert result.status is AcceptEventStatus.PAYLOAD_MISMATCH
    assert result.stored is not None
    assert result.stored.event.vessel_name == "NAVIO A"


def test_missing_device_is_rejected_without_storing_event():
    repository = repo()
    result = repository.accept_maneuver_event_atomic(
        "missing",
        event("00000000-0000-4000-8000-000000000204"),
    )

    assert result.status is AcceptEventStatus.DEVICE_NOT_FOUND
    assert result.stored is None
    assert repository.list_maneuver_events("missing").events == ()


def test_concurrent_identical_accepts_create_one_event():
    repository = repo()
    item = event("00000000-0000-4000-8000-000000000205")

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(
            pool.map(
                lambda _: repository.accept_maneuver_event_atomic("pecem-01", item),
                range(2),
            )
        )

    assert {result.status for result in results} == {
        AcceptEventStatus.ACCEPTED,
        AcceptEventStatus.IDEMPOTENT,
    }
    assert {result.stored.ingestion_id for result in results if result.stored} == {1}
    assert len(repository.list_maneuver_events("pecem-01").events) == 1


def test_feed_is_device_scoped_and_uses_stable_ingestion_order():
    repository = repo()
    ids = [
        "00000000-0000-4000-8000-000000000211",
        "00000000-0000-4000-8000-000000000212",
        "00000000-0000-4000-8000-000000000213",
    ]
    for event_id in ids:
        repository.accept_maneuver_event_atomic("pecem-01", event(event_id))
    repository.accept_maneuver_event_atomic(
        "other-01",
        event("00000000-0000-4000-8000-000000000219"),
    )

    page = repository.list_maneuver_events("pecem-01")

    assert [str(item.event.event_id) for item in page.events] == ids
    assert [item.ingestion_id for item in page.events] == [1, 2, 3]
    assert page.oldest_cursor == 1
    assert page.newest_cursor == 3


def test_feed_initial_after_and_before_pagination_are_gap_free():
    repository = repo()
    for n in range(1, 7):
        repository.accept_maneuver_event_atomic(
            "pecem-01",
            event(f"00000000-0000-4000-8000-{n:012d}"),
        )

    initial = repository.list_maneuver_events("pecem-01", limit=3)
    after = repository.list_maneuver_events(
        "pecem-01",
        after=initial.newest_cursor,
        limit=3,
    )
    before = repository.list_maneuver_events(
        "pecem-01",
        before=initial.oldest_cursor,
        limit=2,
    )

    assert [x.ingestion_id for x in initial.events] == [4, 5, 6]
    assert initial.has_more_before is True
    assert after.events == ()
    assert [x.ingestion_id for x in before.events] == [2, 3]
    assert before.has_more_before is True


def test_after_returns_oldest_next_window_for_burst_drain():
    repository = repo()
    for n in range(1, 7):
        repository.accept_maneuver_event_atomic(
            "pecem-01",
            event(f"10000000-0000-4000-8000-{n:012d}"),
        )

    first = repository.list_maneuver_events("pecem-01", after=1, limit=2)
    second = repository.list_maneuver_events(
        "pecem-01",
        after=first.newest_cursor,
        limit=2,
    )

    assert [x.ingestion_id for x in first.events] == [2, 3]
    assert [x.ingestion_id for x in second.events] == [4, 5]
