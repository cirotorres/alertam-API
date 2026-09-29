from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import UUID

import psycopg
import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.repositories.devices import (
    DeviceAuthRecord,
    SnapshotCandidate,
)
from app.repositories.postgres import PostgresDeviceRepository
from app.security.credentials import hash_secret


DSN = os.getenv("TEST_POSTGRES_DSN")
MIGRATIONS = Path(__file__).parents[2] / "supabase" / "migrations"
SNAPSHOT = Path(__file__).parents[1] / "fixtures" / "mobile_snapshot_v1.json"
TRACKING = Path(__file__).parents[1] / "fixtures" / "vessel_tracking_event_v1.json"
DEVICE = "pecem-01"
DEVICE_SECRET = "D" * 43
VIEW_SECRET = "V" * 43
INSTALL_A = "80000000-0000-4000-8000-000000000001"
INSTALL_B = "80000000-0000-4000-8000-000000000002"
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
            "002_accept_snapshot_rpc.sql",
            "004_maneuver_events.sql",
            "005_push_installations_deliveries.sql",
            "008_vessel_tracking_events.sql",
            "010_mobile_installations.sql",
            "011_tracked_vessels.sql",
        ):
            conn.execute((MIGRATIONS / name).read_text(encoding="utf-8"))
    yield


def setup_repo():
    assert DSN is not None
    repo = PostgresDeviceRepository(DSN)
    repo.create_device(DeviceAuthRecord(
        DEVICE,
        hash_secret(DEVICE_SECRET),
        hash_secret(VIEW_SECRET),
    ))
    raw = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    repo.accept_snapshot_atomic(SnapshotCandidate(
        device_id=DEVICE,
        snapshot=raw,
        snapshot_schema_version=1,
        boot_id=UUID(raw["boot_id"]),
        sequence=raw["sequence"],
        generated_at=datetime.fromisoformat(raw["generated_at"]),
    ))
    return repo


def session(client, installation_id):
    response = client.post(
        "/api/v1/mobile/session",
        headers={"Authorization": f"Bearer {VIEW_SECRET}"},
        json={"device_id": DEVICE, "installation_id": installation_id},
    )
    assert response.status_code == 200


def start(client):
    response = client.post(
        "/api/v1/mobile/tracked-vessels",
        json={
            "vessel_identity": "IMO:1234567",
            "vessel_imo": "1234567",
            "vessel_name": "NAVIO A",
        },
    )
    assert response.status_code == 200
    return response.json()


def tracking_payload(event_id, occurred_at, *, vessel_imo="1234567", name="NAVIO A"):
    raw = json.loads(TRACKING.read_text(encoding="utf-8"))
    raw["event_id"] = event_id
    raw["occurred_at"] = occurred_at.isoformat()
    raw["first_observed_at"] = occurred_at.isoformat()
    raw["vessel_imo"] = vessel_imo
    raw["vessel_name"] = name
    raw["vessel_identity"] = (
        f"IMO:{vessel_imo}"
        if vessel_imo is not None
        else f"NAME:{' '.join(name.upper().split())}"
    )
    return raw


def maneuver_payload(event_id, occurred_at):
    return {
        "event_id": event_id,
        "maneuver_id": "81000000-0000-4000-8000-000000000100",
        "vessel_identity": "IMO:1234567",
        "vessel_imo": "1234567",
        "vessel_name": "NAVIO A",
        "maneuver_type": "ATRACACAO",
        "event_type": "UPDATED",
        "berth": 5,
        "pob": "29/09 02:00",
        "occurred_at": occurred_at.isoformat(),
        "pob_at": occurred_at.isoformat(),
        "first_observed_at": occurred_at.isoformat(),
        "changes": {
            "pob": {"from": None, "to": "29/09 02:00"},
            "berth": {"from": 2, "to": 5},
        },
    }


def post_tracking(client, body):
    return client.post(
        f"/api/v1/devices/{DEVICE}/vessel-tracking-events",
        headers={"Authorization": f"Device {DEVICE_SECRET}"},
        json=body,
    )


def post_maneuver(client, body):
    return client.post(
        f"/api/v1/devices/{DEVICE}/maneuver-events",
        headers={"Authorization": f"Device {DEVICE_SECRET}"},
        json=body,
    )


def test_postgres_projection_timeline_and_foreground_feed_end_to_end():
    repo = setup_repo()
    client = TestClient(create_app(repository=repo))
    now = datetime.now(timezone.utc)

    pre = tracking_payload(
        "82000000-0000-4000-8000-000000000001",
        now - timedelta(minutes=2),
    )
    assert repo.accept_vessel_tracking_event_atomic(
        DEVICE,
        __import__(
            "app.models.vessel_tracking_event",
            fromlist=["VesselTrackingEventIn"],
        ).VesselTrackingEventIn.model_validate(pre),
    ).stored is not None

    session(client, INSTALL_A)
    tracked = start(client)

    baseline = client.get("/api/v1/mobile/tracked-vessels/events").json()
    assert baseline == {"events": [], "newest_cursor": 1}

    eligible_at = now + timedelta(minutes=1)
    eligible = tracking_payload(
        "82000000-0000-4000-8000-000000000002",
        eligible_at,
    )
    assert post_tracking(client, eligible).status_code == 200

    maneuver = maneuver_payload(
        "83000000-0000-4000-8000-000000000001",
        now + timedelta(minutes=2),
    )
    assert post_maneuver(client, maneuver).status_code == 200

    current = client.get("/api/v1/mobile/tracked-vessels").json()[0]
    assert current["current"]["eta"] == eligible["current"]["eta"]
    assert current["current"]["berth"] == 5
    assert current["current"]["pob"] == "29/09 02:00"

    irrelevant = tracking_payload(
        "82000000-0000-4000-8000-000000000003",
        now + timedelta(minutes=3),
        vessel_imo="7654321",
        name="OUTRO NAVIO",
    )
    assert post_tracking(client, irrelevant).status_code == 200

    feed = client.get(
        "/api/v1/mobile/tracked-vessels/events?after=1&limit=50"
    ).json()
    assert feed["newest_cursor"] == 3
    assert [item["event"]["event_id"] for item in feed["events"]] == [
        eligible["event_id"]
    ]

    timeline = client.get(
        f"/api/v1/mobile/tracked-vessels/{tracked['tracked_vessel_id']}/events"
    )
    assert timeline.status_code == 200
    assert [item["kind"] for item in timeline.json()["events"]] == [
        "TRACKING",
        "TRACKING",
        "MANEUVER",
    ]

    session_b = TestClient(create_app(repository=repo))
    session(session_b, INSTALL_B)
    denied = session_b.get(
        f"/api/v1/mobile/tracked-vessels/{tracked['tracked_vessel_id']}/events"
    )
    assert denied.status_code == 404

    assert client.delete(
        f"/api/v1/mobile/tracked-vessels/{tracked['tracked_vessel_id']}"
    ).status_code == 204

    after_stop = tracking_payload(
        "82000000-0000-4000-8000-000000000004",
        now + timedelta(minutes=4),
    )
    assert post_tracking(client, after_stop).status_code == 200
    stopped_feed = client.get(
        "/api/v1/mobile/tracked-vessels/events?after=3"
    ).json()
    assert stopped_feed["events"] == []
    assert stopped_feed["newest_cursor"] == 4

    stopped_timeline = client.get(
        f"/api/v1/mobile/tracked-vessels/{tracked['tracked_vessel_id']}/events"
    )
    assert stopped_timeline.status_code == 200
    assert any(
        item["event"]["event_id"] == after_stop["event_id"]
        for item in stopped_timeline.json()["events"]
    )
