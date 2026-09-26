from __future__ import annotations

from typing import Annotated, Literal, TypeAlias
from uuid import UUID

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    StrictFloat,
    StrictInt,
    model_validator,
)


Number: TypeAlias = StrictFloat | StrictInt | None
PositiveStrictInt = Annotated[StrictInt, Field(gt=0)]


class ContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CollectorV1(ContractModel):
    status: Literal["monitoring"]
    last_collection_at: AwareDatetime


class PortV1(ContractModel):
    name: str

class VesselV1(ContractModel):
    name: str
    imo: str | None
    status: Literal[
        "ATRACADO",
        "DESATRACANDO",
        "FUNDEADO",
        "ATRACANDO",
        "PREVISTO",
        "DESATRACADO",
    ]
    section: Literal["ATRACADO", "FUNDEADO", "PREVISTO"]
    berth: StrictInt | None
    side: str | None
    eta: str | None
    etb_ets: str | None
    pob: str | None
    flag: str | None
    origin_port: str | None
    irin: str | None
    agency: str | None
    tugs: str | None


class EmptyBlock(ContractModel):
    pass

class WeatherV1(ContractModel):
    consulted_at: AwareDatetime | None
    observed_at: AwareDatetime | None
    air_temperature_c: Number
    humidity_pct: Number
    weather_code: StrictInt | None
    wind_speed_kn: Number
    wind_direction_deg: Number
    wind_gust_kn: Number
    visibility_m: Number
    precipitation_mm: Number


class MarineV1(ContractModel):
    consulted_at: AwareDatetime | None
    observed_at: AwareDatetime | None
    wave_height_m: Number
    wave_direction_deg: Number
    wave_period_s: Number
    swell_height_m: Number
    swell_direction_deg: Number
    swell_period_s: Number
    sea_temperature_c: Number
    current_kn: Number
    current_direction_deg: Number

class ManeuverV1(ContractModel):
    id: str
    type: Literal["ATRACACAO", "DESATRACACAO"]
    vessel_name: str
    berth: StrictInt | None
    pob: str | None
    status: Literal["ACTIVE", "COMPLETED"]
    detected_at: AwareDatetime
    completed_at: AwareDatetime | None


class RecentManeuversV1(ContractModel):
    active: list[ManeuverV1]
    completed: list[ManeuverV1]

    @model_validator(mode="after")
    def validate_status_groups(self) -> "RecentManeuversV1":
        for item in self.active:
            if item.status != "ACTIVE" or item.completed_at is not None:
                raise ValueError(
                    "active maneuver must have status ACTIVE and completed_at null"
                )
        for item in self.completed:
            if item.status != "COMPLETED" or item.completed_at is None:
                raise ValueError(
                    "completed maneuver must have status COMPLETED and completed_at set"
                )
        return self

class MobileSnapshotV1(ContractModel):
    schema_version: Literal[1]
    boot_id: UUID
    sequence: PositiveStrictInt
    generated_at: AwareDatetime
    collector: CollectorV1
    port: PortV1
    vessels: list[VesselV1]
    weather: WeatherV1 | EmptyBlock
    marine: MarineV1 | EmptyBlock
    recent_maneuvers: RecentManeuversV1
