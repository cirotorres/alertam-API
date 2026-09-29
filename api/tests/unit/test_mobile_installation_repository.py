from datetime import datetime, timezone
from uuid import UUID

from app.repositories.devices import DeviceAuthRecord
from app.repositories.memory import MemoryDeviceRepository


NOW = datetime(2026, 9, 28, 23, 0, tzinfo=timezone.utc)
INSTALL_A = UUID("10000000-0000-4000-8000-000000000001")


def repo():
    repository = MemoryDeviceRepository(clock=lambda: NOW)
    repository.create_device(DeviceAuthRecord("pecem-01", "hash", "view"))
    repository.create_device(DeviceAuthRecord("other-01", "hash", "view"))
    return repository


def test_mobile_installation_is_idempotent_for_same_device():
    repository = repo()

    first = repository.ensure_mobile_installation("pecem-01", INSTALL_A)
    again = repository.ensure_mobile_installation("pecem-01", INSTALL_A)

    assert first is not None
    assert again == first
    assert first.device_id == "pecem-01"
    assert first.installation_id == INSTALL_A
    assert first.active is True


def test_mobile_installation_id_cannot_move_between_devices():
    repository = repo()
    assert repository.ensure_mobile_installation("pecem-01", INSTALL_A) is not None

    assert repository.ensure_mobile_installation("other-01", INSTALL_A) is None
    assert repository.get_mobile_installation("pecem-01", INSTALL_A) is not None
    assert repository.get_mobile_installation("other-01", INSTALL_A) is None


def test_revoked_mobile_installation_can_be_reactivated_only_by_same_device():
    repository = repo()
    repository.ensure_mobile_installation("pecem-01", INSTALL_A)
    assert repository.revoke_mobile_installation("pecem-01", INSTALL_A) is True
    assert repository.get_mobile_installation("pecem-01", INSTALL_A).active is False

    restored = repository.ensure_mobile_installation("pecem-01", INSTALL_A)

    assert restored is not None
    assert restored.active is True
    assert repository.ensure_mobile_installation("other-01", INSTALL_A) is None
