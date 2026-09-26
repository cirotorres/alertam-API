from __future__ import annotations

from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app
from app.repositories.devices import DeviceAuthRecord
from app.repositories.memory import MemoryDeviceRepository
from app.security.credentials import hash_secret


DEVICE_ID = "pecem-01"
VIEW_SECRET = "V" * 43


def _repo() -> MemoryDeviceRepository:
    repo = MemoryDeviceRepository()
    repo.create_device(
        DeviceAuthRecord(
            device_id=DEVICE_ID,
            device_secret_hash="device-hash",
            view_secret_hash=hash_secret(VIEW_SECRET),
        )
    )
    return repo


def test_create_mobile_session_sets_http_only_cookie_without_view_secret():
    client = TestClient(create_app(repository=_repo()))

    response = client.post(
        "/api/v1/mobile/session",
        headers={"Authorization": f"Bearer {VIEW_SECRET}"},
        json={"device_id": DEVICE_ID},
    )

    assert response.status_code == 200
    assert response.json() == {"device_id": DEVICE_ID}
    cookie = response.headers["set-cookie"]
    assert "alertam_mobile_session=" in cookie
    assert "HttpOnly" in cookie
    assert "SameSite=strict" in cookie
    assert "Path=/api/v1" in cookie
    assert VIEW_SECRET not in cookie


def test_mobile_session_can_be_recovered_from_cookie():
    client = TestClient(create_app(repository=_repo()))

    created = client.post(
        "/api/v1/mobile/session",
        headers={"Authorization": f"Bearer {VIEW_SECRET}"},
        json={"device_id": DEVICE_ID},
    )
    assert created.status_code == 200

    recovered = client.get("/api/v1/mobile/session")

    assert recovered.status_code == 200
    assert recovered.json() == {"device_id": DEVICE_ID}


def test_rotating_view_secret_invalidates_existing_mobile_session():
    repo = _repo()
    client = TestClient(create_app(repository=repo))

    assert client.post(
        "/api/v1/mobile/session",
        headers={"Authorization": f"Bearer {VIEW_SECRET}"},
        json={"device_id": DEVICE_ID},
    ).status_code == 200

    repo.rotate_view_secret_hash(DEVICE_ID, hash_secret("N" * 43))

    recovered = client.get("/api/v1/mobile/session")

    assert recovered.status_code == 401
    assert recovered.json()["detail"]["code"] == "invalid_view_credentials"


def test_delete_mobile_session_clears_cookie():
    client = TestClient(create_app(repository=_repo()))
    assert client.post(
        "/api/v1/mobile/session",
        headers={"Authorization": f"Bearer {VIEW_SECRET}"},
        json={"device_id": DEVICE_ID},
    ).status_code == 200

    response = client.delete("/api/v1/mobile/session")

    assert response.status_code == 204
    assert client.get("/api/v1/mobile/session").status_code == 401


def test_production_mobile_session_cookie_is_secure():
    settings = Settings(
        environment="production",
        persistence_backend="supabase",
        supabase_url="https://example.supabase.co",
        supabase_secret_key="test-only-secret",
    )
    client = TestClient(
        create_app(
            repository=_repo(),
            settings=settings,
        )
    )

    response = client.post(
        "/api/v1/mobile/session",
        headers={"Authorization": f"Bearer {VIEW_SECRET}"},
        json={"device_id": DEVICE_ID},
    )

    assert response.status_code == 200
    cookie = response.headers["set-cookie"]
    assert "Secure" in cookie
    assert "HttpOnly" in cookie
    assert "SameSite=strict" in cookie
