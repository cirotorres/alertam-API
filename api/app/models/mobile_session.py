from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class MobileSessionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    device_id: str = Field(min_length=1, max_length=200)
    installation_id: UUID
    platform: str | None = Field(default=None, max_length=32)


class MobileSessionResponse(BaseModel):
    device_id: str
    installation_id: UUID
    display_code: str
    platform: str


class MobileSessionSwitchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    device_id: str = Field(min_length=1, max_length=200)
    installation_id: UUID
    platform: str = Field(min_length=1, max_length=32)
    switch_id: UUID
