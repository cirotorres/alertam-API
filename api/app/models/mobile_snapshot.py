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


# ---------------------------------------------------------------------------
# MobileSnapshot schema v2 — SPEC 025 Plan 3


class UnavailableV2(ContractModel):
    status: Literal["unavailable"]


class WebPilotAtmospherePrimaryV2(ContractModel):
    status: Literal["fresh", "stale"]
    source: Literal["webpilot"]
    mode: Literal["observed"]
    consulted_at: AwareDatetime
    observed_at: AwareDatetime
    wind_direction_deg: Number
    wind_direction_cardinal: str | None
    wind_speed_current_kn: Number
    wind_speed_mean_kn: Number
    wind_speed_max_kn: Number
    air_temperature_c: Number
    apparent_temperature_c: Number
    humidity_pct: Number
    pressure_hpa: Number
    pressure_6h_hpa: Number
    precipitation_mm: Number


class OpenMeteoAtmospherePrimaryV2(ContractModel):
    status: Literal["fresh", "stale"]
    source: Literal["open_meteo"]
    mode: Literal["fallback"]
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


class OpenMeteoComplementaryV2(ContractModel):
    status: Literal["fresh", "stale"]
    source: Literal["open_meteo"]
    consulted_at: AwareDatetime | None
    observed_at: AwareDatetime | None
    weather_code: StrictInt | None
    visibility_m: Number


AtmospherePrimaryV2: TypeAlias = (
    WebPilotAtmospherePrimaryV2
    | OpenMeteoAtmospherePrimaryV2
    | UnavailableV2
)
AtmosphereComplementaryV2: TypeAlias = OpenMeteoComplementaryV2 | UnavailableV2


class AtmosphereV2(ContractModel):
    primary: AtmospherePrimaryV2
    complementary: AtmosphereComplementaryV2

    @model_validator(mode="after")
    def validate_source_relationship(self) -> "AtmosphereV2":
        primary = self.primary
        complementary = self.complementary
        if isinstance(primary, OpenMeteoAtmospherePrimaryV2) and not isinstance(
            complementary, UnavailableV2
        ):
            raise ValueError(
                "open_meteo primary requires complementary unavailable"
            )
        if isinstance(primary, UnavailableV2) and not isinstance(
            complementary, UnavailableV2
        ):
            raise ValueError(
                "unavailable primary requires complementary unavailable"
            )
        return self


class OpenMeteoMarineV2(ContractModel):
    status: Literal["fresh", "stale"]
    source: Literal["open_meteo"]
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


MarineV2: TypeAlias = OpenMeteoMarineV2 | UnavailableV2


class MobileSnapshotV2(ContractModel):
    schema_version: Literal[2]
    boot_id: UUID
    sequence: PositiveStrictInt
    generated_at: AwareDatetime
    collector: CollectorV1
    port: PortV1
    vessels: list[VesselV1]
    atmosphere: AtmosphereV2
    marine: MarineV2
    recent_maneuvers: RecentManeuversV1


MobileSnapshot: TypeAlias = Annotated[
    MobileSnapshotV1 | MobileSnapshotV2,
    Field(discriminator="schema_version"),
]
