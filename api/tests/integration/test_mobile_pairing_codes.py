from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi.testclient import TestClient

from app.main import create_app
from app.repositories.devices import DeviceAuthRecord
from app.repositories.memory import MemoryDeviceRepository
from app.security.credentials import hash_secret


NOW = [datetime(2026, 10, 2, 17, 0, tzinfo=timezone.utc)]
DEVICE_A = "pecem-a"
DEVICE_B = "pecem-b"
DEVICE_SECRET_A = "device-secret-a"
DEVICE_SECRET_B = "device-secret-b"
VIEW_A = "A" * 43
VIEW_B = "B" * 43
INSTALL_A = "10000000-0000-4000-8000-000000000001"
INSTALL_B = "10000000-0000-4000-8000-000000000002"
INSTALL_OTHER = "10000000-0000-4000-8000-000000000003"
SWITCH_ID = "20000000-0000-4000-8000-000000000001"


def repo() -> MemoryDeviceRepository:
    repository = MemoryDeviceRepository(clock=lambda: NOW[0])
    repository.create_device(
        DeviceAuthRecord(
            DEVICE_A,
            hash_secret(DEVICE_SECRET_A),
            hash_secret(VIEW_A),
        )
    )
    repository.create_device(
        DeviceAuthRecord(
            DEVICE_B,
            hash_secret(DEVICE_SECRET_B),
            hash_secret(VIEW_B),
        )
    )
    return repository


def issue_code(client: TestClient, device_id: str, secret: str) -> str:
    response = client.post(
        f"/api/v1/devices/{device_id}/pairing-code",
        headers={"Authorization": f"Device {secret}"},
    )
    assert response.status_code == 200
    code = response.json()["code"]
    assert len(code) == 6 and code.isdigit()
    return code


def redeem(client: TestClient, code: str) -> dict:
    response = client.post(
        "/api/v1/mobile/pairing/code",
        json={"code": f"{code[:3]} {code[3:]}"},
    )
    assert response.status_code == 200
    return response.json()


def test_desktop_issues_five_minute_code_and_mobile_redeems_ticket():
    NOW[0] = datetime(2026, 10, 2, 17, 0, tzinfo=timezone.utc)
    client = TestClient(
        create_app(repository=repo(), clock=lambda: NOW[0])
    )

    code = issue_code(client, DEVICE_A, DEVICE_SECRET_A)
    ticket = redeem(client, code)

    assert ticket["device_id"] == DEVICE_A
    assert ticket["pairing_ticket"]
    assert datetime.fromisoformat(ticket["expires_at"]) == (
        NOW[0] + timedelta(minutes=5)
    )


def test_pairing_ticket_validates_and_creates_session_once_per_purpose():
    NOW[0] = datetime(2026, 10, 2, 17, 0, tzinfo=timezone.utc)
    repository = repo()
    client = TestClient(
        create_app(repository=repository, clock=lambda: NOW[0])
    )
    ticket = redeem(
        client,
        issue_code(client, DEVICE_A, DEVICE_SECRET_A),
    )
    auth = {"Authorization": f"Pairing {ticket['pairing_ticket']}"}

    validated = client.post(
        "/api/v1/mobile/pairing/validate",
        headers=auth,
        json={"device_id": DEVICE_A},
    )
    assert validated.status_code == 200

    created = client.post(
        "/api/v1/mobile/session",
        headers=auth,
        json={
            "device_id": DEVICE_A,
            "installation_id": INSTALL_A,
            "platform": "ios",
        },
    )
    assert created.status_code == 200

    repeated_same_purpose = client.post(
        "/api/v1/mobile/session",
        headers=auth,
        json={
            "device_id": DEVICE_A,
            "installation_id": INSTALL_A,
            "platform": "ios",
        },
    )
    assert repeated_same_purpose.status_code == 200

    different_purpose = client.post(
        "/api/v1/mobile/session",
        headers=auth,
        json={
            "device_id": DEVICE_A,
            "installation_id": INSTALL_OTHER,
            "platform": "ios",
        },
    )
    assert different_purpose.status_code == 401


def test_expired_code_is_rejected():
    NOW[0] = datetime(2026, 10, 2, 17, 0, tzinfo=timezone.utc)
    client = TestClient(
        create_app(repository=repo(), clock=lambda: NOW[0])
    )
    code = issue_code(client, DEVICE_A, DEVICE_SECRET_A)
    NOW[0] += timedelta(minutes=5, seconds=1)

    response = client.post(
        "/api/v1/mobile/pairing/code",
        json={"code": code},
    )

    assert response.status_code == 401
    assert response.json()["detail"]["code"] == "invalid_mobile_pairing_code"


def test_pairing_ticket_switches_existing_session_to_other_desktop():
    NOW[0] = datetime(2026, 10, 2, 17, 0, tzinfo=timezone.utc)
    repository = repo()
    client = TestClient(
        create_app(repository=repository, clock=lambda: NOW[0])
    )
    assert client.post(
        "/api/v1/mobile/session",
        headers={"Authorization": f"Bearer {VIEW_A}"},
        json={
            "device_id": DEVICE_A,
            "installation_id": INSTALL_A,
            "platform": "ios",
        },
    ).status_code == 200

    ticket = redeem(
        client,
        issue_code(client, DEVICE_B, DEVICE_SECRET_B),
    )
    response = client.post(
        "/api/v1/mobile/session/switch",
        headers={
            "Authorization": f"Pairing {ticket['pairing_ticket']}"
        },
        json={
            "device_id": DEVICE_B,
            "installation_id": INSTALL_B,
            "platform": "ios",
            "switch_id": SWITCH_ID,
        },
    )

    assert response.status_code == 200
    assert response.json()["device_id"] == DEVICE_B
    assert client.get("/api/v1/mobile/session").json()["device_id"] == DEVICE_B
    source = repository.get_mobile_installation(
        DEVICE_A,
        UUID(INSTALL_A),
    )
    target = repository.get_mobile_installation(
        DEVICE_B,
        UUID(INSTALL_B),
    )
    assert source is not None and source.active is False
    assert target is not None and target.active is True
