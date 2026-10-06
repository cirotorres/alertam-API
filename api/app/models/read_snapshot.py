from __future__ import annotations

from pydantic import AwareDatetime, BaseModel

from app.models.mobile_snapshot import MobileSnapshot


class SnapshotMetaResponse(BaseModel):
    received_at: AwareDatetime
    age_seconds: int
    collector_online: bool
    stale_after_seconds: int
    device_enabled: bool = True


class SnapshotReadResponse(BaseModel):
    snapshot: MobileSnapshot
    meta: SnapshotMetaResponse
