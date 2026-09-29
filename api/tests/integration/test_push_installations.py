from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app
from app.repositories.devices import DeviceAuthRecord
from app.repositories.memory import MemoryDeviceRepository
from app.security.credentials import hash_secret


T0 = datetime(2026, 9, 27, 18, 0, tzinfo=timezone.utc)
DEVICE_ID = "pecem-01"
OTHER_ID = "other-01"
VIEW_SECRET = "V" * 43
INSTALL_A = UUID("60000000-0000-4000-8000-000000000001")
INSTALL_B = UUID("60000000-0000-4000-8000-000000000002")


def settings(**overrides) -> Settings:
    values = {
        "web_push_enabled": True,
        "vapid_public_key": "public-vapid-key",
        "vapid_private_key": "private-vapid-key",
        "vapid_subject": "mailto:alerts@example.com",
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)

def prepared(**setting_overrides):
    current = [T0]
    repo = MemoryDeviceRepository(clock=lambda: current[0])
    repo.create_device(
        DeviceAuthRecord(
            DEVICE_ID,
            "device-hash",
            hash_secret(VIEW_SECRET),
        )
    )
    repo.create_device(
        DeviceAuthRecord(
            OTHER_ID,
            "device-hash",
            hash_secret("O" * 43),
        )
    )
    app = create_app(
        repository=repo,
        settings=settings(**setting_overrides),
        clock=lambda: current[0],
    )
    return repo, current, TestClient(app)


def authenticate(client: TestClient) -> None:
    response = client.post(
        "/api/v1/mobile/session",
        headers={"Authorization": f"Bearer {VIEW_SECRET}"},
        json={"device_id": DEVICE_ID, "installation_id": "10000000-0000-4000-8000-000000000099"},
    )
    assert response.status_code == 200

def subscription_body(**extra):
    body = {
        "endpoint": "https://push.example/subscription-a",
        "keys": {
            "p256dh": "browser-public-key",
            "auth": "browser-auth-key",
        },
    }
    body.update(extra)
    return body


def put_installation(client: TestClient, installation_id=INSTALL_A):
    return client.put(
        f"/api/v1/mobile/push/installations/{installation_id}",
        json=subscription_body(),
    )


def test_vapid_public_key_requires_session_and_never_returns_private_key():
    _, _, client = prepared()

    assert client.get(
        "/api/v1/mobile/push/vapid-public-key"
    ).status_code == 401
    authenticate(client)

    response = client.get("/api/v1/mobile/push/vapid-public-key")

    assert response.status_code == 200
    assert response.json() == {
        "enabled": True,
        "public_key": "public-vapid-key",
    }
    assert "private-vapid-key" not in response.text

def test_put_uses_session_device_defaults_preferences_and_hides_subscription():
    repo, _, client = prepared()
    authenticate(client)

    body = subscription_body(device_id=OTHER_ID)
    response = client.put(
        f"/api/v1/mobile/push/installations/{INSTALL_A}",
        json=body,
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["installation_id"] == str(INSTALL_A)
    assert payload["active"] is True
    assert payload["preferences"] == {
        "confirmed": True,
        "updated": True,
        "completed": True,
        "cancelled": True,
    }
    assert "endpoint" not in payload
    assert "p256dh" not in response.text
    assert "browser-auth-key" not in response.text
    assert repo.get_push_installation(DEVICE_ID, INSTALL_A) is not None
    assert repo.get_push_installation(OTHER_ID, INSTALL_A) is None

def test_patch_and_delete_affect_only_requested_installation():
    repo, _, client = prepared()
    authenticate(client)
    assert put_installation(client, INSTALL_A).status_code == 200
    assert put_installation(client, INSTALL_B).status_code == 200

    changed = client.patch(
        f"/api/v1/mobile/push/installations/{INSTALL_A}/preferences",
        json={"confirmed": False},
    )

    assert changed.status_code == 200
    assert changed.json()["preferences"]["confirmed"] is False
    second = repo.get_push_installation(DEVICE_ID, INSTALL_B)
    assert second is not None
    assert second.preferences.confirmed is True

    deleted = client.delete(
        f"/api/v1/mobile/push/installations/{INSTALL_A}"
    )
    assert deleted.status_code == 204
    first = repo.get_push_installation(DEVICE_ID, INSTALL_A)
    assert first is not None and first.active is False
    assert first.endpoint is None and first.p256dh is None and first.auth is None
    assert repo.get_push_installation(DEVICE_ID, INSTALL_B).active is True

def test_foreground_heartbeat_updates_only_active_installation():
    repo, current, client = prepared()
    authenticate(client)
    assert put_installation(client).status_code == 200
    current[0] = T0 + timedelta(seconds=30)

    response = client.post(
        f"/api/v1/mobile/push/installations/{INSTALL_A}/foreground"
    )

    assert response.status_code == 200
    stored = repo.get_push_installation(DEVICE_ID, INSTALL_A)
    assert stored is not None
    assert stored.last_seen_at == current[0]
    assert stored.last_foreground_at == current[0]

    assert client.delete(
        f"/api/v1/mobile/push/installations/{INSTALL_A}"
    ).status_code == 204
    current[0] = T0 + timedelta(seconds=60)
    assert client.post(
        f"/api/v1/mobile/push/installations/{INSTALL_A}/foreground"
    ).status_code == 404

def test_other_device_installation_returns_same_generic_404_as_missing():
    repo, _, client = prepared()
    repo.upsert_push_installation(
        OTHER_ID,
        INSTALL_A,
        endpoint="https://push.example/other",
        p256dh="other-p",
        auth="other-a",
    )
    authenticate(client)

    other = client.get(
        f"/api/v1/mobile/push/installations/{INSTALL_A}"
    )
    missing = client.get(
        "/api/v1/mobile/push/installations/"
        "60000000-0000-4000-8000-000000000099"
    )

    assert other.status_code == 404
    assert missing.status_code == 404
    assert other.json() == missing.json()
    assert other.json()["detail"]["code"] == "push_installation_not_found"
    assert OTHER_ID not in other.text

def test_expired_session_blocks_admin_without_deactivating_push():
    repo, current, client = prepared()
    authenticate(client)
    assert put_installation(client).status_code == 200

    current[0] = T0 + timedelta(days=31)
    response = client.patch(
        f"/api/v1/mobile/push/installations/{INSTALL_A}/preferences",
        json={"updated": False},
    )

    assert response.status_code == 401
    stored = repo.get_push_installation(DEVICE_ID, INSTALL_A)
    assert stored is not None
    assert stored.active is True
    assert stored.preferences.updated is True


def test_cors_allows_patch_and_delete_for_configured_origin():
    _, _, client = prepared(
        allowed_origins="https://mobile.example"
    )
    response = client.options(
        f"/api/v1/mobile/push/installations/{INSTALL_A}/preferences",
        headers={
            "Origin": "https://mobile.example",
            "Access-Control-Request-Method": "PATCH",
        },
    )

    assert response.status_code == 200
    methods = response.headers["access-control-allow-methods"]
    assert "PATCH" in methods
    assert "DELETE" in methods


def test_put_rejects_non_https_subscription_endpoint():
    repo, _, client = prepared()
    authenticate(client)

    for endpoint in (
        "http://127.0.0.1/internal",
        "https://127.0.0.1/internal",
    ):
        response = client.put(
            f"/api/v1/mobile/push/installations/{INSTALL_A}",
            json=subscription_body(endpoint=endpoint),
        )

        assert response.status_code == 422
        assert repo.get_push_installation(DEVICE_ID, INSTALL_A) is None
