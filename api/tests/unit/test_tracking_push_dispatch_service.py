from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID

from app.infrastructure.web_push import PermanentPushError, TransientPushError
from app.models.vessel_tracking_event import VesselTrackingEventIn
from app.repositories.devices import DeviceAuthRecord
from app.repositories.memory import MemoryDeviceRepository
from app.repositories.tracking import (
    TrackingPushDeliveryStatus,
    VesselEvidence,
)
from app.services.tracking_push_dispatch_service import (
    TrackingPushDispatchService,
    build_tracking_push_message,
)


T0 = datetime(2026, 9, 29, 2, 30, tzinfo=timezone.utc)
INSTALL_A = UUID("90000000-0000-4000-8000-000000000001")
INSTALL_B = UUID("90000000-0000-4000-8000-000000000002")


class SelectiveGateway:
    def __init__(self, failures=None):
        self.failures = failures or {}
        self.calls = []

    def send(self, installation, payload):
        self.calls.append((installation, payload))
        error = self.failures.get(installation.installation_id)
        if error is not None:
            raise error


def event(*, event_id="90000000-0000-4000-8000-000000000010", occurred_at=T0, presence=None):
    changes = {
        "eta": {"from": "29/09 03:00", "to": "29/09 04:00"},
    }
    current = {
        "present": True,
        "status": "PREVISTO",
        "section": "PREVISTO",
        "berth": 4,
        "side": "BB",
        "eta": "29/09 04:00",
        "etb_ets": "29/09 05:00",
        "pob": None,
        "pob_at": None,
    }
    if presence is not None:
        changes = {"presence": {"from": not presence, "to": presence}}
        current["present"] = presence
    return VesselTrackingEventIn.model_validate({
        "event_id": event_id,
        "vessel_identity": "IMO:1234567",
        "vessel_imo": "1234567",
        "vessel_name": "NAVIO A",
        "occurred_at": occurred_at,
        "first_observed_at": occurred_at,
        "maneuver_id": None,
        "changes": changes,
        "current": current,
    })


def prepared(*, gateway=None):
    current = [T0]
    repo = MemoryDeviceRepository(clock=lambda: current[0])
    repo.create_device(DeviceAuthRecord("pecem-01", "hash", "view"))
    accepted = repo.accept_vessel_tracking_event_atomic("pecem-01", event())
    assert accepted.stored is not None
    service = TrackingPushDispatchService(
        repo,
        gateway or SelectiveGateway(),
        foreground_fresh_seconds=75,
        clock=lambda: current[0],
    )
    return repo, current, accepted.stored, service


def subscribe(repo, installation_id):
    result = repo.upsert_push_installation(
        "pecem-01",
        installation_id,
        endpoint=f"https://push.example/{installation_id}",
        p256dh="p",
        auth="a",
    )
    assert result is not None
    return result


def track(repo, current, installation_id, *, started_at=T0):
    current[0] = started_at
    assert repo.ensure_mobile_installation("pecem-01", installation_id) is not None
    tracked = repo.upsert_tracked_vessel(
        "pecem-01",
        installation_id,
        VesselEvidence(
            vessel_identity="IMO:1234567",
            vessel_imo="1234567",
            vessel_name="NAVIO A",
            current={
                "present": True,
                "status": "PREVISTO",
                "section": "PREVISTO",
                "berth": 4,
                "side": "BB",
                "eta": "29/09 03:00",
                "etb_ets": "29/09 05:00",
                "pob": None,
                "pob_at": None,
            },
            observed_at=started_at,
        ),
    )
    assert tracked is not None
    return tracked


def test_only_installations_tracking_vessel_receive_tracking_push():
    gateway = SelectiveGateway()
    repo, current, stored, service = prepared(gateway=gateway)
    subscribe(repo, INSTALL_A)
    subscribe(repo, INSTALL_B)
    tracked = track(repo, current, INSTALL_A)
    current[0] = T0 + timedelta(seconds=80)

    service.dispatch_event(stored)

    assert [call[0].installation_id for call in gateway.calls] == [INSTALL_A]
    payload = gateway.calls[0][1]
    assert payload["url"] == (
        f"/acompanhados?track={tracked.tracked_vessel_id}"
        f"&event={stored.event.event_id}"
    )
    assert repo.get_tracking_push_delivery(
        stored.event.event_id, INSTALL_A
    ).status is TrackingPushDeliveryStatus.DELIVERED
    assert repo.get_tracking_push_delivery(stored.event.event_id, INSTALL_B) is None


