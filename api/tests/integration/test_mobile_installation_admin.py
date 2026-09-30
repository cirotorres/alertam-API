from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi.testclient import TestClient

from app.main import create_app
from app.repositories.devices import DeviceAuthRecord
from app.repositories.memory import MemoryDeviceRepository
from app.repositories.tracking import VesselEvidence
from app.security.credentials import hash_secret


DEVICE_A = "pecem-a"
DEVICE_B = "pecem-b"
DEVICE_SECRET_A = "D" * 43
DEVICE_SECRET_B = "E" * 43
VIEW_SECRET_A = "V" * 43
VIEW_SECRET_B = "W" * 43
INSTALL_ACTIVE = UUID("10000000-0000-4000-8000-000000000001")
INSTALL_RECENT = UUID("10000000-0000-4000-8000-000000000002")
INSTALL_OLD = UUID("10000000-0000-4000-8000-000000000003")
INSTALL_B = UUID("10000000-0000-4000-8000-000000000004")
NOW = datetime(2026, 9, 30, 18, 0, tzinfo=timezone.utc)


def _repo(clock):
    repo = MemoryDeviceRepository(clock=clock)
    repo.create_device(DeviceAuthRecord(
        DEVICE_A,
        hash_secret(DEVICE_SECRET_A),
        hash_secret(VIEW_SECRET_A),
    ))
    repo.create_device(DeviceAuthRecord(
        DEVICE_B,
        hash_secret(DEVICE_SECRET_B),
        hash_secret(VIEW_SECRET_B),
    ))
    return repo


def _auth(secret=DEVICE_SECRET_A):
    return {"Authorization": f"Device {secret}"}


def test_admin_list_requires_device_auth_and_is_scoped():
    now = [NOW]
    repo = _repo(lambda: now[0])
    repo.ensure_mobile_installation(
        DEVICE_A,
        INSTALL_ACTIVE,
        platform="ios",
        display_code="K7M4Q2",
    )
    repo.ensure_mobile_installation(
        DEVICE_B,
        INSTALL_B,
        platform="android",
        display_code="P8X4TR",
    )
    client = TestClient(create_app(repository=repo, clock=lambda: now[0]))

    assert client.get(
        f"/api/v1/devices/{DEVICE_A}/mobile-installations",
    ).status_code == 401
    assert client.get(
        f"/api/v1/devices/{DEVICE_A}/mobile-installations",
        headers=_auth("wrong-secret"),
    ).status_code == 401

    response = client.get(
        f"/api/v1/devices/{DEVICE_A}/mobile-installations",
        headers=_auth(),
    )
    assert response.status_code == 200
    body = response.json()
    assert body["active_count"] == 1
    assert [item["installation_id"] for item in body["active"]] == [
        str(INSTALL_ACTIVE)
    ]
    assert all(
        item["installation_id"] != str(INSTALL_B)
        for item in body["active"] + body["recently_revoked"]
    )

    assert client.get(
        f"/api/v1/devices/{DEVICE_B}/mobile-installations",
        headers=_auth(),
    ).status_code == 401


def test_admin_list_returns_active_and_only_last_30_days_revoked():
    now = [NOW - timedelta(days=31)]
    repo = _repo(lambda: now[0])
    repo.ensure_mobile_installation(
        DEVICE_A,
        INSTALL_OLD,
        platform="other",
        display_code="Q7D2AA",
    )
    repo.revoke_mobile_installation(DEVICE_A, INSTALL_OLD)

    now[0] = NOW - timedelta(days=10)
    repo.ensure_mobile_installation(
        DEVICE_A,
        INSTALL_RECENT,
        platform="android",
        display_code="R7C3NT",
    )
    repo.revoke_mobile_installation(DEVICE_A, INSTALL_RECENT)

    now[0] = NOW
    repo.ensure_mobile_installation(
        DEVICE_A,
        INSTALL_ACTIVE,
        platform="ios",
        display_code="K7M4Q2",
    )
    client = TestClient(create_app(repository=repo, clock=lambda: now[0]))

    response = client.get(
        f"/api/v1/devices/{DEVICE_A}/mobile-installations",
        headers=_auth(),
    )
    assert response.status_code == 200
    body = response.json()
    assert body["active_count"] == 1
    assert [item["display_code"] for item in body["active"]] == ["K7M4Q2"]
    assert [item["display_code"] for item in body["recently_revoked"]] == [
        "R7C3NT"
    ]
    item = body["active"][0]
    assert set(item) == {
        "installation_id",
        "display_code",
        "platform",
        "active",
        "created_at",
        "last_seen_at",
        "revoked_at",
    }


def test_admin_delete_is_idempotent_and_revokes_session_tracking_and_push():
    now = [NOW]
    repo = _repo(lambda: now[0])
    repo.ensure_mobile_installation(
        DEVICE_A,
        INSTALL_ACTIVE,
        platform="ios",
        display_code="K7M4Q2",
    )
    tracked = repo.upsert_tracked_vessel(
        DEVICE_A,
        INSTALL_ACTIVE,
        VesselEvidence(
            vessel_identity="IMO:1234567",
            vessel_imo="1234567",
            vessel_name="NAVIO A",
            current={
                "present": True,
                "status": "PREVISTO",
                "section": "PREVISTO",
                "berth": 4,
                "side": None,
                "eta": None,
                "etb_ets": None,
                "pob": None,
                "pob_at": None,
            },
            observed_at=NOW,
        ),
    )
    assert tracked is not None
    repo.upsert_push_installation(
        DEVICE_A,
        INSTALL_ACTIVE,
        endpoint="https://push.example/a",
        p256dh="key",
        auth="auth",
    )
    client = TestClient(create_app(repository=repo, clock=lambda: now[0]))
    session = client.post(
        "/api/v1/mobile/session",
        headers={"Authorization": f"Bearer {VIEW_SECRET_A}"},
        json={
            "device_id": DEVICE_A,
            "installation_id": str(INSTALL_ACTIVE),
            "platform": "ios",
        },
    )
    assert session.status_code == 200

    url = (
        f"/api/v1/devices/{DEVICE_A}/mobile-installations/"
        f"{INSTALL_ACTIVE}"
    )
    first = client.delete(url, headers=_auth())
    second = client.delete(url, headers=_auth())

    assert first.status_code == 204
    assert second.status_code == 204
    assert client.get("/api/v1/mobile/session").status_code == 401

    installation = repo.get_mobile_installation(DEVICE_A, INSTALL_ACTIVE)
    assert installation is not None and installation.active is False
    push = repo.get_push_installation(DEVICE_A, INSTALL_ACTIVE)
    assert push is not None and push.active is False
    stored_track = repo.get_tracked_vessel(
        DEVICE_A,
        INSTALL_ACTIVE,
        tracked.tracked_vessel_id,
    )
    assert stored_track is not None and stored_track.active is False


def test_admin_delete_does_not_reveal_foreign_installation():
    now = [NOW]
    repo = _repo(lambda: now[0])
    repo.ensure_mobile_installation(
        DEVICE_B,
        INSTALL_B,
        platform="android",
        display_code="P8X4TR",
    )
    client = TestClient(create_app(repository=repo, clock=lambda: now[0]))
    url = f"/api/v1/devices/{DEVICE_A}/mobile-installations/{INSTALL_B}"

    response = client.delete(url, headers=_auth())

    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "mobile_installation_not_found"
    foreign = repo.get_mobile_installation(DEVICE_B, INSTALL_B)
    assert foreign is not None and foreign.active is True
