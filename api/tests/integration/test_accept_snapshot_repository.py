from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import json
import os
from pathlib import Path
from uuid import UUID

import psycopg
import pytest


DSN = os.getenv("TEST_POSTGRES_DSN")
MIGRATIONS = Path(__file__).parents[2] / "supabase" / "migrations"
BOOT_A = UUID("550e8400-e29b-41d4-a716-446655440000")
BOOT_B = UUID("660e8400-e29b-41d4-a716-446655440000")
GENERATED_AT = datetime(2026, 9, 25, 16, 0, tzinfo=timezone.utc)

pytestmark = pytest.mark.skipif(
    not DSN,
    reason="TEST_POSTGRES_DSN não configurado",
)


def _ensure_supabase_roles(conn) -> None:
    conn.execute(
        """
        do $$
        begin
            create role anon noinherit;
        exception when duplicate_object then null;
        end $$;
        do $$
        begin
            create role authenticated noinherit;
        exception when duplicate_object then null;
        end $$;
        do $$
        begin
            create role service_role noinherit bypassrls;
        exception when duplicate_object then null;
        end $$;
        """
    )

@pytest.fixture(autouse=True)
def reset_database():
    assert DSN is not None
    with psycopg.connect(DSN, autocommit=True) as conn:
        _ensure_supabase_roles(conn)
        conn.execute("drop schema if exists public cascade")
        conn.execute("create schema public")
        for name in ("001_devices.sql", "002_accept_snapshot_rpc.sql"):
            sql = (MIGRATIONS / name).read_text(encoding="utf-8")
            conn.execute(sql)
    yield


def _insert_device(device_id: str = "pecem-01") -> None:
    assert DSN is not None
    with psycopg.connect(DSN, autocommit=True) as conn:
        conn.execute(
            """
            insert into public.devices (device_id, device_secret_hash)
            values (%s, %s)
            """,
            (device_id, "device-hash"),
        )


def _call(
    sequence: int,
    *,
    boot_id: UUID = BOOT_A,
    marker: str = "same",
    device_id: str = "pecem-01",
):
    assert DSN is not None
    snapshot = {"schema_version": 1, "marker": marker}
    with psycopg.connect(DSN, autocommit=True) as conn:
        row = conn.execute(

            """
            select status, received_at
            from public.accept_device_snapshot(
                %s,
                %s::jsonb,
                %s,
                %s,
                %s,
                %s
            )
            """,
            (
                device_id,
                json.dumps(snapshot),
                1,
                boot_id,
                sequence,
                GENERATED_AT,
            ),
        ).fetchone()
    assert row is not None
    return row


def _stored():
    assert DSN is not None
    with psycopg.connect(DSN, autocommit=True) as conn:
        return conn.execute(
            """
            select boot_id, sequence, snapshot, received_at
            from public.devices
            where device_id = 'pecem-01'
            """
        ).fetchone()


def test_missing_device_returns_device_not_found():
    status, received_at = _call(1, device_id="missing")

    assert status == "device_not_found"
    assert received_at is None

def test_accept_and_idempotent_retry_preserve_received_at():
    _insert_device()

    first_status, first_received = _call(1)
    repeated_status, repeated_received = _call(1)

    assert first_status == "accepted"
    assert repeated_status == "idempotent"
    assert repeated_received == first_received
    assert _stored()[3] == first_received


def test_same_sequence_with_different_payload_is_conflict():
    _insert_device()
    _call(1, marker="first")

    status, received_at = _call(1, marker="different")

    assert status == "sequence_reuse_mismatch"
    assert received_at == _stored()[3]
    assert _stored()[2]["marker"] == "first"


def test_lower_sequence_from_same_boot_is_rejected():
    _insert_device()
    _call(2)

    status, _ = _call(1)

    assert status == "out_of_order"
    assert _stored()[1] == 2

def test_new_boot_can_restart_sequence():
    _insert_device()
    _call(9, boot_id=BOOT_A)

    status, _ = _call(1, boot_id=BOOT_B)

    stored = _stored()
    assert status == "accepted"
    assert stored[0] == BOOT_B
    assert stored[1] == 1


def test_concurrent_requests_cannot_leave_older_sequence_persisted():
    _insert_device()

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(
            pool.map(
                lambda seq: _call(
                    seq,
                    marker=f"sequence-{seq}",
                )[0],
                (1, 2),
            )
        )

    stored = _stored()
    assert stored[1] == 2
    assert stored[2]["marker"] == "sequence-2"
    assert set(results) <= {"accepted", "out_of_order"}
