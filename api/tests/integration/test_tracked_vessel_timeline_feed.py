from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import UUID

from fastapi.testclient import TestClient

from app.main import create_app
from app.models.vessel_tracking_event import VesselTrackingEventIn
from app.repositories.devices import DeviceAuthRecord, StoredSnapshot
from app.repositories.memory import MemoryDeviceRepository
from app.security.credentials import hash_secret


DEVICE = "pecem-01"
DEVICE_SECRET = "D" * 43
VIEW_SECRET = "V" * 43
INSTALL_A = "40000000-0000-4000-8000-000000000001"
INSTALL_B = "40000000-0000-4000-8000-000000000002"
NOW = datetime(2026, 9, 28, 9, 0, tzinfo=timezone(timedelta(hours=-3)))
SNAPSHOT = Path(__file__).parents[1] / "fixtures" / "mobile_snapshot_v1.json"
TRACKING_EVENT = Path(__file__).parents[1] / "fixtures" / "vessel_tracking_event_v1.json"


def repository():
    repo = MemoryDeviceRepository(clock=lambda: NOW)
    repo.create_device(
        DeviceAuthRecord(
            DEVICE,
            hash_secret(DEVICE_SECRET),
            hash_secret(VIEW_SECRET),
        )
    )
    raw = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    repo.put_snapshot(StoredSnapshot(
        device_id=DEVICE,
        snapshot=raw,
        snapshot_schema_version=1,
        boot_id=UUID(raw["boot_id"]),
        sequence=raw["sequence"],
        generated_at=datetime.fromisoformat(raw["generated_at"]),
        received_at=NOW,
    ))
    return repo


def session_client(repo, installation_id=INSTALL_A):
    client = TestClient(create_app(repository=repo))
    response = client.post(
        "/api/v1/mobile/session",
        headers={"Authorization": f"Bearer {VIEW_SECRET}"},
        json={"device_id": DEVICE, "installation_id": installation_id},
    )
    assert response.status_code == 200
    return client


def start_tracking(client):
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


def tracking_payload(
    *,
    event_id="50000000-0000-4000-8000-000000000001",
    occurred_at="2026-09-28T10:02:00-03:00",
    eta="28/09 12:30",
    side="BE",
    vessel_identity="IMO:1234567",
    vessel_imo="1234567",
    vessel_name="NAVIO A",
):
    raw = json.loads(TRACKING_EVENT.read_text(encoding="utf-8"))
    raw["event_id"] = event_id
    raw["occurred_at"] = occurred_at
    raw["first_observed_at"] = occurred_at
    raw["vessel_identity"] = vessel_identity
    raw["vessel_imo"] = vessel_imo
    raw["vessel_name"] = vessel_name
    raw["changes"]["eta"]["to"] = eta
    raw["changes"]["side"]["to"] = side
    raw["current"]["eta"] = eta
    raw["current"]["side"] = side
    return raw


def maneuver_payload(
    *,
    event_id="51000000-0000-4000-8000-000000000001",
    occurred_at="2026-09-28T10:03:00-03:00",
    berth=5,
    pob="28/09 10:30",
):
    return {
        "event_id": event_id,
        "maneuver_id": "51000000-0000-4000-8000-000000000100",
        "vessel_identity": "IMO:1234567",
        "vessel_imo": "1234567",
        "vessel_name": "NAVIO A",
        "maneuver_type": "ATRACACAO",
        "event_type": "UPDATED",
        "berth": berth,
        "pob": pob,
        "occurred_at": occurred_at,
        "pob_at": "2026-09-28T10:30:00-03:00",
        "first_observed_at": occurred_at,
        "changes": {
            "pob": {"from": "28/09 10:00", "to": pob},
            "berth": {"from": 4, "to": berth},
        },
    }


def post_tracking_event(client, payload):
    return client.post(
        f"/api/v1/devices/{DEVICE}/vessel-tracking-events",
        headers={"Authorization": f"Device {DEVICE_SECRET}"},
        json=payload,
    )


def post_maneuver_event(client, payload):
    return client.post(
        f"/api/v1/devices/{DEVICE}/maneuver-events",
        headers={"Authorization": f"Device {DEVICE_SECRET}"},
        json=payload,
    )


