from datetime import datetime, timezone
from uuid import UUID

from fastapi.testclient import TestClient

from app.main import create_app
from app.repositories.devices import (
    DeviceAuthRecord,
    MobileInstallationDisplayCodeConflictError,
    PersistenceUnavailableError,
)
from app.repositories.memory import MemoryDeviceRepository
from app.repositories.tracking import VesselEvidence
from app.security.credentials import hash_secret


DEVICE_A = "pecem-a"
DEVICE_B = "pecem-b"
VIEW_A = "A" * 43
VIEW_B = "B" * 43
INSTALL_A = UUID("10000000-0000-4000-8000-000000000001")
INSTALL_B = UUID("10000000-0000-4000-8000-000000000002")
INSTALL_OTHER = UUID("10000000-0000-4000-8000-000000000003")
SWITCH_ID = UUID("20000000-0000-4000-8000-000000000001")
NOW = datetime(2026, 9, 30, 19, 0, tzinfo=timezone.utc)


def _repo(repository_cls=MemoryDeviceRepository):
    repo = repository_cls(clock=lambda: NOW)
    repo.create_device(DeviceAuthRecord(
        DEVICE_A, "device-a", hash_secret(VIEW_A)
    ))
    repo.create_device(DeviceAuthRecord(
        DEVICE_B, "device-b", hash_secret(VIEW_B)
    ))
    return repo


def _create_a_session(client):
    response = client.post(
        "/api/v1/mobile/session",
        headers={"Authorization": f"Bearer {VIEW_A}"},
        json={
            "device_id": DEVICE_A,
            "installation_id": str(INSTALL_A),
            "platform": "ios",
        },
    )
    assert response.status_code == 200
    return client.cookies.get("alertam_mobile_session")
def _switch_payload(installation_id=INSTALL_B):
    return {
        "device_id": DEVICE_B,
        "installation_id": str(installation_id),
        "platform": "android",
        "switch_id": str(SWITCH_ID),
    }


