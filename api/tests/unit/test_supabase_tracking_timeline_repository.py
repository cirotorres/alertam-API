import json
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID

import httpx

from app.repositories.supabase import SupabaseDeviceRepository


FIXTURES = Path(__file__).parents[1] / "fixtures"
TRACKED_ID = UUID("70000000-0000-4000-8000-000000000001")
INSTALL_ID = UUID("70000000-0000-4000-8000-000000000002")
TRACKING = json.loads(
    (FIXTURES / "vessel_tracking_event_v1.json").read_text(encoding="utf-8")
)
MANEUVER = json.loads(
    (FIXTURES / "maneuver_event_v1.json").read_text(encoding="utf-8")
)


def test_supabase_projection_timeline_cursor_and_feed_contract():
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        path = request.url.path
        if path.endswith("/rpc/project_tracked_vessels"):
            return httpx.Response(200, json=1)
        if path.endswith("/rpc/list_tracked_vessel_timeline"):
            return httpx.Response(200, json=[
                {
                    "kind": "TRACKING",
                    "ingestion_id": 4,
                    "ingested_at": "2026-09-28T13:02:00Z",
                    "event_payload": TRACKING,
                },
                {
                    "kind": "MANEUVER",
                    "ingestion_id": 8,
                    "ingested_at": "2026-09-28T13:03:00Z",
                    "event_payload": MANEUVER,
                },
            ])
        if path.endswith("/vessel_tracking_events"):
            return httpx.Response(200, json=[{"ingestion_id": 9}])
        if path.endswith("/rpc/list_installation_tracking_events"):
            return httpx.Response(200, json=[{
                "tracked_vessel_id": str(TRACKED_ID),
                "ingestion_id": 9,
                "ingested_at": "2026-09-28T13:04:00Z",
                "event_payload": TRACKING,
            }])
        raise AssertionError(path)

    repo = SupabaseDeviceRepository(
        "https://example.supabase.co",
        "sb_secret_backend",
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    projected = repo.project_tracked_vessels(
        "pecem-01",
        vessel_identity="IMO:1234567",
        vessel_imo="1234567",
        vessel_name="NAVIO A",
        observed_at=datetime(2026, 9, 28, 13, 0, tzinfo=timezone.utc),
        replace_current=True,
        current=TRACKING["current"],
    )
    timeline = repo.list_tracked_vessel_event_records(
        "pecem-01", INSTALL_ID, TRACKED_ID
    )
    cursor = repo.latest_tracking_event_cursor("pecem-01")
    feed = repo.list_installation_tracking_events(
        "pecem-01", INSTALL_ID, after=8, limit=50
    )

    assert projected == 1
    assert [item.kind for item in timeline] == ["TRACKING", "MANEUVER"]
    assert cursor == 9
    assert len(feed) == 1
    assert feed[0].tracked_vessel_id == TRACKED_ID
    assert feed[0].stored.ingestion_id == 9

    project_request = next(
        request for request in calls
        if request.url.path.endswith("/rpc/project_tracked_vessels")
    )
    body = json.loads(project_request.content)
    assert body["p_replace_current"] is True
    assert body["p_vessel_identity"] == "IMO:1234567"

    feed_request = next(
        request for request in calls
        if request.url.path.endswith("/rpc/list_installation_tracking_events")
    )
    assert json.loads(feed_request.content)["p_after"] == 8
