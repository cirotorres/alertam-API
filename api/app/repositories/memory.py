from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DeviceRecord:
    device_id: str
    device_secret_hash: str
    view_secret_hash: str | None = None


class MemoryDeviceRepository:
    """Repository efêmero para desenvolvimento e testes sem Supabase."""

    def __init__(self) -> None:
        self._devices: dict[str, DeviceRecord] = {}

    def put_device(self, record: DeviceRecord) -> None:
        self._devices[record.device_id] = record

    def get_device_auth(self, device_id: str) -> DeviceRecord | None:
        return self._devices.get(device_id)
