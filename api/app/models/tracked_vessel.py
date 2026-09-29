from __future__ import annotations

from typing import Literal
from uuid import UUID

from app.models.maneuver_event import ManeuverEventIn
from app.models.vessel_tracking_event import VesselTrackingEventIn
from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    StrictBool,
    StrictInt,
    model_validator,
)


class ContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class TrackedVesselCurrent(ContractModel):
    present: StrictBool | None
    status: str | None
    section: str | None
    berth: StrictInt | None
    side: str | None
    eta: str | None
    etb_ets: str | None
    pob: str | None
    pob_at: AwareDatetime | None


class TrackedVesselCreateRequest(ContractModel):
    vessel_identity: str = Field(min_length=1)
    vessel_imo: str | None
    vessel_name: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_identity(self) -> "TrackedVesselCreateRequest":
        if self.vessel_imo is not None:
            expected = f"IMO:{self.vessel_imo.strip()}"
        else:
            normalized = " ".join(self.vessel_name.upper().split())
            expected = f"NAME:{normalized}"
        if self.vessel_identity != expected:
            raise ValueError(
                "vessel_identity não corresponde ao IMO/nome informado."
            )
        return self


class TrackedVesselResponse(ContractModel):
    tracked_vessel_id: UUID
    vessel_identity: str
    vessel_imo: str | None
    vessel_name: str
    started_at: AwareDatetime
    active: StrictBool
    stopped_at: AwareDatetime | None
    last_seen_at: AwareDatetime | None
    current: TrackedVesselCurrent | None


class TrackedTimelineManeuverItem(ContractModel):
    kind: Literal["MANEUVER"] = "MANEUVER"
    ingestion_id: int
    ingested_at: AwareDatetime
    event: ManeuverEventIn


class TrackedTimelineTrackingItem(ContractModel):
    kind: Literal["TRACKING"] = "TRACKING"
    ingestion_id: int
    ingested_at: AwareDatetime
    event: VesselTrackingEventIn


class TrackedVesselTimelineResponse(ContractModel):
    tracked_vessel_id: UUID
    events: list[
        TrackedTimelineManeuverItem | TrackedTimelineTrackingItem
    ]


class TrackingForegroundFeedItem(ContractModel):
    tracked_vessel_id: UUID
    ingestion_id: int
    ingested_at: AwareDatetime
    event: VesselTrackingEventIn


class TrackingForegroundFeedResponse(ContractModel):
    events: list[TrackingForegroundFeedItem]
    newest_cursor: int | None
