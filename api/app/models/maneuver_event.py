from __future__ import annotations

from typing import Literal

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    StrictInt,
    model_validator,
)
from uuid import UUID


class ContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class PobChange(ContractModel):
    from_: str | None = Field(alias="from")
    to: str | None


class BerthChange(ContractModel):
    from_: StrictInt | None = Field(alias="from")
    to: StrictInt | None


class ManeuverChanges(ContractModel):
    pob: PobChange | None = None
    berth: BerthChange | None = None

    @model_validator(mode="after")
    def require_changed_field(self) -> "ManeuverChanges":
        if self.pob is None and self.berth is None:
            raise ValueError("UPDATED exige ao menos uma alteração.")
        return self


class ManeuverEventIn(ContractModel):
    event_id: UUID
    maneuver_id: UUID
    vessel_identity: str = Field(min_length=1)
    vessel_imo: str | None
    vessel_name: str = Field(min_length=1)
    maneuver_type: Literal["ATRACACAO", "DESATRACACAO"]
    event_type: Literal["CONFIRMED", "UPDATED", "COMPLETED", "CANCELLED"]
    berth: StrictInt | None
    pob: str | None
    occurred_at: AwareDatetime
    changes: ManeuverChanges | None

    @model_validator(mode="after")
    def validate_changes_for_event_type(self) -> "ManeuverEventIn":
        if self.event_type == "UPDATED":
            if self.changes is None:
                raise ValueError("UPDATED exige changes.")
            return self
        if self.changes is not None:
            raise ValueError("Somente UPDATED aceita changes.")
        return self

    def canonical_payload(self) -> dict[str, object]:
        return self.model_dump(
            mode="json",
            by_alias=True,
            exclude_unset=True,
        )


class ManeuverEventAcceptedResponse(BaseModel):
    ok: Literal[True] = True
    status: Literal["accepted", "idempotent"]
    ingestion_id: int
    received_at: AwareDatetime


class ManeuverEventFeedItem(ManeuverEventIn):
    ingestion_id: int
    ingested_at: AwareDatetime


class ManeuverEventFeedResponse(BaseModel):
    events: list[ManeuverEventFeedItem]
    oldest_cursor: int | None
    newest_cursor: int | None
    has_more_before: bool
