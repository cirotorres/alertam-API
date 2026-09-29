from __future__ import annotations

from uuid import UUID

from app.core.errors import (
    InvalidViewCredentialsError,
    TrackedVesselNotFoundError,
    VesselTrackingTargetNotFoundError,
)
from app.models.tracked_vessel import (
    TrackedVesselCreateRequest,
    TrackedVesselCurrent,
    TrackedVesselResponse,
)
from app.repositories.events import AlertaRepository
from app.repositories.tracking import TrackedVesselRecord
from app.services.mobile_session_service import MobileSessionPrincipal


class TrackedVesselService:
    def __init__(self, repository: AlertaRepository) -> None:
        self._repository = repository

    def start(
        self,
        principal: MobileSessionPrincipal,
        request: TrackedVesselCreateRequest,
    ) -> TrackedVesselResponse:
        evidence = self._repository.find_vessel_evidence(
            principal.device_id,
            vessel_identity=request.vessel_identity,
            vessel_imo=request.vessel_imo,
            vessel_name=request.vessel_name,
        )
        if evidence is None:
            raise VesselTrackingTargetNotFoundError()

        record = self._repository.upsert_tracked_vessel(
            principal.device_id,
            principal.installation_id,
            evidence,
        )
        if record is None:
            raise InvalidViewCredentialsError()
        return self._response(record)

    def list(
        self,
        principal: MobileSessionPrincipal,
    ) -> list[TrackedVesselResponse]:
        return [
            self._response(item)
            for item in self._repository.list_tracked_vessels(
                principal.device_id,
                principal.installation_id,
            )
        ]

    def stop(
        self,
        principal: MobileSessionPrincipal,
        tracked_vessel_id: UUID,
    ) -> None:
        record = self._repository.deactivate_tracked_vessel(
            principal.device_id,
            principal.installation_id,
            tracked_vessel_id,
        )
        if record is None:
            raise TrackedVesselNotFoundError()

    @staticmethod
    def _response(record: TrackedVesselRecord) -> TrackedVesselResponse:
        current = (
            None
            if record.current is None
            else TrackedVesselCurrent.model_validate(record.current)
        )
        return TrackedVesselResponse(
            tracked_vessel_id=record.tracked_vessel_id,
            vessel_identity=record.vessel_identity,
            vessel_imo=record.vessel_imo,
            vessel_name=record.vessel_name,
            started_at=record.started_at,
            active=record.active,
            stopped_at=record.stopped_at,
            last_seen_at=record.last_seen_at,
            current=current,
        )
