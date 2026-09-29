from __future__ import annotations

import os
from pathlib import Path
from uuid import UUID

import psycopg
import pytest

from app.repositories.devices import DeviceAuthRecord
from app.repositories.postgres import PostgresDeviceRepository


DSN = os.getenv("TEST_POSTGRES_DSN")
MIGRATIONS = Path(__file__).parents[2] / "supabase" / "migrations"
INSTALL_A = UUID("10000000-0000-4000-8000-000000000001")
INSTALL_B = UUID("10000000-0000-4000-8000-000000000002")
pytestmark = pytest.mark.skipif(not DSN, reason="TEST_POSTGRES_DSN não configurado")


def _ensure_roles(conn):
    conn.execute("""
    do $$ begin create role anon noinherit;
    exception when duplicate_object then null; end $$;
    do $$ begin create role authenticated noinherit;
    exception when duplicate_object then null; end $$;
    do $$ begin create role service_role noinherit bypassrls;
    exception when duplicate_object then null; end $$;
    """)


@pytest.fixture(autouse=True)
def reset_database():
    assert DSN is not None
    with psycopg.connect(DSN, autocommit=True) as conn:
        _ensure_roles(conn)
        conn.execute("drop schema if exists public cascade")
        conn.execute("create schema public")
        for name in (
            "001_devices.sql",
            "004_maneuver_events.sql",
            "005_push_installations_deliveries.sql",
            "010_mobile_installations.sql",
        ):
            conn.execute((MIGRATIONS / name).read_text(encoding="utf-8"))
    yield


def repo():
    assert DSN is not None
    repository = PostgresDeviceRepository(DSN)
    repository.create_device(DeviceAuthRecord("pecem-01", "hash", "view"))
    repository.create_device(DeviceAuthRecord("other-01", "hash", "view"))
    return repository


def test_postgres_mobile_installation_lifecycle_and_isolation():
    repository = repo()

    first = repository.ensure_mobile_installation("pecem-01", INSTALL_A)
    assert first is not None and first.active is True
    assert repository.ensure_mobile_installation("other-01", INSTALL_A) is None

    assert repository.revoke_mobile_installation("pecem-01", INSTALL_A) is True
    assert repository.get_mobile_installation("pecem-01", INSTALL_A).active is False
    assert repository.ensure_mobile_installation("pecem-01", INSTALL_A).active is True


def test_migration_backfills_existing_push_installation_id():
    repository = repo()
    assert DSN is not None

    with psycopg.connect(DSN, autocommit=True) as conn:
        conn.execute(
            """
            insert into public.push_installations (
                installation_id, device_id, endpoint, p256dh, auth
            ) values (%s, %s, %s, %s, %s)
            """,
            (INSTALL_B, "pecem-01", "https://push", "key", "auth"),
        )
        conn.execute("drop table public.mobile_installations cascade")
        conn.execute(
            (MIGRATIONS / "010_mobile_installations.sql").read_text(
                encoding="utf-8"
            )
        )

    mobile = repository.get_mobile_installation("pecem-01", INSTALL_B)
    assert mobile is not None
    assert mobile.installation_id == INSTALL_B


def test_rotation_deactivates_mobile_and_push_installations():
    repository = repo()
    assert repository.ensure_mobile_installation("pecem-01", INSTALL_B) is not None
    assert DSN is not None

    with psycopg.connect(DSN, autocommit=True) as conn:
        conn.execute(
            """
            insert into public.push_installations (
                installation_id, device_id, endpoint, p256dh, auth
            ) values (%s, %s, %s, %s, %s)
            """,
            (INSTALL_B, "pecem-01", "https://push", "key", "auth"),
        )

    assert repository.rotate_view_secret_hash("pecem-01", "new-view") is True
    assert repository.get_mobile_installation("pecem-01", INSTALL_B).active is False

    with psycopg.connect(DSN, autocommit=True) as conn:
        active = conn.execute(
            "select active from public.push_installations where installation_id=%s",
            (INSTALL_B,),
        ).fetchone()[0]
    assert active is False
