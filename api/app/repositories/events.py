from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Protocol
from uuid import UUID

from app.models.maneuver_event import ManeuverEventIn
from app.repositories.devices import DevicesRepository
from app.repositories.tracking import TrackingEventsRepository


class AcceptEventStatus(StrEnum):
    ACCEPTED = "accepted"
    IDEMPOTENT = "idempotent"
    PAYLOAD_MISMATCH = "payload_mismatch"
    DEVICE_NOT_FOUND = "device_not_found"


@dataclass(frozen=True)
class StoredManeuverEvent:
    ingestion_id: int
    device_id: str
    event: ManeuverEventIn
    ingested_at: datetime


@dataclass(frozen=True)
class AcceptEventResult:
    status: AcceptEventStatus
    stored: StoredManeuverEvent | None = None


@dataclass(frozen=True)
class EventPage:
    events: tuple[StoredManeuverEvent, ...]
    oldest_cursor: int | None
    newest_cursor: int | None
    has_more_before: bool


@dataclass(frozen=True)
class ManeuverEventDetail:
    selected_event_id: UUID
    maneuver_id: UUID
    events: tuple[StoredManeuverEvent, ...]


class ManeuverEventsRepository(Protocol):
    def accept_maneuver_event_atomic(
        self,
        device_id: str,
        event: ManeuverEventIn,
    ) -> AcceptEventResult: ...

    def list_maneuver_events(
        self,
        device_id: str,
        *,
        after: int | None = None,
        before: int | None = None,
        limit: int = 50,
    ) -> EventPage: ...

    def get_maneuver_event_detail(
        self,
        device_id: str,
        event_id: UUID,
    ) -> ManeuverEventDetail | None: ...


@dataclass(frozen=True)
class PushPreferences:
    confirmed: bool = True
    updated: bool = True
    completed: bool = True
    cancelled: bool = True


@dataclass(frozen=True)
class PushInstallation:
    installation_id: UUID
    device_id: str
    endpoint: str | None = field(repr=False)
    p256dh: str | None = field(repr=False)
    auth: str | None = field(repr=False)
    preferences: PushPreferences
    push_enabled_at: datetime
    last_seen_at: datetime
    last_foreground_at: datetime | None
    active: bool
    created_at: datetime
    updated_at: datetime


class PushDeliveryStatus(StrEnum):
    SENDING = "SENDING"
    DELIVERED = "DELIVERED"
    IGNORED_PREFERENCE = "IGNORED_PREFERENCE"
    IGNORED_FOREGROUND = "IGNORED_FOREGROUND"
    IGNORED_BEFORE_OPT_IN = "IGNORED_BEFORE_OPT_IN"
    RETRY_PENDING = "RETRY_PENDING"
    PERMANENT_FAILURE = "PERMANENT_FAILURE"


@dataclass(frozen=True)
class PushDelivery:
    event_id: UUID
    installation_id: UUID
    status: PushDeliveryStatus
    claimed_at: datetime
    updated_at: datetime


class PushRepository(Protocol):
    def upsert_push_installation(
        self,
        device_id: str,
        installation_id: UUID,
        *,
        endpoint: str,
        p256dh: str,
        auth: str,
    ) -> PushInstallation | None: ...

    def get_push_installation(
        self,
        device_id: str,
        installation_id: UUID,
    ) -> PushInstallation | None: ...

    def update_push_preferences(
        self,
        device_id: str,
        installation_id: UUID,
        preferences: PushPreferences,
    ) -> PushInstallation | None: ...

    def touch_push_foreground(
        self,
        device_id: str,
        installation_id: UUID,
    ) -> PushInstallation | None: ...

    def deactivate_push_installation(
        self,
        device_id: str,
        installation_id: UUID,
    ) -> bool: ...

    def list_active_push_installations(
        self,
        device_id: str,
    ) -> tuple[PushInstallation, ...]: ...

    def claim_push_delivery(
        self,
        event_id: str | UUID,
        installation_id: UUID,
        *,
        lease_seconds: int = 8,
    ) -> bool: ...

    def set_push_delivery_status(
        self,
        event_id: str | UUID,
        installation_id: UUID,
        status: PushDeliveryStatus,
    ) -> None: ...

    def get_push_delivery(
        self,
        event_id: str | UUID,
        installation_id: UUID,
    ) -> PushDelivery | None: ...


class AlertaRepository(
    DevicesRepository,
    ManeuverEventsRepository,
    TrackingEventsRepository,
    PushRepository,
    Protocol,
):
    pass
