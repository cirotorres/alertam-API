from __future__ import annotations

import json
from uuid import UUID

import httpx

from app.repositories.supabase import SupabaseDeviceRepository
from app.repositories.tracking import TrackingPushDeliveryStatus


INSTALL = UUID("92000000-0000-4000-8000-000000000001")
EVENT = "92000000-0000-4000-8000-000000000002"


def test_supabase_tracking_delivery_uses_dedicated_rpcs_and_table():
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST":
            calls.append((request.url.path, json.loads(request.content)))
        if request.url.path.endswith("/rpc/claim_vessel_tracking_delivery"):
            return httpx.Response(200, json=[{"claimed": True}])
        if request.url.path.endswith(
            "/rpc/set_vessel_tracking_delivery_status"
        ):
            return httpx.Response(200, json=[{"updated": True}])
        if request.url.path.endswith("/vessel_tracking_deliveries"):
            return httpx.Response(200, json=[{
                "event_id": EVENT,
                "installation_id": str(INSTALL),
                "status": "DELIVERED",
                "claimed_at": "2026-09-29T02:30:00Z",
                "updated_at": "2026-09-29T02:31:00Z",
            }])
        raise AssertionError(str(request.url))

    repo = SupabaseDeviceRepository(
        "https://example.supabase.co",
        "sb_secret_backend",
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    assert repo.claim_tracking_push_delivery(
        EVENT, INSTALL, lease_seconds=8
    ) is True
    repo.set_tracking_push_delivery_status(
        EVENT,
        INSTALL,
        TrackingPushDeliveryStatus.DELIVERED,
    )
    delivery = repo.get_tracking_push_delivery(EVENT, INSTALL)

    assert delivery is not None
    assert delivery.status is TrackingPushDeliveryStatus.DELIVERED
    assert calls[0][0].endswith("/rpc/claim_vessel_tracking_delivery")
    assert calls[0][1]["p_lease_seconds"] == 8
    assert calls[1][0].endswith(
        "/rpc/set_vessel_tracking_delivery_status"
    )
    assert calls[1][1]["p_status"] == "DELIVERED"
