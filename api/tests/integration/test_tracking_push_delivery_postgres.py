from __future__ import annotations

import json
import os
from pathlib import Path
from uuid import UUID

import psycopg
import pytest

from app.models.vessel_tracking_event import VesselTrackingEventIn
from app.repositories.devices import DeviceAuthRecord
from app.repositories.postgres import PostgresDeviceRepository
from app.repositories.tracking import TrackingPushDeliveryStatus


DSN = os.getenv("TEST_POSTGRES_DSN")
MIGRATIONS = Path(__file__).parents[2] / "supabase" / "migrations"
FIXTURE = Path(__file__).parents[1] / "fixtures" / "vessel_tracking_event_v1.json"
INSTALL = UUID("93000000-0000-4000-8000-000000000001")
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
            "008_vessel_tracking_events.sql",
            "010_mobile_installations.sql",
            "011_tracked_vessels.sql",
            "012_vessel_tracking_deliveries.sql",
        ):
            conn.execute((MIGRATIONS / name).read_text(encoding="utf-8"))
    yield


def event(event_id=None):
    body = json.loads(FIXTURE.read_text(encoding="utf-8"))
    if event_id is not None:
        body["event_id"] = event_id
    return VesselTrackingEventIn.model_validate(body)


def repository():
    assert DSN is not None
    repo = PostgresDeviceRepository(DSN)
    repo.create_device(DeviceAuthRecord("pecem-01", "hash", "view"))
    accepted = repo.accept_vessel_tracking_event_atomic(
        "pecem-01", event()
    )
    assert accepted.stored is not None
    assert repo.upsert_push_installation(
        "pecem-01",
        INSTALL,
        endpoint="https://push.example/a",
        p256dh="p",
        auth="a",
    ) is not None
    return repo, accepted.stored


def test_postgres_tracking_delivery_claim_retry_and_terminal_dedupe():
    repo, stored = repository()
    event_id = stored.event.event_id

    assert repo.claim_tracking_push_delivery(
        event_id, INSTALL, lease_seconds=8
    ) is True
    assert repo.claim_tracking_push_delivery(
        event_id, INSTALL, lease_seconds=8
    ) is False

    repo.set_tracking_push_delivery_status(
        event_id,
        INSTALL,
        TrackingPushDeliveryStatus.RETRY_PENDING,
    )
    assert repo.claim_tracking_push_delivery(
        event_id, INSTALL, lease_seconds=8
    ) is True

    repo.set_tracking_push_delivery_status(
        event_id,
        INSTALL,
        TrackingPushDeliveryStatus.DELIVERED,
    )
    delivery = repo.get_tracking_push_delivery(event_id, INSTALL)

    assert delivery is not None
    assert delivery.status is TrackingPushDeliveryStatus.DELIVERED
    assert repo.claim_tracking_push_delivery(
        event_id, INSTALL, lease_seconds=8
    ) is False


def test_postgres_tracking_delivery_claim_rejects_inactive_push_installation():
    repo, _stored = repository()
    second = repo.accept_vessel_tracking_event_atomic(
        "pecem-01",
        event("93000000-0000-4000-8000-000000000099"),
    )
    assert second.stored is not None
    assert repo.deactivate_push_installation("pecem-01", INSTALL) is True

    claimed = repo.claim_tracking_push_delivery(
        second.stored.event.event_id,
        INSTALL,
    )

    assert claimed is False
    assert repo.get_tracking_push_delivery(
        second.stored.event.event_id,
        INSTALL,
    ) is None
