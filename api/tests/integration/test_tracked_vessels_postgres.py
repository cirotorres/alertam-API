from __future__ import annotations

import os
from datetime import timedelta
from pathlib import Path
from uuid import UUID

import psycopg
import pytest

from app.repositories.devices import DeviceAuthRecord
from app.repositories.postgres import PostgresDeviceRepository
from app.repositories.tracking import VesselEvidence


DSN = os.getenv("TEST_POSTGRES_DSN")
MIGRATIONS = Path(__file__).parents[2] / "supabase" / "migrations"
INSTALL_A = UUID("20000000-0000-4000-8000-000000000001")
INSTALL_B = UUID("20000000-0000-4000-8000-000000000002")
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
            "018_device_admin_metadata.sql",
            "004_maneuver_events.sql",
            "005_push_installations_deliveries.sql",
            "017_anchorage_notifications.sql",
            "008_vessel_tracking_events.sql",
            "010_mobile_installations.sql",
            "013_mobile_installation_management.sql",
            "011_tracked_vessels.sql",
        ):
            conn.execute((MIGRATIONS / name).read_text(encoding="utf-8"))
    yield


def repo():
    assert DSN is not None
    repository = PostgresDeviceRepository(DSN)
    repository.create_device(DeviceAuthRecord("pecem-01", "hash", "view"))
    assert repository.ensure_mobile_installation(
        "pecem-01",
        INSTALL_A,
        display_code="AAAAAA",
    )
    assert repository.ensure_mobile_installation(
        "pecem-01",
        INSTALL_B,
        display_code="BBBBBB",
    )
    return repository


def evidence(
    *,
    identity="NAME:NAVIO A",
    imo=None,
    name="NAVIO A",
):
    return VesselEvidence(
        vessel_identity=identity,
        vessel_imo=imo,
        vessel_name=name,
        current={
            "present": True,
            "status": "PREVISTO",
            "section": "PREVISTO",
            "berth": 4,
            "side": "BB",
            "eta": "28/09 12:30",
            "etb_ets": "28/09 13:00",
            "pob": None,
            "pob_at": None,
        },
        observed_at=None,
    )


def test_postgres_tracked_vessel_is_idempotent_and_installation_scoped():
    repository = repo()

    first = repository.upsert_tracked_vessel(
        "pecem-01", INSTALL_A, evidence()
    )
    repeated = repository.upsert_tracked_vessel(
        "pecem-01", INSTALL_A, evidence()
    )
    other = repository.upsert_tracked_vessel(
        "pecem-01", INSTALL_B, evidence()
    )

    assert first is not None and repeated is not None and other is not None
    assert repeated.tracked_vessel_id == first.tracked_vessel_id
    assert other.tracked_vessel_id != first.tracked_vessel_id


def test_postgres_exact_name_fallback_promotes_same_record_to_imo():
    repository = repo()
    first = repository.upsert_tracked_vessel(
        "pecem-01", INSTALL_A, evidence()
    )

    promoted = repository.upsert_tracked_vessel(
        "pecem-01",
        INSTALL_A,
        evidence(
            identity="IMO:1234567",
            imo="1234567",
            name="  navio   a ",
        ),
    )

    assert first is not None and promoted is not None
    assert promoted.tracked_vessel_id == first.tracked_vessel_id
    assert promoted.vessel_identity == "IMO:1234567"
    assert promoted.vessel_imo == "1234567"


def test_postgres_stop_preserves_record_and_rotation_deactivates_active_tracking():
    repository = repo()
    first = repository.upsert_tracked_vessel(
        "pecem-01", INSTALL_A, evidence()
    )
    second = repository.upsert_tracked_vessel(
        "pecem-01", INSTALL_B, evidence(
            identity="IMO:1234567",
            imo="1234567",
        )
    )
    assert first is not None and second is not None

    stopped = repository.deactivate_tracked_vessel(
        "pecem-01", INSTALL_A, first.tracked_vessel_id
    )
    assert stopped is not None and stopped.active is False
    assert repository.get_tracked_vessel(
        "pecem-01", INSTALL_A, first.tracked_vessel_id
    ) is not None

    assert repository.rotate_view_secret_hash(
        "pecem-01", "rotated-view"
    ) is True
    after = repository.get_tracked_vessel(
        "pecem-01", INSTALL_B, second.tracked_vessel_id
    )
    assert after is not None and after.active is False


def test_postgres_mobile_revoke_deactivates_only_that_installation_tracking():
    repository = repo()
    first = repository.upsert_tracked_vessel(
        "pecem-01", INSTALL_A, evidence()
    )
    second = repository.upsert_tracked_vessel(
        "pecem-01", INSTALL_B, evidence(
            identity="IMO:1234567",
            imo="1234567",
        )
    )
    assert first is not None and second is not None

    assert repository.revoke_mobile_installation(
        "pecem-01", INSTALL_A
    ) is True

    a = repository.get_tracked_vessel(
        "pecem-01", INSTALL_A, first.tracked_vessel_id
    )
    b = repository.get_tracked_vessel(
        "pecem-01", INSTALL_B, second.tracked_vessel_id
    )
    assert a is not None and a.active is False
    assert b is not None and b.active is True


def test_postgres_tracking_lookup_for_maneuver_push_respects_started_at():
    repository = repo()
    tracked = repository.upsert_tracked_vessel(
        "pecem-01",
        INSTALL_A,
        evidence(identity="IMO:1234567", imo="1234567"),
    )
    assert tracked is not None

    before = repository.find_active_tracked_vessel_for_event(
        "pecem-01",
        INSTALL_A,
        vessel_identity="IMO:1234567",
        vessel_imo="1234567",
        vessel_name="NAVIO A",
        occurred_at=tracked.started_at - timedelta(microseconds=1),
    )
    equal = repository.find_active_tracked_vessel_for_event(
        "pecem-01",
        INSTALL_A,
        vessel_identity="IMO:1234567",
        vessel_imo="1234567",
        vessel_name="NAVIO A",
        occurred_at=tracked.started_at,
    )

    assert before is None
    assert equal is not None
    assert equal.tracked_vessel_id == tracked.tracked_vessel_id
