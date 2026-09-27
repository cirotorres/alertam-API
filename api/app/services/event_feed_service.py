from __future__ import annotations

from app.core.errors import PersistenceUnavailableApiError
from app.models.maneuver_event import (
    ManeuverEventFeedItem,
    ManeuverEventFeedResponse,
)
from app.repositories.devices import PersistenceUnavailableError
from app.repositories.events import AlertaRepository, StoredManeuverEvent


class EventFeedService:
    def __init__(self, repository: AlertaRepository) -> None:
        self._repository = repository

    def get_page(
        self,
        device_id: str,
        *,
        after: int | None = None,
        before: int | None = None,
        limit: int = 50,
    ) -> ManeuverEventFeedResponse:
        try:
            page = self._repository.list_maneuver_events(
                device_id,
                after=after,
                before=before,
                limit=limit,
            )
        except PersistenceUnavailableError as exc:
            raise PersistenceUnavailableApiError() from exc

        return ManeuverEventFeedResponse(
            events=[self._to_item(item) for item in page.events],
            oldest_cursor=page.oldest_cursor,
            newest_cursor=page.newest_cursor,
            has_more_before=page.has_more_before,
        )

    @staticmethod
    def _to_item(stored: StoredManeuverEvent) -> ManeuverEventFeedItem:
        return ManeuverEventFeedItem.model_validate({
            **stored.event.canonical_payload(),
            "ingestion_id": stored.ingestion_id,
            "ingested_at": stored.ingested_at,
        })
