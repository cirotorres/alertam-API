from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID

from app.infrastructure.web_push import (
    PermanentPushError,
    TransientPushError,
)
from app.models.maneuver_event import ManeuverEventIn
from app.repositories.devices import DeviceAuthRecord
from app.repositories.events import (
    PushDeliveryStatus,
    PushPreferences,
)
from app.repositories.memory import MemoryDeviceRepository
from app.services.push_dispatch_service import (
    PushDispatchService,
    build_push_message,
)


T0 = datetime(2026, 9, 27, 18, 0, tzinfo=timezone.utc)
INSTALL = UUID("80000000-0000-4000-8000-000000000001")


class RecordingGateway:
    def __init__(self, error: Exception | None = None) -> None:
        self.error = error
        self.calls = []
    def send(self, installation, payload) -> None:
        self.calls.append((installation, payload))
        if self.error is not None:
            raise self.error


def event(
    *,
    event_type: str = "CONFIRMED",
    occurred_at: datetime = T0,
) -> ManeuverEventIn:
    changes = None
    if event_type == "UPDATED":
        changes = {
            "pob": {"from": "14:30", "to": "15:00"},
        }
    return ManeuverEventIn.model_validate({
        "event_id": "80000000-0000-4000-8000-000000000010",
        "maneuver_id": "80000000-0000-4000-8000-000000000020",
        "vessel_identity": "NAME:NAVIO A",
        "vessel_imo": None,
        "vessel_name": "NAVIO A",
        "maneuver_type": "ATRACACAO",
        "event_type": event_type,
        "berth": 4,
        "pob": "15:00",
        "occurred_at": occurred_at,
        "changes": changes,
    })

def prepared(
    *,
    occurred_at: datetime = T0,
    gateway_error: Exception | None = None,
):
    current = [T0]
    repo = MemoryDeviceRepository(clock=lambda: current[0])
    repo.create_device(DeviceAuthRecord("pecem-01", "hash", "view"))
    accepted = repo.accept_maneuver_event_atomic(
        "pecem-01",
        event(occurred_at=occurred_at),
    )
    assert accepted.stored is not None
    gateway = RecordingGateway(gateway_error)
    service = PushDispatchService(
        repo,
        gateway,
        foreground_fresh_seconds=75,
        clock=lambda: current[0],
    )
    return repo, current, accepted.stored, gateway, service


def subscribe(repo):
    installation = repo.upsert_push_installation(
        "pecem-01",
        INSTALL,
        endpoint="https://push.example/a",
        p256dh="p",
        auth="a",
    )
    assert installation is not None
    return installation


def test_event_before_opt_in_is_recorded_ignored_without_send():
    repo, current, stored, gateway, service = prepared(
        occurred_at=T0 - timedelta(seconds=1)
    )
    subscribe(repo)

    service.dispatch_event(stored)

    assert gateway.calls == []
    delivery = repo.get_push_delivery(stored.event.event_id, INSTALL)
    assert delivery is not None
    assert delivery.status is PushDeliveryStatus.IGNORED_BEFORE_OPT_IN


def test_disabled_preference_is_ignored_before_foreground_and_send():
    repo, _, stored, gateway, service = prepared()
    subscribe(repo)
    repo.update_push_preferences(
        "pecem-01",
        INSTALL,
        PushPreferences(confirmed=False),
    )

    service.dispatch_event(stored)

    assert gateway.calls == []
    delivery = repo.get_push_delivery(stored.event.event_id, INSTALL)
    assert delivery is not None
    assert delivery.status is PushDeliveryStatus.IGNORED_PREFERENCE


def test_recent_foreground_is_ignored_within_75_seconds():
    repo, current, stored, gateway, service = prepared()
    subscribe(repo)
    repo.touch_push_foreground("pecem-01", INSTALL)
    current[0] = T0 + timedelta(seconds=75)

    service.dispatch_event(stored)

    assert gateway.calls == []
    delivery = repo.get_push_delivery(stored.event.event_id, INSTALL)
    assert delivery is not None
    assert delivery.status is PushDeliveryStatus.IGNORED_FOREGROUND


def test_eligible_delivery_sends_once_and_marks_delivered():
    repo, current, stored, gateway, service = prepared()
    subscribe(repo)
    current[0] = T0 + timedelta(seconds=76)

    service.dispatch_event(stored)
    service.dispatch_event(stored)

    assert len(gateway.calls) == 1
    delivery = repo.get_push_delivery(stored.event.event_id, INSTALL)
    assert delivery is not None
    assert delivery.status is PushDeliveryStatus.DELIVERED

def test_permanent_failure_deactivates_only_installation_and_records_status():
    repo, _, stored, gateway, service = prepared(
        gateway_error=PermanentPushError()
    )
    subscribe(repo)

    service.dispatch_event(stored)

    assert len(gateway.calls) == 1
    installation = repo.get_push_installation("pecem-01", INSTALL)
    assert installation is not None
    assert installation.active is False
    delivery = repo.get_push_delivery(stored.event.event_id, INSTALL)
    assert delivery is not None
    assert delivery.status is PushDeliveryStatus.PERMANENT_FAILURE


def test_transient_failure_keeps_installation_active_and_retry_pending():
    repo, _, stored, gateway, service = prepared(
        gateway_error=TransientPushError()
    )
    subscribe(repo)

    service.dispatch_event(stored)

    assert len(gateway.calls) == 1
    assert repo.get_push_installation("pecem-01", INSTALL).active is True
    delivery = repo.get_push_delivery(stored.event.event_id, INSTALL)
    assert delivery is not None
    assert delivery.status is PushDeliveryStatus.RETRY_PENDING

def test_retry_pending_can_be_reclaimed_but_delivered_cannot():
    repo, current, stored, gateway, service = prepared(
        gateway_error=TransientPushError()
    )
    subscribe(repo)

    service.dispatch_event(stored)
    assert len(gateway.calls) == 1

    gateway.error = None
    current[0] = T0 + timedelta(seconds=10)
    service.dispatch_event(stored)
    service.dispatch_event(stored)

    assert len(gateway.calls) == 2
    assert repo.get_push_delivery(
        stored.event.event_id,
        INSTALL,
    ).status is PushDeliveryStatus.DELIVERED


def test_build_push_message_contains_only_public_payload_fields():
    message = build_push_message(event(event_type="UPDATED"))

    assert set(message) == {"event_id", "title", "body", "url"}
    assert message["title"] == "Atracação atualizada"
    assert "NAVIO A" in message["body"]
    assert "14:30 → 15:00" in message["body"]
    assert message["url"].endswith(str(event().event_id))
