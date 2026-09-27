from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import create_app
from app.repositories.devices import DeviceAuthRecord, PersistenceUnavailableError
from app.repositories.memory import MemoryDeviceRepository
from app.security.credentials import hash_secret


FIXTURE = Path(__file__).parents[1] / "fixtures" / "maneuver_event_v1.json"
DEVICE_ID = "pecem-01"
DEVICE_SECRET = "device-secret"


def payload() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def repo() -> MemoryDeviceRepository:
    repository = MemoryDeviceRepository()
    repository.create_device(
        DeviceAuthRecord(DEVICE_ID, hash_secret(DEVICE_SECRET))
    )
    return repository


def test_post_event_rejects_invalid_device_credentials_before_invalid_body():
    client = TestClient(create_app(repository=repo()))
    body = payload()
    body["event_type"] = "INVALID"

    response = client.post(
        f"/api/v1/devices/{DEVICE_ID}/maneuver-events",
        headers={"Authorization": "Device wrong-secret"},
        json=body,
    )

    assert response.status_code == 401
    assert response.json()["detail"]["code"] == "invalid_device_credentials"


def test_post_event_accepts_and_idempotent_retry_has_same_ingestion_id():
    client = TestClient(create_app(repository=repo()))
    request = {
        "headers": {"Authorization": f"Device {DEVICE_SECRET}"},
        "json": payload(),
    }

    first = client.post(
        f"/api/v1/devices/{DEVICE_ID}/maneuver-events",
        **request,
    )
    retry = client.post(
        f"/api/v1/devices/{DEVICE_ID}/maneuver-events",
        **request,
    )

    assert first.status_code == 200
    assert retry.status_code == 200
    assert first.json()["status"] == "accepted"
    assert retry.json()["status"] == "idempotent"
    assert retry.json()["ingestion_id"] == first.json()["ingestion_id"]
    assert retry.json()["received_at"] == first.json()["received_at"]
    assert "event" not in first.json()


def test_post_event_payload_mismatch_is_409():
    client = TestClient(create_app(repository=repo()))
    headers = {"Authorization": f"Device {DEVICE_SECRET}"}
    first = payload()
    assert client.post(
        f"/api/v1/devices/{DEVICE_ID}/maneuver-events",
        headers=headers,
        json=first,
    ).status_code == 200
    changed = payload()
    changed["vessel_name"] = "OUTRO NAVIO"

    response = client.post(
        f"/api/v1/devices/{DEVICE_ID}/maneuver-events",
        headers=headers,
        json=changed,
    )

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "event_id_payload_mismatch"


class BrokenRepository(MemoryDeviceRepository):
    def accept_maneuver_event_atomic(self, device_id, event):
        raise PersistenceUnavailableError()


def test_post_event_repository_failure_is_503():
    repository = BrokenRepository()
    repository.create_device(
        DeviceAuthRecord(DEVICE_ID, hash_secret(DEVICE_SECRET))
    )
    client = TestClient(create_app(repository=repository))

    response = client.post(
        f"/api/v1/devices/{DEVICE_ID}/maneuver-events",
        headers={"Authorization": f"Device {DEVICE_SECRET}"},
        json=payload(),
    )

    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "persistence_unavailable"
