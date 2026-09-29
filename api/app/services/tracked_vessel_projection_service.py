from __future__ import annotations

from app.repositories.events import AlertaRepository, StoredManeuverEvent
from app.repositories.tracking import StoredVesselTrackingEvent


class TrackedVesselProjectionService:
    def __init__(self, repository: AlertaRepository) -> None:
        self._repository = repository

    def apply_tracking_event(
        self,
        stored: StoredVesselTrackingEvent,
    ) -> None:
        event = stored.event
        self._repository.project_tracked_vessels(
            stored.device_id,
            vessel_identity=event.vessel_identity,
            vessel_imo=event.vessel_imo,
            vessel_name=event.vessel_name,
            observed_at=event.occurred_at,
            replace_current=True,
            current=event.current.model_dump(mode="json"),
        )

    def apply_maneuver_event(
        self,
        stored: StoredManeuverEvent,
    ) -> None:
        event = stored.event
        patch = {
            "berth": event.berth,
            "pob": event.pob,
            "pob_at": (
                None if event.pob_at is None else event.pob_at.isoformat()
            ),
        }
        self._repository.project_tracked_vessels(
            stored.device_id,
            vessel_identity=event.vessel_identity,
            vessel_imo=event.vessel_imo,
            vessel_name=event.vessel_name,
            observed_at=event.occurred_at,
            replace_current=False,
            patch=patch,
        )
