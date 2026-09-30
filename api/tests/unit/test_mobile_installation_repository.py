from datetime import datetime, timedelta, timezone
from uuid import UUID

from app.repositories.devices import DeviceAuthRecord
from app.repositories.memory import MemoryDeviceRepository


NOW = datetime(2026, 9, 28, 23, 0, tzinfo=timezone.utc)
INSTALL_A = UUID("10000000-0000-4000-8000-000000000001")
INSTALL_B = UUID("10000000-0000-4000-8000-000000000002")
INSTALL_C = UUID("10000000-0000-4000-8000-000000000003")


def repo(clock=lambda: NOW):
    repository = MemoryDeviceRepository(clock=clock)
    repository.create_device(DeviceAuthRecord("pecem-01", "hash", "view"))
    repository.create_device(DeviceAuthRecord("other-01", "hash", "view"))
    return repository


def test_mobile_installation_is_idempotent_for_same_device():
    repository = repo()

    first = repository.ensure_mobile_installation(
        "pecem-01",
        INSTALL_A,
        platform="ios",
        display_code="K7M4Q2",
    )
    again = repository.ensure_mobile_installation(
        "pecem-01",
        INSTALL_A,
        platform="android",
        display_code="ZZZZZZ",
    )

    assert first is not None
    assert again == first
    assert first.device_id == "pecem-01"
    assert first.installation_id == INSTALL_A
    assert first.active is True
    assert first.platform == "ios"
    assert first.display_code == "K7M4Q2"


def test_mobile_installation_id_cannot_move_between_devices():
    repository = repo()
    assert repository.ensure_mobile_installation("pecem-01", INSTALL_A) is not None

    assert repository.ensure_mobile_installation("other-01", INSTALL_A) is None
    assert repository.get_mobile_installation("pecem-01", INSTALL_A) is not None
    assert repository.get_mobile_installation("other-01", INSTALL_A) is None


def test_revoked_mobile_installation_cannot_be_reactivated():
    repository = repo()
    repository.ensure_mobile_installation("pecem-01", INSTALL_A)
    assert repository.revoke_mobile_installation("pecem-01", INSTALL_A) is True
    revoked = repository.get_mobile_installation("pecem-01", INSTALL_A)
    assert revoked is not None
    assert revoked.active is False

    restored = repository.ensure_mobile_installation("pecem-01", INSTALL_A)

    assert restored is None
    assert repository.get_mobile_installation("pecem-01", INSTALL_A) == revoked


def test_list_mobile_installations_keeps_active_and_revoked_at_30_day_boundary():
    now = [NOW]
    repository = repo(clock=lambda: now[0])

    repository.ensure_mobile_installation("pecem-01", INSTALL_A)
    repository.ensure_mobile_installation("pecem-01", INSTALL_B)
    repository.revoke_mobile_installation("pecem-01", INSTALL_B)
    now[0] = NOW + timedelta(days=30)

    items = repository.list_mobile_installations(
        "pecem-01",
        revoked_since=now[0] - timedelta(days=30),
    )

    assert {item.installation_id for item in items} == {INSTALL_A, INSTALL_B}


def test_list_mobile_installations_omits_revoked_older_than_30_days():
    now = [NOW]
    repository = repo(clock=lambda: now[0])

    repository.ensure_mobile_installation("pecem-01", INSTALL_A)
    repository.revoke_mobile_installation("pecem-01", INSTALL_A)
    now[0] = NOW + timedelta(days=30, seconds=1)

    items = repository.list_mobile_installations(
        "pecem-01",
        revoked_since=now[0] - timedelta(days=30),
    )

    assert items == ()


def test_touch_updates_last_seen_and_only_fills_unknown_platform():
    now = [NOW]
    repository = repo(clock=lambda: now[0])
    repository.ensure_mobile_installation(
        "pecem-01",
        INSTALL_A,
        platform="other",
        display_code="K7M4Q2",
    )

    now[0] = NOW + timedelta(minutes=5)
    touched = repository.touch_mobile_installation(
        "pecem-01",
        INSTALL_A,
        platform="ios",
    )
    assert touched is not None
    assert touched.last_seen_at == now[0]
    assert touched.platform == "ios"

    now[0] = NOW + timedelta(minutes=10)
    touched_again = repository.touch_mobile_installation(
        "pecem-01",
        INSTALL_A,
        platform="android",
    )
    assert touched_again is not None
    assert touched_again.platform == "ios"


def test_touch_never_reactivates_revoked_installation():
    repository = repo()
    repository.ensure_mobile_installation("pecem-01", INSTALL_C)
    repository.revoke_mobile_installation("pecem-01", INSTALL_C)

    assert repository.touch_mobile_installation(
        "pecem-01",
        INSTALL_C,
        platform="android",
    ) is None
    assert repository.get_mobile_installation("pecem-01", INSTALL_C).active is False


def test_revoke_mobile_installation_deactivates_push_credentials():
    repository = repo()
    repository.ensure_mobile_installation(
        "pecem-01",
        INSTALL_A,
        display_code="K7M4Q2",
    )
    repository.upsert_push_installation(
        "pecem-01",
        INSTALL_A,
        endpoint="https://push.example/endpoint",
        p256dh="key",
        auth="auth",
    )

    assert repository.revoke_mobile_installation("pecem-01", INSTALL_A) is True

    push = repository.get_push_installation("pecem-01", INSTALL_A)
    assert push is not None
    assert push.active is False
    assert push.endpoint is None
    assert push.p256dh is None
    assert push.auth is None
