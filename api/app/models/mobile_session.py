from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class MobileSessionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    device_id: str = Field(min_length=1, max_length=200)
    installation_id: UUID


class MobileSessionResponse(BaseModel):
    device_id: str
    installation_id: UUID
