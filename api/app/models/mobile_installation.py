from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class PairingValidationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    device_id: str = Field(min_length=1, max_length=200)


class PairingValidationResponse(BaseModel):
    device_id: str


class MobileHeartbeatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    platform: str | None = Field(default=None, max_length=32)


class MobileInstallationAdminItem(BaseModel):
    installation_id: UUID
    display_code: str
    platform: str
    active: bool
    created_at: datetime
    last_seen_at: datetime
    revoked_at: datetime | None


class MobileInstallationsAdminResponse(BaseModel):
    active_count: int
    active: list[MobileInstallationAdminItem]
    recently_revoked: list[MobileInstallationAdminItem]
