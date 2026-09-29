from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Any, Protocol
from uuid import UUID

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

    def find_vessel_evidence(
        self,
        device_id: str,
        *,
        vessel_identity: str,
        vessel_imo: str | None,
        vessel_name: str,
    ) -> VesselEvidence | None: ...

    def upsert_tracked_vessel(
        self,
        device_id: str,
        installation_id: UUID,
        evidence: VesselEvidence,
    ) -> TrackedVesselRecord | None: ...

    def list_tracked_vessels(
        self,
        device_id: str,
        installation_id: UUID,
    ) -> tuple[TrackedVesselRecord, ...]: ...

    def get_tracked_vessel(
        self,
        device_id: str,
        installation_id: UUID,
        tracked_vessel_id: UUID,
    ) -> TrackedVesselRecord | None: ...

    def deactivate_tracked_vessel(
        self,
        device_id: str,
        installation_id: UUID,
        tracked_vessel_id: UUID,
    ) -> TrackedVesselRecord | None: ...


@dataclass(frozen=True)
class VesselEvidence:
    vessel_identity: str
    vessel_imo: str | None
    vessel_name: str
    current: dict[str, Any] | None
    observed_at: datetime | None


@dataclass(frozen=True)
class TrackedVesselRecord:
    tracked_vessel_id: UUID
    device_id: str
    installation_id: UUID
    vessel_identity: str
    vessel_imo: str | None
    vessel_name: str
    started_at: datetime
    active: bool
    stopped_at: datetime | None
    last_seen_at: datetime | None
    current: dict[str, Any] | None