def test_tracking_and_maneuver_events_update_current_projection_without_regression():
    repo = repository()
    client = session_client(repo)
    tracked = start_tracking(client)

    assert post_tracking_event(
        client,
        tracking_payload(),
    ).status_code == 200

    current = client.get("/api/v1/mobile/tracked-vessels").json()[0]
    assert current["current"]["eta"] == "28/09 12:30"
    assert current["current"]["side"] == "BE"
    assert current["last_seen_at"] == "2026-09-28T10:02:00-03:00"

    assert post_maneuver_event(
        client,
        maneuver_payload(),
    ).status_code == 200

    current = client.get("/api/v1/mobile/tracked-vessels").json()[0]
    assert current["tracked_vessel_id"] == tracked["tracked_vessel_id"]
    assert current["current"]["eta"] == "28/09 12:30"
    assert current["current"]["side"] == "BE"
    assert current["current"]["berth"] == 5
    assert current["current"]["pob"] == "28/09 10:30"
    assert current["last_seen_at"] == "2026-09-28T10:03:00-03:00"

    older = tracking_payload(
        event_id="50000000-0000-4000-8000-000000000002",
        occurred_at="2026-09-28T09:30:00-03:00",
        eta="28/09 11:00",
    )
    assert post_tracking_event(client, older).status_code == 200

    current = client.get("/api/v1/mobile/tracked-vessels").json()[0]
    assert current["current"]["eta"] == "28/09 12:30"
    assert current["last_seen_at"] == "2026-09-28T10:03:00-03:00"


def test_timeline_unifies_retained_events_before_and_after_tracking_start():
    repo = repository()
    pre = VesselTrackingEventIn.model_validate(
        tracking_payload(
            event_id="50000000-0000-4000-8000-000000000010",
            occurred_at="2026-09-28T08:30:00-03:00",
            eta="28/09 11:30",
        )
    )
    repo.accept_vessel_tracking_event_atomic(DEVICE, pre)
    client = session_client(repo)
    tracked = start_tracking(client)

    assert post_tracking_event(
        client,
        tracking_payload(
            event_id="50000000-0000-4000-8000-000000000011",
            occurred_at="2026-09-28T10:00:00-03:00",
        ),
    ).status_code == 200
    assert post_maneuver_event(
        client,
        maneuver_payload(
            event_id="51000000-0000-4000-8000-000000000011",
            occurred_at="2026-09-28T10:01:00-03:00",
        ),
    ).status_code == 200

    response = client.get(
        f"/api/v1/mobile/tracked-vessels/{tracked['tracked_vessel_id']}/events"
    )

    assert response.status_code == 200
    body = response.json()
    assert body["tracked_vessel_id"] == tracked["tracked_vessel_id"]
    assert [item["kind"] for item in body["events"]] == [
        "TRACKING",
        "TRACKING",
        "MANEUVER",
    ]
    assert [item["event"]["event_id"] for item in body["events"]] == [
        "50000000-0000-4000-8000-000000000010",
        "50000000-0000-4000-8000-000000000011",
        "51000000-0000-4000-8000-000000000011",
    ]


def test_other_installation_cannot_read_tracking_timeline():
    repo = repository()
    a = session_client(repo, INSTALL_A)
    tracked = start_tracking(a)
    b = session_client(repo, INSTALL_B)

    response = b.get(
        f"/api/v1/mobile/tracked-vessels/{tracked['tracked_vessel_id']}/events"
    )

    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "tracked_vessel_not_found"


