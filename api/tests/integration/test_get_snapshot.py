from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
from uuid import UUID

from fastapi.testclient import TestClient

from app.main import create_app
from app.repositories.devices import DeviceAuthRecord, StoredSnapshot
from app.repositories.memory import MemoryDeviceRepository
from app.security.credentials import hash_secret


FIXTURE = Path(__file__).parents[1] / "fixtures" / "mobile_snapshot_v1.json"
V2_FIXTURE = Path(__file__).parents[1] / "fixtures" / "mobile_snapshot_v2_webpilot.json"
DEVICE_ID = "pecem-01"
VIEW_SECRET = "V" * 43
RECEIVED_AT = datetime(2026, 9, 25, 16, 0, tzinfo=timezone.utc)


def _payload() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def _repo(*, view_hash: str | None = None, with_snapshot: bool = True):
    repo = MemoryDeviceRepository()
    repo.create_device(
        DeviceAuthRecord(
            device_id=DEVICE_ID,
            device_secret_hash="device-hash",
            view_secret_hash=(
                view_hash
                if view_hash is not None
                else hash_secret(VIEW_SECRET)
            ),
        )
    )

    if with_snapshot:
        payload = _payload()
        repo.put_snapshot(
            StoredSnapshot(
                device_id=DEVICE_ID,
                snapshot=payload,
                snapshot_schema_version=1,
                boot_id=UUID(payload["boot_id"]),
                sequence=payload["sequence"],
                generated_at=datetime.fromisoformat(
                    payload["generated_at"]
                ),
                received_at=RECEIVED_AT,
            )
        )
    return repo


def _client(repo, now):
    return TestClient(
        create_app(
            repository=repo,
            clock=lambda: now,
        )
    )


def test_get_snapshot_requires_bearer_view_secret():
    client = _client(_repo(), RECEIVED_AT)

    response = client.get(
        f"/api/v1/devices/{DEVICE_ID}/snapshot",
        headers={"Authorization": "Bearer wrong-secret"},
    )

    assert response.status_code == 401
    assert response.json()["detail"]["code"] == "invalid_view_credentials"

def test_get_snapshot_returns_404_when_no_snapshot_exists():
    client = _client(
        _repo(with_snapshot=False),
        RECEIVED_AT,
    )

    response = client.get(
        f"/api/v1/devices/{DEVICE_ID}/snapshot",
        headers={"Authorization": f"Bearer {VIEW_SECRET}"},
    )

    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "snapshot_not_available"


def test_get_snapshot_returns_snapshot_and_meta():
    client = _client(
        _repo(),
        RECEIVED_AT + timedelta(seconds=24),
    )

    response = client.get(
        f"/api/v1/devices/{DEVICE_ID}/snapshot",
        headers={"Authorization": f"Bearer {VIEW_SECRET}"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["snapshot"]["schema_version"] == 1
    assert body["snapshot"]["sequence"] == 1
    assert body["meta"] == {
        "received_at": "2026-09-25T16:00:00Z",
        "age_seconds": 24,
        "collector_online": True,
        "stale_after_seconds": 120,
    }

def test_get_snapshot_120_seconds_is_offline_but_data_remains():
    client = _client(
        _repo(),
        RECEIVED_AT + timedelta(seconds=120),
    )

    response = client.get(
        f"/api/v1/devices/{DEVICE_ID}/snapshot",
        headers={"Authorization": f"Bearer {VIEW_SECRET}"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["meta"]["collector_online"] is False
    assert body["meta"]["age_seconds"] == 120
    assert body["snapshot"]["sequence"] == 1

def test_get_snapshot_without_authorization_is_401():
    client = _client(_repo(), RECEIVED_AT)

    response = client.get(
        f"/api/v1/devices/{DEVICE_ID}/snapshot",
    )

    assert response.status_code == 401
    assert response.json()["detail"]["code"] == "invalid_view_credentials"


def test_get_snapshot_accepts_valid_mobile_session_cookie():
    client = _client(
        _repo(),
        RECEIVED_AT + timedelta(seconds=24),
    )

    created = client.post(
        "/api/v1/mobile/session",
        headers={"Authorization": f"Bearer {VIEW_SECRET}"},
        json={"device_id": DEVICE_ID, "installation_id": "10000000-0000-4000-8000-000000000099"},
    )
    assert created.status_code == 200

    response = client.get(
        f"/api/v1/devices/{DEVICE_ID}/snapshot",
    )

    assert response.status_code == 200
    assert response.json()["snapshot"]["schema_version"] == 1


def test_mobile_session_cookie_cannot_read_another_device_path():
    client = _client(_repo(), RECEIVED_AT)

    created = client.post(
        "/api/v1/mobile/session",
        headers={"Authorization": f"Bearer {VIEW_SECRET}"},
        json={"device_id": DEVICE_ID, "installation_id": "10000000-0000-4000-8000-000000000099"},
    )
    assert created.status_code == 200

    response = client.get(
        "/api/v1/devices/outro-device/snapshot",
    )

    assert response.status_code == 401
    assert response.json()["detail"]["code"] == "invalid_view_credentials"


def test_get_snapshot_returns_v2_exact_structure_when_v2_is_stored():
    repo = _repo(with_snapshot=False)
    payload = json.loads(V2_FIXTURE.read_text(encoding="utf-8"))
    repo.put_snapshot(
        StoredSnapshot(
            device_id=DEVICE_ID,
            snapshot=payload,
            snapshot_schema_version=2,
            boot_id=UUID(payload["boot_id"]),
            sequence=payload["sequence"],
            generated_at=datetime.fromisoformat(payload["generated_at"]),
            received_at=RECEIVED_AT,
        )
    )
    client = _client(repo, RECEIVED_AT + timedelta(seconds=10))

    response = client.get(
        f"/api/v1/devices/{DEVICE_ID}/snapshot",
        headers={"Authorization": f"Bearer {VIEW_SECRET}"},
    )

    assert response.status_code == 200
    assert response.json()["snapshot"] == payload
