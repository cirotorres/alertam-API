from datetime import datetime, timedelta, timezone
from uuid import UUID
import json

import httpx

from app.repositories.supabase import SupabaseDeviceRepository


INSTALL = UUID("10000000-0000-4000-8000-000000000001")
NOW = datetime(2026, 9, 28, 23, 0, tzinfo=timezone.utc)
SINCE = NOW - timedelta(days=30)
ROW = {
    "installation_id": str(INSTALL),
    "device_id": "pecem-01",
    "active": True,
    "created_at": "2026-09-28T23:00:00Z",
    "last_seen_at": "2026-09-28T23:00:00Z",
    "revoked_at": None,
    "platform": "ios",
    "display_code": "K7M4Q2",
}


def test_supabase_mobile_installation_repository_uses_rpc_and_scoped_get():
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        path = request.url.path
        if path.endswith("/rpc/ensure_mobile_installation"):
            return httpx.Response(200, json=[ROW])
        if path.endswith("/rpc/touch_mobile_installation"):
            return httpx.Response(200, json=[ROW])
        if path.endswith("/rpc/list_mobile_installations"):
            return httpx.Response(200, json=[ROW])
        if path.endswith("/mobile_installations"):
            return httpx.Response(200, json=[ROW])
        if path.endswith("/rpc/revoke_mobile_installation"):
            return httpx.Response(200, json=[{"updated": True}])
        raise AssertionError(str(request.url))

    repo = SupabaseDeviceRepository(
        "https://example.supabase.co",
        "sb_secret_backend",
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    ensured = repo.ensure_mobile_installation(
        "pecem-01",
        INSTALL,
        platform="ios",
        display_code="K7M4Q2",
    )
    loaded = repo.get_mobile_installation("pecem-01", INSTALL)
    touched = repo.touch_mobile_installation(
        "pecem-01",
        INSTALL,
        platform="android",
    )
    listed = repo.list_mobile_installations(
        "pecem-01",
        revoked_since=SINCE,
    )
    revoked = repo.revoke_mobile_installation("pecem-01", INSTALL)

    assert ensured == loaded == touched == listed[0]
    assert ensured is not None
    assert ensured.platform == "ios"
    assert ensured.display_code == "K7M4Q2"
    assert revoked is True

    ensure_request = next(
        request for request in calls
        if request.url.path.endswith("/rpc/ensure_mobile_installation")
    )
    assert json.loads(ensure_request.content) == {
        "p_device_id": "pecem-01",
        "p_installation_id": str(INSTALL),
        "p_platform": "ios",
        "p_display_code": "K7M4Q2",
    }

    touch_request = next(
        request for request in calls
        if request.url.path.endswith("/rpc/touch_mobile_installation")
    )
    assert json.loads(touch_request.content) == {
        "p_device_id": "pecem-01",
        "p_installation_id": str(INSTALL),
        "p_platform": "android",
    }

    list_request = next(
        request for request in calls
        if request.url.path.endswith("/rpc/list_mobile_installations")
    )
    assert json.loads(list_request.content) == {
        "p_device_id": "pecem-01",
        "p_revoked_since": SINCE.isoformat(),
    }

    get_request = next(
        request for request in calls
        if request.url.path.endswith("/mobile_installations")
    )
    params = dict(get_request.url.params)
    assert params["device_id"] == "eq.pecem-01"
    assert params["installation_id"] == f"eq.{INSTALL}"
    assert "platform" in params["select"]
    assert "display_code" in params["select"]


def test_supabase_maps_display_code_unique_violation():
    import pytest

    from app.repositories.devices import (
        MobileInstallationDisplayCodeConflictError,
    )

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            409,
            json={
                "code": "23505",
                "message": (
                    'duplicate key value violates unique constraint '
                    '"mobile_installations_display_code_unique"'
                ),
            },
        )

    repo = SupabaseDeviceRepository(
        "https://example.supabase.co",
        "sb_secret_backend",
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    with pytest.raises(MobileInstallationDisplayCodeConflictError):
        repo.ensure_mobile_installation(
            "pecem-01",
            INSTALL,
            platform="ios",
            display_code="K7M4Q2",
        )
