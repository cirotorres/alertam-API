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
pytestmark = pytest.mark.skipif(not DSN, reason="TEST_POSTGRES_DSN não configurado")
INSTALL = UUID("30000000-0000-4000-8000-000000000001")


def _ensure_roles(conn) -> None:
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
            "018_device_admin_metadata.sql",
            "004_maneuver_events.sql",
            "005_push_installations_deliveries.sql",
            "017_anchorage_notifications.sql",
        ):
            conn.execute((MIGRATIONS / name).read_text(encoding="utf-8"))
    yield


def test_postgres_push_installation_reactivation_and_view_rotation():
    assert DSN is not None
    repo = PostgresDeviceRepository(DSN)
    repo.create_device(DeviceAuthRecord("pecem-01", "hash", "view"))

    created = repo.upsert_push_installation(
        "pecem-01",
        INSTALL,
        endpoint="https://push.example/a",
        p256dh="p",
        auth="a",
    )
    assert created is not None and created.active is True

    assert repo.deactivate_push_installation("pecem-01", INSTALL) is True
    reactivated = repo.upsert_push_installation(
        "pecem-01",
        INSTALL,
        endpoint="https://push.example/b",
        p256dh="p2",
        auth="a2",
    )
    assert reactivated is not None and reactivated.active is True
    assert reactivated.push_enabled_at >= created.push_enabled_at

    assert repo.rotate_view_secret_hash("pecem-01", "new-view") is True
    assert repo.get_push_installation("pecem-01", INSTALL).active is False
