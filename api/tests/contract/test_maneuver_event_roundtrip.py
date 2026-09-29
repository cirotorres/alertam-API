from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import create_app
from app.repositories.devices import DeviceAuthRecord
from app.repositories.memory import MemoryDeviceRepository
from app.security.credentials import hash_secret


FIXTURE = Path(__file__).parents[1] / "fixtures" / "maneuver_event_v1.json"
DEVICE_ID = "pecem-01"
DEVICE_SECRET = "device-secret"
VIEW_SECRET = "V" * 43


def prepared_client() -> TestClient:
    repository = MemoryDeviceRepository()
    repository.create_device(
        DeviceAuthRecord(
            DEVICE_ID,
            hash_secret(DEVICE_SECRET),
            hash_secret(VIEW_SECRET),
        )
    )
    return TestClient(create_app(repository=repository))
def authenticate_mobile(client: TestClient) -> None:
    response = client.post(
        "/api/v1/mobile/session",
        headers={"Authorization": f"Bearer {VIEW_SECRET}"},
        json={"device_id": DEVICE_ID, "installation_id": "10000000-0000-4000-8000-000000000099"},
    )
    assert response.status_code == 200


def post_event(client: TestClient, body: dict) -> None:
    response = client.post(
        f"/api/v1/devices/{DEVICE_ID}/maneuver-events",
        headers={"Authorization": f"Device {DEVICE_SECRET}"},
        json=body,
    )
    assert response.status_code == 200


def test_desktop_fixture_roundtrips_from_post_to_mobile_feed_without_loss():
    client = prepared_client()
    body = json.loads(FIXTURE.read_text(encoding="utf-8"))

    post_event(client, body)
    authenticate_mobile(client)
    response = client.get("/api/v1/mobile/maneuver-events")

    assert response.status_code == 200
    item = response.json()["events"][0]
    for key, value in body.items():
        assert item[key] == value
    assert item["ingestion_id"] == 1


def test_shift_preserves_completed_before_confirmed_with_same_occurred_at():
    client = prepared_client()
    base = json.loads(FIXTURE.read_text(encoding="utf-8"))
    occurred_at = "2026-09-27T14:00:00-03:00"

    completed = {
        **base,
        "event_id": "83000000-0000-4000-8000-000000000001",
        "maneuver_id": "83000000-0000-4000-8000-000000000011",
        "maneuver_type": "DESATRACACAO",
        "event_type": "COMPLETED",
        "occurred_at": occurred_at,
        "changes": None,
    }
    confirmed = {
        **base,
        "event_id": "83000000-0000-4000-8000-000000000002",
        "maneuver_id": "83000000-0000-4000-8000-000000000012",
        "maneuver_type": "ATRACACAO",
        "event_type": "CONFIRMED",
        "occurred_at": occurred_at,
        "changes": None,
    }

    post_event(client, completed)
    post_event(client, confirmed)
    authenticate_mobile(client)

    events = client.get(
        "/api/v1/mobile/maneuver-events?limit=10"
    ).json()["events"]

    assert [item["event_type"] for item in events] == [
        "COMPLETED",
        "CONFIRMED",
    ]
    assert [item["ingestion_id"] for item in events] == [1, 2]
    assert events[0]["occurred_at"] == events[1]["occurred_at"]