def _seed_tracking_and_push(repo):
    tracked = repo.upsert_tracked_vessel(
        DEVICE_A,
        INSTALL_A,
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
    push = repo.upsert_push_installation(
        DEVICE_A,
        INSTALL_A,
        endpoint="https://push.example/a",
        p256dh="key",
        auth="auth",
    )
    assert push is not None
    return tracked


def test_switch_session_moves_identity_and_revokes_old_installation():
    repo = _repo()
    client = TestClient(create_app(repository=repo, clock=lambda: NOW))
    _create_a_session(client)
    tracked = _seed_tracking_and_push(repo)

    response = client.post(
        "/api/v1/mobile/session/switch",
        headers={"Authorization": f"Bearer {VIEW_B}"},
        json=_switch_payload(),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["device_id"] == DEVICE_B
    assert body["installation_id"] == str(INSTALL_B)
    assert body["platform"] == "android"
    old = repo.get_mobile_installation(DEVICE_A, INSTALL_A)
    new = repo.get_mobile_installation(DEVICE_B, INSTALL_B)
    assert old is not None and old.active is False
    assert new is not None and new.active is True

    push = repo.get_push_installation(DEVICE_A, INSTALL_A)
    assert push is not None and push.active is False
    stored_track = repo.get_tracked_vessel(
        DEVICE_A,
        INSTALL_A,
        tracked.tracked_vessel_id,
    )
    assert stored_track is not None and stored_track.active is False

    recovered = client.get("/api/v1/mobile/session")
    assert recovered.status_code == 200
    assert recovered.json()["device_id"] == DEVICE_B
    assert recovered.json()["installation_id"] == str(INSTALL_B)


class FailingSwitchRepository(MemoryDeviceRepository):
    def switch_mobile_installation(self, *args, **kwargs):
        raise PersistenceUnavailableError()


def test_switch_persistence_failure_keeps_source_active_and_target_absent():
    repo = _repo(FailingSwitchRepository)
    client = TestClient(create_app(repository=repo, clock=lambda: NOW))
    _create_a_session(client)

    response = client.post(
        "/api/v1/mobile/session/switch",
        headers={"Authorization": f"Bearer {VIEW_B}"},
        json=_switch_payload(),
    )

    assert response.status_code == 503
    source = repo.get_mobile_installation(DEVICE_A, INSTALL_A)
    assert source is not None and source.active is True
    assert repo.get_mobile_installation(DEVICE_B, INSTALL_B) is None
class OneCollisionRepository(MemoryDeviceRepository):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.switch_calls = 0

    def switch_mobile_installation(self, *args, **kwargs):
        self.switch_calls += 1
        if self.switch_calls == 1:
            raise MobileInstallationDisplayCodeConflictError()
        return super().switch_mobile_installation(*args, **kwargs)


def test_switch_retries_code_collision_and_replays_same_switch_id():
    repo = _repo(OneCollisionRepository)
    client = TestClient(create_app(repository=repo, clock=lambda: NOW))
    old_cookie = _create_a_session(client)

    first = client.post(
        "/api/v1/mobile/session/switch",
        headers={"Authorization": f"Bearer {VIEW_B}"},
        json=_switch_payload(),
    )

    assert first.status_code == 200
    assert repo.switch_calls == 2
    first_body = first.json()

    client.cookies.set(
        "alertam_mobile_session",
        old_cookie,
        path="/api/v1",
    )
    replay = client.post(
        "/api/v1/mobile/session/switch",
        headers={"Authorization": f"Bearer {VIEW_B}"},
        json=_switch_payload(),
    )

    assert replay.status_code == 200
    assert replay.json() == first_body
    assert repo.switch_calls == 3
    matches = [
        item for item in repo.list_mobile_installations(
            DEVICE_B,
            revoked_since=datetime(1970, 1, 1, tzinfo=timezone.utc),
        )
        if item.installation_id == INSTALL_B
    ]
    assert len(matches) == 1
def test_switch_id_reuse_with_different_payload_is_conflict_without_mutation():
    repo = _repo()
    client = TestClient(create_app(repository=repo, clock=lambda: NOW))
    old_cookie = _create_a_session(client)

    first = client.post(
        "/api/v1/mobile/session/switch",
        headers={"Authorization": f"Bearer {VIEW_B}"},
        json=_switch_payload(),
    )
    assert first.status_code == 200

    client.cookies.set(
        "alertam_mobile_session",
        old_cookie,
        path="/api/v1",
    )
    divergent = client.post(
        "/api/v1/mobile/session/switch",
        headers={"Authorization": f"Bearer {VIEW_B}"},
        json=_switch_payload(INSTALL_OTHER),
    )

    assert divergent.status_code == 409
    assert divergent.json()["detail"]["code"] == "mobile_session_switch_conflict"
    original = repo.get_mobile_installation(DEVICE_B, INSTALL_B)
    assert original is not None and original.active is True
    assert repo.get_mobile_installation(DEVICE_B, INSTALL_OTHER) is None


def test_switch_rejects_invalid_target_view_secret_without_revoking_source():
    repo = _repo()
    client = TestClient(create_app(repository=repo, clock=lambda: NOW))
    _create_a_session(client)

    response = client.post(
        "/api/v1/mobile/session/switch",
        headers={"Authorization": "Bearer invalid-target-secret"},
        json=_switch_payload(),
    )

    assert response.status_code == 401
    source = repo.get_mobile_installation(DEVICE_A, INSTALL_A)
    assert source is not None and source.active is True
    assert repo.get_mobile_installation(DEVICE_B, INSTALL_B) is None


def test_switch_requires_existing_signed_source_cookie():
    repo = _repo()
    client = TestClient(create_app(repository=repo, clock=lambda: NOW))

    response = client.post(
        "/api/v1/mobile/session/switch",
        headers={"Authorization": f"Bearer {VIEW_B}"},
        json=_switch_payload(),
    )

    assert response.status_code == 401
    assert repo.get_mobile_installation(DEVICE_B, INSTALL_B) is None
