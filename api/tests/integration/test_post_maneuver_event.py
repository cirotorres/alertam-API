from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from uuid import UUID

from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app
from app.repositories.devices import DeviceAuthRecord, PersistenceUnavailableError
from app.repositories.events import PushDeliveryStatus
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


def test_post_round_trips_operational_timing_fields():
    repository = repo()
    client = TestClient(create_app(repository=repository))
    body = payload()
    body["event_type"] = "COMPLETED"
    body["changes"] = None
    body["pob"] = "29/09 02:30"
    body["pob_at"] = "2026-09-29T02:30:00-03:00"
    body["occurred_at"] = "2026-09-29T10:46:36-03:00"
    body["first_observed_at"] = "2026-09-29T10:45:35-03:00"
    body["operational_at"] = "2026-09-29T05:28:00-03:00"
    body["operational_marker"] = "ATRAC"

    response = client.post(
        f"/api/v1/devices/{DEVICE_ID}/maneuver-events",
        headers={"Authorization": f"Device {DEVICE_SECRET}"},
        json=body,
    )

    assert response.status_code == 200
    stored = repository.list_maneuver_events(DEVICE_ID).events[0].event
    assert stored.operational_at.isoformat() == "2026-09-29T05:28:00-03:00"
    assert stored.operational_marker == "ATRAC"


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


class RecordingPushGateway:
    def __init__(self) -> None:
        self.calls = []

    def send(self, installation, push_payload) -> None:
        self.calls.append((installation, push_payload))


def test_enabled_web_push_dispatches_once_across_idempotent_post_retry():
    current = [
        datetime(2026, 9, 27, 13, 0, tzinfo=timezone.utc)
    ]
    repository = MemoryDeviceRepository(clock=lambda: current[0])
    repository.create_device(
        DeviceAuthRecord(DEVICE_ID, hash_secret(DEVICE_SECRET))
    )
    installation_id = UUID(
        "90000000-0000-4000-8000-000000000001"
    )
    repository.upsert_push_installation(
        DEVICE_ID,
        installation_id,
        endpoint="https://push.example/a",
        p256dh="p",
        auth="a",
    )
    gateway = RecordingPushGateway()
    settings = Settings(
        _env_file=None,
        web_push_enabled=True,
        vapid_public_key="public-vapid",
        vapid_private_key="private-vapid",
        vapid_subject="mailto:alerts@example.com",
    )
    client = TestClient(
        create_app(
            repository=repository,
            settings=settings,
            clock=lambda: current[0],
            web_push_gateway=gateway,
        )
    )
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
    assert first.json()["status"] == "accepted"
    assert retry.status_code == 200
    assert retry.json()["status"] == "idempotent"
    assert len(gateway.calls) == 1
    event_id = UUID(payload()["event_id"])
    delivery = repository.get_push_delivery(
        event_id,
        installation_id,
    )
    assert delivery is not None
    assert delivery.status is PushDeliveryStatus.DELIVERED
