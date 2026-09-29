import json
from datetime import datetime, timedelta
from pathlib import Path
from uuid import UUID

from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app
from app.repositories.devices import DeviceAuthRecord, PersistenceUnavailableError
from app.repositories.memory import MemoryDeviceRepository
from app.repositories.tracking import (
    TrackingPushDeliveryStatus,
    VesselEvidence,
)
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


def test_http_dispatch_callback_runs_only_for_original_tracking_event_ingest():
    repository = repo()
    dispatched = []
    client = TestClient(create_app(
        repository=repository,
        dispatch_tracking_event=lambda stored: dispatched.append(
            stored.event.event_id
        ),
    ))
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
    assert dispatched == [
        __import__("uuid").UUID(payload()["event_id"])
    ]


class RecordingPushGateway:
    def __init__(self):
        self.calls = []

    def send(self, installation, push_payload):
        self.calls.append((installation, push_payload))


def test_enabled_web_push_dispatches_tracking_event_once_across_idempotent_retry():
    raw = payload()
    event_time = datetime.fromisoformat(raw["occurred_at"])
    current = [event_time - timedelta(seconds=1)]
    repository = MemoryDeviceRepository(clock=lambda: current[0])
    repository.create_device(
        DeviceAuthRecord(DEVICE_ID, hash_secret(DEVICE_SECRET))
    )
    installation_id = UUID("94000000-0000-4000-8000-000000000001")
    assert repository.ensure_mobile_installation(
        DEVICE_ID, installation_id
    ) is not None
    tracked = repository.upsert_tracked_vessel(
        DEVICE_ID,
        installation_id,
        VesselEvidence(
            vessel_identity=raw["vessel_identity"],
            vessel_imo=raw["vessel_imo"],
            vessel_name=raw["vessel_name"],
            current=raw["current"],
            observed_at=current[0],
        ),
    )
    assert tracked is not None
    assert repository.upsert_push_installation(
        DEVICE_ID,
        installation_id,
        endpoint="https://push.example/tracking",
        p256dh="p",
        auth="a",
    ) is not None

    gateway = RecordingPushGateway()
    settings = Settings(
        _env_file=None,
        web_push_enabled=True,
        vapid_public_key="public-vapid",
        vapid_private_key="private-vapid",
        vapid_subject="mailto:alerts@example.com",
    )
    current[0] = event_time + timedelta(seconds=80)
    client = TestClient(create_app(
        repository=repository,
        settings=settings,
        clock=lambda: current[0],
        web_push_gateway=gateway,
    ))
    request = {
        "headers": {"Authorization": f"Device {DEVICE_SECRET}"},
        "json": raw,
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
    assert first.json()["status"] == "accepted"
    assert retry.status_code == 200
    assert retry.json()["status"] == "idempotent"
    assert len(gateway.calls) == 1
    assert gateway.calls[0][1]["url"] == (
        f"/acompanhados?track={tracked.tracked_vessel_id}"
        f"&event={raw['event_id']}"
    )
    delivery = repository.get_tracking_push_delivery(
        UUID(raw["event_id"]),
        installation_id,
    )
    assert delivery is not None
    assert delivery.status is TrackingPushDeliveryStatus.DELIVERED
