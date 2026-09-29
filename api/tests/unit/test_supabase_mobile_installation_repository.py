from uuid import UUID

import httpx

from app.repositories.supabase import SupabaseDeviceRepository


INSTALL = UUID("10000000-0000-4000-8000-000000000001")


def test_supabase_mobile_installation_repository_uses_rpc_and_scoped_get():
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        if request.url.path.endswith("/rpc/ensure_mobile_installation"):
            return httpx.Response(200, json=[{
                "installation_id": str(INSTALL),
                "device_id": "pecem-01",
                "active": True,
                "created_at": "2026-09-28T23:00:00Z",
                "last_seen_at": "2026-09-28T23:00:00Z",
                "revoked_at": None,
            }])
        if request.url.path.endswith("/mobile_installations"):
            return httpx.Response(200, json=[{
                "installation_id": str(INSTALL),
                "device_id": "pecem-01",
                "active": True,
                "created_at": "2026-09-28T23:00:00Z",
                "last_seen_at": "2026-09-28T23:00:00Z",
                "revoked_at": None,
            }])
        if request.url.path.endswith("/rpc/revoke_mobile_installation"):
            return httpx.Response(200, json=[{"updated": True}])
        raise AssertionError(str(request.url))

    repo = SupabaseDeviceRepository(
        "https://example.supabase.co",
        "sb_secret_backend",
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    ensured = repo.ensure_mobile_installation("pecem-01", INSTALL)
    loaded = repo.get_mobile_installation("pecem-01", INSTALL)
    revoked = repo.revoke_mobile_installation("pecem-01", INSTALL)

    assert ensured == loaded
    assert revoked is True
    get_request = next(
        request for request in calls
        if request.url.path.endswith("/mobile_installations")
    )
    params = dict(get_request.url.params)
    assert params["device_id"] == "eq.pecem-01"
    assert params["installation_id"] == f"eq.{INSTALL}"
