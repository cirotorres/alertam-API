from __future__ import annotations

from uuid import UUID

from app.core.errors import (
    ManeuverEventNotFoundError,
    PersistenceUnavailableApiError,
)
from app.models.maneuver_event import (
    ManeuverEventDetailResponse,
    ManeuverEventFeedItem,
)
from app.repositories.devices import PersistenceUnavailableError
from app.repositories.events import AlertaRepository, StoredManeuverEvent


class EventDetailService:
    def __init__(self, repository: AlertaRepository) -> None:
        self._repository = repository

    def get_detail(
        self,
        device_id: str,
        event_id: UUID,
    ) -> ManeuverEventDetailResponse:
        try:
            detail = self._repository.get_maneuver_event_detail(
                device_id,
                event_id,
            )
        except PersistenceUnavailableError as exc:
            raise PersistenceUnavailableApiError() from exc

        if detail is None:
            raise ManeuverEventNotFoundError()

        return ManeuverEventDetailResponse(
            selected_event_id=detail.selected_event_id,
            maneuver_id=detail.maneuver_id,
            events=[self._to_item(item) for item in detail.events],
        )

    @staticmethod
    def _to_item(
        stored: StoredManeuverEvent,
    ) -> ManeuverEventFeedItem:
        return ManeuverEventFeedItem.model_validate({
            **stored.event.canonical_payload(),
            "ingestion_id": stored.ingestion_id,
            "ingested_at": stored.ingested_at,
        })
