from __future__ import annotations

from uuid import UUID

from app.core.errors import TrackedVesselNotFoundError
from app.models.maneuver_event import ManeuverEventIn
from app.models.tracked_vessel import (
    TrackingForegroundFeedItem,
    TrackingForegroundFeedResponse,
    TrackedTimelineManeuverItem,
    TrackedTimelineTrackingItem,
    TrackedVesselTimelineResponse,
)
from app.models.vessel_tracking_event import VesselTrackingEventIn
from app.repositories.events import AlertaRepository
from app.services.mobile_session_service import MobileSessionPrincipal


class TrackedVesselTimelineService:
    def __init__(self, repository: AlertaRepository) -> None:
        self._repository = repository

    def get_timeline(
        self,
        principal: MobileSessionPrincipal,
        tracked_vessel_id: UUID,
    ) -> TrackedVesselTimelineResponse:
        tracked = self._repository.get_tracked_vessel(
            principal.device_id,
            principal.installation_id,
            tracked_vessel_id,
        )
        if tracked is None:
            raise TrackedVesselNotFoundError()

        records = self._repository.list_tracked_vessel_event_records(
            principal.device_id,
            principal.installation_id,
            tracked_vessel_id,
        )
        ordered = sorted(
            records,
            key=lambda item: (
                item.event.occurred_at,
                item.ingested_at,
                str(item.event.event_id),
            ),
        )
        events = []
        for record in ordered:
            if record.kind == "MANEUVER":
                event = record.event
                if not isinstance(event, ManeuverEventIn):
                    continue
                events.append(TrackedTimelineManeuverItem(
                    ingestion_id=record.ingestion_id,
                    ingested_at=record.ingested_at,
                    event=event,
                ))
            else:
                event = record.event
                if not isinstance(event, VesselTrackingEventIn):
                    continue
                events.append(TrackedTimelineTrackingItem(
                    ingestion_id=record.ingestion_id,
                    ingested_at=record.ingested_at,
                    event=event,
                ))
        return TrackedVesselTimelineResponse(
            tracked_vessel_id=tracked_vessel_id,
            events=events,
        )

    def get_foreground_feed(
        self,
        principal: MobileSessionPrincipal,
        *,
        after: int | None,
        limit: int,
    ) -> TrackingForegroundFeedResponse:
        if after is None:
            return TrackingForegroundFeedResponse(
                events=[],
                newest_cursor=(
                    self._repository.latest_tracking_event_cursor(
                        principal.device_id
                    )
                    or 0
                ),
            )

        records = self._repository.list_installation_tracking_events(
            principal.device_id,
            principal.installation_id,
            after=after,
            limit=limit,
        )
        if records and len(records) >= limit:
            cursor = max(after, records[-1].stored.ingestion_id)
        else:
            newest = self._repository.latest_tracking_event_cursor(
                principal.device_id
            )
            cursor = max(
                after,
                0 if newest is None else newest,
            )
        return TrackingForegroundFeedResponse(
            events=[
                TrackingForegroundFeedItem(
                    tracked_vessel_id=item.tracked_vessel_id,
                    ingestion_id=item.stored.ingestion_id,
                    ingested_at=item.stored.ingested_at,
                    event=item.stored.event,
                )
                for item in records
            ],
            newest_cursor=cursor,
        )
