from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from app.core.errors import InvalidDeviceCredentialsError
from app.main import create_app
from app.repositories.devices import DeviceAuthRecord, StoredSnapshot
from app.repositories.memory import MemoryDeviceRepository
from app.security.credentials import hash_secret
from app.services.device_auth import DeviceAuthService


DEVICE_ID = "pecem-disabled"
DEVICE_SECRET = "device-secret"


def _repo(*, enabled: bool) -> MemoryDeviceRepository:
    return MemoryDeviceRepository(
        devices=[
            DeviceAuthRecord(
                device_id=DEVICE_ID,
                device_secret_hash=hash_secret(DEVICE_SECRET),
                enabled=enabled,
                description="Notebook do pai",
            )
        ]
    )


def test_operational_auth_rejects_disabled_but_status_auth_accepts_same_secret():
    service = DeviceAuthService(_repo(enabled=False))

    with pytest.raises(InvalidDeviceCredentialsError):
        service.authenticate(DEVICE_ID, DEVICE_SECRET)

    status = service.authenticate_status(DEVICE_ID, DEVICE_SECRET)
    assert status.device_id == DEVICE_ID
    assert status.enabled is False


def test_operational_auth_accepts_enabled_device():
    authenticated = DeviceAuthService(_repo(enabled=True)).authenticate(
        DEVICE_ID, DEVICE_SECRET
    )
    assert authenticated.device_id == DEVICE_ID


def test_status_endpoint_returns_disabled_for_valid_secret_and_rejects_wrong_secret():
    client = TestClient(create_app(repository=_repo(enabled=False)))

    response = client.get(
        f"/api/v1/devices/{DEVICE_ID}/status",
        headers={"Authorization": f"Device {DEVICE_SECRET}"},
    )
    assert response.status_code == 200
    assert response.json() == {"device_id": DEVICE_ID, "enabled": False}

    wrong = client.get(
        f"/api/v1/devices/{DEVICE_ID}/status",
        headers={"Authorization": "Device wrong-secret"},
    )
    assert wrong.status_code == 401
    assert wrong.json()["detail"]["code"] == "invalid_device_credentials"


def test_status_endpoint_maps_persistence_failure_to_503_not_disabled():
    from app.repositories.devices import PersistenceUnavailableError

    class BrokenRepository(MemoryDeviceRepository):
        def get_device_auth(self, device_id):
            raise PersistenceUnavailableError()

    client = TestClient(create_app(repository=BrokenRepository()))
    response = client.get(
        f"/api/v1/devices/{DEVICE_ID}/status",
        headers={"Authorization": f"Device {DEVICE_SECRET}"},
    )

    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "persistence_unavailable"