def test_foreground_feed_baselines_cursor_filters_started_at_and_advances_over_irrelevant_events():
    repo = repository()
    client = session_client(repo)
    pre = VesselTrackingEventIn.model_validate(
        tracking_payload(
            event_id="50000000-0000-4000-8000-000000000020",
            occurred_at="2026-09-28T08:30:00-03:00",
        )
    )
    repo.accept_vessel_tracking_event_atomic(DEVICE, pre)
    tracked = start_tracking(client)

    baseline = client.get("/api/v1/mobile/tracked-vessels/events")
    assert baseline.status_code == 200
    assert baseline.json() == {"events": [], "newest_cursor": 1}

    eligible = tracking_payload(
        event_id="50000000-0000-4000-8000-000000000021",
        occurred_at=NOW.isoformat(),
    )
    assert post_tracking_event(client, eligible).status_code == 200

    irrelevant = tracking_payload(
        event_id="50000000-0000-4000-8000-000000000022",
        occurred_at="2026-09-28T09:01:00-03:00",
        vessel_identity="IMO:7654321",
        vessel_imo="7654321",
        vessel_name="OUTRO NAVIO",
    )
    assert post_tracking_event(client, irrelevant).status_code == 200

    feed = client.get(
        "/api/v1/mobile/tracked-vessels/events?after=1&limit=50"
    )
    assert feed.status_code == 200
    body = feed.json()
    assert body["newest_cursor"] == 3
    assert len(body["events"]) == 1
    assert body["events"][0]["tracked_vessel_id"] == tracked["tracked_vessel_id"]
    assert body["events"][0]["event"]["event_id"] == eligible["event_id"]


def test_stopped_tracking_gets_no_new_foreground_events_but_timeline_remains_available():
    repo = repository()
    client = session_client(repo)
    tracked = start_tracking(client)
    baseline = client.get("/api/v1/mobile/tracked-vessels/events").json()
    cursor = baseline["newest_cursor"]

    path = f"/api/v1/mobile/tracked-vessels/{tracked['tracked_vessel_id']}"
    assert client.delete(path).status_code == 204

    event = tracking_payload(
        event_id="50000000-0000-4000-8000-000000000030",
        occurred_at="2026-09-28T10:30:00-03:00",
    )
    assert post_tracking_event(client, event).status_code == 200

    query = (
        "/api/v1/mobile/tracked-vessels/events"
        if cursor is None
        else f"/api/v1/mobile/tracked-vessels/events?after={cursor}"
    )
    feed = client.get(query).json()
    assert feed["events"] == []

    timeline = client.get(
        f"/api/v1/mobile/tracked-vessels/{tracked['tracked_vessel_id']}/events"
    )
    assert timeline.status_code == 200
    assert any(
        item["event"]["event_id"] == event["event_id"]
        for item in timeline.json()["events"]
    )


def test_foreground_feed_full_page_advances_only_to_last_delivered_event():
    repo = repository()
    client = session_client(repo)
    start_tracking(client)

    for index in range(1, 5):
        payload = tracking_payload(
            event_id=f"50000000-0000-4000-8000-{100 + index:012d}",
            occurred_at=f"2026-09-28T09:0{index}:00-03:00",
            eta=f"28/09 12:3{index}",
        )
        assert post_tracking_event(client, payload).status_code == 200

    first = client.get(
        "/api/v1/mobile/tracked-vessels/events?after=1&limit=2"
    ).json()

    assert len(first["events"]) == 2
    assert first["newest_cursor"] == first["events"][-1]["ingestion_id"]
    assert first["newest_cursor"] < 4

    second = client.get(
        f"/api/v1/mobile/tracked-vessels/events?after={first['newest_cursor']}&limit=2"
    ).json()
    assert [item["event"]["event_id"] for item in second["events"]] == [
        "50000000-0000-4000-8000-000000000104"
    ]
    assert second["newest_cursor"] == 4


def test_empty_tracking_feed_baseline_returns_zero_and_after_zero_reads_first_future_event():
    repo = repository()
    client = session_client(repo)
    tracked = start_tracking(client)

    baseline = client.get("/api/v1/mobile/tracked-vessels/events")
    assert baseline.status_code == 200
    assert baseline.json() == {"events": [], "newest_cursor": 0}

    first = tracking_payload(
        event_id="50000000-0000-4000-8000-000000000999",
        occurred_at="2026-09-28T10:45:00-03:00",
    )
    assert post_tracking_event(client, first).status_code == 200

    feed = client.get(
        "/api/v1/mobile/tracked-vessels/events?after=0&limit=50"
    )
    assert feed.status_code == 200
    assert feed.json()["newest_cursor"] == 1
    assert feed.json()["events"][0]["tracked_vessel_id"] == tracked[
        "tracked_vessel_id"
    ]
    assert feed.json()["events"][0]["event"]["event_id"] == first["event_id"]
