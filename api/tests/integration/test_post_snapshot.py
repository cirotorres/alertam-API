from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import create_app
from app.repositories.devices import DeviceAuthRecord, PersistenceUnavailableError
from app.repositories.memory import MemoryDeviceRepository
from app.security.credentials import hash_secret


FIXTURE = Path(__file__).parents[1] / "fixtures" / "mobile_snapshot_v1.json"
V2_FIXTURE = Path(__file__).parents[1] / "fixtures" / "mobile_snapshot_v2_webpilot.json"
DEVICE_ID = "pecem-01"
DEVICE_SECRET = "device-secret"


def _payload() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def _payload_v2() -> dict:
    return json.loads(V2_FIXTURE.read_text(encoding="utf-8"))


def _repo() -> MemoryDeviceRepository:
    repo = MemoryDeviceRepository()
    repo.create_device(
        DeviceAuthRecord(
            device_id=DEVICE_ID,
            device_secret_hash=hash_secret(DEVICE_SECRET),
        )
    )
    return repo


def _client(repo: MemoryDeviceRepository) -> TestClient:
    return TestClient(create_app(repository=repo))

def test_post_snapshot_rejects_invalid_device_credentials_generically():
    client = _client(_repo())

    response = client.post(
        f"/api/v1/devices/{DEVICE_ID}/snapshot",
        headers={"Authorization": "Device wrong-secret"},
        json=_payload(),
    )

    assert response.status_code == 401
    assert response.json() == {
        "detail": {
            "code": "invalid_device_credentials",
            "message": "Credenciais do dispositivo inválidas.",
        }
    }


def test_post_snapshot_accepts_valid_desktop_payload():
    client = _client(_repo())

    response = client.post(
        f"/api/v1/devices/{DEVICE_ID}/snapshot",
        headers={"Authorization": f"Device {DEVICE_SECRET}"},
        json=_payload(),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert "received_at" in body
    assert "snapshot" not in body

def test_post_snapshot_idempotent_retry_returns_same_received_at():
    client = _client(_repo())
    request = {
        "headers": {"Authorization": f"Device {DEVICE_SECRET}"},
        "json": _payload(),
    }

    first = client.post(
        f"/api/v1/devices/{DEVICE_ID}/snapshot",
        **request,
    )
    repeated = client.post(
        f"/api/v1/devices/{DEVICE_ID}/snapshot",
        **request,
    )

    assert repeated.status_code == 200
    assert repeated.json()["received_at"] == first.json()["received_at"]


def test_post_snapshot_maps_out_of_order_to_409():
    client = _client(_repo())
    newer = _payload()
    newer["sequence"] = 2
    headers = {"Authorization": f"Device {DEVICE_SECRET}"}
    assert client.post(
        f"/api/v1/devices/{DEVICE_ID}/snapshot",
        headers=headers,
        json=newer,
    ).status_code == 200

    response = client.post(
        f"/api/v1/devices/{DEVICE_ID}/snapshot",
        headers=headers,
        json=_payload(),
    )

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "out_of_order_snapshot"

def test_post_snapshot_maps_sequence_reuse_mismatch_to_409():
    client = _client(_repo())
    headers = {"Authorization": f"Device {DEVICE_SECRET}"}
    first = _payload()
    assert client.post(
        f"/api/v1/devices/{DEVICE_ID}/snapshot",
        headers=headers,
        json=first,
    ).status_code == 200
    changed = _payload()
    changed["port"]["name"] = "PORTO ALTERADO"

    response = client.post(
        f"/api/v1/devices/{DEVICE_ID}/snapshot",
        headers=headers,
        json=changed,
    )

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "sequence_reuse_mismatch"


def test_post_snapshot_unknown_schema_has_specific_422_code():
    client = _client(_repo())
    payload = _payload()
    payload["schema_version"] = 3

    response = client.post(
        f"/api/v1/devices/{DEVICE_ID}/snapshot",
        headers={"Authorization": f"Device {DEVICE_SECRET}"},
        json=payload,
    )

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "unsupported_snapshot_schema"

class BrokenRepository(MemoryDeviceRepository):
    def accept_snapshot_atomic(self, candidate):
        raise PersistenceUnavailableError()


def test_post_snapshot_repository_failure_never_returns_success():
    repo = BrokenRepository()
    repo.create_device(
        DeviceAuthRecord(
            device_id=DEVICE_ID,
            device_secret_hash=hash_secret(DEVICE_SECRET),
        )
    )
    client = _client(repo)

    response = client.post(
        f"/api/v1/devices/{DEVICE_ID}/snapshot",
        headers={"Authorization": f"Device {DEVICE_SECRET}"},
        json=_payload(),
    )

    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "persistence_unavailable"

def test_missing_schema_is_not_classified_as_unsupported_version():
    client = _client(_repo())
    payload = _payload()
    payload.pop("schema_version")

    response = client.post(
        f"/api/v1/devices/{DEVICE_ID}/snapshot",
        headers={"Authorization": f"Device {DEVICE_SECRET}"},
        json=payload,
    )

    assert response.status_code == 422
    detail = response.json()["detail"]
    assert not (
        isinstance(detail, dict)
        and detail.get("code") == "unsupported_snapshot_schema"
    )


def test_invalid_credentials_win_over_invalid_payload():
    client = _client(_repo())
    payload = _payload()
    payload["schema_version"] = 3

    response = client.post(
        f"/api/v1/devices/{DEVICE_ID}/snapshot",
        headers={"Authorization": "Device wrong-secret"},
        json=payload,
    )

    assert response.status_code == 401
    assert response.json()["detail"]["code"] == "invalid_device_credentials"


def test_post_snapshot_accepts_v2_payload():
    client = _client(_repo())

    response = client.post(
        f"/api/v1/devices/{DEVICE_ID}/snapshot",
        headers={"Authorization": f"Device {DEVICE_SECRET}"},
        json=_payload_v2(),
    )

    assert response.status_code == 200
    assert response.json()["ok"] is True
