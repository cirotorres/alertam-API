from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Protocol

from app.models.vessel_tracking_event import VesselTrackingEventIn


class AcceptTrackingEventStatus(StrEnum):
    ACCEPTED = "accepted"
    IDEMPOTENT = "idempotent"
    PAYLOAD_MISMATCH = "payload_mismatch"
    DEVICE_NOT_FOUND = "device_not_found"


@dataclass(frozen=True)
class StoredVesselTrackingEvent:
    ingestion_id: int
    device_id: str
    event: VesselTrackingEventIn
    ingested_at: datetime


@dataclass(frozen=True)
class AcceptTrackingEventResult:
    status: AcceptTrackingEventStatus
    stored: StoredVesselTrackingEvent | None = None


class TrackingEventsRepository(Protocol):
    def accept_vessel_tracking_event_atomic(
        self,
        device_id: str,
        event: VesselTrackingEventIn,
    ) -> AcceptTrackingEventResult: ...
