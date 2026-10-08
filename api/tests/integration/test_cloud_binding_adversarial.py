from __future__ import annotations

from dataclasses import replace
import logging

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.core.errors import CloudRealmUnauthorizedError
from app.main import create_app
from app.models.cloud_binding import CloudBindingEnsureRequest
from app.repositories.cloud_bindings import WebPilotAuthRealmRecord
from app.repositories.devices import DeviceAuthRecord
from app.repositories.memory import MemoryDeviceRepository
from app.security.credentials import hash_secret
from app.services.cloud_binding_service import CloudBindingService


DEVICE_A = "pecem-a"
DEVICE_B = "pecem-b"
DEVICE_SECRET_A = "desktop-secret-a"
DEVICE_SECRET_B = "desktop-secret-b"
REALM_A = "webpilot-a"
REALM_B = "webpilot-b"
CREDENTIAL_A = "A" * 43
CREDENTIAL_B = "B" * 43


def _repo() -> MemoryDeviceRepository:
    repo = MemoryDeviceRepository()
    now = repo._clock()
    for device_id, secret in (
        (DEVICE_A, DEVICE_SECRET_A),
        (DEVICE_B, DEVICE_SECRET_B),
    ):
        repo.put_device(
            DeviceAuthRecord(
                device_id,
                hash_secret(secret),
                enabled=True,
            )
        )
    for realm_id in (REALM_A, REALM_B):
        repo.put_webpilot_auth_realm(
            WebPilotAuthRealmRecord(
                realm_id=realm_id,
                active=True,
                created_at=now,
                updated_at=now,
            )
        )
    assert repo.authorize_realm_device(REALM_A, DEVICE_A) is not None
    assert repo.authorize_realm_device(REALM_B, DEVICE_B) is not None
    return repo


def _client(repo: MemoryDeviceRepository) -> TestClient:
    settings = Settings(
        _env_file=None,
        environment="test",
        persistence_backend="memory",
        mock_seed_device=False,
    )
    return TestClient(create_app(settings=settings, repository=repo))


def _headers(secret: str) -> dict[str, str]:
    return {"Authorization": f"Device {secret}"}


def _bind(
    service: CloudBindingService,
    device_id: str,
    realm_id: str,
    credential: str,
):
    return service.ensure(
        device_id,
        CloudBindingEnsureRequest(
            realm_id=realm_id,
            credential=credential,
        ),
    )


def test_cross_device_paths_and_binding_ids_are_isolated():
    repo = _repo()
    service = CloudBindingService(repo)
    binding_a = _bind(service, DEVICE_A, REALM_A, CREDENTIAL_A)
    binding_b = _bind(service, DEVICE_B, REALM_B, CREDENTIAL_B)
    client = _client(repo)
    path_b = f"/api/v1/devices/{DEVICE_B}/cloud-binding"

    unauthorized_get = client.get(
        path_b,
        headers=_headers(DEVICE_SECRET_A),
    )
    assert unauthorized_get.status_code == 401

    unknown_get = client.get(
        "/api/v1/devices/unknown/cloud-binding",
        headers=_headers(DEVICE_SECRET_A),
    )
    assert unknown_get.status_code == 401
    assert unknown_get.json() == unauthorized_get.json()

    unauthorized_ensure = client.put(
        path_b,
        headers=_headers(DEVICE_SECRET_A),
        json={"realm_id": REALM_B, "credential": CREDENTIAL_A},
    )
    unknown_ensure = client.put(
        "/api/v1/devices/unknown/cloud-binding",
        headers=_headers(DEVICE_SECRET_A),
        json={"realm_id": REALM_B, "credential": CREDENTIAL_A},
    )
    assert unauthorized_ensure.status_code == 401
    assert unknown_ensure.status_code == 401
    assert unauthorized_ensure.json() == unknown_ensure.json()

    assert client.post(
        f"{path_b}/rotate",
        headers=_headers(DEVICE_SECRET_A),
        json={"credential": "C" * 43},
    ).status_code == 401
    assert client.delete(
        path_b,
        headers=_headers(DEVICE_SECRET_A),
    ).status_code == 401

    still_b = repo.get_active_cloud_binding(DEVICE_B)
    assert still_b is not None
    assert still_b.cloud_binding_id == binding_b.cloud_binding_id
    assert still_b.credential_version == 1

    with pytest.raises(CloudRealmUnauthorizedError):
        service.authenticate_cloud_binding(
            binding_b.cloud_binding_id,
            CREDENTIAL_A,
        )
    with pytest.raises(CloudRealmUnauthorizedError):
        service.authenticate_cloud_binding(
            binding_a.cloud_binding_id,
            CREDENTIAL_B,
        )


