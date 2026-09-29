from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
from threading import Lock
from typing import Callable, Iterable
from uuid import UUID, uuid4

from app.models.maneuver_event import ManeuverEventIn
from app.models.vessel_tracking_event import VesselTrackingEventIn
from app.repositories.devices import (
    AcceptSnapshotResult,
    AcceptSnapshotStatus,
    DeviceAlreadyExistsError,
    DeviceAuthRecord,
    MobileInstallationRecord,
    SnapshotCandidate,
    StoredSnapshot,
)
from app.repositories.events import (
    AcceptEventResult,
    AcceptEventStatus,
    EventPage,
    ManeuverEventDetail,
    PushDelivery,
    PushDeliveryStatus,
    PushInstallation,
    PushPreferences,
    StoredManeuverEvent,
)
from app.repositories.tracking import (
    AcceptTrackingEventResult,
    AcceptTrackingEventStatus,
    StoredVesselTrackingEvent,
    TrackedVesselRecord,
    VesselEvidence,
)


DeviceRecord = DeviceAuthRecord


class MemoryDeviceRepository:
    """Repository efêmero para desenvolvimento e testes sem Supabase."""

    def __init__(
        self,
        *,
        devices: Iterable[DeviceAuthRecord] = (),
        snapshots: Iterable[StoredSnapshot] = (),
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._devices = {item.device_id: item for item in devices}
        self._snapshots = {item.device_id: item for item in snapshots}
        self._events_by_id: dict[str, StoredManeuverEvent] = {}
        self._event_ingestion_sequence = 0
        self._tracking_events_by_id: dict[str, StoredVesselTrackingEvent] = {}
        self._tracking_event_ingestion_sequence = 0
        self._mobile_installations: dict[UUID, MobileInstallationRecord] = {}
        self._tracked_vessels: dict[UUID, TrackedVesselRecord] = {}
        self._push_installations: dict[object, PushInstallation] = {}
        self._push_deliveries: dict[tuple[str, object], PushDelivery] = {}
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._lock = Lock()

    def create_device(self, record: DeviceAuthRecord) -> None:
        if record.device_id in self._devices:
            raise DeviceAlreadyExistsError(record.device_id)
        self._devices[record.device_id] = record

    def put_device(self, record: DeviceAuthRecord) -> None:
        self._devices[record.device_id] = record

    def get_device_auth(self, device_id: str) -> DeviceAuthRecord | None:
        return self._devices.get(device_id)

    def ensure_mobile_installation(
        self,
        device_id: str,
        installation_id: UUID,
    ) -> MobileInstallationRecord | None:
        with self._lock:
            if device_id not in self._devices:
                return None
            now = self._clock()
            current = self._mobile_installations.get(installation_id)
            if current is not None and current.device_id != device_id:
                return None
            if current is None:
                current = MobileInstallationRecord(
                    installation_id=installation_id,
                    device_id=device_id,
                    active=True,
                    created_at=now,
                    last_seen_at=now,
                    revoked_at=None,
                )
            else:
                current = replace(
                    current,
                    active=True,
                    last_seen_at=now,
                    revoked_at=None,
                )
            self._mobile_installations[installation_id] = current
            return current

    def get_mobile_installation(
        self,
        device_id: str,
        installation_id: UUID,
    ) -> MobileInstallationRecord | None:
        current = self._mobile_installations.get(installation_id)
        if current is None or current.device_id != device_id:
            return None
        return current

    def revoke_mobile_installation(
        self,
        device_id: str,
        installation_id: UUID,
    ) -> bool:
        with self._lock:
            current = self._mobile_installations.get(installation_id)
            if current is None or current.device_id != device_id:
                return False
            now = self._clock()
            self._mobile_installations[installation_id] = replace(
                current,
                active=False,
                last_seen_at=now,
                revoked_at=now,
            )
            for tracked_id, tracked in tuple(self._tracked_vessels.items()):
                if tracked.installation_id != installation_id or not tracked.active:
                    continue
                self._tracked_vessels[tracked_id] = replace(
                    tracked,
                    active=False,
                    stopped_at=now,
                )
            return True

    def get_snapshot(self, device_id: str) -> StoredSnapshot | None:
        return self._snapshots.get(device_id)

    def put_snapshot(self, snapshot: StoredSnapshot) -> None:
        self._snapshots[snapshot.device_id] = snapshot

    def rotate_view_secret_hash(
        self,
        device_id: str,
        view_secret_hash: str,
    ) -> bool:
        with self._lock:
            current = self._devices.get(device_id)
            if current is None:
                return False
            self._devices[device_id] = replace(
                current,
                view_secret_hash=view_secret_hash,
            )
            now = self._clock()
            for installation_id, installation in tuple(
                self._mobile_installations.items()
            ):
                if installation.device_id != device_id:
                    continue
                self._mobile_installations[installation_id] = replace(
                    installation,
                    active=False,
                    last_seen_at=now,
                    revoked_at=now,
                )
            for tracked_id, tracked in tuple(
                self._tracked_vessels.items()
            ):
                if tracked.device_id != device_id or not tracked.active:
                    continue
                self._tracked_vessels[tracked_id] = replace(
                    tracked,
                    active=False,
                    stopped_at=now,
                )
            for installation_id, installation in tuple(
                self._push_installations.items()
            ):
                if installation.device_id != device_id:
                    continue
                self._push_installations[installation_id] = replace(
                    installation,
                    endpoint=None,
                    p256dh=None,
                    auth=None,
                    active=False,
                    last_seen_at=now,
                    updated_at=now,
                )
            return True

    def accept_snapshot_atomic(
        self,
        candidate: SnapshotCandidate,
    ) -> AcceptSnapshotResult:
        with self._lock:
            if candidate.device_id not in self._devices:
                return AcceptSnapshotResult(
                    status=AcceptSnapshotStatus.DEVICE_NOT_FOUND,
                )

            current = self._snapshots.get(candidate.device_id)
            if current is not None and current.boot_id == candidate.boot_id:
                if candidate.sequence < current.sequence:
                    return AcceptSnapshotResult(
                        status=AcceptSnapshotStatus.OUT_OF_ORDER,
                        received_at=current.received_at,
                    )
                if candidate.sequence == current.sequence:
                    if current.snapshot == candidate.snapshot:
                        return AcceptSnapshotResult(
                            status=AcceptSnapshotStatus.IDEMPOTENT,
                            received_at=current.received_at,
                        )
                    return AcceptSnapshotResult(
                        status=AcceptSnapshotStatus.SEQUENCE_REUSE_MISMATCH,
                        received_at=current.received_at,
                    )

            received_at = self._clock()
            self._snapshots[candidate.device_id] = StoredSnapshot(
                device_id=candidate.device_id,
                snapshot=candidate.snapshot,
                snapshot_schema_version=candidate.snapshot_schema_version,
                boot_id=candidate.boot_id,
                sequence=candidate.sequence,
                generated_at=candidate.generated_at,
                received_at=received_at,
            )
            return AcceptSnapshotResult(
                status=AcceptSnapshotStatus.ACCEPTED,
                received_at=received_at,
            )

    def accept_maneuver_event_atomic(
        self,
        device_id: str,
        event: ManeuverEventIn,
    ) -> AcceptEventResult:
        with self._lock:
            if device_id not in self._devices:
                return AcceptEventResult(AcceptEventStatus.DEVICE_NOT_FOUND)

            event_id = str(event.event_id)
            existing = self._events_by_id.get(event_id)
            if existing is not None:
                same = (
                    existing.device_id == device_id
                    and existing.event.canonical_payload()
                    == event.canonical_payload()
                )
                return AcceptEventResult(
                    AcceptEventStatus.IDEMPOTENT
                    if same
                    else AcceptEventStatus.PAYLOAD_MISMATCH,
                    existing,
                )

            self._event_ingestion_sequence += 1
            stored = StoredManeuverEvent(
                ingestion_id=self._event_ingestion_sequence,
                device_id=device_id,
                event=event,
                ingested_at=self._clock(),
            )
            self._events_by_id[event_id] = stored
            return AcceptEventResult(AcceptEventStatus.ACCEPTED, stored)

    @staticmethod
    def _normalized_vessel_name(value: str) -> str:
        return " ".join(value.upper().split())

    @classmethod
    def _same_vessel(
        cls,
        requested_imo: str | None,
        requested_name: str,
        candidate_imo: str | None,
        candidate_name: str,
    ) -> bool:
        if requested_imo:
            return (
                candidate_imo is not None
                and candidate_imo.strip() == requested_imo.strip()
            )
        return cls._normalized_vessel_name(candidate_name) == (
            cls._normalized_vessel_name(requested_name)
        )

    def find_vessel_evidence(
        self,
        device_id: str,
        *,
        vessel_identity: str,
        vessel_imo: str | None,
        vessel_name: str,
    ) -> VesselEvidence | None:
        snapshot = self._snapshots.get(device_id)
        if snapshot is not None:
            vessels = snapshot.snapshot.get("vessels", [])
            if isinstance(vessels, list):
                for raw in vessels:
                    if not isinstance(raw, dict):
                        continue
                    name = str(raw.get("name", ""))
                    imo = raw.get("imo")
                    candidate_imo = None if imo is None else str(imo)
                    if not self._same_vessel(
                        vessel_imo, vessel_name, candidate_imo, name
                    ):
                        continue
                    identity = (
                        f"IMO:{candidate_imo}"
                        if candidate_imo
                        else f"NAME:{self._normalized_vessel_name(name)}"
                    )
                    return VesselEvidence(
                        vessel_identity=identity,
                        vessel_imo=candidate_imo,
                        vessel_name=name,
                        current={
                            "present": True,
                            "status": raw.get("status"),
                            "section": raw.get("section"),
                            "berth": raw.get("berth"),
                            "side": raw.get("side"),
                            "eta": raw.get("eta"),
                            "etb_ets": raw.get("etb_ets"),
                            "pob": raw.get("pob"),
                            "pob_at": None,
                        },
                        observed_at=snapshot.generated_at,
                    )

        tracking = sorted(
            (
                item
                for item in self._tracking_events_by_id.values()
                if item.device_id == device_id
                and self._same_vessel(
                    vessel_imo,
                    vessel_name,
                    item.event.vessel_imo,
                    item.event.vessel_name,
                )
            ),
            key=lambda item: item.ingestion_id,
            reverse=True,
        )
        if tracking:
            item = tracking[0]
            return VesselEvidence(
                vessel_identity=item.event.vessel_identity,
                vessel_imo=item.event.vessel_imo,
                vessel_name=item.event.vessel_name,
                current=item.event.current.model_dump(mode="json"),
                observed_at=item.event.occurred_at,
            )

        maneuvers = sorted(
            (
                item
                for item in self._events_by_id.values()
                if item.device_id == device_id
                and self._same_vessel(
                    vessel_imo,
                    vessel_name,
                    item.event.vessel_imo,
                    item.event.vessel_name,
                )
            ),
            key=lambda item: item.ingestion_id,
            reverse=True,
        )
        if maneuvers:
            item = maneuvers[0]
            event = item.event
            return VesselEvidence(
                vessel_identity=event.vessel_identity,
                vessel_imo=event.vessel_imo,
                vessel_name=event.vessel_name,
                current={
                    "present": None,
                    "status": None,
                    "section": None,
                    "berth": event.berth,
                    "side": None,
                    "eta": None,
                    "etb_ets": None,
                    "pob": event.pob,
                    "pob_at": (
                        None
                        if event.pob_at is None
                        else event.pob_at.isoformat()
                    ),
                },
                observed_at=event.occurred_at,
            )
        return None

    def upsert_tracked_vessel(
        self,
        device_id: str,
        installation_id: UUID,
        evidence: VesselEvidence,
    ) -> TrackedVesselRecord | None:
        with self._lock:
            installation = self._mobile_installations.get(installation_id)
            if (
                installation is None
                or installation.device_id != device_id
                or not installation.active
            ):
                return None
            existing = None
            for item in self._tracked_vessels.values():
                if (
                    item.device_id != device_id
                    or item.installation_id != installation_id
                ):
                    continue
                if item.vessel_identity == evidence.vessel_identity:
                    existing = item
                    break
                if (
                    evidence.vessel_imo
                    and item.vessel_imo is None
                    and self._normalized_vessel_name(item.vessel_name)
                    == self._normalized_vessel_name(evidence.vessel_name)
                ):
                    existing = item
                    break
            now = self._clock()
            if existing is None:
                record = TrackedVesselRecord(
                    tracked_vessel_id=uuid4(),
                    device_id=device_id,
                    installation_id=installation_id,
                    vessel_identity=evidence.vessel_identity,
                    vessel_imo=evidence.vessel_imo,
                    vessel_name=evidence.vessel_name,
                    started_at=now,
                    active=True,
                    stopped_at=None,
                    last_seen_at=evidence.observed_at,
                    current=evidence.current,
                )
            else:
                record = replace(
                    existing,
                    vessel_identity=evidence.vessel_identity,
                    vessel_imo=evidence.vessel_imo,
                    vessel_name=evidence.vessel_name,
                    started_at=(
                        existing.started_at if existing.active else now
                    ),
                    active=True,
                    stopped_at=None,
                    last_seen_at=evidence.observed_at,
                    current=evidence.current,
                )
            self._tracked_vessels[record.tracked_vessel_id] = record
            return record

    def list_tracked_vessels(
        self,
        device_id: str,
        installation_id: UUID,
    ) -> tuple[TrackedVesselRecord, ...]:
        with self._lock:
            return tuple(sorted(
                (
                    item for item in self._tracked_vessels.values()
                    if item.device_id == device_id
                    and item.installation_id == installation_id
                    and item.active
                ),
                key=lambda item: item.started_at,
            ))

    def get_tracked_vessel(
        self,
        device_id: str,
        installation_id: UUID,
        tracked_vessel_id: UUID,
    ) -> TrackedVesselRecord | None:
        with self._lock:
            item = self._tracked_vessels.get(tracked_vessel_id)
            if (
                item is None
                or item.device_id != device_id
                or item.installation_id != installation_id
            ):
                return None
            return item

    def deactivate_tracked_vessel(
        self,
        device_id: str,
        installation_id: UUID,
        tracked_vessel_id: UUID,
    ) -> TrackedVesselRecord | None:
        with self._lock:
            item = self._tracked_vessels.get(tracked_vessel_id)
            if (
                item is None
                or item.device_id != device_id
                or item.installation_id != installation_id
            ):
                return None
            if item.active:
                item = replace(
                    item,
                    active=False,
                    stopped_at=self._clock(),
                )
                self._tracked_vessels[tracked_vessel_id] = item
            return item

    def accept_vessel_tracking_event_atomic(
        self,
        device_id: str,
        event: VesselTrackingEventIn,
    ) -> AcceptTrackingEventResult:
        with self._lock:
            if device_id not in self._devices:
                return AcceptTrackingEventResult(
                    AcceptTrackingEventStatus.DEVICE_NOT_FOUND
                )

            event_id = str(event.event_id)
            existing = self._tracking_events_by_id.get(event_id)
            if existing is not None:
                same = (
                    existing.device_id == device_id
                    and existing.event.canonical_payload()
                    == event.canonical_payload()
                )
                return AcceptTrackingEventResult(
                    AcceptTrackingEventStatus.IDEMPOTENT
                    if same
                    else AcceptTrackingEventStatus.PAYLOAD_MISMATCH,
                    existing,
                )

            self._tracking_event_ingestion_sequence += 1
            stored = StoredVesselTrackingEvent(
                ingestion_id=self._tracking_event_ingestion_sequence,
                device_id=device_id,
                event=event,
                ingested_at=self._clock(),
            )
            self._tracking_events_by_id[event_id] = stored
            return AcceptTrackingEventResult(
                AcceptTrackingEventStatus.ACCEPTED,
                stored,
            )

    def list_maneuver_events(
        self,
        device_id: str,
        *,
        after: int | None = None,
        before: int | None = None,
        limit: int = 50,
    ) -> EventPage:
        if after is not None and before is not None:
            raise ValueError("after e before são mutuamente exclusivos")
        if not 1 <= limit <= 100:
            raise ValueError("limit deve estar entre 1 e 100")

        with self._lock:
            items = sorted(
                (
                    item
                    for item in self._events_by_id.values()
                    if item.device_id == device_id
                ),
                key=lambda item: item.ingestion_id,
            )

        if after is not None:
            selected = [item for item in items if item.ingestion_id > after][:limit]
            has_more_before = False
        else:
            eligible = (
                [item for item in items if item.ingestion_id < before]
                if before is not None
                else items
            )
            has_more_before = len(eligible) > limit
            selected = eligible[-limit:]

        if not selected:
            return EventPage((), None, None, has_more_before)

        return EventPage(
            events=tuple(selected),
            oldest_cursor=selected[0].ingestion_id,
            newest_cursor=selected[-1].ingestion_id,
            has_more_before=has_more_before,
        )

    def get_maneuver_event_detail(
        self,
        device_id: str,
        event_id: UUID,
    ) -> ManeuverEventDetail | None:
        with self._lock:
            selected = self._events_by_id.get(str(event_id))
            if selected is None or selected.device_id != device_id:
                return None
            maneuver_id = selected.event.maneuver_id
            events = tuple(sorted(
                (
                    item
                    for item in self._events_by_id.values()
                    if item.device_id == device_id
                    and item.event.maneuver_id == maneuver_id
                ),
                key=lambda item: item.ingestion_id,
            ))
        return ManeuverEventDetail(
            selected_event_id=event_id,
            maneuver_id=maneuver_id,
            events=events,
        )

    def upsert_push_installation(
        self,
        device_id,
        installation_id,
        *,
        endpoint: str,
        p256dh: str,
        auth: str,
    ):
        with self._lock:
            if device_id not in self._devices:
                return None
            now = self._clock()
            current = self._push_installations.get(installation_id)
            if current is not None and current.device_id != device_id:
                return None
            if current is None:
                installation = PushInstallation(
                    installation_id=installation_id,
                    device_id=device_id,
                    endpoint=endpoint,
                    p256dh=p256dh,
                    auth=auth,
                    preferences=PushPreferences(),
                    push_enabled_at=now,
                    last_seen_at=now,
                    last_foreground_at=None,
                    active=True,
                    created_at=now,
                    updated_at=now,
                )
            else:
                installation = replace(
                    current,
                    endpoint=endpoint,
                    p256dh=p256dh,
                    auth=auth,
                    push_enabled_at=(
                        current.push_enabled_at if current.active else now
                    ),
                    last_seen_at=now,
                    active=True,
                    updated_at=now,
                )
            self._push_installations[installation_id] = installation
            return installation

    def get_push_installation(
        self,
        device_id,
        installation_id,
    ):
        with self._lock:
            installation = self._push_installations.get(installation_id)
            if installation is None or installation.device_id != device_id:
                return None
            return installation

    def update_push_preferences(
        self,
        device_id,
        installation_id,
        preferences: PushPreferences,
    ):
        with self._lock:
            current = self._push_installations.get(installation_id)
            if current is None or current.device_id != device_id:
                return None
            now = self._clock()
            updated = replace(
                current,
                preferences=preferences,
                last_seen_at=now,
                updated_at=now,
            )
            self._push_installations[installation_id] = updated
            return updated

    def touch_push_foreground(
        self,
        device_id,
        installation_id,
    ):
        with self._lock:
            current = self._push_installations.get(installation_id)
            if (
                current is None
                or current.device_id != device_id
                or not current.active
            ):
                return None
            now = self._clock()
            updated = replace(
                current,
                last_seen_at=now,
                last_foreground_at=now,
                updated_at=now,
            )
            self._push_installations[installation_id] = updated
            return updated

    def deactivate_push_installation(
        self,
        device_id,
        installation_id,
    ) -> bool:
        with self._lock:
            current = self._push_installations.get(installation_id)
            if current is None or current.device_id != device_id:
                return False
            now = self._clock()
            self._push_installations[installation_id] = replace(
                current,
                endpoint=None,
                p256dh=None,
                auth=None,
                active=False,
                last_seen_at=now,
                updated_at=now,
            )
            return True

    def list_active_push_installations(
        self,
        device_id: str,
    ) -> tuple[PushInstallation, ...]:
        with self._lock:
            return tuple(
                installation
                for installation in self._push_installations.values()
                if installation.device_id == device_id
                and installation.active
            )

    def claim_push_delivery(
        self,
        event_id,
        installation_id,
        *,
        lease_seconds: int = 8,
    ) -> bool:
        with self._lock:
            event_key = str(event_id)
            installation = self._push_installations.get(installation_id)
            if (
                event_key not in self._events_by_id
                or installation is None
                or not installation.active
            ):
                return False
            key = (event_key, installation_id)
            now = self._clock()
            current = self._push_deliveries.get(key)
            if current is None:
                self._push_deliveries[key] = PushDelivery(
                    event_id=current_event_id(event_key),
                    installation_id=installation_id,
                    status=PushDeliveryStatus.SENDING,
                    claimed_at=now,
                    updated_at=now,
                )
                return True

            recoverable = (
                current.status is PushDeliveryStatus.RETRY_PENDING
                or (
                    current.status is PushDeliveryStatus.SENDING
                    and (now - current.claimed_at).total_seconds()
                    >= lease_seconds
                )
            )
            if not recoverable:
                return False
            self._push_deliveries[key] = replace(
                current,
                status=PushDeliveryStatus.SENDING,
                claimed_at=now,
                updated_at=now,
            )
            return True

    def set_push_delivery_status(
        self,
        event_id,
        installation_id,
        status: PushDeliveryStatus,
    ) -> None:
        with self._lock:
            event_key = str(event_id)
            key = (event_key, installation_id)
            now = self._clock()
            current = self._push_deliveries.get(key)
            if current is None:
                if (
                    event_key not in self._events_by_id
                    or installation_id not in self._push_installations
                ):
                    return
                self._push_deliveries[key] = PushDelivery(
                    event_id=current_event_id(event_key),
                    installation_id=installation_id,
                    status=status,
                    claimed_at=now,
                    updated_at=now,
                )
                return
            self._push_deliveries[key] = replace(
                current,
                status=status,
                updated_at=now,
            )

    def get_push_delivery(
        self,
        event_id,
        installation_id,
    ):
        with self._lock:
            return self._push_deliveries.get(
                (str(event_id), installation_id)
            )


def current_event_id(value: str):
    from uuid import UUID, uuid4

    return UUID(value)
