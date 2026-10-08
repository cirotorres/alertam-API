from __future__ import annotations

import json
from datetime import datetime, timezone
from uuid import UUID

import httpx
import pytest

from app.repositories.devices import PersistenceUnavailableError
from app.repositories.session_broker import (
    ProviderScopeProfile,
    ScopeStatus,
    SessionLeaseGenerationConflictError,
    SessionLeaseReplayError,
    SessionLeaseStatus,
    SessionPublisherConflictError,
)
from app.repositories.supabase import SupabaseDeviceRepository


PUB = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
LEASE = UUID("11111111-1111-1111-1111-111111111111")
NOW = "2026-10-08T12:00:00Z"

SCOPE_ROW = {
    "realm_id": "webpilot-pecem",
    "scope_id": "pecem-standard",
    "schema_version": 1,
    "capabilities": ["maneuvers", "weather"],
    "updated_at": NOW,
}
PUBLISHER_ROW = {
    "publisher_id": str(PUB),
    "realm_id": "webpilot-pecem",
    "device_id": "pecem-01",
    "provider_scope_id": "pecem-standard",
    "provider_scope_schema_version": 1,
    "provider_scope_capabilities": ["maneuvers", "weather"],
    "scope_status": "verified",
    "scope_verified_at": NOW,
    "last_generation": 1,
    "status": "active",
    "created_at": NOW,
    "updated_at": NOW,
    "revoked_at": None,
}
LEASE_ROW = {
    "lease_id": str(LEASE),
    "realm_id": "webpilot-pecem",
    "publisher_id": str(PUB),
    "local_generation": 1,
    "realm_epoch": 7,
    "payload_fingerprint": "a" * 64,
    "ciphertext": "ciphertext",
    "nonce": "nonce",
    "key_version": 1,
    "payload_schema_version": 1,
    "received_at": NOW,
    "expires_at": "2026-10-08T13:00:00Z",
    "status": "accepted",
    "revoked_at": None,
    "invalidated_at": None,
}


def _repo(handler) -> SupabaseDeviceRepository:
    return SupabaseDeviceRepository(
        "https://example.supabase.co",
        "sb_secret_backend",
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )


def test_supabase_session_broker_rpc_payloads_and_mappers():
    calls: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        path = request.url.path
        if path.endswith("/rpc/set_required_provider_scope"):
            return httpx.Response(200, json=[SCOPE_ROW])
        if path.endswith("/rpc/ensure_session_publisher"):
            return httpx.Response(200, json=[{**PUBLISHER_ROW, "scope_status": "unverified", "scope_verified_at": None, "last_generation": 0}])
        if path.endswith("/rpc/verify_session_publisher_scope"):
            return httpx.Response(200, json=[PUBLISHER_ROW])
        if path.endswith("/rpc/revoke_session_publisher"):
            return httpx.Response(200, json=[{**PUBLISHER_ROW, "status": "revoked", "revoked_at": NOW}])
        if path.endswith("/rpc/accept_session_lease"):
            return httpx.Response(200, json=[LEASE_ROW])
        if path.endswith("/rpc/get_current_session_lease"):
            return httpx.Response(200, json=[LEASE_ROW])
        if path.endswith("/rpc/revoke_session_lease"):
            return httpx.Response(200, json=[{**LEASE_ROW, "status": "revoked", "revoked_at": NOW}])
        if path.endswith("/rpc/invalidate_session_lease"):
            return httpx.Response(200, json=[{**LEASE_ROW, "status": "invalidated", "invalidated_at": NOW}])
        if path.endswith("/webpilot_provider_scope_requirements"):
            return httpx.Response(200, json=[SCOPE_ROW])
        if path.endswith("/webpilot_session_publishers"):
            return httpx.Response(200, json=[PUBLISHER_ROW])
        if path.endswith("/webpilot_session_leases"):
            return httpx.Response(200, json=[LEASE_ROW])
        raise AssertionError(str(request.url))

    repo = _repo(handler)
    profile = ProviderScopeProfile(
        scope_id="pecem-standard",
        schema_version=1,
        capabilities=("maneuvers", "weather"),
    )

    scope = repo.set_required_provider_scope("webpilot-pecem", profile)
    assert scope is not None and scope.profile == profile
    assert repo.get_required_provider_scope("webpilot-pecem") == scope

    publisher = repo.ensure_session_publisher(
        device_id="pecem-01",
        realm_id="webpilot-pecem",
        publisher_id=PUB,
        provider_scope=profile,
    )
    assert publisher is not None
    assert publisher.scope_status is ScopeStatus.UNVERIFIED
    assert repo.verify_session_publisher_scope(PUB).scope_status is ScopeStatus.VERIFIED
    assert repo.get_session_publisher(PUB).publisher_id == PUB
    assert repo.revoke_session_publisher(PUB).status.value == "revoked"

    lease = repo.accept_session_lease_atomic(
        device_id="pecem-01",
        realm_id="webpilot-pecem",
        publisher_id=PUB,
        lease_id=LEASE,
        local_generation=1,
        payload_fingerprint="a" * 64,
        ciphertext="ciphertext",
        nonce="nonce",
        key_version=1,
        payload_schema_version=1,
        expires_at=datetime(2026, 10, 8, 13, 0, tzinfo=timezone.utc),
    )
    assert lease is not None
    assert lease.status is SessionLeaseStatus.ACCEPTED
    assert repo.get_session_lease(LEASE) == lease
    assert repo.get_current_session_lease(
        "webpilot-pecem",
        now=datetime(2026, 10, 8, 12, 0, tzinfo=timezone.utc),
    ) == lease
    assert repo.revoke_session_lease(
        device_id="pecem-01",
        realm_id="webpilot-pecem",
        lease_id=LEASE,
    ).status is SessionLeaseStatus.REVOKED
    assert repo.invalidate_session_lease(
        realm_id="webpilot-pecem",
        lease_id=LEASE,
        realm_epoch=7,
    ).status is SessionLeaseStatus.INVALIDATED

    accept = next(r for r in calls if r.url.path.endswith("/rpc/accept_session_lease"))
    payload = json.loads(accept.content)
    assert payload["p_device_id"] == "pecem-01"
    assert payload["p_payload_fingerprint"] == "a" * 64
    assert "cookie" not in json.dumps(payload).lower()


