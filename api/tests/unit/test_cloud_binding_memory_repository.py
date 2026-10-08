from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.repositories.cloud_bindings import (
    CloudBindingConflictError,
    CloudBindingStatus,
    WebPilotAuthRealmRecord,
)
from app.repositories.devices import DeviceAuthRecord
from app.repositories.memory import MemoryDeviceRepository


BASE = datetime(2026, 10, 8, 5, 45, tzinfo=timezone.utc)


def _device(device_id: str, *, enabled: bool = True) -> DeviceAuthRecord:
    return DeviceAuthRecord(
        device_id=device_id,
        device_secret_hash=f"{device_id}-device-hash",
        enabled=enabled,
    )


def _realm(
    realm_id: str = "webpilot-pecem",
    *,
    active: bool = True,
) -> WebPilotAuthRealmRecord:
    return WebPilotAuthRealmRecord(
        realm_id=realm_id,
        active=active,
        created_at=BASE,
        updated_at=BASE,
    )


def _authorized_repo():
    now = [BASE]
    repo = MemoryDeviceRepository(clock=lambda: now[0])
    repo.put_device(_device("pecem-01"))
    repo.put_webpilot_auth_realm(_realm())
    authorization = repo.authorize_realm_device("webpilot-pecem", "pecem-01")
    assert authorization is not None
    return repo, now


def test_memory_repository_authorizes_existing_device_in_existing_realm():
    repo = MemoryDeviceRepository(clock=lambda: BASE)
    repo.put_device(_device("pecem-01"))
    repo.put_webpilot_auth_realm(_realm())

    assert repo.get_realm_device_authorization("webpilot-pecem", "pecem-01") is None

    authorization = repo.authorize_realm_device("webpilot-pecem", "pecem-01")

    assert authorization is not None
    assert authorization.realm_id == "webpilot-pecem"
    assert authorization.device_id == "pecem-01"
    assert authorization.authorized_at == BASE
    assert authorization.active is True
    assert repo.get_realm_device_authorization(
        "webpilot-pecem",
        "pecem-01",
    ) == authorization

    assert repo.authorize_realm_device("missing", "pecem-01") is None
    assert repo.authorize_realm_device("webpilot-pecem", "missing") is None


def test_ensure_cloud_binding_is_idempotent_and_rejects_second_active_binding():
    repo, _now = _authorized_repo()

    first = repo.ensure_cloud_binding(
        "pecem-01",
        "webpilot-pecem",
        "cloud-hash-v1",
    )
    repeated = repo.ensure_cloud_binding(
        "pecem-01",
        "webpilot-pecem",
        "cloud-hash-v1",
    )

    assert first is not None
    assert repeated == first
    assert first.status is CloudBindingStatus.ACTIVE
    assert first.credential_version == 1
    assert repo.get_active_cloud_binding("pecem-01") == first

    with pytest.raises(CloudBindingConflictError):
        repo.ensure_cloud_binding(
            "pecem-01",
            "webpilot-pecem",
            "different-cloud-hash",
        )


def test_binding_creation_and_rotation_require_current_authority():
    repo = MemoryDeviceRepository(clock=lambda: BASE)
    repo.put_device(_device("pecem-01"))
    repo.put_webpilot_auth_realm(_realm())

    assert repo.ensure_cloud_binding(
        "pecem-01",
        "webpilot-pecem",
        "cloud-hash",
    ) is None

    repo.authorize_realm_device("webpilot-pecem", "pecem-01")
    binding = repo.ensure_cloud_binding(
        "pecem-01",
        "webpilot-pecem",
        "cloud-hash",
    )
    assert binding is not None

    repo.put_device(_device("pecem-01", enabled=False))

    assert repo.rotate_cloud_binding("pecem-01", "cloud-hash-v2") is None
    assert repo.get_active_cloud_binding("pecem-01") == binding


def test_revoke_fails_closed_when_device_is_disabled():
    repo, _now = _authorized_repo()
    binding = repo.ensure_cloud_binding(
        "pecem-01",
        "webpilot-pecem",
        "cloud-hash-v1",
    )
    assert binding is not None

    repo.put_device(_device("pecem-01", enabled=False))

    assert repo.revoke_cloud_binding("pecem-01") is None
    assert repo.get_active_cloud_binding("pecem-01") == binding


def test_rotate_is_idempotent_for_same_hash_and_increments_once_for_new_hash():
    repo, now = _authorized_repo()
    first = repo.ensure_cloud_binding(
        "pecem-01",
        "webpilot-pecem",
        "cloud-hash-v1",
    )
    assert first is not None

    same = repo.rotate_cloud_binding("pecem-01", "cloud-hash-v1")

    assert same == first
    assert same.credential_version == 1

    now[0] += timedelta(minutes=1)
    rotated = repo.rotate_cloud_binding("pecem-01", "cloud-hash-v2")

    assert rotated is not None
    assert rotated.cloud_binding_id == first.cloud_binding_id
    assert rotated.credential_hash == "cloud-hash-v2"
    assert rotated.credential_version == 2
    assert rotated.updated_at == now[0]

    repeated = repo.rotate_cloud_binding("pecem-01", "cloud-hash-v2")
    assert repeated == rotated
    assert repeated.credential_version == 2


def test_revoke_is_idempotent_and_preserves_binding_history_for_rebind():
    repo, now = _authorized_repo()
    first = repo.ensure_cloud_binding(
        "pecem-01",
        "webpilot-pecem",
        "cloud-hash-v1",
    )
    assert first is not None

    now[0] += timedelta(minutes=1)
    revoked = repo.revoke_cloud_binding("pecem-01")

    assert revoked is not None
    assert revoked.status is CloudBindingStatus.REVOKED
    assert revoked.revoked_at == now[0]
    assert repo.get_active_cloud_binding("pecem-01") is None

    repeated = repo.revoke_cloud_binding("pecem-01")
    assert repeated == revoked

    now[0] += timedelta(minutes=1)
    rebound = repo.ensure_cloud_binding(
        "pecem-01",
        "webpilot-pecem",
        "cloud-hash-v2",
    )

    assert rebound is not None
    assert rebound.cloud_binding_id != revoked.cloud_binding_id
    assert rebound.credential_version == 1
    assert repo.list_cloud_bindings("pecem-01") == (revoked, rebound)


def test_cloud_binding_operations_are_scoped_to_device():
    repo = MemoryDeviceRepository(clock=lambda: BASE)
    repo.put_webpilot_auth_realm(_realm())
    for device_id in ("pecem-01", "pecem-02"):
        repo.put_device(_device(device_id))
        assert repo.authorize_realm_device("webpilot-pecem", device_id) is not None

    first = repo.ensure_cloud_binding(
        "pecem-01",
        "webpilot-pecem",
        "cloud-hash-a",
    )
    second = repo.ensure_cloud_binding(
        "pecem-02",
        "webpilot-pecem",
        "cloud-hash-b",
    )
    assert first is not None
    assert second is not None

    repo.rotate_cloud_binding("pecem-01", "cloud-hash-a2")
    repo.revoke_cloud_binding("pecem-01")

    assert repo.get_active_cloud_binding("pecem-01") is None
    assert repo.get_active_cloud_binding("pecem-02") == second
    assert repo.list_cloud_bindings("pecem-02") == (second,)
