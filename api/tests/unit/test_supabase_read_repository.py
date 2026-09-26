from __future__ import annotations

from datetime import datetime, timezone

import httpx
import pytest

from app.repositories.devices import PersistenceUnavailableError
from app.repositories.supabase import SupabaseDeviceRepository


def test_get_snapshot_maps_supabase_row():
    observed: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        observed["path"] = request.url.path
        observed["query"] = dict(request.url.params)
        return httpx.Response(
            200,
            json=[{
                "device_id": "pecem-01",
                "snapshot": {"schema_version": 1},
                "snapshot_schema_version": 1,
                "boot_id": "550e8400-e29b-41d4-a716-446655440000",
                "sequence": 7,
                "generated_at": "2026-09-25T16:00:00+00:00",
                "received_at": "2026-09-25T16:00:10+00:00",
            }],
        )

    repo = SupabaseDeviceRepository(
        "https://example.supabase.co",
        "sb_secret_backend",
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    stored = repo.get_snapshot("pecem-01")

    assert observed["path"] == "/rest/v1/devices"
    assert observed["query"]["device_id"] == "eq.pecem-01"
    assert stored.device_id == "pecem-01"
    assert stored.snapshot == {"schema_version": 1}
    assert stored.snapshot_schema_version == 1
    assert stored.sequence == 7
    assert stored.received_at == datetime(
        2026, 9, 25, 16, 0, 10, tzinfo=timezone.utc
    )


@pytest.mark.parametrize(
    "payload",
    [
        [],
        [{
            "device_id": "pecem-01",
            "snapshot": None,
            "snapshot_schema_version": None,
            "boot_id": None,
            "sequence": None,
            "generated_at": None,
            "received_at": None,
        }],
    ],
)
def test_get_snapshot_returns_none_when_unavailable(payload):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=payload)

    repo = SupabaseDeviceRepository(
        "https://example.supabase.co",
        "sb_secret_backend",
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    assert repo.get_snapshot("pecem-01") is None


def test_get_snapshot_failure_is_sanitized():
    key = "sb_secret_nao_vazar"

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, json={"message": "unavailable"})

    repo = SupabaseDeviceRepository(
        "https://example.supabase.co",
        key,
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    with pytest.raises(PersistenceUnavailableError) as exc:
        repo.get_snapshot("pecem-01")

    assert key not in str(exc.value)
