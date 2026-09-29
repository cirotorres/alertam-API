from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import create_app
from app.models.maneuver_event import ManeuverEventIn
from app.repositories.devices import DeviceAuthRecord
from app.repositories.memory import MemoryDeviceRepository
from app.security.credentials import hash_secret


DEVICE_ID = "pecem-01"
OTHER_ID = "other-01"
VIEW_SECRET = "V" * 43


def event(n: int) -> ManeuverEventIn:
    return ManeuverEventIn.model_validate({
        "event_id": f"00000000-0000-4000-8000-{n:012d}",
        "maneuver_id": "00000000-0000-4000-8000-000000000501",
        "vessel_identity": "NAME:NAVIO A",
        "vessel_imo": None,
        "vessel_name": "NAVIO A",
        "maneuver_type": "ATRACACAO",
        "event_type": "CONFIRMED",
        "berth": 4,
        "pob": "27/09 10:00",
        "occurred_at": "2026-09-27T10:00:00-03:00",
        "changes": None,
    })


def prepared() -> tuple[MemoryDeviceRepository, TestClient]:
    repository = MemoryDeviceRepository()
    repository.create_device(
        DeviceAuthRecord(
            DEVICE_ID,
            "device-hash",
            hash_secret(VIEW_SECRET),
        )
    )
    repository.create_device(
        DeviceAuthRecord(
            OTHER_ID,
            "device-hash",
            hash_secret("O" * 43),
        )
    )
    for n in range(1, 5):
        repository.accept_maneuver_event_atomic(DEVICE_ID, event(n))
    repository.accept_maneuver_event_atomic(OTHER_ID, event(99))
    return repository, TestClient(create_app(repository=repository))


def authenticate(client: TestClient) -> None:
    response = client.post(
        "/api/v1/mobile/session",
        headers={"Authorization": f"Bearer {VIEW_SECRET}"},
        json={"device_id": DEVICE_ID, "installation_id": "10000000-0000-4000-8000-000000000099"},
    )
    assert response.status_code == 200


def test_feed_requires_mobile_session_cookie():
    _, client = prepared()

    response = client.get("/api/v1/mobile/maneuver-events")

    assert response.status_code == 401


def test_feed_is_scoped_to_session_device_and_ignores_arbitrary_device_query():
    _, client = prepared()
    authenticate(client)

    response = client.get(
        f"/api/v1/mobile/maneuver-events?device_id={OTHER_ID}&limit=2"
    )

    assert response.status_code == 200
    body = response.json()
    assert [item["ingestion_id"] for item in body["events"]] == [3, 4]
    assert all(item["event_id"].endswith(("003", "004")) for item in body["events"])
    assert body["has_more_before"] is True


def test_feed_after_and_before_are_gap_free():
    _, client = prepared()
    authenticate(client)

    latest = client.get("/api/v1/mobile/maneuver-events?limit=2").json()
    older = client.get(
        f"/api/v1/mobile/maneuver-events?before={latest['oldest_cursor']}&limit=2"
    ).json()
    after = client.get(
        f"/api/v1/mobile/maneuver-events?after={older['newest_cursor']}&limit=2"
    ).json()

    assert [x["ingestion_id"] for x in latest["events"]] == [3, 4]
    assert [x["ingestion_id"] for x in older["events"]] == [1, 2]
    assert [x["ingestion_id"] for x in after["events"]] == [3, 4]


def test_feed_returns_operational_timing_without_loss():
    repository = MemoryDeviceRepository()
    repository.create_device(DeviceAuthRecord(
        DEVICE_ID,
        "device-hash",
        hash_secret(VIEW_SECRET),
    ))
    raw = {
        **event(1).canonical_payload(),
        "event_type": "COMPLETED",
        "changes": None,
        "operational_at": "2026-09-29T05:28:00-03:00",
        "operational_marker": "ATRAC",
    }
    repository.accept_maneuver_event_atomic(
        DEVICE_ID,
        ManeuverEventIn.model_validate(raw),
    )
    client = TestClient(create_app(repository=repository))
    authenticate(client)

    response = client.get("/api/v1/mobile/maneuver-events")

    assert response.status_code == 200
    item = response.json()["events"][0]
    assert item["operational_at"] == "2026-09-29T05:28:00-03:00"
    assert item["operational_marker"] == "ATRAC"


def test_feed_rejects_after_and_before_together_without_leaking_data():
    _, client = prepared()
    authenticate(client)

    response = client.get(
        "/api/v1/mobile/maneuver-events?after=1&before=4"
    )

    assert response.status_code == 422
    assert "NAVIO A" not in response.text
