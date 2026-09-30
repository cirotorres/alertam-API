from pydantic import BaseModel, ConfigDict, Field


class PairingValidationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    device_id: str = Field(min_length=1, max_length=200)


class PairingValidationResponse(BaseModel):
    device_id: str


class MobileHeartbeatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    platform: str | None = Field(default=None, max_length=32)
