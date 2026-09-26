from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
from uuid import UUID

import psycopg
import pytest

from app.repositories.devices import (
    AcceptSnapshotStatus,
    DeviceAlreadyExistsError,
    DeviceAuthRecord,
    SnapshotCandidate,
)
from app.repositories.postgres import PostgresDeviceRepository


DSN = os.getenv("TEST_POSTGRES_DSN")
MIGRATIONS = Path(__file__).parents[2] / "supabase" / "migrations"
pytestmark = pytest.mark.skipif(
    not DSN,
    reason="TEST_POSTGRES_DSN não configurado",
)


def _ensure_roles(conn) -> None:
    conn.execute(
        """
        do $$
        begin create role anon noinherit;
        exception when duplicate_object then null;
        end $$;
        do $$
        begin create role authenticated noinherit;
        exception when duplicate_object then null;
        end $$;
        do $$
        begin create role service_role noinherit bypassrls;
        exception when duplicate_object then null;
        end $$;
        """
    )


@pytest.fixture(autouse=True)
def reset_database():
    assert DSN is not None
    with psycopg.connect(DSN, autocommit=True) as conn:
        _ensure_roles(conn)
        conn.execute("drop schema if exists public cascade")
        conn.execute("create schema public")
        for name in (
            "001_devices.sql",
            "002_accept_snapshot_rpc.sql",
            "003_rotate_view_secret_rpc.sql",
        ):
            conn.execute((MIGRATIONS / name).read_text(encoding="utf-8"))
    yield


def _repo() -> PostgresDeviceRepository:
    assert DSN is not None
    return PostgresDeviceRepository(DSN)


def test_postgres_repository_creates_and_reads_device():
    repo = _repo()
    record = DeviceAuthRecord(
        device_id="pecem-01",
        device_secret_hash="device-hash",
        view_secret_hash=None,
    )

    repo.create_device(record)

    assert repo.get_device_auth("pecem-01") == record
    with pytest.raises(DeviceAlreadyExistsError):
        repo.create_device(record)


def test_postgres_repository_rotates_view_secret_hash():
    repo = _repo()
    repo.create_device(DeviceAuthRecord("pecem-01", "device-hash"))

    assert repo.rotate_view_secret_hash("pecem-01", "view-hash") is True
    assert repo.get_device_auth("pecem-01").view_secret_hash == "view-hash"
    assert repo.rotate_view_secret_hash("missing", "other-hash") is False


def test_postgres_repository_accepts_and_reads_snapshot():
    repo = _repo()
    repo.create_device(DeviceAuthRecord("pecem-01", "device-hash"))
    candidate = SnapshotCandidate(
        device_id="pecem-01",
        snapshot={"schema_version": 1, "marker": "local-postgres"},
        snapshot_schema_version=1,
        boot_id=UUID("550e8400-e29b-41d4-a716-446655440000"),
        sequence=1,
        generated_at=datetime(2026, 9, 25, 16, 0, tzinfo=timezone.utc),
    )

    accepted = repo.accept_snapshot_atomic(candidate)
    stored = repo.get_snapshot("pecem-01")

    assert accepted.status is AcceptSnapshotStatus.ACCEPTED
    assert stored is not None
    assert stored.snapshot == candidate.snapshot
    assert stored.boot_id == candidate.boot_id
    assert stored.sequence == 1
    assert stored.received_at == accepted.received_at


def test_postgres_repository_preserves_idempotency():
    repo = _repo()
    repo.create_device(DeviceAuthRecord("pecem-01", "device-hash"))
    candidate = SnapshotCandidate(
        device_id="pecem-01",
        snapshot={"schema_version": 1},
        snapshot_schema_version=1,
        boot_id=UUID("550e8400-e29b-41d4-a716-446655440000"),
        sequence=1,
        generated_at=datetime(2026, 9, 25, 16, 0, tzinfo=timezone.utc),
    )

    first = repo.accept_snapshot_atomic(candidate)
    repeated = repo.accept_snapshot_atomic(candidate)

    assert repeated.status is AcceptSnapshotStatus.IDEMPOTENT
    assert repeated.received_at == first.received_at