@pytest.mark.parametrize(
    ("marker", "expected"),
    [
        ("session_lease_generation_conflict", SessionLeaseGenerationConflictError),
        ("session_lease_replay", SessionLeaseReplayError),
    ],
)
def test_supabase_session_broker_maps_typed_conflicts(marker, expected):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(400, json={"message": marker})

    repo = _repo(handler)
    with pytest.raises(expected):
        repo.accept_session_lease_atomic(
            device_id="pecem-01",
            realm_id="webpilot-pecem",
            publisher_id=PUB,
            lease_id=LEASE,
            local_generation=1,
            payload_fingerprint="a" * 64,
            ciphertext="ciphertext",
            nonce="nonce",
            key_version=1,
            payload_schema_version=1,
            expires_at=None,
        )


@pytest.mark.parametrize(
    "path",
    [
        "/rpc/set_required_provider_scope",
        "/rpc/ensure_session_publisher",
        "/rpc/accept_session_lease",
        "/rpc/get_current_session_lease",
    ],
)
def test_supabase_session_broker_malformed_200_is_sanitized(path: str):
    backend_detail = "backend-secret-payload"

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith(path)
        return httpx.Response(200, json=[{"unexpected": backend_detail}])

    repo = _repo(handler)
    profile = ProviderScopeProfile("pecem-standard", 1, ("maneuvers", "weather"))

    if path.endswith("set_required_provider_scope"):
        operation = lambda: repo.set_required_provider_scope("webpilot-pecem", profile)
    elif path.endswith("ensure_session_publisher"):
        operation = lambda: repo.ensure_session_publisher(
            device_id="pecem-01",
            realm_id="webpilot-pecem",
            publisher_id=PUB,
            provider_scope=profile,
        )
    elif path.endswith("accept_session_lease"):
        operation = lambda: repo.accept_session_lease_atomic(
            device_id="pecem-01",
            realm_id="webpilot-pecem",
            publisher_id=PUB,
            lease_id=LEASE,
            local_generation=1,
            payload_fingerprint="a" * 64,
            ciphertext="ciphertext",
            nonce="nonce",
            key_version=1,
            payload_schema_version=1,
            expires_at=None,
        )
    else:
        operation = lambda: repo.get_current_session_lease(
            "webpilot-pecem",
            now=datetime(2026, 10, 8, 12, 0, tzinfo=timezone.utc),
        )

    with pytest.raises(PersistenceUnavailableError) as exc:
        operation()
    assert backend_detail not in str(exc.value)
    assert "sb_secret_backend" not in str(exc.value)


def test_supabase_session_publisher_conflict_is_typed():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/rpc/ensure_session_publisher")
        return httpx.Response(
            400,
            json={"message": "session_publisher_conflict"},
        )

    repo = _repo(handler)
    with pytest.raises(SessionPublisherConflictError):
        repo.ensure_session_publisher(
            device_id="pecem-01",
            realm_id="webpilot-pecem",
            publisher_id=PUB,
            provider_scope=ProviderScopeProfile(
                "pecem-standard",
                1,
                ("maneuvers", "weather"),
            ),
        )
