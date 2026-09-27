from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import os
from pathlib import Path

import psycopg
import pytest

from app.models.maneuver_event import ManeuverEventIn
from app.repositories.devices import DeviceAuthRecord
from app.repositories.events import AcceptEventStatus
from app.repositories.postgres import PostgresDeviceRepository


DSN = os.getenv("TEST_POSTGRES_DSN")
MIGRATIONS = Path(__file__).parents[2] / "supabase" / "migrations"
pytestmark = pytest.mark.skipif(not DSN, reason="TEST_POSTGRES_DSN não configurado")


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
        for name in ("001_devices.sql", "004_maneuver_events.sql"):
            conn.execute((MIGRATIONS / name).read_text(encoding="utf-8"))
    yield


def _repo() -> PostgresDeviceRepository:
    assert DSN is not None
    repo = PostgresDeviceRepository(DSN)
    repo.create_device(DeviceAuthRecord("pecem-01", "hash"))
    return repo


def _event() -> ManeuverEventIn:
    return ManeuverEventIn.model_validate({
        "event_id": "00000000-0000-4000-8000-000000000402",
        "maneuver_id": "00000000-0000-4000-8000-000000000401",
        "vessel_identity": "NAME:NAVIO A",
        "vessel_imo": None,
        "vessel_name": "NAVIO A",
        "maneuver_type": "ATRACACAO",
        "event_type": "CONFIRMED",
        "berth": 4,
        "pob": "27/09 10:00",
        "occurred_at": "2026-09-27T10:00:00-03:00",
        "changes": None,
    })


def test_postgres_event_repository_accepts_and_is_idempotent():
    repo = _repo()
    first = repo.accept_maneuver_event_atomic("pecem-01", _event())
    second = repo.accept_maneuver_event_atomic("pecem-01", _event())

    assert first.status is AcceptEventStatus.ACCEPTED
    assert second.status is AcceptEventStatus.IDEMPOTENT
    assert first.stored == second.stored


def test_postgres_event_repository_concurrent_retry_creates_one_row():
    repo = _repo()

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(
            lambda _: repo.accept_maneuver_event_atomic("pecem-01", _event()),
            range(2),
        ))

    assert {r.status for r in results} == {
        AcceptEventStatus.ACCEPTED,
        AcceptEventStatus.IDEMPOTENT,
    }
    assert len(repo.list_maneuver_events("pecem-01").events) == 1
