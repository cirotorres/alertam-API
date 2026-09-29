import json
from pathlib import Path

import httpx

from app.models.vessel_tracking_event import VesselTrackingEventIn
from app.repositories.supabase import SupabaseDeviceRepository
from app.repositories.tracking import AcceptTrackingEventStatus


FIXTURE = Path(__file__).parents[1] / "fixtures" / "vessel_tracking_event_v1.json"


def event():
    return VesselTrackingEventIn.model_validate(
        json.loads(FIXTURE.read_text(encoding="utf-8"))
    )


def test_supabase_accept_tracking_event_calls_dedicated_rpc():
    observed = {}

    def handler(request: httpx.Request) -> httpx.Response:
        observed["path"] = request.url.path
        observed["body"] = json.loads(request.content)
        return httpx.Response(200, json=[{
            "status": "accepted",
            "ingestion_id": 17,
            "ingested_at": "2026-09-28T13:02:01-03:00",
            "event_payload": event().canonical_payload(),
        }])

    repository = SupabaseDeviceRepository(
        "https://example.supabase.co",
        "sb_secret_backend",
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    result = repository.accept_vessel_tracking_event_atomic(
        "pecem-01", event()
    )

    assert observed["path"] == "/rest/v1/rpc/accept_vessel_tracking_event"
    assert observed["body"] == {
        "p_device_id": "pecem-01",
        "p_event": event().canonical_payload(),
    }
    assert result.status is AcceptTrackingEventStatus.ACCEPTED
    assert result.stored is not None
    assert result.stored.ingestion_id == 17
