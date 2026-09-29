from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Any, Protocol
from uuid import UUID

from app.models.maneuver_event import ManeuverEventIn
from app.models.vessel_tracking_event import VesselTrackingEventIn


class AcceptTrackingEventStatus(StrEnum):
    ACCEPTED = "accepted"
    IDEMPOTENT = "idempotent"
    PAYLOAD_MISMATCH = "payload_mismatch"
    DEVICE_NOT_FOUND = "device_not_found"


class TrackingPushDeliveryStatus(StrEnum):
    SENDING = "SENDING"
    DELIVERED = "DELIVERED"
    IGNORED_FOREGROUND = "IGNORED_FOREGROUND"
    IGNORED_BEFORE_TRACKING = "IGNORED_BEFORE_TRACKING"
    RETRY_PENDING = "RETRY_PENDING"
    PERMANENT_FAILURE = "PERMANENT_FAILURE"


@dataclass(frozen=True)
class TrackingPushDelivery:
    event_id: UUID
    installation_id: UUID
    status: TrackingPushDeliveryStatus
    claimed_at: datetime
    updated_at: datetime


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

    def project_tracked_vessels(
        self,
        device_id: str,
        *,
        vessel_identity: str,
        vessel_imo: str | None,
        vessel_name: str,
        observed_at: datetime,
        replace_current: bool,
        current: dict[str, Any] | None = None,
        patch: dict[str, Any] | None = None,
    ) -> int: ...

    def list_tracked_vessel_event_records(
        self,
        device_id: str,
        installation_id: UUID,
        tracked_vessel_id: UUID,
    ) -> tuple[VesselEventRecord, ...]: ...

    def latest_tracking_event_cursor(
        self,
        device_id: str,
    ) -> int | None: ...

    def list_installation_tracking_events(
        self,
        device_id: str,
        installation_id: UUID,
        *,
        after: int,
        limit: int,
    ) -> tuple[InstallationTrackingEventRecord, ...]: ...

    def find_active_tracked_vessel_for_event(
        self,
        device_id: str,
        installation_id: UUID,
        *,
        vessel_identity: str,
        vessel_imo: str | None,
        vessel_name: str,
        occurred_at: datetime,
    ) -> TrackedVesselRecord | None: ...

    def claim_tracking_push_delivery(
        self,
        event_id: str | UUID,
        installation_id: UUID,
        *,
        lease_seconds: int = 8,
    ) -> bool: ...

    def set_tracking_push_delivery_status(
        self,
        event_id: str | UUID,
        installation_id: UUID,
        status: TrackingPushDeliveryStatus,
    ) -> None: ...

    def get_tracking_push_delivery(
        self,
        event_id: str | UUID,
        installation_id: UUID,
    ) -> TrackingPushDelivery | None: ...


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


@dataclass(frozen=True)
class VesselEventRecord:
    kind: str
    ingestion_id: int
    ingested_at: datetime
    event: ManeuverEventIn | VesselTrackingEventIn


@dataclass(frozen=True)
class InstallationTrackingEventRecord:
    tracked_vessel_id: UUID
    stored: StoredVesselTrackingEvent
