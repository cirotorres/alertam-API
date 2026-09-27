from __future__ import annotations

from app.models.mobile_snapshot import ContractModel


class VesselPhotoResponse(ContractModel):
    imo: str
    photo_url: str | None = None
    author: str | None = None
    license: str | None = None
    source_url: str | None = None
