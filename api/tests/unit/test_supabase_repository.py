from __future__ import annotations

from datetime import datetime, timezone
import json
from uuid import UUID

import httpx
import pytest

from app.repositories.devices import (
    AcceptSnapshotStatus,
    PersistenceUnavailableError,
    SnapshotCandidate,
)
from app.repositories.supabase import SupabaseDeviceRepository


def _candidate() -> SnapshotCandidate:
    return SnapshotCandidate(
        device_id="pecem-01",
        snapshot={"schema_version": 1, "marker": "rpc"},
        snapshot_schema_version=1,
        boot_id=UUID("550e8400-e29b-41d4-a716-446655440000"),
        sequence=4,
        generated_at=datetime(2026, 9, 25, 16, 0, tzinfo=timezone.utc),
    )


def test_accept_snapshot_calls_supabase_rpc_with_current_secret_key():
    observed: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        observed["path"] = request.url.path

        observed["apikey"] = request.headers.get("apikey")
        observed["authorization"] = request.headers.get("authorization")
        observed["body"] = json.loads(request.content)
        return httpx.Response(
            200,
            json=[{
                "status": "accepted",
                "received_at": "2026-09-25T16:00:10+00:00",
            }],
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    repo = SupabaseDeviceRepository(
        "https://example.supabase.co",
        "sb_secret_backend",
        client=client,
    )

    result = repo.accept_snapshot_atomic(_candidate())

    assert observed["path"] == "/rest/v1/rpc/accept_device_snapshot"
    assert observed["apikey"] == "sb_secret_backend"
    assert observed["authorization"] is None
    assert observed["body"]["p_device_id"] == "pecem-01"
    assert observed["body"]["p_sequence"] == 4
    assert result.status is AcceptSnapshotStatus.ACCEPTED
    assert result.received_at == datetime(
        2026, 9, 25, 16, 0, 10, tzinfo=timezone.utc
    )

def test_legacy_service_role_key_keeps_bearer_compatibility():
    observed: dict[str, str | None] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        observed["apikey"] = request.headers.get("apikey")
        observed["authorization"] = request.headers.get("authorization")
        return httpx.Response(
            200,
            json=[{"status": "device_not_found", "received_at": None}],
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    repo = SupabaseDeviceRepository(
        "https://example.supabase.co",
        "legacy-service-role",
        client=client,
    )

    result = repo.accept_snapshot_atomic(_candidate())

    assert observed["apikey"] == "legacy-service-role"
    assert observed["authorization"] == "Bearer legacy-service-role"
    assert result.status is AcceptSnapshotStatus.DEVICE_NOT_FOUND


def test_rpc_failure_is_sanitized_and_never_leaks_server_key():
    key = "sb_secret_nao_vazar"

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, json={"message": "unavailable"})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    repo = SupabaseDeviceRepository(
        "https://example.supabase.co",
        key,
        client=client,
    )

    with pytest.raises(PersistenceUnavailableError) as exc:
        repo.accept_snapshot_atomic(_candidate())

    assert key not in str(exc.value)
