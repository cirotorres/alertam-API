import json
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import create_app
from app.repositories.devices import DeviceAuthRecord
from app.repositories.memory import MemoryDeviceRepository
from app.security.credentials import hash_secret


FIXTURE = Path(__file__).parents[1] / "fixtures" / "mobile_snapshot_v1.json"
DEVICE_ID = "pecem-disabled"
DEVICE_SECRET = "device-secret"


def test_disabled_device_cannot_publish_snapshot_but_status_remains_visible():
    repo = MemoryDeviceRepository(
        devices=[
            DeviceAuthRecord(
                DEVICE_ID,
                hash_secret(DEVICE_SECRET),
                enabled=False,
                description="PC Sala de Operações",
            )
        ]
    )
    client = TestClient(create_app(repository=repo))
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))

    rejected = client.post(
        f"/api/v1/devices/{DEVICE_ID}/snapshot",
        headers={"Authorization": f"Device {DEVICE_SECRET}"},
        json=payload,
    )
    assert rejected.status_code == 401

    status = client.get(
        f"/api/v1/devices/{DEVICE_ID}/status",
        headers={"Authorization": f"Device {DEVICE_SECRET}"},
    )
    assert status.status_code == 200
    assert status.json()["enabled"] is False