def test_cross_realm_authority_revocation_and_restoration_are_fail_closed():
    repo = _repo()
    service = CloudBindingService(repo)

    with pytest.raises(CloudRealmUnauthorizedError):
        _bind(service, DEVICE_A, REALM_B, CREDENTIAL_A)

    binding = _bind(service, DEVICE_A, REALM_A, CREDENTIAL_A)
    assert service.authenticate_cloud_binding(
        binding.cloud_binding_id,
        CREDENTIAL_A,
    )

    inactive = repo.set_webpilot_auth_realm_active(REALM_A, False)
    assert inactive is not None and not inactive.active
    with pytest.raises(CloudRealmUnauthorizedError):
        service.authenticate_cloud_binding(
            binding.cloud_binding_id,
            CREDENTIAL_A,
        )
    assert repo.get_active_cloud_binding(DEVICE_A) is not None
    assert repo.set_webpilot_auth_realm_active(REALM_A, False) == inactive

    active = repo.set_webpilot_auth_realm_active(REALM_A, True)
    assert active is not None and active.active
    assert repo.set_webpilot_auth_realm_active(REALM_A, True) == active
    assert service.authenticate_cloud_binding(
        binding.cloud_binding_id,
        CREDENTIAL_A,
    )

    revoked_membership = repo.revoke_realm_device(REALM_A, DEVICE_A)
    assert revoked_membership is not None
    assert revoked_membership.revoked_at is not None
    assert (
        repo.revoke_realm_device(REALM_A, DEVICE_A).revoked_at
        == revoked_membership.revoked_at
    )
    with pytest.raises(CloudRealmUnauthorizedError):
        service.authenticate_cloud_binding(
            binding.cloud_binding_id,
            CREDENTIAL_A,
        )

    reauthorized = repo.authorize_realm_device(REALM_A, DEVICE_A)
    assert reauthorized is not None and reauthorized.active
    assert reauthorized.authorized_at >= revoked_membership.authorized_at
    assert service.authenticate_cloud_binding(
        binding.cloud_binding_id,
        CREDENTIAL_A,
    )

    device = repo.get_device_auth(DEVICE_A)
    assert device is not None
    repo.put_device(replace(device, enabled=False))
    with pytest.raises(CloudRealmUnauthorizedError):
        service.authenticate_cloud_binding(
            binding.cloud_binding_id,
            CREDENTIAL_A,
        )

    repo.put_device(replace(device, enabled=True))
    assert service.authenticate_cloud_binding(
        binding.cloud_binding_id,
        CREDENTIAL_A,
    )

    revoked_binding = repo.revoke_cloud_binding(DEVICE_A)
    assert revoked_binding is not None
    repo.set_webpilot_auth_realm_active(REALM_A, False)
    repo.set_webpilot_auth_realm_active(REALM_A, True)
    repo.put_device(replace(device, enabled=False))
    repo.put_device(replace(device, enabled=True))

    with pytest.raises(CloudRealmUnauthorizedError):
        service.authenticate_cloud_binding(
            binding.cloud_binding_id,
            CREDENTIAL_A,
        )


def test_authorization_logs_reprs_and_errors_do_not_expose_secrets(caplog):
    caplog.set_level(logging.INFO, logger="alertam.api.http")
    repo = _repo()
    service = CloudBindingService(repo)
    binding = _bind(service, DEVICE_A, REALM_A, CREDENTIAL_A)
    authority = repo.get_cloud_binding_authority(binding.cloud_binding_id)
    assert authority is not None

    wrong = "Z" * 43
    with pytest.raises(CloudRealmUnauthorizedError) as exc:
        service.authenticate_cloud_binding(
            binding.cloud_binding_id,
            wrong,
        )

    client = _client(repo)
    response = client.get(
        f"/api/v1/devices/{DEVICE_A}/cloud-binding",
        headers=_headers(DEVICE_SECRET_A),
    )
    assert response.status_code == 200

    secret_values = (
        CREDENTIAL_A,
        wrong,
        hash_secret(CREDENTIAL_A),
        DEVICE_SECRET_A,
    )
    combined = "\n".join(
        (
            repr(authority),
            repr(exc.value),
            str(exc.value),
            caplog.text,
        )
    )
    for secret in secret_values:
        assert secret not in combined
