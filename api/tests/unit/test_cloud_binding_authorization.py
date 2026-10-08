from __future__ import annotations

from dataclasses import replace

import pytest

from app.core.errors import CloudRealmUnauthorizedError, PersistenceUnavailableApiError
from app.models.cloud_binding import CloudBindingEnsureRequest
from app.repositories.cloud_bindings import WebPilotAuthRealmRecord
from app.repositories.devices import DeviceAuthRecord, PersistenceUnavailableError
from app.repositories.memory import MemoryDeviceRepository
from app.security.credentials import hash_secret
from app.services.cloud_binding_service import CloudBindingService


CREDENTIAL = "A" * 43


def _bound_repo() -> tuple[MemoryDeviceRepository, CloudBindingService, object]:
    repo = MemoryDeviceRepository()
    now = repo._clock()
    repo.put_device(
        DeviceAuthRecord(
            "pecem-01",
            hash_secret("desktop-secret"),
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
    service = CloudBindingService(repo)
    binding = service.ensure(
        "pecem-01",
        CloudBindingEnsureRequest(
            realm_id="webpilot-pecem",
            credential=CREDENTIAL,
        ),
    )
    return repo, service, binding


def test_authenticate_cloud_binding_authorizes_only_secret_free_ids():
    _repo, service, binding = _bound_repo()

    authorized = service.authenticate_cloud_binding(
        binding.cloud_binding_id,
        CREDENTIAL,
    )

    assert authorized.cloud_binding_id == binding.cloud_binding_id
    assert authorized.device_id == "pecem-01"
    assert authorized.realm_id == "webpilot-pecem"
    assert set(authorized.__dict__) == {
        "cloud_binding_id",
        "device_id",
        "realm_id",
    }
    assert CREDENTIAL not in repr(authorized)
    assert "credential_hash" not in repr(authorized)


@pytest.mark.parametrize(
    "invalidate",
    [
        "wrong_hash",
        "binding_revoked",
        "device_disabled",
        "realm_inactive",
        "membership_revoked",
    ],
)
def test_authenticate_cloud_binding_denies_invalid_authority(invalidate: str):
    repo, service, binding = _bound_repo()
    credential = CREDENTIAL

    if invalidate == "wrong_hash":
        credential = "B" * 43
    elif invalidate == "binding_revoked":
        assert repo.revoke_cloud_binding("pecem-01") is not None
    elif invalidate == "device_disabled":
        current = repo.get_device_auth("pecem-01")
        assert current is not None
        repo.put_device(replace(current, enabled=False))
    elif invalidate == "realm_inactive":
        realm = repo.set_webpilot_auth_realm_active(
            "webpilot-pecem",
            False,
        )
        assert realm is not None and not realm.active
    elif invalidate == "membership_revoked":
        membership = repo.revoke_realm_device(
            "webpilot-pecem",
            "pecem-01",
        )
        assert membership is not None and not membership.active

    with pytest.raises(CloudRealmUnauthorizedError) as exc:
        service.authenticate_cloud_binding(
            binding.cloud_binding_id,
            credential,
        )

    assert credential not in str(exc.value)
    assert "credential_hash" not in str(exc.value)


def test_realm_deactivate_blocks_and_reactivate_restores_only_valid_binding():
    repo, service, binding = _bound_repo()

    assert service.authenticate_cloud_binding(
        binding.cloud_binding_id,
        CREDENTIAL,
    )

    inactive = repo.set_webpilot_auth_realm_active(
        "webpilot-pecem",
        False,
    )
    assert inactive is not None and not inactive.active
    with pytest.raises(CloudRealmUnauthorizedError):
        service.authenticate_cloud_binding(
            binding.cloud_binding_id,
            CREDENTIAL,
        )

    repeated = repo.set_webpilot_auth_realm_active(
        "webpilot-pecem",
        False,
    )
    assert repeated == inactive

    active = repo.set_webpilot_auth_realm_active(
        "webpilot-pecem",
        True,
    )
    assert active is not None and active.active
    assert service.authenticate_cloud_binding(
        binding.cloud_binding_id,
        CREDENTIAL,
    )

    repeated_active = repo.set_webpilot_auth_realm_active(
        "webpilot-pecem",
        True,
    )
    assert repeated_active == active


class FailingAuthorityRepository(MemoryDeviceRepository):
    def get_cloud_binding_authority(self, cloud_binding_id):
        raise PersistenceUnavailableError()


def test_authenticate_cloud_binding_persistence_failure_is_fail_closed():
    service = CloudBindingService(FailingAuthorityRepository())

    with pytest.raises(PersistenceUnavailableApiError) as exc:
        service.authenticate_cloud_binding(
            "11111111-1111-1111-1111-111111111111",
            CREDENTIAL,
        )

    assert CREDENTIAL not in str(exc.value)
    assert "backend-secret-detail" not in str(exc.value)
