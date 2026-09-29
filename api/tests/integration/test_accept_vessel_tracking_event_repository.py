from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path

import psycopg
import pytest

from app.models.vessel_tracking_event import VesselTrackingEventIn
from app.repositories.devices import DeviceAuthRecord
from app.repositories.postgres import PostgresDeviceRepository
from app.repositories.tracking import AcceptTrackingEventStatus


DSN = os.getenv("TEST_POSTGRES_DSN")
MIGRATIONS = Path(__file__).parents[2] / "supabase" / "migrations"
FIXTURE = Path(__file__).parents[1] / "fixtures" / "vessel_tracking_event_v1.json"
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
            "008_vessel_tracking_events.sql",
            "009_vessel_tracking_retention.sql",
        ):
            conn.execute((MIGRATIONS / name).read_text(encoding="utf-8"))
    yield


def event(**overrides):
    body = json.loads(FIXTURE.read_text(encoding="utf-8"))
    body.update(overrides)
    return VesselTrackingEventIn.model_validate(body)


def repo():
    assert DSN is not None
    repository = PostgresDeviceRepository(DSN)
    repository.create_device(DeviceAuthRecord("pecem-01", "hash"))
    return repository


def test_postgres_tracking_event_accepts_and_is_idempotent():
    repository = repo()

    first = repository.accept_vessel_tracking_event_atomic("pecem-01", event())
    retry = repository.accept_vessel_tracking_event_atomic("pecem-01", event())

    assert first.status is AcceptTrackingEventStatus.ACCEPTED
    assert retry.status is AcceptTrackingEventStatus.IDEMPOTENT
    assert first.stored == retry.stored


def test_postgres_tracking_event_concurrent_retry_creates_one_row():
    repository = repo()

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(
            lambda _: repository.accept_vessel_tracking_event_atomic(
                "pecem-01", event()
            ),
            range(2),
        ))

    assert {result.status for result in results} == {
        AcceptTrackingEventStatus.ACCEPTED,
        AcceptTrackingEventStatus.IDEMPOTENT,
    }
    ingestion_ids = {
        result.stored.ingestion_id
        for result in results
        if result.stored is not None
    }
    assert len(ingestion_ids) == 1


def test_postgres_tracking_event_payload_mismatch_does_not_overwrite():
    repository = repo()
    repository.accept_vessel_tracking_event_atomic("pecem-01", event())

    result = repository.accept_vessel_tracking_event_atomic(
        "pecem-01", event(vessel_name="OUTRO NAVIO")
    )

    assert result.status is AcceptTrackingEventStatus.PAYLOAD_MISMATCH
    assert result.stored is not None
    assert result.stored.event.vessel_name == "NAVIO A"


def test_postgres_tracking_retention_removes_only_events_older_than_30_days():
    repository = repo()
    old_id = "00000000-0000-4000-8000-000000000501"
    recent_id = "00000000-0000-4000-8000-000000000502"
    repository.accept_vessel_tracking_event_atomic(
        "pecem-01", event(event_id=old_id)
    )
    repository.accept_vessel_tracking_event_atomic(
        "pecem-01", event(event_id=recent_id)
    )

    assert DSN is not None
    with psycopg.connect(DSN, autocommit=True) as conn:
        conn.execute(
            "update public.vessel_tracking_events "
            "set ingested_at = '2026-08-28T12:00:00Z' "
            "where event_id = %s",
            (old_id,),
        )
        conn.execute(
            "update public.vessel_tracking_events "
            "set ingested_at = '2026-09-27T12:00:00Z' "
            "where event_id = %s",
            (recent_id,),
        )
        deleted = conn.execute(
            "select public.cleanup_vessel_tracking_retention("
            "'2026-09-28T12:00:00Z'::timestamptz)"
        ).fetchone()[0]
        rows = conn.execute(
            "select event_id from public.vessel_tracking_events "
            "order by event_id"
        ).fetchall()

    assert deleted == 1
    assert [str(row[0]) for row in rows] == [recent_id]
