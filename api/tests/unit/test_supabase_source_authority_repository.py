from __future__ import annotations

import json
from datetime import datetime, timezone
from uuid import UUID

import httpx
import pytest

from app.models.source_authority import (
    AuthorityMode,
    AuthorityStatus,
    ManagedSnapshotCandidate,
    PublishUnderCurrentGrant,
    Source,
    TransitionCandidate,
)
from app.repositories.devices import PersistenceUnavailableError
from app.repositories.supabase import SupabaseDeviceRepository


BOOT = UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
LEASE = UUID("11111111-1111-4111-8111-111111111111")
NOW = datetime(2026, 10, 9, 15, 0, tzinfo=timezone.utc)

AUTHORITY_ROW = {
    "device_id": "pecem-a",
    "mode": "managed",
    "active_source": "desktop",
    "authority_epoch": 1,
    "authority_lease_id": str(LEASE),
    "holder_instance_id": str(BOOT),
    "lease_expires_at": "2026-10-09T15:03:00Z",
    "granted_at": "2026-10-09T15:00:00Z",
    "last_renewed_at": "2026-10-09T15:00:00Z",
    "last_transition_at": "2026-10-09T15:00:00Z",
    "transition_reason": "desktop_healthy",
    "last_authoritative_snapshot_at": "2026-10-09T15:00:00Z",
    "authoritative_snapshot_stale_since": None,
    "cloud_binding_id": None,
    "realm_id": None,
    "observed_realm_epoch": None,
    "updated_at": "2026-10-09T15:00:00Z",
}
HEARTBEAT_ROW = {
    "device_id": "pecem-a",
    "source": "desktop",
    "instance_id": str(BOOT),
    "last_heartbeat_at": "2026-10-09T15:00:00Z",
    "collection_healthy": True,
    "process_healthy": True,
    "healthy_since": "2026-10-09T14:59:00Z",
    "consecutive_healthy": 3,
    "last_collection_ok_at": "2026-10-09T15:00:00Z",
    "last_reported_generated_at": "2026-10-09T15:00:00Z",
    "last_candidate_generated_at": None,
    "last_reason_code": "desktop_healthy",
    "persistent_state_ready": None,
    "updated_at": "2026-10-09T15:00:00Z",
}
RESULT_ROW = {
    "status": "accepted",
    "reason_code": None,
    "received_at": "2026-10-09T15:00:01Z",
    "device_id": "pecem-a",
    "source": "desktop",
    "authority_epoch": 1,
    "authority_lease_id": str(LEASE),
    "holder_instance_id": str(BOOT),
    "lease_expires_at": "2026-10-09T15:03:00Z",
    "previous_source": "desktop",
    "source_transition": False,
    "side_effect_policy": "desktop_continuity",
    "previous_snapshot": {
        "schema_version": 2,
        "boot_id": str(BOOT),
        "sequence": 1,
        "generated_at": "2026-10-09T15:00:00Z",
    },
}


def _repo(handler) -> SupabaseDeviceRepository:
    return SupabaseDeviceRepository(
        "https://example.supabase.co",
        "sb_secret_backend",
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )


def _candidate(source: Source = Source.DESKTOP) -> ManagedSnapshotCandidate:
    instance = BOOT
    body = {
        "schema_version": 2,
        "boot_id": str(instance),
        "sequence": 2,
        "generated_at": NOW.isoformat(),
    }
    return ManagedSnapshotCandidate(
        device_id="pecem-a",
        source=source,
        holder_instance_id=instance,
        boot_id=instance,
        sequence=2,
        generated_at=NOW,
        snapshot_schema_version=2,
        snapshot=body,
    )


