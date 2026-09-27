from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from uuid import UUID

from fastapi.testclient import TestClient

from app.main import create_app
from app.models.vessel_photo import VesselPhotoResponse
from app.repositories.devices import DeviceAuthRecord, StoredSnapshot
from app.repositories.memory import MemoryDeviceRepository
from app.security.credentials import hash_secret

FIXTURE = Path(__file__).parents[1] / "fixtures" / "mobile_snapshot_v1.json"
DEVICE_ID = "pecem-01"
VIEW_SECRET = "V" * 43
NOW = datetime(2026, 9, 25, 16, 0, tzinfo=timezone.utc)


class FakePhotoService:
    def __init__(self):
        self.calls: list[str] = []

    def get_photo(self, imo: str) -> VesselPhotoResponse:
        self.calls.append(imo)
        return VesselPhotoResponse(
            imo=imo,
            photo_url="https://upload.wikimedia.org/navio.jpg",
            author="Autor",
            license="CC BY-SA 4.0",
            source_url="https://commons.wikimedia.org/wiki/File:Navio.jpg",
        )


def _repo() -> MemoryDeviceRepository:
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    repo = MemoryDeviceRepository()
    repo.create_device(DeviceAuthRecord(
        device_id=DEVICE_ID,
        device_secret_hash="device-hash",
        view_secret_hash=hash_secret(VIEW_SECRET),
    ))
    repo.put_snapshot(StoredSnapshot(
        device_id=DEVICE_ID,
        snapshot=payload,
        snapshot_schema_version=1,
        boot_id=UUID(payload["boot_id"]),
        sequence=payload["sequence"],
        generated_at=datetime.fromisoformat(payload["generated_at"]),
        received_at=NOW,
    ))
    return repo


def _client(service: FakePhotoService) -> TestClient:
    return TestClient(create_app(
        repository=_repo(),
        vessel_photo_service=service,
        clock=lambda: NOW,
    ))


def test_vessel_photo_requires_view_auth():
    service = FakePhotoService()
    response = _client(service).get(
        f"/api/v1/devices/{DEVICE_ID}/vessels/1234567/photo"
    )
    assert response.status_code == 401
    assert service.calls == []


def test_vessel_photo_only_allows_imo_from_current_snapshot():
    service = FakePhotoService()
    response = _client(service).get(
        f"/api/v1/devices/{DEVICE_ID}/vessels/9999999/photo",
        headers={"Authorization": f"Bearer {VIEW_SECRET}"},
    )
    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "vessel_not_in_snapshot"
    assert service.calls == []


def test_vessel_photo_returns_external_photo_for_snapshot_vessel():
    service = FakePhotoService()
    response = _client(service).get(
        f"/api/v1/devices/{DEVICE_ID}/vessels/1234567/photo",
        headers={"Authorization": f"Bearer {VIEW_SECRET}"},
    )
    assert response.status_code == 200
    assert response.json()["photo_url"].endswith("navio.jpg")
    assert response.json()["author"] == "Autor"
    assert service.calls == ["1234567"]


def test_vessel_photo_accepts_mobile_session_cookie():
    service = FakePhotoService()
    client = _client(service)
    session = client.post(
        "/api/v1/mobile/session",
        json={"device_id": DEVICE_ID},
        headers={"Authorization": f"Bearer {VIEW_SECRET}"},
    )
    assert session.status_code == 200

    response = client.get(
        f"/api/v1/devices/{DEVICE_ID}/vessels/1234567/photo"
    )

    assert response.status_code == 200
    assert service.calls == ["1234567"]
