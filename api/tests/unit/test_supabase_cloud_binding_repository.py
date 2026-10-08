from __future__ import annotations

import json
from uuid import UUID

import httpx
import pytest

from app.repositories.cloud_bindings import CloudBindingConflictError, CloudBindingStatus
from app.repositories.devices import PersistenceUnavailableError
from app.repositories.supabase import SupabaseDeviceRepository


BINDING_ID = UUID("11111111-1111-1111-1111-111111111111")
REALM_ROW = {
    "realm_id": "webpilot-pecem",
    "active": True,
    "created_at": "2026-10-08T12:00:00Z",
    "updated_at": "2026-10-08T12:00:00Z",
}
AUTH_ROW = {
    "realm_id": "webpilot-pecem",
    "device_id": "pecem-01",
    "authorized_at": "2026-10-08T12:00:00Z",
    "revoked_at": None,
}
BINDING_ROW = {
    "cloud_binding_id": str(BINDING_ID),
    "device_id": "pecem-01",
    "realm_id": "webpilot-pecem",
    "credential_hash": "hash-v1",
    "credential_version": 1,
    "status": "active",
    "created_at": "2026-10-08T12:00:00Z",
    "updated_at": "2026-10-08T12:00:00Z",
    "revoked_at": None,
}


def test_supabase_cloud_binding_repository_uses_scoped_rest_and_rpc_payloads():
    calls: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        path = request.url.path
        if path.endswith("/webpilot_auth_realms"):
            if request.method == "POST":
                return httpx.Response(201, json=[REALM_ROW])
            return httpx.Response(200, json=[REALM_ROW])
        if path.endswith("/webpilot_auth_realm_devices"):
            return httpx.Response(200, json=[AUTH_ROW])
        if path.endswith("/cloud_bindings"):
            return httpx.Response(200, json=[BINDING_ROW])
        if path.endswith("/rpc/authorize_realm_device"):
            return httpx.Response(200, json=[AUTH_ROW])
        if path.endswith("/rpc/revoke_realm_device"):
            return httpx.Response(200, json=[{**AUTH_ROW, "revoked_at": "2026-10-08T12:01:00Z"}])
        if path.endswith("/rpc/set_webpilot_auth_realm_active"):
            payload = json.loads(request.content)
            return httpx.Response(200, json=[{**REALM_ROW, "active": payload["p_active"]}])
        if path.endswith("/rpc/ensure_cloud_binding"):
            return httpx.Response(200, json=[BINDING_ROW])
        if path.endswith("/rpc/rotate_cloud_binding"):
            return httpx.Response(200, json=[BINDING_ROW])
        if path.endswith("/rpc/revoke_cloud_binding"):
            return httpx.Response(200, json=[{**BINDING_ROW, "status": "revoked", "revoked_at": "2026-10-08T12:02:00Z"}])
        raise AssertionError(str(request.url))

    repo = SupabaseDeviceRepository(
        "https://example.supabase.co",
        "sb_secret_backend",
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    assert repo.ensure_webpilot_auth_realm("webpilot-pecem").active
    assert repo.get_webpilot_auth_realm("webpilot-pecem").active
    assert repo.authorize_realm_device("webpilot-pecem", "pecem-01").active
    assert repo.get_realm_device_authorization("webpilot-pecem", "pecem-01").active
    assert not repo.revoke_realm_device("webpilot-pecem", "pecem-01").active
    assert not repo.set_webpilot_auth_realm_active("webpilot-pecem", False).active

    binding = repo.ensure_cloud_binding("pecem-01", "webpilot-pecem", "hash-v1")
    assert binding is not None and binding.status is CloudBindingStatus.ACTIVE
    assert repo.rotate_cloud_binding("pecem-01", "hash-v2") is not None
    assert repo.get_active_cloud_binding("pecem-01") == binding
    assert repo.list_cloud_bindings("pecem-01") == (binding,)
    assert repo.revoke_cloud_binding("pecem-01").status is CloudBindingStatus.REVOKED

    ensure_request = next(r for r in calls if r.url.path.endswith("/rpc/ensure_cloud_binding"))
    assert json.loads(ensure_request.content) == {
        "p_device_id": "pecem-01",
        "p_realm_id": "webpilot-pecem",
        "p_credential_hash": "hash-v1",
    }


@pytest.mark.parametrize(
    ("operation", "suffix"),
    [
        (
            lambda repo: repo.set_webpilot_auth_realm_active(
                "webpilot-pecem",
                False,
            ),
            "/rpc/set_webpilot_auth_realm_active",
        ),
        (
            lambda repo: repo.authorize_realm_device(
                "webpilot-pecem",
                "pecem-01",
            ),
            "/rpc/authorize_realm_device",
        ),
        (
            lambda repo: repo.revoke_realm_device(
                "webpilot-pecem",
                "pecem-01",
            ),
            "/rpc/revoke_realm_device",
        ),
        (
            lambda repo: repo.ensure_cloud_binding(
                "pecem-01",
                "webpilot-pecem",
                "hash-v1",
            ),
            "/rpc/ensure_cloud_binding",
        ),
        (
            lambda repo: repo.rotate_cloud_binding(
                "pecem-01",
                "hash-v2",
            ),
            "/rpc/rotate_cloud_binding",
        ),
        (
            lambda repo: repo.revoke_cloud_binding("pecem-01"),
            "/rpc/revoke_cloud_binding",
        ),
    ],
)
def test_supabase_cloud_rpc_malformed_200_is_sanitized(
    operation,
    suffix,
):
    backend_detail = "backend-secret-payload"

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith(suffix)
        return httpx.Response(
            200,
            json=[{"unexpected": backend_detail}],
        )

    repo = SupabaseDeviceRepository(
        "https://example.supabase.co",
        "sb_secret_backend",
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    with pytest.raises(PersistenceUnavailableError) as exc:
        operation(repo)

    assert backend_detail not in str(exc.value)


def test_supabase_cloud_binding_maps_conflict_and_sanitizes_persistence_errors():
    def conflict_handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/rpc/ensure_cloud_binding"):
            return httpx.Response(400, json={"message": "cloud_binding_conflict"})
        return httpx.Response(500, text="backend secret details")

    repo = SupabaseDeviceRepository(
        "https://example.supabase.co",
        "sb_secret_backend",
        client=httpx.Client(transport=httpx.MockTransport(conflict_handler)),
    )

    with pytest.raises(CloudBindingConflictError):
        repo.ensure_cloud_binding("pecem-01", "webpilot-pecem", "hash")

    with pytest.raises(PersistenceUnavailableError) as exc:
        repo.get_webpilot_auth_realm("webpilot-pecem")
    assert "backend secret details" not in str(exc.value)

    with pytest.raises(PersistenceUnavailableError) as rotate_exc:
        repo.rotate_cloud_binding("pecem-01", "hash-v2")
    assert "backend secret details" not in str(rotate_exc.value)
