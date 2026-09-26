from __future__ import annotations

from app.repositories.memory import DeviceRecord, MemoryDeviceRepository


def test_memory_repository_stores_and_reads_device_without_external_io():
    repo = MemoryDeviceRepository()
    record = DeviceRecord(
        device_id="pecem-01",
        device_secret_hash="device-hash",
        view_secret_hash=None,
    )

    repo.put_device(record)

    assert repo.get_device_auth("pecem-01") == record
    assert repo.get_device_auth("missing") is None


def test_memory_repository_instances_do_not_share_state():
    first = MemoryDeviceRepository()
    second = MemoryDeviceRepository()

    first.put_device(
        DeviceRecord(
            device_id="pecem-01",
            device_secret_hash="device-hash",
            view_secret_hash=None,
        )
    )

    assert second.get_device_auth("pecem-01") is None