def test_supabase_source_authority_rpc_payloads_and_mappers():
    calls: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        path = request.url.path
        if path.endswith("/rpc/get_device_source_authority"):
            return httpx.Response(200, json=[AUTHORITY_ROW])
        if path.endswith("/device_source_heartbeats"):
            return httpx.Response(200, json=[HEARTBEAT_ROW])
        if path.endswith("/rpc/bootstrap_managed_source_authority"):
            return httpx.Response(
                200,
                json=[{
                    **RESULT_ROW,
                    "previous_source": None,
                    "side_effect_policy": "none",
                    "previous_snapshot": None,
                }],
            )
        if path.endswith("/rpc/accept_managed_snapshot_current_grant"):
            return httpx.Response(200, json=[RESULT_ROW])
        if path.endswith("/rpc/accept_managed_snapshot_transition_candidate"):
            return httpx.Response(
                200,
                json=[{
                    **RESULT_ROW,
                    "source": "cloud",
                    "authority_epoch": 2,
                    "authority_lease_id": "22222222-2222-4222-8222-222222222222",
                    "holder_instance_id": str(BOOT),
                    "previous_source": "desktop",
                    "source_transition": True,
                    "side_effect_policy": "none",
                    "previous_snapshot": None,
                    "reason_code": "failover_granted",
                }],
            )
        if path.endswith("/rpc/return_source_authority_to_legacy"):
            return httpx.Response(
                200,
                json=[{
                    **AUTHORITY_ROW,
                    "mode": "legacy",
                    "active_source": None,
                    "authority_epoch": 2,
                    "authority_lease_id": None,
                    "holder_instance_id": None,
                    "lease_expires_at": None,
                    "granted_at": None,
                    "last_renewed_at": None,
                    "cloud_binding_id": None,
                    "realm_id": None,
                    "observed_realm_epoch": None,
                    "transition_reason": "legacy_mode",
                }],
            )
        raise AssertionError(str(request.url))

    repo = _repo(handler)
    authority = repo.get_source_authority("pecem-a")
    assert authority is not None
    assert authority.mode is AuthorityMode.MANAGED
    assert repo.get_current_grant("pecem-a").authority_epoch == 1
    heartbeat = repo.get_source_heartbeat("pecem-a", Source.DESKTOP, BOOT)
    assert heartbeat is not None and heartbeat.instance_id == BOOT

    bootstrapped = repo.bootstrap_managed_source_authority("pecem-a")
    assert bootstrapped.status is AuthorityStatus.ACCEPTED

    current = repo.accept_current_grant_snapshot(
        PublishUnderCurrentGrant(
            candidate=_candidate(),
            authority_epoch=1,
            authority_lease_id=LEASE,
            holder_instance_id=BOOT,
        )
    )
    assert current.status is AuthorityStatus.ACCEPTED

    transition = repo.accept_transition_candidate(
        TransitionCandidate(candidate=_candidate(Source.CLOUD))
    )
    assert transition.status is AuthorityStatus.ACCEPTED
    assert transition.grant is not None and transition.grant.authority_epoch == 2

    legacy = repo.return_source_authority_to_legacy("pecem-a")
    assert legacy is not None and legacy.mode is AuthorityMode.LEGACY

    current_request = next(
        r for r in calls
        if r.url.path.endswith("/rpc/accept_managed_snapshot_current_grant")
    )
    current_payload = json.loads(current_request.content)
    assert current_payload["p_authority_epoch"] == 1
    assert current_payload["p_authority_lease_id"] == str(LEASE)
    assert "realm_epoch" not in json.dumps(current_payload)

    transition_request = next(
        r for r in calls
        if r.url.path.endswith("/rpc/accept_managed_snapshot_transition_candidate")
    )
    transition_payload = json.loads(transition_request.content)
    assert "p_authority_epoch" not in transition_payload
    assert "p_authority_lease_id" not in transition_payload


@pytest.mark.parametrize(
    ("suffix", "operation"),
    [
        (
            "/rpc/get_device_source_authority",
            lambda repo: repo.get_source_authority("pecem-a"),
        ),
        (
            "/rpc/bootstrap_managed_source_authority",
            lambda repo: repo.bootstrap_managed_source_authority("pecem-a"),
        ),
        (
            "/rpc/accept_managed_snapshot_current_grant",
            lambda repo: repo.accept_current_grant_snapshot(
                PublishUnderCurrentGrant(
                    candidate=_candidate(),
                    authority_epoch=1,
                    authority_lease_id=LEASE,
                    holder_instance_id=BOOT,
                )
            ),
        ),
        (
            "/rpc/accept_managed_snapshot_transition_candidate",
            lambda repo: repo.accept_transition_candidate(
                TransitionCandidate(candidate=_candidate(Source.CLOUD))
            ),
        ),
        (
            "/rpc/return_source_authority_to_legacy",
            lambda repo: repo.return_source_authority_to_legacy("pecem-a"),
        ),
    ],
)
def test_supabase_source_authority_malformed_200_is_sanitized(suffix, operation):
    backend_detail = "backend-private-detail"

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith(suffix)
        return httpx.Response(200, json=[{"unexpected": backend_detail}])

    repo = _repo(handler)
    with pytest.raises(PersistenceUnavailableError) as exc:
        operation(repo)
    assert backend_detail not in str(exc.value)
    assert "sb_secret_backend" not in str(exc.value)


def test_r12_supabase_heartbeat_rpc_payload_has_no_client_authority_decision():
    from app.models.source_heartbeat import SourceHeartbeatRequest
    from app.models.source_authority import Source

    received = []

    def handler(request: httpx.Request) -> httpx.Response:
        received.append(request)
        assert request.url.path.endswith("/rpc/record_source_heartbeat")
        return httpx.Response(200, json=[{
            "status": "accepted",
            "reason_code": "desktop_healthy",
            "authority_epoch": 1,
            "authority_lease_id": str(LEASE),
            "holder_instance_id": str(BOOT),
            "lease_expires_at": "2026-10-09T15:03:00Z",
            "renewed": True,
        }])

    repo = _repo(handler)
    response = repo.record_source_heartbeat(
        "pecem-a", Source.DESKTOP,
        SourceHeartbeatRequest(instance_id=BOOT, collection_healthy=True),
    )
    assert response.renewed
    assert response.grant is not None
    assert response.grant.authority_epoch == 1
    payload = json.loads(received[0].content)
    assert payload["p_instance_id"] == str(BOOT)
    assert payload["p_source"] == "desktop"
    assert payload["p_cloud_binding_id"] is None
    assert "failover_granted" not in json.dumps(payload)
    assert "p_reason" not in payload
    assert "p_authority_epoch" not in payload
    assert "p_authority_lease_id" not in payload


def test_r12_supabase_heartbeat_malformed_rpc_result_fail_closed_and_sanitized():
    from app.models.source_heartbeat import SourceHeartbeatRequest
    from app.models.source_authority import Source

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/rpc/record_source_heartbeat")
        return httpx.Response(200, json=[{"unexpected": "private-leak"}])

    repo = _repo(handler)
    with pytest.raises(PersistenceUnavailableError) as exc:
        repo.record_source_heartbeat(
            "pecem-a", Source.DESKTOP,
            SourceHeartbeatRequest(instance_id=BOOT, collection_healthy=True),
        )
    assert "private-leak" not in str(exc.value)
    assert "sb_secret_backend" not in str(exc.value)
