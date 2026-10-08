from __future__ import annotations

import logging

from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app
from app.repositories.cloud_bindings import WebPilotAuthRealmRecord
from app.repositories.devices import DeviceAuthRecord, PersistenceUnavailableError
from app.repositories.memory import MemoryDeviceRepository
from app.security.credentials import hash_secret


DEVICE_SECRET = "desktop-secret"
CREDENTIAL = "A" * 43


def _repo() -> MemoryDeviceRepository:
    repo = MemoryDeviceRepository()
    now = repo._clock()
    repo.put_device(
        DeviceAuthRecord(
            "pecem-01",
            hash_secret(DEVICE_SECRET),
            enabled=True,
        )
    )
    repo.put_webpilot_auth_realm(
        WebPilotAuthRealmRecord(
            realm_id="webpilot-pecem",
            active=True,
            created_at=now,
            updated_at=now,
        )
    )
    assert repo.authorize_realm_device("webpilot-pecem", "pecem-01") is not None
    return repo


def _client(repo) -> TestClient:
    settings = Settings(
        _env_file=None,
        environment="test",
        persistence_backend="memory",
        mock_seed_device=False,
    )
    return TestClient(create_app(settings=settings, repository=repo))


def _device_headers(secret: str = DEVICE_SECRET) -> dict[str, str]:
    return {"Authorization": f"Device {secret}"}


def test_cloud_binding_desktop_only_http_lifecycle_and_secret_free_response():
    repo = _repo()
    client = _client(repo)
    path = "/api/v1/devices/pecem-01/cloud-binding"

    created = client.put(
        path,
        headers=_device_headers(),
        json={"realm_id": "webpilot-pecem", "credential": CREDENTIAL},
    )
    assert created.status_code == 200
    body = created.json()
    assert body["device_id"] == "pecem-01"
    assert body["realm_id"] == "webpilot-pecem"
    assert body["credential_version"] == 1
    assert body["status"] == "active"
    assert "credential" not in body
    assert "credential_hash" not in body
    assert CREDENTIAL not in created.text

    loaded = client.get(path, headers=_device_headers())
    assert loaded.status_code == 200
    assert loaded.json() == body

    same = client.post(
        f"{path}/rotate",
        headers=_device_headers(),
        json={"credential": CREDENTIAL},
    )
    assert same.status_code == 200
    assert same.json()["credential_version"] == 1

    rotated = client.post(
        f"{path}/rotate",
        headers=_device_headers(),
        json={"credential": "B" * 43},
    )
    assert rotated.status_code == 200
    assert rotated.json()["credential_version"] == 2

    revoked = client.delete(path, headers=_device_headers())
    assert revoked.status_code == 200
    assert revoked.json()["status"] == "revoked"

    retried = client.delete(path, headers=_device_headers())
    assert retried.status_code == 200
    assert retried.json() == revoked.json()


def test_cloud_binding_rejects_wrong_scheme_wrong_secret_and_disabled_mutation_but_allows_status_get():
    repo = _repo()
    client = _client(repo)
    path = "/api/v1/devices/pecem-01/cloud-binding"

    assert client.put(
        path,
        headers={"Authorization": "Bearer view-secret"},
        json={"realm_id": "webpilot-pecem", "credential": CREDENTIAL},
    ).status_code == 401
    assert client.put(
        path,
        headers=_device_headers("wrong"),
        json={"realm_id": "webpilot-pecem", "credential": CREDENTIAL},
    ).status_code == 401

    assert client.put(
        path,
        headers=_device_headers(),
        json={"realm_id": "webpilot-pecem", "credential": CREDENTIAL},
    ).status_code == 200

    repo.put_device(
        DeviceAuthRecord(
            "pecem-01",
            hash_secret(DEVICE_SECRET),
            enabled=False,
        )
    )

    loaded = client.get(path, headers=_device_headers())
    assert loaded.status_code == 200
    assert loaded.json()["device_enabled"] is False
    assert loaded.json()["usable"] is False

    assert client.post(
        f"{path}/rotate",
        headers=_device_headers(),
        json={"credential": "C" * 43},
    ).status_code == 401
    assert client.delete(path, headers=_device_headers()).status_code == 401


