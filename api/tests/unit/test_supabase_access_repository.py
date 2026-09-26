from __future__ import annotations

import json

import httpx
import pytest

from app.repositories.devices import PersistenceUnavailableError
from app.repositories.supabase import SupabaseDeviceRepository


def test_get_device_auth_returns_hash_record_without_plaintext():
    observed: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        observed["path"] = request.url.path
        observed["query"] = dict(request.url.params)
        return httpx.Response(
            200,
            json=[{
                "device_id": "pecem-01",
                "device_secret_hash": "device-hash",
                "view_secret_hash": "view-hash",
            }],
        )

    repo = SupabaseDeviceRepository(
        "https://example.supabase.co",
        "sb_secret_backend",
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    record = repo.get_device_auth("pecem-01")

    assert observed["path"] == "/rest/v1/devices"
    assert observed["query"]["device_id"] == "eq.pecem-01"

    assert record.device_id == "pecem-01"
    assert record.device_secret_hash == "device-hash"
    assert record.view_secret_hash == "view-hash"


def test_get_device_auth_returns_none_for_missing_device():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=[])

    repo = SupabaseDeviceRepository(
        "https://example.supabase.co",
        "sb_secret_backend",
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    assert repo.get_device_auth("missing") is None


def test_rotate_view_secret_hash_calls_rpc_with_hash_only():
    observed: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        observed["path"] = request.url.path
        observed["body"] = json.loads(request.content)
        return httpx.Response(200, json=[{"updated": True}])

    repo = SupabaseDeviceRepository(
        "https://example.supabase.co",
        "sb_secret_backend",
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    updated = repo.rotate_view_secret_hash(
        "pecem-01",
        "sha256-view-hash",
    )

    assert updated is True
    assert observed["path"] == "/rest/v1/rpc/rotate_device_view_secret"
    assert observed["body"] == {
        "p_device_id": "pecem-01",
        "p_view_secret_hash": "sha256-view-hash",
    }


def test_rotate_view_secret_hash_returns_false_for_missing_device():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=[{"updated": False}])

    repo = SupabaseDeviceRepository(
        "https://example.supabase.co",
        "sb_secret_backend",
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    assert repo.rotate_view_secret_hash("missing", "hash") is False


def test_access_repository_failure_is_sanitized():
    key = "sb_secret_nao_vazar"

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"message": "db error"})

    repo = SupabaseDeviceRepository(
        "https://example.supabase.co",
        key,
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    with pytest.raises(PersistenceUnavailableError) as exc:
        repo.get_device_auth("pecem-01")

    assert key not in str(exc.value)
