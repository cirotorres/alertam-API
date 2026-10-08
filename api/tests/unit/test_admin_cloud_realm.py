from __future__ import annotations

from app.repositories.devices import DeviceAuthRecord
from app.repositories.memory import MemoryDeviceRepository
from scripts.admin_cloud_realm import (
    activate_realm,
    authorize_device,
    deactivate_realm,
    ensure_realm,
    revoke_device,
)
from scripts.admin_device import _DEPENDENCY_PROBES


def _repo() -> MemoryDeviceRepository:
    repo = MemoryDeviceRepository()
    repo.put_device(DeviceAuthRecord("pecem-01", "device-hash"))
    return repo


def test_admin_realm_lifecycle_is_idempotent_and_membership_reuses_row():
    repo = _repo()

    first = ensure_realm(repo, "webpilot-pecem")
    repeated = ensure_realm(repo, "webpilot-pecem")
    assert first == repeated
    assert first.active is True

    deactivated = deactivate_realm(repo, "webpilot-pecem")
    repeated_deactivate = deactivate_realm(repo, "webpilot-pecem")
    assert deactivated == repeated_deactivate
    assert deactivated.active is False

    activated = activate_realm(repo, "webpilot-pecem")
    repeated_activate = activate_realm(repo, "webpilot-pecem")
    assert activated == repeated_activate
    assert activated.active is True

    authorized = authorize_device(repo, "webpilot-pecem", "pecem-01")
    repeated_authorize = authorize_device(repo, "webpilot-pecem", "pecem-01")
    assert authorized == repeated_authorize
    assert authorized.active is True

    revoked = revoke_device(repo, "webpilot-pecem", "pecem-01")
    repeated_revoke = revoke_device(repo, "webpilot-pecem", "pecem-01")
    assert revoked == repeated_revoke
    assert revoked.active is False
    assert repeated_revoke.revoked_at == revoked.revoked_at

    reauthorized = authorize_device(repo, "webpilot-pecem", "pecem-01")
    assert reauthorized.active is True
    assert reauthorized.revoked_at is None
    assert repo.get_realm_device_authorization("webpilot-pecem", "pecem-01") == reauthorized


def test_admin_device_compensation_probes_cloud_dependencies():
    assert ("webpilot_auth_realm_devices", "device_id") in _DEPENDENCY_PROBES
    assert ("cloud_bindings", "device_id") in _DEPENDENCY_PROBES