class FailingCloudRepository(MemoryDeviceRepository):
    def get_device_auth(self, device_id: str):
        raise PersistenceUnavailableError()


class FailingCloudMutationRepository(MemoryDeviceRepository):
    def ensure_cloud_binding(
        self,
        device_id: str,
        realm_id: str,
        credential_hash: str,
    ):
        raise PersistenceUnavailableError()


def test_cloud_binding_http_errors_are_typed_and_do_not_echo_credential(caplog):
    caplog.set_level(logging.INFO, logger="alertam.api.http")
    repo = _repo()
    client = _client(repo)
    path = "/api/v1/devices/pecem-01/cloud-binding"

    not_found = client.get(path, headers=_device_headers())
    assert not_found.status_code == 404
    assert not_found.json()["detail"]["code"] == "cloud_binding_not_found"

    unauthorized_repo = MemoryDeviceRepository()
    now = unauthorized_repo._clock()
    unauthorized_repo.put_device(
        DeviceAuthRecord(
            "pecem-01",
            hash_secret(DEVICE_SECRET),
            enabled=True,
        )
    )
    unauthorized_repo.put_webpilot_auth_realm(
        WebPilotAuthRealmRecord(
            realm_id="webpilot-pecem",
            active=True,
            created_at=now,
            updated_at=now,
        )
    )
    unauthorized_client = _client(unauthorized_repo)
    forbidden = unauthorized_client.put(
        path,
        headers=_device_headers(),
        json={"realm_id": "webpilot-pecem", "credential": CREDENTIAL},
    )
    assert forbidden.status_code == 403
    assert forbidden.json()["detail"]["code"] == "cloud_realm_unauthorized"
    assert CREDENTIAL not in forbidden.text

    created = client.put(
        path,
        headers=_device_headers(),
        json={"realm_id": "webpilot-pecem", "credential": CREDENTIAL},
    )
    assert created.status_code == 200

    conflict_secret = "D" * 43
    conflict = client.put(
        path,
        headers=_device_headers(),
        json={"realm_id": "webpilot-pecem", "credential": conflict_secret},
    )
    assert conflict.status_code == 409
    assert conflict.json()["detail"]["code"] == "cloud_binding_conflict"
    assert conflict_secret not in conflict.text

    invalid_secret = "too-short"
    invalid = client.post(
        f"{path}/rotate",
        headers=_device_headers(),
        json={"credential": invalid_secret},
    )
    assert invalid.status_code == 422
    assert invalid_secret not in invalid.text

    logs = caplog.text
    assert DEVICE_SECRET not in logs
    assert CREDENTIAL not in logs
    assert conflict_secret not in logs
    assert invalid_secret not in logs


def test_cloud_binding_persistence_failure_is_503_and_does_not_echo_secret():
    client = _client(FailingCloudRepository())
    response = client.put(
        "/api/v1/devices/pecem-01/cloud-binding",
        headers=_device_headers(),
        json={"realm_id": "webpilot-pecem", "credential": CREDENTIAL},
    )

    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "persistence_unavailable"
    assert CREDENTIAL not in response.text


def test_cloud_binding_mutation_persistence_failure_is_503_without_state_change():
    repo = FailingCloudMutationRepository()
    now = repo._clock()
    repo.put_device(
        DeviceAuthRecord(
            "pecem-01",
            hash_secret(DEVICE_SECRET),
            enabled=True,
        )
    )
    repo.put_webpilot_auth_realm(
        WebPilotAuthRealmRecord(
            realm_id="webpilot-pecem",
            active=True,
            created_at=now,
            updated_at=now,
        )
    )
    assert repo.authorize_realm_device(
        "webpilot-pecem",
        "pecem-01",
    ) is not None

    client = _client(repo)
    response = client.put(
        "/api/v1/devices/pecem-01/cloud-binding",
        headers=_device_headers(),
        json={"realm_id": "webpilot-pecem", "credential": CREDENTIAL},
    )

    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "persistence_unavailable"
    assert CREDENTIAL not in response.text
    assert repo.list_cloud_bindings("pecem-01") == ()
