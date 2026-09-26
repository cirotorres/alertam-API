from __future__ import annotations

from pydantic import AwareDatetime, BaseModel

from app.models.mobile_snapshot import MobileSnapshotV1


class SnapshotMetaResponse(BaseModel):
    received_at: AwareDatetime
    age_seconds: int
    collector_online: bool
    stale_after_seconds: int


class SnapshotReadResponse(BaseModel):
    snapshot: MobileSnapshotV1
    meta: SnapshotMetaResponse