def test_recent_foreground_suppresses_tracking_web_push():
    gateway = SelectiveGateway()
    repo, current, stored, service = prepared(gateway=gateway)
    subscribe(repo, INSTALL_A)
    track(repo, current, INSTALL_A)
    current[0] = T0 + timedelta(seconds=10)
    repo.touch_push_foreground("pecem-01", INSTALL_A)

    service.dispatch_event(stored)

    assert gateway.calls == []
    delivery = repo.get_tracking_push_delivery(stored.event.event_id, INSTALL_A)
    assert delivery is not None
    assert delivery.status is TrackingPushDeliveryStatus.IGNORED_FOREGROUND


def test_failure_in_one_installation_does_not_block_another():
    gateway = SelectiveGateway({
        INSTALL_A: TransientPushError(),
    })
    repo, current, stored, service = prepared(gateway=gateway)
    for installation_id in (INSTALL_A, INSTALL_B):
        subscribe(repo, installation_id)
        track(repo, current, installation_id)
    current[0] = T0 + timedelta(seconds=80)

    service.dispatch_event(stored)

    assert len(gateway.calls) == 2
    assert repo.get_tracking_push_delivery(
        stored.event.event_id, INSTALL_A
    ).status is TrackingPushDeliveryStatus.RETRY_PENDING
    assert repo.get_tracking_push_delivery(
        stored.event.event_id, INSTALL_B
    ).status is TrackingPushDeliveryStatus.DELIVERED


def test_event_before_tracking_is_recorded_ignored_without_send():
    gateway = SelectiveGateway()
    repo, current, stored, service = prepared(gateway=gateway)
    subscribe(repo, INSTALL_A)
    track(repo, current, INSTALL_A, started_at=T0 + timedelta(seconds=1))
    current[0] = T0 + timedelta(seconds=80)

    service.dispatch_event(stored)

    assert gateway.calls == []
    delivery = repo.get_tracking_push_delivery(stored.event.event_id, INSTALL_A)
    assert delivery is not None
    assert delivery.status is TrackingPushDeliveryStatus.IGNORED_BEFORE_TRACKING


def test_disappearance_message_never_claims_ship_departed():
    message = build_tracking_push_message(
        event(
            event_id="90000000-0000-4000-8000-000000000011",
            presence=False,
        ),
        UUID("90000000-0000-4000-8000-000000000099"),
    )

    assert "desatrac" not in message["title"].lower()
    assert "desatrac" not in message["body"].lower()
    assert "não aparece" in message["body"].lower()


def test_permanent_failure_deactivates_push_not_tracking():
    gateway = SelectiveGateway({
        INSTALL_A: PermanentPushError(),
    })
    repo, current, stored, service = prepared(gateway=gateway)
    subscribe(repo, INSTALL_A)
    tracked = track(repo, current, INSTALL_A)
    current[0] = T0 + timedelta(seconds=80)

    service.dispatch_event(stored)

    assert repo.get_push_installation("pecem-01", INSTALL_A).active is False
    still_tracked = repo.get_tracked_vessel(
        "pecem-01", INSTALL_A, tracked.tracked_vessel_id
    )
    assert still_tracked is not None and still_tracked.active is True
    delivery = repo.get_tracking_push_delivery(stored.event.event_id, INSTALL_A)
    assert delivery is not None
    assert delivery.status is TrackingPushDeliveryStatus.PERMANENT_FAILURE


def test_revoked_mobile_installation_stops_future_tracking_push_delivery():
    gateway = SelectiveGateway()
    repo, current, stored, service = prepared(gateway=gateway)
    subscribe(repo, INSTALL_A)
    track(repo, current, INSTALL_A)
    assert repo.revoke_mobile_installation("pecem-01", INSTALL_A) is True
    current[0] = T0 + timedelta(seconds=80)

    service.dispatch_event(stored)

    assert gateway.calls == []
    assert repo.get_tracking_push_delivery(
        stored.event.event_id, INSTALL_A
    ) is None


def test_reactivated_push_does_not_replay_event_older_than_new_opt_in():
    gateway = SelectiveGateway()
    repo, current, stored, service = prepared(gateway=gateway)
    subscribe(repo, INSTALL_A)
    track(repo, current, INSTALL_A)
    assert repo.deactivate_push_installation("pecem-01", INSTALL_A) is True

    current[0] = T0 + timedelta(minutes=5)
    subscribe(repo, INSTALL_A)
    service.dispatch_event(stored)

    assert gateway.calls == []
    assert repo.get_tracking_push_delivery(
        stored.event.event_id, INSTALL_A
    ) is None
