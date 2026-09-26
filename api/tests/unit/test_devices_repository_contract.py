from __future__ import annotations

from dataclasses import fields
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID

from app.repositories.devices import DeviceAuthRecord, StoredSnapshot
from app.repositories.memory import MemoryDeviceRepository


MIGRATION = Path(__file__).parents[2] / "supabase" / "migrations" / "001_devices.sql"


def test_repository_auth_record_contains_hashes_not_plaintext_secrets():
    names = {field.name for field in fields(DeviceAuthRecord)}

    assert names == {
        "device_id",
        "device_secret_hash",
        "view_secret_hash",
    }


def test_memory_repository_represents_missing_and_empty_device():
    repo = MemoryDeviceRepository()
    record = DeviceAuthRecord(
        device_id="pecem-01",
        device_secret_hash="device-hash",
        view_secret_hash=None,
    )

    assert repo.get_device_auth("pecem-01") is None
    assert repo.get_snapshot("pecem-01") is None

    repo.create_device(record)

    assert repo.get_device_auth("pecem-01") == record
    assert repo.get_snapshot("pecem-01") is None


def test_memory_repository_represents_device_with_snapshot():
    stored = StoredSnapshot(
        device_id="pecem-01",
        snapshot={"schema_version": 1},
        snapshot_schema_version=1,
        boot_id=UUID("550e8400-e29b-41d4-a716-446655440000"),
        sequence=7,
        generated_at=datetime(2026, 9, 25, 13, 40, tzinfo=timezone.utc),
        received_at=datetime(2026, 9, 25, 13, 41, tzinfo=timezone.utc),
    )
    repo = MemoryDeviceRepository(snapshots=[stored])

    assert repo.get_snapshot("pecem-01") == stored


def test_rotate_view_secret_hash_never_requires_plaintext_secret():
    repo = MemoryDeviceRepository()

    repo.create_device(
        DeviceAuthRecord(
            device_id="pecem-01",
            device_secret_hash="device-hash",
            view_secret_hash=None,
        )
    )

    assert repo.rotate_view_secret_hash("pecem-01", "view-hash") is True
    assert repo.get_device_auth("pecem-01").view_secret_hash == "view-hash"
    assert repo.rotate_view_secret_hash("missing", "view-hash") is False


def test_devices_migration_enables_rls_without_public_policy():
    sql = MIGRATION.read_text(encoding="utf-8").lower()

    assert "create table" in sql
    assert "public.devices" in sql
    assert "device_id text primary key" in sql
    assert "snapshot jsonb" in sql
    assert "enable row level security" in sql
    assert "create policy" not in sql
