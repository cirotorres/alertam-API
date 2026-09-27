from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID

from app.models.maneuver_event import ManeuverEventIn
from app.repositories.devices import DeviceAuthRecord
from app.repositories.events import (
    PushDeliveryStatus,
    PushPreferences,
)
from app.repositories.memory import MemoryDeviceRepository


T0 = datetime(2026, 9, 27, 16, 0, tzinfo=timezone.utc)
INSTALL_A = UUID("10000000-0000-4000-8000-000000000001")
INSTALL_B = UUID("10000000-0000-4000-8000-000000000002")
EVENT_ID = "20000000-0000-4000-8000-000000000001"


def event() -> ManeuverEventIn:
    return ManeuverEventIn.model_validate({
        "event_id": EVENT_ID,
        "maneuver_id": "20000000-0000-4000-8000-000000000002",
        "vessel_identity": "NAME:NAVIO A",
        "vessel_imo": None,
        "vessel_name": "NAVIO A",
        "maneuver_type": "ATRACACAO",
        "event_type": "CONFIRMED",
        "berth": 4,
        "pob": "10:00",
        "occurred_at": "2026-09-27T10:00:00-03:00",
        "changes": None,
    })


def repository():
    current = [T0]
    repo = MemoryDeviceRepository(clock=lambda: current[0])
    repo.create_device(DeviceAuthRecord("pecem-01", "hash", "view-a"))
    repo.create_device(DeviceAuthRecord("other-01", "hash", "view-b"))
    repo.accept_maneuver_event_atomic("pecem-01", event())
    return repo, current


def put(repo, installation_id, device_id="pecem-01"):
    return repo.upsert_push_installation(
        device_id,
        installation_id,
        endpoint=f"https://push.example/{installation_id}",
        p256dh="public-key",
        auth="auth-key",
    )


def test_two_installations_keep_independent_preferences_and_hide_subscription_in_repr():
    repo, _ = repository()
    first = put(repo, INSTALL_A)
    second = put(repo, INSTALL_B)

    assert first is not None and second is not None
    assert first.preferences == PushPreferences()
    assert second.preferences == PushPreferences()
    assert "push.example" not in repr(first)
    assert "public-key" not in repr(first)

    changed = repo.update_push_preferences(
        "pecem-01",
        INSTALL_A,
        PushPreferences(
            confirmed=False,
            updated=True,
            completed=True,
            cancelled=True,
        ),
    )

    assert changed is not None
    assert changed.preferences.confirmed is False
    assert repo.get_push_installation("pecem-01", INSTALL_B).preferences.confirmed is True


def test_reactivation_resets_push_enabled_at_but_active_refresh_preserves_it():
    repo, current = repository()
    first = put(repo, INSTALL_A)
    assert first is not None
    assert first.push_enabled_at == T0

    current[0] = T0 + timedelta(minutes=1)
    refreshed = put(repo, INSTALL_A)
    assert refreshed.push_enabled_at == T0

    current[0] = T0 + timedelta(minutes=2)
    assert repo.deactivate_push_installation("pecem-01", INSTALL_A) is True

    current[0] = T0 + timedelta(minutes=3)
    reactivated = put(repo, INSTALL_A)
    assert reactivated.push_enabled_at == current[0]


def test_installation_id_cannot_be_taken_over_by_other_device():
    repo, _ = repository()
    assert put(repo, INSTALL_A) is not None

    attempted = put(repo, INSTALL_A, device_id="other-01")

    assert attempted is None
    assert repo.get_push_installation("pecem-01", INSTALL_A) is not None
    assert repo.get_push_installation("other-01", INSTALL_A) is None


def test_delivery_claim_has_eight_second_lease_and_terminal_status_deduplicates():
    repo, current = repository()
    assert put(repo, INSTALL_A) is not None

    assert repo.claim_push_delivery(EVENT_ID, INSTALL_A, lease_seconds=8) is True
    current[0] = T0 + timedelta(seconds=7)
    assert repo.claim_push_delivery(EVENT_ID, INSTALL_A, lease_seconds=8) is False
    current[0] = T0 + timedelta(seconds=8)
    assert repo.claim_push_delivery(EVENT_ID, INSTALL_A, lease_seconds=8) is True

    repo.set_push_delivery_status(
        EVENT_ID,
        INSTALL_A,
        PushDeliveryStatus.DELIVERED,
    )
    current[0] = T0 + timedelta(seconds=30)
    assert repo.claim_push_delivery(EVENT_ID, INSTALL_A, lease_seconds=8) is False


def test_rotate_view_secret_deactivates_all_installations_only_for_device():
    repo, _ = repository()
    assert put(repo, INSTALL_A) is not None
    assert put(repo, INSTALL_B) is not None
    other = UUID("10000000-0000-4000-8000-000000000003")
    assert put(repo, other, device_id="other-01") is not None

    assert repo.rotate_view_secret_hash("pecem-01", "new-view-hash") is True

    assert repo.get_push_installation("pecem-01", INSTALL_A).active is False
    assert repo.get_push_installation("pecem-01", INSTALL_B).active is False
    assert repo.get_push_installation("other-01", other).active is True
