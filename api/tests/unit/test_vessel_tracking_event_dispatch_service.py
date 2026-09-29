from datetime import datetime, timezone

from app.models.vessel_tracking_event import VesselTrackingEventIn
from app.repositories.devices import DeviceAuthRecord
from app.repositories.memory import MemoryDeviceRepository
from app.repositories.tracking import AcceptTrackingEventStatus
from app.services.device_auth import AuthenticatedDevice
from app.services.vessel_tracking_event_service import VesselTrackingEventService


NOW = datetime(2026, 9, 29, 2, 30, tzinfo=timezone.utc)


def payload():
    return VesselTrackingEventIn.model_validate({
        "event_id": "91000000-0000-4000-8000-000000000001",
        "vessel_identity": "IMO:1234567",
        "vessel_imo": "1234567",
        "vessel_name": "NAVIO A",
        "occurred_at": NOW,
        "first_observed_at": NOW,
        "maneuver_id": None,
        "changes": {
            "eta": {"from": "03:00", "to": "04:00"},
        },
        "current": {
            "present": True,
            "status": "PREVISTO",
            "section": "PREVISTO",
            "berth": 4,
            "side": "BB",
            "eta": "04:00",
            "etb_ets": "05:00",
            "pob": None,
            "pob_at": None,
        },
    })


def test_idempotent_desktop_retry_does_not_trigger_new_tracking_push_dispatch():
    repo = MemoryDeviceRepository(clock=lambda: NOW)
    repo.create_device(DeviceAuthRecord("pecem-01", "hash", "view"))
    dispatched = []
    service = VesselTrackingEventService(
        repo,
        dispatch_event=lambda stored: dispatched.append(stored.event.event_id),
    )
    device = AuthenticatedDevice("pecem-01")

    first = service.accept_authenticated_event(device, payload())
    retry = service.accept_authenticated_event(device, payload())

    assert first.status == AcceptTrackingEventStatus.ACCEPTED.value
    assert retry.status == AcceptTrackingEventStatus.IDEMPOTENT.value
    assert dispatched == [payload().event_id]
