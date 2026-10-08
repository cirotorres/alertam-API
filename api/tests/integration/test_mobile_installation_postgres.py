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


def _apply(conn, *names):
    for name in names:
        conn.execute((MIGRATIONS / name).read_text(encoding="utf-8"))


@pytest.fixture(autouse=True)
def reset_database():
    assert DSN is not None
    with psycopg.connect(DSN, autocommit=True) as conn:
        _ensure_roles(conn)
        conn.execute("drop schema if exists public cascade")
        conn.execute("create schema public")
        _apply(
            conn,
            "001_devices.sql",
            "018_device_admin_metadata.sql",
            "004_maneuver_events.sql",
            "005_push_installations_deliveries.sql",
            "008_vessel_tracking_events.sql",
            "010_mobile_installations.sql",
            "011_tracked_vessels.sql",
            "013_mobile_installation_management.sql",
            "014_mobile_session_switch.sql",
        )
    yield


def repo():
    assert DSN is not None
    repository = PostgresDeviceRepository(DSN)
    repository.create_device(DeviceAuthRecord("pecem-01", "hash", "view"))
    repository.create_device(DeviceAuthRecord("other-01", "hash", "view"))
    return repository


def test_postgres_mobile_installation_lifecycle_and_isolation():
    repository = repo()

    first = repository.ensure_mobile_installation(
        "pecem-01",
        INSTALL_A,
        platform="ios",
        display_code="K7M4Q2",
    )
    assert first is not None
    assert first.active is True
    assert first.platform == "ios"
    assert first.display_code == "K7M4Q2"
    assert repository.ensure_mobile_installation(
        "other-01",
        INSTALL_A,
        platform="android",
        display_code="P8X4TR",
    ) is None

    assert repository.revoke_mobile_installation("pecem-01", INSTALL_A) is True
    revoked = repository.get_mobile_installation("pecem-01", INSTALL_A)
    assert revoked is not None and revoked.active is False
    assert repository.ensure_mobile_installation(
        "pecem-01",
        INSTALL_A,
        platform="ios",
        display_code="B7K9P3",
    ) is None
    assert repository.touch_mobile_installation(
        "pecem-01",
        INSTALL_A,
        platform="android",
    ) is None


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
        conn.execute("drop table public.tracked_vessels cascade")
        conn.execute("drop table public.mobile_installations cascade")
        _apply(
            conn,
            "010_mobile_installations.sql",
            "011_tracked_vessels.sql",
            "013_mobile_installation_management.sql",
        )

    mobile = repository.get_mobile_installation("pecem-01", INSTALL_B)
    assert mobile is not None
    assert mobile.installation_id == INSTALL_B
    assert mobile.platform == "other"
    assert len(mobile.display_code) == 6


def test_rotation_deactivates_mobile_and_push_installations():
    repository = repo()
    assert repository.ensure_mobile_installation(
        "pecem-01",
        INSTALL_B,
        platform="android",
        display_code="P8X4TR",
    ) is not None
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
    mobile = repository.get_mobile_installation("pecem-01", INSTALL_B)
    assert mobile is not None and mobile.active is False

    with psycopg.connect(DSN, autocommit=True) as conn:
        active = conn.execute(
            "select active from public.push_installations where installation_id=%s",
            (INSTALL_B,),
        ).fetchone()[0]
    assert active is False


def test_postgres_mobile_session_switch_is_idempotent_and_conflict_safe():
    from app.repositories.devices import MobileInstallationSwitchConflictError

    repository = repo()
    switch_id = UUID("20000000-0000-4000-8000-000000000001")
    source = repository.ensure_mobile_installation(
        "pecem-01",
        INSTALL_A,
        platform="ios",
        display_code="K7M4Q2",
    )
    assert source is not None

    first = repository.switch_mobile_installation(
        "pecem-01",
        INSTALL_A,
        "other-01",
        INSTALL_B,
        platform="android",
        display_code="P8X4TR",
        switch_id=switch_id,
    )
    replay = repository.switch_mobile_installation(
        "pecem-01",
        INSTALL_A,
        "other-01",
        INSTALL_B,
        platform="android",
        display_code="Z7Z7Z7",
        switch_id=switch_id,
    )

    assert first is not None
    assert replay == first
    old = repository.get_mobile_installation("pecem-01", INSTALL_A)
    assert old is not None and old.active is False

    with pytest.raises(MobileInstallationSwitchConflictError):
        repository.switch_mobile_installation(
            "pecem-01",
            INSTALL_A,
            "other-01",
            UUID("10000000-0000-4000-8000-000000000099"),
            platform="android",
            display_code="Q7D2AA",
            switch_id=switch_id,
        )
