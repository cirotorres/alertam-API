from __future__ import annotations

import secrets

import pytest
from pydantic import ValidationError

from app.models.cloud_binding import (
    CloudBindingCredentialRequest,
    CloudBindingEnsureRequest,
)
from app.repositories.cloud_bindings import (
    CloudBindingConflictError,
    WebPilotAuthRealmRecord,
)
from app.repositories.devices import DeviceAuthRecord
from app.repositories.memory import MemoryDeviceRepository
from app.security.credentials import hash_secret
from app.services.cloud_binding_service import CloudBindingService


VALID = "A" * 43
MAX_VALID = "B" * 86


def _repo() -> MemoryDeviceRepository:
    repo = MemoryDeviceRepository()
    repo.put_device(DeviceAuthRecord("pecem-01", "device-hash", enabled=True))
    repo.put_webpilot_auth_realm(
        WebPilotAuthRealmRecord(
            realm_id="webpilot-pecem",
            active=True,
            created_at=repo._clock(),
            updated_at=repo._clock(),
        )
    )
    assert repo.authorize_realm_device("webpilot-pecem", "pecem-01") is not None
    return repo


def test_cloud_credential_model_accepts_canonical_min_and_max_and_redacts_repr():
    canonical = secrets.token_urlsafe(32)
    assert len(canonical) == 43

    for credential in (canonical, VALID, MAX_VALID):
        request = CloudBindingCredentialRequest(credential=credential)
        assert request.credential.get_secret_value() == credential
        assert credential not in repr(request)


@pytest.mark.parametrize(
    "credential",
    [
        "",
        "A" * 42,
        "A" * 87,
        " " + ("A" * 43),
        ("A" * 20) + " " + ("A" * 23),
        ("A" * 43) + " ",
        ("A" * 42) + "=",
        ("A" * 42) + "+",
    ],
)
def test_cloud_credential_model_rejects_invalid_format_without_leaking(credential):
    with pytest.raises(ValidationError) as exc:
        CloudBindingCredentialRequest(credential=credential)
    if credential:
        assert credential not in str(exc.value)


def test_service_hashes_before_repository_and_returns_secret_free_metadata():
    repo = _repo()
    service = CloudBindingService(repo)

    result = service.ensure(
        "pecem-01",
        CloudBindingEnsureRequest(
            realm_id="webpilot-pecem",
            credential=VALID,
        ),
    )

    stored = repo.get_active_cloud_binding("pecem-01")
    assert stored is not None
    assert stored.credential_hash == hash_secret(VALID)
    assert result.cloud_binding_id == stored.cloud_binding_id
    assert result.credential_version == 1
    dumped = result.model_dump()
    assert "credential" not in dumped
    assert "credential_hash" not in dumped


def test_service_ensure_rotate_and_revoke_are_idempotent_and_conflict_safe():
    repo = _repo()
    service = CloudBindingService(repo)
    request = CloudBindingEnsureRequest(
        realm_id="webpilot-pecem",
        credential=VALID,
    )

    first = service.ensure("pecem-01", request)
    repeated = service.ensure("pecem-01", request)
    assert repeated == first

    with pytest.raises(CloudBindingConflictError):
        service.ensure(
            "pecem-01",
            CloudBindingEnsureRequest(
                realm_id="webpilot-pecem",
                credential="C" * 43,
            ),
        )

    same = service.rotate(
        "pecem-01",
        CloudBindingCredentialRequest(credential=VALID),
    )
    assert same.credential_version == 1

    rotated = service.rotate(
        "pecem-01",
        CloudBindingCredentialRequest(credential="D" * 43),
    )
    assert rotated.credential_version == 2

    revoked = service.revoke("pecem-01")
    retry = service.revoke("pecem-01")
    assert retry == revoked
    assert revoked.status == "revoked"
