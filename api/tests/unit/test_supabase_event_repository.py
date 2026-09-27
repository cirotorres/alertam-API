from __future__ import annotations

import json

import httpx

from app.models.maneuver_event import ManeuverEventIn
from app.repositories.events import AcceptEventStatus
from app.repositories.supabase import SupabaseDeviceRepository


def event() -> ManeuverEventIn:
    return ManeuverEventIn.model_validate({
        "event_id": "00000000-0000-4000-8000-000000000302",
        "maneuver_id": "00000000-0000-4000-8000-000000000301",
        "vessel_identity": "NAME:NAVIO A",
        "vessel_imo": None,
        "vessel_name": "NAVIO A",
        "maneuver_type": "DESATRACACAO",
        "event_type": "COMPLETED",
        "berth": 4,
        "pob": None,
        "occurred_at": "2026-09-27T10:05:00-03:00",
        "changes": None,
    })


def test_accept_event_calls_rpc_and_parses_stored_metadata():
    observed = {}

    def handler(request: httpx.Request) -> httpx.Response:
        observed["path"] = request.url.path
        observed["body"] = json.loads(request.content)
        return httpx.Response(200, json=[{
            "status": "accepted",
            "ingestion_id": 7,
            "ingested_at": "2026-09-27T13:05:01-03:00",
            "event_payload": event().canonical_payload(),
        }])

    repo = SupabaseDeviceRepository(
        "https://example.supabase.co",
        "sb_secret_backend",
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    result = repo.accept_maneuver_event_atomic("pecem-01", event())

    assert observed["path"] == "/rest/v1/rpc/accept_maneuver_event"
    assert observed["body"] == {
        "p_device_id": "pecem-01",
        "p_event": event().canonical_payload(),
    }
    assert result.status is AcceptEventStatus.ACCEPTED
    assert result.stored is not None
    assert result.stored.ingestion_id == 7


def test_list_events_uses_postgrest_cursor_and_normalizes_desc_page():
    observed = {}

    def handler(request: httpx.Request) -> httpx.Response:
        observed["params"] = dict(request.url.params)
        payload = event().canonical_payload()
        return httpx.Response(200, json=[
            {
                "ingestion_id": 9,
                "device_id": "pecem-01",
                "event_payload": payload,
                "ingested_at": "2026-09-27T13:05:09-03:00",
            },
            {
                "ingestion_id": 8,
                "device_id": "pecem-01",
                "event_payload": payload,
                "ingested_at": "2026-09-27T13:05:08-03:00",
            },
        ])

    repo = SupabaseDeviceRepository(
        "https://example.supabase.co",
        "sb_secret_backend",
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    page = repo.list_maneuver_events("pecem-01", before=10, limit=2)

    assert observed["params"]["device_id"] == "eq.pecem-01"
    assert observed["params"]["ingestion_id"] == "lt.10"
    assert observed["params"]["order"] == "ingestion_id.desc"
    assert [item.ingestion_id for item in page.events] == [8, 9]
