from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import create_app
from app.repositories.devices import DeviceAuthRecord
from app.repositories.memory import MemoryDeviceRepository
from app.security.credentials import hash_secret, verify_secret


DEVICE_ID = "pecem-01"
DEVICE_SECRET = "device-secret"
VIEW_SECRET = "V" * 43


def _repo() -> MemoryDeviceRepository:
    repo = MemoryDeviceRepository()
    repo.create_device(
        DeviceAuthRecord(
            device_id=DEVICE_ID,
            device_secret_hash=hash_secret(DEVICE_SECRET),
        )
    )
    return repo


def test_put_view_access_requires_valid_device_credentials():
    client = TestClient(create_app(repository=_repo()))

    response = client.put(
        f"/api/v1/devices/{DEVICE_ID}/view-access",
        headers={"Authorization": "Device wrong-secret"},
        json={"view_secret": VIEW_SECRET},
    )

    assert response.status_code == 401
    assert response.json()["detail"]["code"] == "invalid_device_credentials"

def test_put_view_access_returns_204_and_no_secret():
    repo = _repo()
    client = TestClient(create_app(repository=repo))

    response = client.put(
        f"/api/v1/devices/{DEVICE_ID}/view-access",
        headers={"Authorization": f"Device {DEVICE_SECRET}"},
        json={"view_secret": VIEW_SECRET},
    )

    assert response.status_code == 204
    assert response.content == b""
    stored_hash = repo.get_device_auth(DEVICE_ID).view_secret_hash
    assert stored_hash == hash_secret(VIEW_SECRET)
    assert verify_secret(VIEW_SECRET, stored_hash) is True


def test_invalid_view_secret_is_422_without_echoing_secret():
    client = TestClient(create_app(repository=_repo()))
    bad_secret = "segredo-curto"

    response = client.put(
        f"/api/v1/devices/{DEVICE_ID}/view-access",
        headers={"Authorization": f"Device {DEVICE_SECRET}"},
        json={"view_secret": bad_secret},
    )

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "invalid_view_secret"
    assert bad_secret not in response.text

def test_invalid_device_credentials_win_over_invalid_view_secret():
    client = TestClient(create_app(repository=_repo()))

    response = client.put(
        f"/api/v1/devices/{DEVICE_ID}/view-access",
        headers={"Authorization": "Device wrong-secret"},
        json={"view_secret": "short"},
    )

    assert response.status_code == 401
    assert response.json()["detail"]["code"] == "invalid_device_credentials"


def test_second_rotation_invalidates_first_token():
    repo = _repo()
    client = TestClient(create_app(repository=repo))
    headers = {"Authorization": f"Device {DEVICE_SECRET}"}
    first = "A" * 43
    second = "B" * 43

    assert client.put(
        f"/api/v1/devices/{DEVICE_ID}/view-access",
        headers=headers,
        json={"view_secret": first},
    ).status_code == 204
    assert client.put(
        f"/api/v1/devices/{DEVICE_ID}/view-access",
        headers=headers,
        json={"view_secret": second},
    ).status_code == 204

    current_hash = repo.get_device_auth(DEVICE_ID).view_secret_hash
    assert verify_secret(first, current_hash) is False
    assert verify_secret(second, current_hash) is True

def test_validation_error_never_echoes_view_secret_input():
    client = TestClient(create_app(repository=_repo()))
    token_value = "S" * 43

    response = client.put(
        f"/api/v1/devices/{DEVICE_ID}/view-access",
        headers={"Authorization": f"Device {DEVICE_SECRET}"},
        json={"view_secret": [token_value]},
    )

    assert response.status_code == 422
    assert token_value not in response.text
