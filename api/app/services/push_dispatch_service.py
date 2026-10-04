from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone
from typing import Protocol

from app.infrastructure.web_push import (
    PermanentPushError,
    TransientPushError,
)
from app.models.maneuver_event import ManeuverEventIn
from app.repositories.events import (
    AlertaRepository,
    PushDeliveryStatus,
    PushInstallation,
    PushPreferences,
    StoredManeuverEvent,
)
from app.repositories.tracking import TrackedVesselRecord
from app.services.anchorage_entry import AnchorageEntryEvent


class PushGateway(Protocol):
    def send(
        self,
        installation: PushInstallation,
        payload: dict[str, str],
    ) -> None: ...


_TERMINAL_DELIVERY_STATUSES = {
    PushDeliveryStatus.DELIVERED,
    PushDeliveryStatus.IGNORED_PREFERENCE,
    PushDeliveryStatus.IGNORED_FOREGROUND,
    PushDeliveryStatus.IGNORED_BEFORE_OPT_IN,
    PushDeliveryStatus.PERMANENT_FAILURE,
}


class AnchoragePushDispatchService:
    def __init__(
        self,
        repository: AlertaRepository,
        gateway: PushGateway,
        *,
        foreground_fresh_seconds: int = 75,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._repository = repository
        self._gateway = gateway
        self._foreground_fresh_seconds = foreground_fresh_seconds
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def dispatch_event(self, event: AnchorageEntryEvent) -> None:
        installations = self._repository.list_active_push_installations(
            event.device_id
        )
        for installation in installations:
            if event.occurred_at < installation.push_enabled_at:
                continue
            if not installation.preferences.anchored:
                continue
            if installation.last_foreground_at is not None:
                age = (
                    self._clock() - installation.last_foreground_at
                ).total_seconds()
                if age <= self._foreground_fresh_seconds:
                    continue
            try:
                self._gateway.send(
                    installation,
                    build_anchorage_push_message(event),
                )
            except PermanentPushError:
                self._repository.deactivate_push_installation(
                    event.device_id,
                    installation.installation_id,
                )
            except TransientPushError:
                continue


def build_anchorage_push_message(
    event: AnchorageEntryEvent,
) -> dict[str, str]:
    return {
        "event_id": str(event.event_id),
        "title": "Entrada no fundeio",
        "body": f"{event.vessel_name} · Fundeado",
        "url": "/",
    }


class PushDispatchService:
    def __init__(
        self,
        repository: AlertaRepository,
        gateway: PushGateway,
        *,
        foreground_fresh_seconds: int = 75,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._repository = repository
        self._gateway = gateway
        self._foreground_fresh_seconds = foreground_fresh_seconds
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def dispatch_event(self, stored: StoredManeuverEvent) -> None:
        installations = self._repository.list_active_push_installations(
            stored.device_id
        )
        for installation in installations:
            self._dispatch_installation(stored, installation)

    def _dispatch_installation(
        self,
        stored: StoredManeuverEvent,
        installation: PushInstallation,
    ) -> None:
        event_id = stored.event.event_id
        existing = self._repository.get_push_delivery(
            event_id,
            installation.installation_id,
        )
        if (
            existing is not None
            and existing.status in _TERMINAL_DELIVERY_STATUSES
        ):
            return

        ignored_status, tracked = self._eligibility(
            stored,
            installation,
        )

        if (
            existing is not None
            and existing.status is PushDeliveryStatus.SENDING
        ):
            claimed = self._repository.claim_push_delivery(
                event_id,
                installation.installation_id,
            )
            if not claimed:
                return
            if ignored_status is not None:
                self._repository.set_push_delivery_status(
                    event_id,
                    installation.installation_id,
                    ignored_status,
                )
                return
            self._send_claimed(stored, installation, tracked)
            return

        if ignored_status is not None:
            self._repository.set_push_delivery_status(
                event_id,
                installation.installation_id,
                ignored_status,
            )
            return

        claimed = self._repository.claim_push_delivery(
            event_id,
            installation.installation_id,
        )
        if not claimed:
            return
        self._send_claimed(stored, installation, tracked)

    def _eligibility(
        self,
        stored: StoredManeuverEvent,
        installation: PushInstallation,
    ) -> tuple[PushDeliveryStatus | None, TrackedVesselRecord | None]:
        event = stored.event
        if event.occurred_at < installation.push_enabled_at:
            return PushDeliveryStatus.IGNORED_BEFORE_OPT_IN, None

        general_enabled = _preference_enabled(
            installation.preferences,
            event.event_type,
        )
        tracked = None
        if not general_enabled:
            tracked = self._repository.find_active_tracked_vessel_for_event(
                stored.device_id,
                installation.installation_id,
                vessel_identity=event.vessel_identity,
                vessel_imo=event.vessel_imo,
                vessel_name=event.vessel_name,
                occurred_at=event.occurred_at,
            )
            if tracked is None:
                return PushDeliveryStatus.IGNORED_PREFERENCE, None

        if installation.last_foreground_at is not None:
            age = (
                self._clock() - installation.last_foreground_at
            ).total_seconds()
            if age <= self._foreground_fresh_seconds:
                return PushDeliveryStatus.IGNORED_FOREGROUND, tracked

        if general_enabled:
            return None, None
        return None, tracked

    def _send_claimed(
        self,
        stored: StoredManeuverEvent,
        installation: PushInstallation,
        tracked: TrackedVesselRecord | None,
    ) -> None:
        event_id = stored.event.event_id
        try:
            payload = build_push_message(stored.event)
            if tracked is not None:
                payload["url"] = (
                    f"/acompanhados?track={tracked.tracked_vessel_id}"
                    f"&event={stored.event.event_id}"
                )
            self._gateway.send(installation, payload)
        except PermanentPushError:
            self._repository.deactivate_push_installation(
                stored.device_id,
                installation.installation_id,
            )
            self._repository.set_push_delivery_status(
                event_id,
                installation.installation_id,
                PushDeliveryStatus.PERMANENT_FAILURE,
            )
            return
        except TransientPushError:
            self._repository.set_push_delivery_status(
                event_id,
                installation.installation_id,
                PushDeliveryStatus.RETRY_PENDING,
            )
            return

        self._repository.set_push_delivery_status(
            event_id,
            installation.installation_id,
            PushDeliveryStatus.DELIVERED,
        )


def _preference_enabled(
    preferences: PushPreferences,
    event_type: str,
) -> bool:
    return {
        "CONFIRMED": preferences.confirmed,
        "UPDATED": preferences.updated,
        "COMPLETED": preferences.completed,
        "CANCELLED": preferences.cancelled,
    }[event_type]


def build_push_message(event: ManeuverEventIn) -> dict[str, str]:
    maneuver = (
        "Atracação"
        if event.maneuver_type == "ATRACACAO"
        else "Desatracação"
    )
    suffix = {
        "CONFIRMED": "confirmada",
        "UPDATED": "atualizada",
        "COMPLETED": "concluída",
        "CANCELLED": "cancelada",
    }[event.event_type]

    body_parts = [event.vessel_name]
    if event.event_type == "UPDATED" and event.changes is not None:
        if event.changes.berth is not None:
            body_parts.append(
                "Berço "
                f"{_display(event.changes.berth.from_)}"
                f" → {_display(event.changes.berth.to)}"
            )
        elif event.berth is not None:
            body_parts.append(f"Berço {event.berth}")

        if event.changes.pob is not None:
            body_parts.append(
                "POB "
                f"{_display(event.changes.pob.from_)}"
                f" → {_display(event.changes.pob.to)}"
            )
        elif event.pob:
            body_parts.append(f"POB {event.pob}")
    else:
        if event.berth is not None:
            body_parts.append(f"Berço {event.berth}")
        if event.pob:
            body_parts.append(f"POB {event.pob}")

    return {
        "event_id": str(event.event_id),
        "title": f"{maneuver} {suffix}",
        "body": " · ".join(body_parts),
        "url": f"/alertas?event={event.event_id}",
    }


def _display(value: object | None) -> str:
    return "—" if value is None else str(value)
