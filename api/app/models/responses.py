from __future__ import annotations

from datetime import datetime

from pydantic import AwareDatetime, BaseModel


class SnapshotAcceptedResponse(BaseModel):
    ok: bool = True
    received_at: AwareDatetime
