from datetime import datetime
from uuid import UUID

from app.models.maneuver_event import ManeuverEventIn
from app.repositories.events import StoredManeuverEvent
from app.services.tracked_vessel_projection_service import TrackedVesselProjectionService


class FakeRepository:
    def __init__(self):
        self.calls = []

    def project_tracked_vessels(self, device_id, **kwargs):
        self.calls.append((device_id, kwargs))
        return 1


def stored(maneuver_type: str, event_type: str) -> StoredManeuverEvent:
    event = ManeuverEventIn(
        event_id=UUID("10000000-0000-4000-8000-000000000001"),
        maneuver_id=UUID("10000000-0000-4000-8000-000000000002"),
        vessel_identity="IMO:9961972",
        vessel_imo="9961972",
        vessel_name="LOG-IN EXPERIENCE",
        maneuver_type=maneuver_type,
        event_type=event_type,
        berth=10,
        pob="30/09 12:30",
        occurred_at="2026-09-30T12:46:00-03:00",
        pob_at="2026-09-30T12:30:00-03:00",
        first_observed_at="2026-09-30T12:45:00-03:00",
        changes=None,
    )
    return StoredManeuverEvent(
        ingestion_id=1,
        device_id="desktop-1",
        event=event,
        ingested_at=datetime.fromisoformat("2026-09-30T15:46:01+00:00"),
    )


def test_completed_departure_projects_tracked_vessel_as_absent():
    repository = FakeRepository()
    service = TrackedVesselProjectionService(repository)

    service.apply_maneuver_event(stored("DESATRACACAO", "COMPLETED"))

    _, call = repository.calls[-1]
    assert call["replace_current"] is False
    assert call["patch"]["present"] is False


def test_completed_arrival_does_not_force_tracked_vessel_absent():
    repository = FakeRepository()
    service = TrackedVesselProjectionService(repository)

    service.apply_maneuver_event(stored("ATRACACAO", "COMPLETED"))

    _, call = repository.calls[-1]
    assert "present" not in call["patch"]
