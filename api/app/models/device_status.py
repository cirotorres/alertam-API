from pydantic import BaseModel


class DeviceStatusResponse(BaseModel):
    device_id: str
    enabled: bool
