from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone

from app.infrastructure.web_push import PermanentPushError, TransientPushError
from app.repositories.events import AlertaRepository, PushInstallation
from app.repositories.tracking import (
    StoredVesselTrackingEvent,
    TrackedVesselRecord,
    TrackingPushDeliveryStatus,
)
from app.services.push_dispatch_service import PushGateway


_TERMINAL_STATUSES = {
    TrackingPushDeliveryStatus.DELIVERED,
    TrackingPushDeliveryStatus.IGNORED_FOREGROUND,
    TrackingPushDeliveryStatus.IGNORED_BEFORE_TRACKING,
    TrackingPushDeliveryStatus.PERMANENT_FAILURE,
}


class TrackingPushDispatchService:
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

    def dispatch_event(self, stored: StoredVesselTrackingEvent) -> None:
        installations = self._repository.list_active_push_installations(
            stored.device_id
        )
        for installation in installations:
            tracked = self._matching_tracking(stored, installation)
            if tracked is None:
                continue
            self._dispatch_installation(stored, installation, tracked)

    def _matching_tracking(
        self,
        stored: StoredVesselTrackingEvent,
        installation: PushInstallation,
    ) -> TrackedVesselRecord | None:
        event = stored.event
        for tracked in self._repository.list_tracked_vessels(
            stored.device_id,
            installation.installation_id,
        ):
            if _matches(
                tracked,
                vessel_identity=event.vessel_identity,
                vessel_imo=event.vessel_imo,
                vessel_name=event.vessel_name,
            ):
                return tracked
        return None

    def _dispatch_installation(
        self,
        stored: StoredVesselTrackingEvent,
        installation: PushInstallation,
        tracked: TrackedVesselRecord,
    ) -> None:
        event = stored.event
        event_id = event.event_id
        existing = self._repository.get_tracking_push_delivery(
            event_id,
            installation.installation_id,
        )
        if (
            existing is not None
            and existing.status in _TERMINAL_STATUSES
        ):
            return

        if event.occurred_at < tracked.started_at:
            self._repository.set_tracking_push_delivery_status(
                event_id,
                installation.installation_id,
                TrackingPushDeliveryStatus.IGNORED_BEFORE_TRACKING,
            )
            return

        # Push reativado depois do fato não deve criar replay. O tracking
        # continua salvo, mas esse evento já é anterior ao novo opt-in.
        if event.occurred_at < installation.push_enabled_at:
            return

        if installation.last_foreground_at is not None:
            age = (
                self._clock() - installation.last_foreground_at
            ).total_seconds()
            if age <= self._foreground_fresh_seconds:
                self._repository.set_tracking_push_delivery_status(
                    event_id,
                    installation.installation_id,
                    TrackingPushDeliveryStatus.IGNORED_FOREGROUND,
                )
                return

        if (
            existing is not None
            and existing.status is TrackingPushDeliveryStatus.SENDING
        ):
            claimed = self._repository.claim_tracking_push_delivery(
                event_id,
                installation.installation_id,
            )
            if not claimed:
                return
            self._send_claimed(stored, installation, tracked)
            return

        claimed = self._repository.claim_tracking_push_delivery(
            event_id,
            installation.installation_id,
        )
        if not claimed:
            return
        self._send_claimed(stored, installation, tracked)

    def _send_claimed(
        self,
        stored: StoredVesselTrackingEvent,
        installation: PushInstallation,
        tracked: TrackedVesselRecord,
    ) -> None:
        event_id = stored.event.event_id
        try:
            self._gateway.send(
                installation,
                build_tracking_push_message(
                    stored.event,
                    tracked.tracked_vessel_id,
                ),
            )
        except PermanentPushError:
            self._repository.deactivate_push_installation(
                stored.device_id,
                installation.installation_id,
            )
            self._repository.set_tracking_push_delivery_status(
                event_id,
                installation.installation_id,
                TrackingPushDeliveryStatus.PERMANENT_FAILURE,
            )
            return
        except TransientPushError:
            self._repository.set_tracking_push_delivery_status(
                event_id,
                installation.installation_id,
                TrackingPushDeliveryStatus.RETRY_PENDING,
            )
            return

        self._repository.set_tracking_push_delivery_status(
            event_id,
            installation.installation_id,
            TrackingPushDeliveryStatus.DELIVERED,
        )


def _matches(
    tracked: TrackedVesselRecord,
    *,
    vessel_identity: str,
    vessel_imo: str | None,
    vessel_name: str,
) -> bool:
    if tracked.vessel_identity == vessel_identity:
        return True
    if vessel_imo is not None:
        if tracked.vessel_imo == vessel_imo:
            return True
        if (
            tracked.vessel_imo is None
            and _normalize_name(tracked.vessel_name)
            == _normalize_name(vessel_name)
        ):
            return True
        return False
    return (
        tracked.vessel_imo is None
        and _normalize_name(tracked.vessel_name)
        == _normalize_name(vessel_name)
    )


def _normalize_name(value: str) -> str:
    return " ".join(value.upper().split())


def build_tracking_push_message(
    event,
    tracked_vessel_id,
) -> dict[str, str]:
    title = f"{event.vessel_name} · Acompanhamento"
    changes = event.changes

    if changes.presence is not None:
        if changes.presence.to is False:
            body = "Navio não aparece mais na planilha."
        else:
            body = "Navio voltou a aparecer na planilha."
    else:
        parts: list[str] = []
        for label, change in (
            ("Status", changes.status),
            ("Berço", changes.berth),
            ("Bordo", changes.side),
            ("ETA", changes.eta),
            ("ETB/ETS", changes.etb_ets),
            ("POB", changes.pob),
        ):
            if change is None:
                continue
            parts.append(
                f"{label} {_display(change.from_)} → {_display(change.to)}"
            )
        body = " · ".join(parts) if parts else "Atualização observada no AlertaM."

    return {
        "event_id": str(event.event_id),
        "title": title,
        "body": body,
        "url": (
            f"/acompanhados?track={tracked_vessel_id}"
            f"&event={event.event_id}"
        ),
    }


def _display(value: object | None) -> str:
    return "—" if value is None else str(value)
