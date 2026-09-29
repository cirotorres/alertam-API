from __future__ import annotations

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
