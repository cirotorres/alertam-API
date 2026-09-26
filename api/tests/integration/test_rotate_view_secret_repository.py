from __future__ import annotations

import os
from pathlib import Path

import psycopg
import pytest


DSN = os.getenv("TEST_POSTGRES_DSN")
MIGRATIONS = Path(__file__).parents[2] / "supabase" / "migrations"

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
        for name in ("001_devices.sql", "003_rotate_view_secret_rpc.sql"):
            conn.execute(
                (MIGRATIONS / name).read_text(encoding="utf-8")
            )
        conn.execute(
            """
            insert into public.devices (
                device_id,
                device_secret_hash
            )
            values ('pecem-01', 'device-hash')
            """
        )
    yield


def _rotate(device_id: str, view_hash: str):
    assert DSN is not None
    with psycopg.connect(DSN, autocommit=True) as conn:
        return conn.execute(
            """
            select updated
            from public.rotate_device_view_secret(%s, %s)
            """,
            (device_id, view_hash),
        ).fetchone()[0]

def _stored():
    assert DSN is not None
    with psycopg.connect(DSN, autocommit=True) as conn:
        return conn.execute(
            """
            select view_secret_hash, view_secret_updated_at, updated_at
            from public.devices
            where device_id = 'pecem-01'
            """
        ).fetchone()


def test_rotation_updates_only_hash_and_timestamps():
    assert _rotate("pecem-01", "hash-a") is True

    stored = _stored()
    assert stored[0] == "hash-a"
    assert stored[1] is not None
    assert stored[2] is not None


def test_second_rotation_replaces_previous_hash():
    assert _rotate("pecem-01", "hash-a") is True
    first = _stored()

    assert _rotate("pecem-01", "hash-b") is True
    second = _stored()

    assert second[0] == "hash-b"
    assert second[1] >= first[1]
    assert second[2] >= first[2]


def test_rotation_returns_false_for_missing_device():
    assert _rotate("missing", "hash") is False
