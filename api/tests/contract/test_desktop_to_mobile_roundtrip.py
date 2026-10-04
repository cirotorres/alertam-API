from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path

from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app
from app.repositories.devices import DeviceAuthRecord
from app.repositories.memory import MemoryDeviceRepository
from app.security.credentials import hash_secret


FIXTURE = Path(__file__).parents[1] / "fixtures" / "mobile_snapshot_v1.json"
V2_FIXTURE = Path(__file__).parents[1] / "fixtures" / "mobile_snapshot_v2_webpilot.json"
DEVICE_ID = "pecem-01"
DEVICE_SECRET = "device-secret"
VIEW_SECRET = "V" * 43
NOW = datetime(2026, 9, 25, 16, 0, tzinfo=timezone.utc)


def _payload() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def _client() -> TestClient:
    repo = MemoryDeviceRepository(clock=lambda: NOW)
    repo.create_device(
        DeviceAuthRecord(
            device_id=DEVICE_ID,
            device_secret_hash=hash_secret(DEVICE_SECRET),
        )
    )
    settings = Settings(
        _env_file=None,
        persistence_backend="memory",
        stale_after_seconds=120,
    )
    return TestClient(
        create_app(
            repository=repo,
            settings=settings,
            clock=lambda: NOW,
        )
    )


def test_desktop_fixture_roundtrips_post_to_mobile_get_without_loss():
    client = _client()
    payload = _payload()

    post = client.post(
        f"/api/v1/devices/{DEVICE_ID}/snapshot",
        headers={"Authorization": f"Device {DEVICE_SECRET}"},
        json=payload,
    )
    assert post.status_code == 200

    rotate = client.put(
        f"/api/v1/devices/{DEVICE_ID}/view-access",
        headers={"Authorization": f"Device {DEVICE_SECRET}"},
        json={"view_secret": VIEW_SECRET},
    )
    assert rotate.status_code == 204

    read = client.get(
        f"/api/v1/devices/{DEVICE_ID}/snapshot",
        headers={"Authorization": f"Bearer {VIEW_SECRET}"},
    )
    assert read.status_code == 200
    assert read.json()["snapshot"] == payload


def test_roundtrip_never_exposes_desktop_internal_fields():
    client = _client()
    payload = _payload()

    assert client.post(
        f"/api/v1/devices/{DEVICE_ID}/snapshot",
        headers={"Authorization": f"Device {DEVICE_SECRET}"},
        json=payload,
    ).status_code == 200
    assert client.put(
        f"/api/v1/devices/{DEVICE_ID}/view-access",
        headers={"Authorization": f"Device {DEVICE_SECRET}"},
        json={"view_secret": VIEW_SECRET},
    ).status_code == 204

    body = client.get(
        f"/api/v1/devices/{DEVICE_ID}/snapshot",
        headers={"Authorization": f"Bearer {VIEW_SECRET}"},
    ).json()["snapshot"]

    serialized = json.dumps(body, ensure_ascii=False).casefold()
    for forbidden in (
        "linhas_brutas",
        "cookie",
        "session",
        "sessao",
        "authorization",
        "device_secret",
        "view_secret",
    ):
        assert forbidden not in serialized


def test_v2_fixture_roundtrips_post_to_mobile_get_without_loss():
    client = _client()
    payload = json.loads(V2_FIXTURE.read_text(encoding="utf-8"))

    post = client.post(
        f"/api/v1/devices/{DEVICE_ID}/snapshot",
        headers={"Authorization": f"Device {DEVICE_SECRET}"},
        json=payload,
    )
    assert post.status_code == 200

    assert client.put(
        f"/api/v1/devices/{DEVICE_ID}/view-access",
        headers={"Authorization": f"Device {DEVICE_SECRET}"},
        json={"view_secret": VIEW_SECRET},
    ).status_code == 204

    read = client.get(
        f"/api/v1/devices/{DEVICE_ID}/snapshot",
        headers={"Authorization": f"Bearer {VIEW_SECRET}"},
    )
    assert read.status_code == 200
    assert read.json()["snapshot"] == payload
