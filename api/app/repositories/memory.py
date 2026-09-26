from __future__ import annotations

from dataclasses import replace
from typing import Iterable

from app.repositories.devices import (
    DeviceAlreadyExistsError,
    DeviceAuthRecord,
    StoredSnapshot,
)


DeviceRecord = DeviceAuthRecord


class MemoryDeviceRepository:
    """Repository efêmero para desenvolvimento e testes sem Supabase."""

    def __init__(
        self,
        *,
        devices: Iterable[DeviceAuthRecord] = (),
        snapshots: Iterable[StoredSnapshot] = (),
    ) -> None:
        self._devices = {item.device_id: item for item in devices}
        self._snapshots = {item.device_id: item for item in snapshots}

    def create_device(self, record: DeviceAuthRecord) -> None:
        if record.device_id in self._devices:
            raise DeviceAlreadyExistsError(record.device_id)
        self._devices[record.device_id] = record

    def put_device(self, record: DeviceAuthRecord) -> None:
        self._devices[record.device_id] = record

    def get_device_auth(self, device_id: str) -> DeviceAuthRecord | None:
        return self._devices.get(device_id)

    def get_snapshot(self, device_id: str) -> StoredSnapshot | None:
        return self._snapshots.get(device_id)

    def put_snapshot(self, snapshot: StoredSnapshot) -> None:
        self._snapshots[snapshot.device_id] = snapshot

    def rotate_view_secret_hash(
        self,
        device_id: str,
        view_secret_hash: str,
    ) -> bool:
        current = self._devices.get(device_id)
        if current is None:
            return False
        self._devices[device_id] = replace(
            current,
            view_secret_hash=view_secret_hash,
        )
        return True
