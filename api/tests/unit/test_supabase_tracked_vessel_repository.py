from uuid import UUID

import httpx

from app.repositories.supabase import SupabaseDeviceRepository
from app.repositories.tracking import VesselEvidence


TRACK_ID = UUID("30000000-0000-4000-8000-000000000001")
INSTALL = UUID("20000000-0000-4000-8000-000000000001")
CURRENT = {
    "present": True,
    "status": "PREVISTO",
    "section": "PREVISTO",
    "berth": 4,
    "side": "BB",
    "eta": "28/09 12:30",
    "etb_ets": "28/09 13:00",
    "pob": None,
    "pob_at": None,
}


def row(active=True):
    return {
        "tracked_vessel_id": str(TRACK_ID),
        "device_id": "pecem-01",
        "installation_id": str(INSTALL),
        "vessel_identity": "IMO:1234567",
        "vessel_imo": "1234567",
        "vessel_name": "NAVIO A",
        "started_at": "2026-09-28T23:10:00Z",
        "active": active,
        "stopped_at": None if active else "2026-09-28T23:20:00Z",
        "last_seen_at": "2026-09-28T23:10:00Z",
        "current": CURRENT,
    }


def test_supabase_tracked_vessel_crud_contract():
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        path = request.url.path
        if path.endswith("/rpc/upsert_tracked_vessel"):
            return httpx.Response(200, json=[row()])
        if path.endswith("/rpc/deactivate_tracked_vessel"):
            return httpx.Response(200, json=[row(False)])
        if path.endswith("/tracked_vessels"):
            return httpx.Response(200, json=[row()])
        raise AssertionError(path)

    repo = SupabaseDeviceRepository(
        "https://example.supabase.co",
        "sb_secret_backend",
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    evidence = VesselEvidence(
        vessel_identity="IMO:1234567",
        vessel_imo="1234567",
        vessel_name="NAVIO A",
        current=CURRENT,
        observed_at=None,
    )

    created = repo.upsert_tracked_vessel("pecem-01", INSTALL, evidence)
    listed = repo.list_tracked_vessels("pecem-01", INSTALL)
    loaded = repo.get_tracked_vessel("pecem-01", INSTALL, TRACK_ID)
    stopped = repo.deactivate_tracked_vessel("pecem-01", INSTALL, TRACK_ID)

    assert created is not None and created.tracked_vessel_id == TRACK_ID
    assert listed == (created,)
    assert loaded == created
    assert stopped is not None and stopped.active is False
    assert any(
        request.url.path.endswith("/rpc/upsert_tracked_vessel")
        for request in calls
    )
