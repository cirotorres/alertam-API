from __future__ import annotations

from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app
from app.repositories.devices import (
    DeviceAuthRecord,
    PersistenceUnavailableError,
)
from app.repositories.memory import MemoryDeviceRepository
from app.security.credentials import hash_secret


DEVICE_ID = "pecem-01"
VIEW_SECRET = "V" * 43
INSTALLATION_ID = "10000000-0000-4000-8000-000000000001"


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
        json={
            "device_id": DEVICE_ID,
            "installation_id": INSTALLATION_ID,
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "device_id": DEVICE_ID,
        "installation_id": INSTALLATION_ID,
    }
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
        json={
            "device_id": DEVICE_ID,
            "installation_id": INSTALLATION_ID,
        },
    )
    assert created.status_code == 200

    recovered = client.get("/api/v1/mobile/session")

    assert recovered.status_code == 200
    assert recovered.json() == {
        "device_id": DEVICE_ID,
        "installation_id": INSTALLATION_ID,
    }


def test_rotating_view_secret_invalidates_existing_mobile_session():
    repo = _repo()
    client = TestClient(create_app(repository=repo))

    assert client.post(
        "/api/v1/mobile/session",
        headers={"Authorization": f"Bearer {VIEW_SECRET}"},
        json={
            "device_id": DEVICE_ID,
            "installation_id": INSTALLATION_ID,
        },
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
        json={
            "device_id": DEVICE_ID,
            "installation_id": INSTALLATION_ID,
        },
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
        json={
            "device_id": DEVICE_ID,
            "installation_id": INSTALLATION_ID,
        },
    )

    assert response.status_code == 200
    cookie = response.headers["set-cookie"]
    assert "Secure" in cookie
    assert "HttpOnly" in cookie
    assert "SameSite=strict" in cookie


def test_old_cookie_payload_without_installation_id_is_rejected():
    repo = _repo()
    service = __import__(
        "app.services.mobile_session_service",
        fromlist=["MobileSessionService"],
    ).MobileSessionService(repo)
    auth = repo.get_device_auth(DEVICE_ID)
    payload = service._encode_payload({"device_id": DEVICE_ID, "exp": 9999999999})
    token = f"{payload}.{service._sign(payload, auth.view_secret_hash)}"
    client = TestClient(create_app(repository=repo))
    client.cookies.set("alertam_mobile_session", token, path="/api/v1")

    response = client.get("/api/v1/mobile/session")

    assert response.status_code == 401


def test_same_mobile_installation_is_recovered_and_reused():
    from uuid import UUID

    repo = _repo()
    client = TestClient(create_app(repository=repo))

    created = client.post(
        "/api/v1/mobile/session",
        headers={"Authorization": f"Bearer {VIEW_SECRET}"},
        json={
            "device_id": DEVICE_ID,
            "installation_id": INSTALLATION_ID,
        },
    )
    assert created.status_code == 200

    installation = repo.get_mobile_installation(
        DEVICE_ID,
        UUID(INSTALLATION_ID),
    )
    assert installation is not None
    assert installation.active is True

    recovered = client.get("/api/v1/mobile/session")
    assert recovered.status_code == 200
    assert recovered.json()["installation_id"] == INSTALLATION_ID


def test_mobile_installation_cannot_be_taken_over_by_other_device():
    from uuid import UUID

    repo = _repo()
    other_secret = "O" * 43
    repo.create_device(
        DeviceAuthRecord(
            "other-01",
            "device-hash",
            hash_secret(other_secret),
        )
    )
    assert repo.ensure_mobile_installation(
        DEVICE_ID,
        UUID(INSTALLATION_ID),
    ) is not None
    client = TestClient(create_app(repository=repo))

    response = client.post(
        "/api/v1/mobile/session",
        headers={"Authorization": f"Bearer {other_secret}"},
        json={
            "device_id": "other-01",
            "installation_id": INSTALLATION_ID,
        },
    )

    assert response.status_code == 401
    assert repo.get_mobile_installation(
        DEVICE_ID,
        UUID(INSTALLATION_ID),
    ) is not None
    assert repo.get_mobile_installation(
        "other-01",
        UUID(INSTALLATION_ID),
    ) is None


def test_delete_mobile_session_revokes_installation_identity():
    from uuid import UUID

    repo = _repo()
    client = TestClient(create_app(repository=repo))
    assert client.post(
        "/api/v1/mobile/session",
        headers={"Authorization": f"Bearer {VIEW_SECRET}"},
        json={
            "device_id": DEVICE_ID,
            "installation_id": INSTALLATION_ID,
        },
    ).status_code == 200

    assert client.delete("/api/v1/mobile/session").status_code == 204

    installation = repo.get_mobile_installation(
        DEVICE_ID,
        UUID(INSTALLATION_ID),
    )
    assert installation is not None
    assert installation.active is False
    assert installation.revoked_at is not None


def test_rotating_view_secret_revokes_mobile_installations():
    from uuid import UUID

    repo = _repo()
    client = TestClient(create_app(repository=repo))
    assert client.post(
        "/api/v1/mobile/session",
        headers={"Authorization": f"Bearer {VIEW_SECRET}"},
        json={
            "device_id": DEVICE_ID,
            "installation_id": INSTALLATION_ID,
        },
    ).status_code == 200

    repo.rotate_view_secret_hash(DEVICE_ID, hash_secret("N" * 43))

    installation = repo.get_mobile_installation(
        DEVICE_ID,
        UUID(INSTALLATION_ID),
    )
    assert installation is not None
    assert installation.active is False


class BrokenRevokeRepository(MemoryDeviceRepository):
    def revoke_mobile_installation(self, device_id, installation_id):
        raise PersistenceUnavailableError()


def test_delete_session_does_not_mask_installation_revocation_failure():
    repo = BrokenRevokeRepository()
    repo.create_device(
        DeviceAuthRecord(
            device_id=DEVICE_ID,
            device_secret_hash="device-hash",
            view_secret_hash=hash_secret(VIEW_SECRET),
        )
    )
    client = TestClient(create_app(repository=repo))
    assert client.post(
        "/api/v1/mobile/session",
        headers={"Authorization": f"Bearer {VIEW_SECRET}"},
        json={
            "device_id": DEVICE_ID,
            "installation_id": INSTALLATION_ID,
        },
    ).status_code == 200

    response = client.delete("/api/v1/mobile/session")

    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "persistence_unavailable"
