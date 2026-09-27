from __future__ import annotations

import json
from uuid import UUID

import httpx

from app.repositories.events import PushDeliveryStatus, PushPreferences
from app.repositories.supabase import SupabaseDeviceRepository


INSTALL = UUID("40000000-0000-4000-8000-000000000001")
EVENT = "40000000-0000-4000-8000-000000000002"


def installation_row(active: bool = True):
    return {
        "installation_id": str(INSTALL),
        "device_id": "pecem-01",
        "endpoint": "https://push.example/a" if active else None,
        "p256dh": "p" if active else None,
        "auth": "a" if active else None,
        "pref_confirmed": True,
        "pref_updated": True,
        "pref_completed": True,
        "pref_cancelled": True,
        "push_enabled_at": "2026-09-27T16:00:00+00:00",
        "last_seen_at": "2026-09-27T16:00:00+00:00",
        "last_foreground_at": None,
        "active": active,
        "created_at": "2026-09-27T16:00:00+00:00",
        "updated_at": "2026-09-27T16:00:00+00:00",
    }


def test_upsert_push_installation_calls_rpc_without_device_override():
    observed = {}

    def handler(request: httpx.Request) -> httpx.Response:
        observed["path"] = request.url.path
        observed["body"] = json.loads(request.content)
        return httpx.Response(200, json=[installation_row()])

    repo = SupabaseDeviceRepository(
        "https://example.supabase.co",
        "sb_secret_backend",
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    result = repo.upsert_push_installation(
        "pecem-01",
        INSTALL,
        endpoint="https://push.example/a",
        p256dh="p",
        auth="a",
    )

    assert observed["path"] == "/rest/v1/rpc/upsert_push_installation"
    assert observed["body"]["p_device_id"] == "pecem-01"
    assert observed["body"]["p_installation_id"] == str(INSTALL)
    assert result is not None
    assert result.preferences == PushPreferences()


def test_claim_and_status_use_push_delivery_rpcs():
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append((request.url.path, json.loads(request.content)))
        if request.url.path.endswith("claim_push_delivery"):
            return httpx.Response(200, json=[{"claimed": True}])
        return httpx.Response(200, json=[{"updated": True}])

    repo = SupabaseDeviceRepository(
        "https://example.supabase.co",
        "sb_secret_backend",
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    assert repo.claim_push_delivery(EVENT, INSTALL, lease_seconds=8) is True
    repo.set_push_delivery_status(
        EVENT,
        INSTALL,
        PushDeliveryStatus.RETRY_PENDING,
    )

    assert calls[0][0].endswith("/rpc/claim_push_delivery")
    assert calls[0][1]["p_lease_seconds"] == 8
    assert calls[1][0].endswith("/rpc/set_push_delivery_status")
    assert calls[1][1]["p_status"] == "RETRY_PENDING"


def test_update_preferences_serializes_four_independent_flags():
    observed = {}

    def handler(request: httpx.Request) -> httpx.Response:
        observed["body"] = json.loads(request.content)
        row = installation_row()
        row["pref_confirmed"] = False
        return httpx.Response(200, json=[row])

    repo = SupabaseDeviceRepository(
        "https://example.supabase.co",
        "sb_secret_backend",
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    result = repo.update_push_preferences(
        "pecem-01",
        INSTALL,
        PushPreferences(
            confirmed=False,
            updated=True,
            completed=True,
            cancelled=True,
        ),
    )

    assert observed["body"]["p_confirmed"] is False
    assert observed["body"]["p_updated"] is True
    assert result is not None
    assert result.preferences.confirmed is False
