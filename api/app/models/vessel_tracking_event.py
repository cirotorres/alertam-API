from __future__ import annotations

from typing import Literal
from uuid import UUID

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
    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class StringChange(ContractModel):
    from_: str | None = Field(alias="from")
    to: str | None


class IntegerChange(ContractModel):
    from_: StrictInt | None = Field(alias="from")
    to: StrictInt | None


class BooleanChange(ContractModel):
    from_: StrictBool = Field(alias="from")
    to: StrictBool


class VesselTrackingChanges(ContractModel):
    presence: BooleanChange | None = None
    status: StringChange | None = None
    section: StringChange | None = None
    berth: IntegerChange | None = None
    side: StringChange | None = None
    eta: StringChange | None = None
    etb_ets: StringChange | None = None
    pob: StringChange | None = None

    @model_validator(mode="after")
    def require_changed_field(self) -> "VesselTrackingChanges":
        if not any(
            getattr(self, field) is not None
            for field in (
                "presence",
                "status",
                "section",
                "berth",
                "side",
                "eta",
                "etb_ets",
                "pob",
            )
        ):
            raise ValueError("VesselTrackingEvent exige ao menos uma alteração.")
        return self


class VesselTrackingCurrent(ContractModel):
    present: StrictBool
    status: str | None
    section: str | None
    berth: StrictInt | None
    side: str | None
    eta: str | None
    etb_ets: str | None
    pob: str | None
    pob_at: AwareDatetime | None


class VesselTrackingEventIn(ContractModel):
    event_id: UUID
    vessel_identity: str = Field(min_length=1)
    vessel_imo: str | None
    vessel_name: str = Field(min_length=1)
    occurred_at: AwareDatetime
    first_observed_at: AwareDatetime | None
    maneuver_id: UUID | None
    changes: VesselTrackingChanges
    current: VesselTrackingCurrent

    def canonical_payload(self) -> dict[str, object]:
        return self.model_dump(
            mode="json",
            by_alias=True,
            exclude_unset=True,
        )


class VesselTrackingEventAcceptedResponse(BaseModel):
    ok: Literal[True] = True
    status: Literal["accepted", "idempotent"]
    ingestion_id: int
    received_at: AwareDatetime
