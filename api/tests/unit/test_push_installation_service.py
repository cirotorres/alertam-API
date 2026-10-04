from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID

import pytest

from app.core.errors import PushInstallationNotFoundError
from app.repositories.devices import DeviceAuthRecord
from app.repositories.events import PushPreferences
from app.repositories.memory import MemoryDeviceRepository
from app.services.push_installation_service import PushInstallationService


T0 = datetime(2026, 9, 27, 18, 0, tzinfo=timezone.utc)
INSTALL_A = UUID("50000000-0000-4000-8000-000000000001")


def prepared():
    current = [T0]
    repo = MemoryDeviceRepository(clock=lambda: current[0])
    repo.create_device(DeviceAuthRecord("pecem-01", "hash", "view-a"))
    repo.create_device(DeviceAuthRecord("other-01", "hash", "view-b"))
    return repo, current, PushInstallationService(repo)


def test_service_registers_session_device_and_keeps_subscription_internal():
    repo, _, service = prepared()

    result = service.register_installation(
        "pecem-01",
        INSTALL_A,
        endpoint="https://push.example/secret-endpoint",
        p256dh="public-key-secret",
        auth="auth-secret",
    )

    assert result.device_id == "pecem-01"
    assert result.preferences == PushPreferences()
    assert repo.get_push_installation("pecem-01", INSTALL_A) == result
    assert repo.get_push_installation("other-01", INSTALL_A) is None
    assert "secret-endpoint" not in repr(result)
    assert "public-key-secret" not in repr(result)


def test_service_merges_only_supplied_preference_fields():
    repo, _, service = prepared()
    service.register_installation(
        "pecem-01",
        INSTALL_A,
        endpoint="https://push.example/a",
        p256dh="p",
        auth="a",
    )

    changed = service.update_preferences(
        "pecem-01",
        INSTALL_A,
        {"confirmed": False},
    )

    assert changed.preferences == PushPreferences(
        confirmed=False,
        updated=True,
        completed=True,
        cancelled=True,
    )
    stored = repo.get_push_installation("pecem-01", INSTALL_A)
    assert stored is not None
    assert stored.preferences == changed.preferences


def test_service_foreground_updates_active_installation_only():
    repo, current, service = prepared()
    service.register_installation(
        "pecem-01",
        INSTALL_A,
        endpoint="https://push.example/a",
        p256dh="p",
        auth="a",
    )
    current[0] = T0 + timedelta(seconds=30)

    touched = service.touch_foreground("pecem-01", INSTALL_A)

    assert touched.last_seen_at == current[0]
    assert touched.last_foreground_at == current[0]

    service.deactivate_installation("pecem-01", INSTALL_A)
    current[0] = T0 + timedelta(seconds=60)

    with pytest.raises(PushInstallationNotFoundError):
        service.touch_foreground("pecem-01", INSTALL_A)

    inactive = repo.get_push_installation("pecem-01", INSTALL_A)
    assert inactive is not None
    assert inactive.last_foreground_at == T0 + timedelta(seconds=30)


def test_service_does_not_expose_other_device_installation():
    repo, _, service = prepared()
    repo.upsert_push_installation(
        "other-01",
        INSTALL_A,
        endpoint="https://push.example/other",
        p256dh="other-p",
        auth="other-a",
    )

    with pytest.raises(PushInstallationNotFoundError):
        service.get_installation("pecem-01", INSTALL_A)


def test_new_push_installation_enables_anchorage_notifications_by_default():
    _, _, service = prepared()

    result = service.register_installation(
        "pecem-01",
        INSTALL_A,
        endpoint="https://push.example/a",
        p256dh="p",
        auth="a",
    )

    assert result.preferences.anchored is True
