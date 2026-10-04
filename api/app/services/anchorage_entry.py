from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID, NAMESPACE_URL, uuid5

from app.models.mobile_snapshot import MobileSnapshot, VesselV1
from app.repositories.devices import StoredSnapshot


@dataclass(frozen=True)
class AnchorageEntryEvent:
    event_id: UUID
    device_id: str
    vessel_identity: str
    vessel_imo: str | None
    vessel_name: str
    previous_section: str | None
    occurred_at: datetime


def _normalize_name(value: str) -> str:
    return " ".join(value.upper().split())


def _identity(vessel: VesselV1) -> str:
    if vessel.imo:
        return f"IMO:{vessel.imo.strip()}"
    return f"NAME:{_normalize_name(vessel.name)}"


def _previous_match(
    vessel: VesselV1,
    previous_vessels: list[dict],
) -> dict | None:
    normalized_name = _normalize_name(vessel.name)
    if vessel.imo:
        for previous in previous_vessels:
            if previous.get("imo") == vessel.imo:
                return previous
        for previous in previous_vessels:
            if (
                not previous.get("imo")
                and _normalize_name(str(previous.get("name", "")))
                == normalized_name
            ):
                return previous
        return None

    for previous in previous_vessels:
        if _normalize_name(str(previous.get("name", ""))) == normalized_name:
            return previous
    return None


def detect_anchorage_entries(
    device_id: str,
    previous: StoredSnapshot | None,
    current: MobileSnapshot,
) -> tuple[AnchorageEntryEvent, ...]:
    # The first accepted snapshot is a baseline. Existing anchored vessels
    # must not generate a notification burst when this feature starts.
    if previous is None:
        return ()

    previous_vessels = list(previous.snapshot.get("vessels", []))
    entries: list[AnchorageEntryEvent] = []
    for vessel in current.vessels:
        if vessel.section != "FUNDEADO":
            continue

        matched = _previous_match(vessel, previous_vessels)
        previous_section = (
            None if matched is None else str(matched.get("section"))
        )
        if previous_section == "FUNDEADO":
            continue

        identity = _identity(vessel)
        event_id = uuid5(
            NAMESPACE_URL,
            (
                "alertam:anchorage:"
                f"{device_id}:{current.boot_id}:{current.sequence}:{identity}"
            ),
        )
        entries.append(
            AnchorageEntryEvent(
                event_id=event_id,
                device_id=device_id,
                vessel_identity=identity,
                vessel_imo=vessel.imo,
                vessel_name=vessel.name,
                previous_section=previous_section,
                occurred_at=current.generated_at,
            )
        )
    return tuple(entries)
