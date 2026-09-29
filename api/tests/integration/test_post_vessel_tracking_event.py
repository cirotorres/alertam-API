import json
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import create_app
from app.repositories.devices import DeviceAuthRecord, PersistenceUnavailableError
from app.repositories.memory import MemoryDeviceRepository
from app.security.credentials import hash_secret


FIXTURE = Path(__file__).parents[1] / "fixtures" / "vessel_tracking_event_v1.json"
DEVICE_ID = "pecem-01"
DEVICE_SECRET = "device-secret"


def payload():
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def repo():
    repository = MemoryDeviceRepository()
    repository.create_device(
        DeviceAuthRecord(DEVICE_ID, hash_secret(DEVICE_SECRET))
    )
    return repository


def test_post_tracking_event_rejects_invalid_device_credentials_before_body():
    client = TestClient(create_app(repository=repo()))

    response = client.post(
        f"/api/v1/devices/{DEVICE_ID}/vessel-tracking-events",
        headers={"Authorization": "Device wrong-secret"},
        json={"invalid": True},
    )

    assert response.status_code == 401
    assert response.json()["detail"]["code"] == "invalid_device_credentials"


def test_post_tracking_event_accepts_and_retry_is_idempotent():
    client = TestClient(create_app(repository=repo()))
    request = {
        "headers": {"Authorization": f"Device {DEVICE_SECRET}"},
        "json": payload(),
    }

    first = client.post(
        f"/api/v1/devices/{DEVICE_ID}/vessel-tracking-events",
        **request,
    )
    retry = client.post(
        f"/api/v1/devices/{DEVICE_ID}/vessel-tracking-events",
        **request,
    )

    assert first.status_code == 200
    assert retry.status_code == 200
    assert first.json()["status"] == "accepted"
    assert retry.json()["status"] == "idempotent"
    assert first.json()["ingestion_id"] == retry.json()["ingestion_id"]
    assert first.json()["received_at"] == retry.json()["received_at"]


def test_post_tracking_event_payload_mismatch_is_409():
    client = TestClient(create_app(repository=repo()))
    headers = {"Authorization": f"Device {DEVICE_SECRET}"}
    assert client.post(
        f"/api/v1/devices/{DEVICE_ID}/vessel-tracking-events",
        headers=headers,
        json=payload(),
    ).status_code == 200

    changed = payload()
    changed["vessel_name"] = "OUTRO NAVIO"
    response = client.post(
        f"/api/v1/devices/{DEVICE_ID}/vessel-tracking-events",
        headers=headers,
        json=changed,
    )

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "event_id_payload_mismatch"


class BrokenRepository(MemoryDeviceRepository):
    def accept_vessel_tracking_event_atomic(self, device_id, event):
        raise PersistenceUnavailableError()


def test_post_tracking_event_repository_failure_is_503():
    repository = BrokenRepository()
    repository.create_device(
        DeviceAuthRecord(DEVICE_ID, hash_secret(DEVICE_SECRET))
    )
    client = TestClient(create_app(repository=repository))

    response = client.post(
        f"/api/v1/devices/{DEVICE_ID}/vessel-tracking-events",
        headers={"Authorization": f"Device {DEVICE_SECRET}"},
        json=payload(),
    )

    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "persistence_unavailable"
