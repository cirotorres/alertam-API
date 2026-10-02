from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class MobilePairingCodeResponse(BaseModel):
    code: str
    expires_at: datetime


class MobilePairingCodeRedeemRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str = Field(min_length=6, max_length=16)


class MobilePairingTicketResponse(BaseModel):
    device_id: str
    pairing_ticket: str
    expires_at: datetime
