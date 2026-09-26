from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class ViewAccessRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    view_secret: str
