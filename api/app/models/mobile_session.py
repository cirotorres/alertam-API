from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class MobileSessionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    device_id: str = Field(min_length=1, max_length=200)


class MobileSessionResponse(BaseModel):
    device_id: str
