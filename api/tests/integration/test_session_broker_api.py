from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app
from app.repositories.cloud_bindings import WebPilotAuthRealmRecord
from app.repositories.devices import DeviceAuthRecord
from app.repositories.memory import MemoryDeviceRepository
from app.repositories.session_broker import ProviderScopeProfile
from app.security.credentials import hash_secret
from app.security.session_crypto import SessionCryptoKeyring


NOW = datetime(2026, 10, 8, 12, 0, tzinfo=timezone.utc)
PUB = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
DEVICE_SECRET = "desktop-secret"
CLOUD_CREDENTIAL = "C" * 43


def _setup() -> tuple[TestClient, MemoryDeviceRepository]:
    repo = MemoryDeviceRepository(clock=lambda: NOW)
    repo.put_device(DeviceAuthRecord("pecem-01", hash_secret(DEVICE_SECRET), enabled=True))
    repo.put_webpilot_auth_realm(
        WebPilotAuthRealmRecord(
            realm_id="webpilot-pecem",
            active=True,
            created_at=NOW,
            updated_at=NOW,
        )
    )
    repo.authorize_realm_device("webpilot-pecem", "pecem-01")
    repo.set_required_provider_scope(
        "webpilot-pecem",
        ProviderScopeProfile(
            "pecem-standard",
            1,
            ("maneuvers", "weather"),
        ),
    )
    binding = repo.ensure_cloud_binding(
        "pecem-01",
        "webpilot-pecem",
        hash_secret(CLOUD_CREDENTIAL),
    )
    assert binding is not None
    app = create_app(
        settings=Settings(
            _env_file=None,
            environment="test",
            persistence_backend="memory",
            mock_seed_device=False,
        ),
        repository=repo,
        session_broker_crypto=SessionCryptoKeyring(
            keys={1: b"K" * 32},
            active_key_version=1,
        ),
        session_broker_fingerprint_key=b"F" * 32,
    )
    return TestClient(app), repo


def _device_headers(secret: str = DEVICE_SECRET):
    return {"Authorization": f"Device {secret}"}


def test_session_broker_desktop_and_cloud_contract():
    client, repo = _setup()

    publisher = client.put(
        "/api/v1/devices/pecem-01/webpilot-session-publisher",
        headers=_device_headers(),
        json={
            "realm_id": "webpilot-pecem",
            "publisher_id": str(PUB),
            "provider_scope": {
                "scope_id": "pecem-standard",
                "schema_version": 1,
                "capabilities": ["maneuvers", "weather"],
            },
        },
    )
    assert publisher.status_code == 200
    assert publisher.json()["scope_status"] == "unverified"
    assert repo.verify_session_publisher_scope(PUB).scope_status.value == "verified"

    payload = {
        "realm_id": "webpilot-pecem",
        "publisher_id": str(PUB),
        "local_generation": 1,
        "expires_at": None,
        "cookies": [{"name": "session", "value": "cookie-secret", "expiry": None}],
    }
    first = client.post(
        "/api/v1/devices/pecem-01/webpilot-session-leases",
        headers=_device_headers(),
        json=payload,
    )
    assert first.status_code == 200
    retry = client.post(
        "/api/v1/devices/pecem-01/webpilot-session-leases",
        headers=_device_headers(),
        json=payload,
    )
    assert retry.status_code == 200
    assert retry.json()["lease_id"] == first.json()["lease_id"]
    assert retry.json()["realm_epoch"] == first.json()["realm_epoch"]

    mismatch = {
        **payload,
        "cookies": [{"name": "session", "value": "different", "expiry": None}],
    }
    conflict = client.post(
        "/api/v1/devices/pecem-01/webpilot-session-leases",
        headers=_device_headers(),
        json=mismatch,
    )
    assert conflict.status_code == 409
    assert conflict.json()["detail"]["code"] == "session_lease_generation_conflict"
    assert "different" not in conflict.text

    binding = repo.get_active_cloud_binding("pecem-01")
    assert binding is not None
    consume = client.get(
        f"/api/v1/cloud-bindings/{binding.cloud_binding_id}/webpilot-session-lease",
        headers={"Authorization": f"CloudBinding {CLOUD_CREDENTIAL}"},
    )
    assert consume.status_code == 200
    assert consume.headers["cache-control"] == "no-store"
    assert consume.json()["cookies"][0]["value"] == "cookie-secret"

    invalidated = client.post(
        f"/api/v1/cloud-bindings/{binding.cloud_binding_id}/webpilot-session-lease/invalidate",
        headers={"Authorization": f"CloudBinding {CLOUD_CREDENTIAL}"},
        json={
            "lease_id": first.json()["lease_id"],
            "realm_epoch": first.json()["realm_epoch"],
        },
    )
    assert invalidated.status_code == 200
    assert invalidated.json()["status"] == "invalidated"

    unavailable = client.get(
        f"/api/v1/cloud-bindings/{binding.cloud_binding_id}/webpilot-session-lease",
        headers={"Authorization": f"CloudBinding {CLOUD_CREDENTIAL}"},
    )
    assert unavailable.status_code == 404


def test_session_broker_auth_and_scope_fail_closed():
    client, repo = _setup()
    request = {
        "realm_id": "webpilot-pecem",
        "publisher_id": str(PUB),
        "provider_scope": {
            "scope_id": "pecem-standard",
            "schema_version": 1,
            "capabilities": ["maneuvers", "weather"],
        },
    }
    assert client.put(
        "/api/v1/devices/pecem-01/webpilot-session-publisher",
        headers=_device_headers("wrong"),
        json=request,
    ).status_code == 401

    publisher = client.put(
        "/api/v1/devices/pecem-01/webpilot-session-publisher",
        headers=_device_headers(),
        json=request,
    )
    assert publisher.status_code == 200

    unverified = client.post(
        "/api/v1/devices/pecem-01/webpilot-session-leases",
        headers=_device_headers(),
        json={
            "realm_id": "webpilot-pecem",
            "publisher_id": str(PUB),
            "local_generation": 1,
            "expires_at": None,
            "cookies": [{"name": "session", "value": "secret", "expiry": None}],
        },
    )
    assert unverified.status_code == 403

    binding = repo.get_active_cloud_binding("pecem-01")
    assert binding is not None
    wrong_cloud = client.get(
        f"/api/v1/cloud-bindings/{binding.cloud_binding_id}/webpilot-session-lease",
        headers={"Authorization": "CloudBinding wrong"},
    )
    assert wrong_cloud.status_code == 403


def test_session_broker_openapi_is_write_only_and_not_mobile():
    client, _repo = _setup()
    schema = client.get("/openapi.json").json()

    cookie_schema = schema["components"]["schemas"]["SessionCookieIn"]
    assert cookie_schema["properties"]["value"]["writeOnly"] is True

    consume_schema = schema["components"]["schemas"]["SessionLeaseConsumeResponse"]
    assert "ciphertext" not in consume_schema["properties"]
    assert "nonce" not in consume_schema["properties"]
    assert "payload_fingerprint" not in consume_schema["properties"]

    broker_paths = {
        path for path in schema["paths"]
        if "webpilot-session" in path
    }
    assert broker_paths
    assert not any(path.startswith("/api/v1/mobile/") for path in broker_paths)


def test_session_broker_openapi_documents_error_contract():
    client, _repo = _setup()
    paths = client.get("/openapi.json").json()["paths"]

    publisher = paths["/api/v1/devices/{device_id}/webpilot-session-publisher"]
    leases = paths["/api/v1/devices/{device_id}/webpilot-session-leases"]
    revoke = paths["/api/v1/devices/{device_id}/webpilot-session-leases/revoke"]
    cloud = paths["/api/v1/cloud-bindings/{cloud_binding_id}/webpilot-session-lease"]
    invalidate = paths[
        "/api/v1/cloud-bindings/{cloud_binding_id}/webpilot-session-lease/invalidate"
    ]

    assert set(publisher["put"]["responses"]) >= {
        "200", "401", "403", "409", "422", "503"
    }
    assert set(publisher["delete"]["responses"]) >= {
        "200", "401", "403", "422", "503"
    }
    assert set(leases["post"]["responses"]) >= {
        "200", "401", "403", "409", "422", "503"
    }
    assert set(revoke["post"]["responses"]) >= {
        "200", "401", "403", "404", "422", "503"
    }
    assert set(cloud["get"]["responses"]) >= {
        "200", "403", "404", "503"
    }
    assert set(invalidate["post"]["responses"]) >= {
        "200", "403", "404", "422", "503"
    }


def test_session_broker_missing_crypto_is_503_without_cookie_echo():
    repo = MemoryDeviceRepository(clock=lambda: NOW)
    repo.put_device(
        DeviceAuthRecord("pecem-01", hash_secret(DEVICE_SECRET), enabled=True)
    )
    repo.put_webpilot_auth_realm(
        WebPilotAuthRealmRecord(
            realm_id="webpilot-pecem",
            active=True,
            created_at=NOW,
            updated_at=NOW,
        )
    )
    repo.authorize_realm_device("webpilot-pecem", "pecem-01")
    repo.set_required_provider_scope(
        "webpilot-pecem",
        ProviderScopeProfile(
            "pecem-standard",
            1,
            ("maneuvers", "weather"),
        ),
    )
    publisher = repo.ensure_session_publisher(
        device_id="pecem-01",
        realm_id="webpilot-pecem",
        publisher_id=PUB,
        provider_scope=ProviderScopeProfile(
            "pecem-standard",
            1,
            ("maneuvers", "weather"),
        ),
    )
    assert publisher is not None
    assert repo.verify_session_publisher_scope(PUB) is not None

    app = create_app(
        settings=Settings(
            _env_file=None,
            environment="test",
            persistence_backend="memory",
            mock_seed_device=False,
        ),
        repository=repo,
    )
    client = TestClient(app)

    secret = "must-never-echo"
    response = client.post(
        "/api/v1/devices/pecem-01/webpilot-session-leases",
        headers=_device_headers(),
        json={
            "realm_id": "webpilot-pecem",
            "publisher_id": str(PUB),
            "local_generation": 1,
            "expires_at": None,
            "cookies": [
                {"name": "session", "value": secret, "expiry": None},
            ],
        },
    )

    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "persistence_unavailable"
    assert secret not in response.text


def test_session_broker_duplicate_cookie_names_are_422_without_secret_echo():
    client, repo = _setup()
    client.put(
        "/api/v1/devices/pecem-01/webpilot-session-publisher",
        headers=_device_headers(),
        json={
            "realm_id": "webpilot-pecem",
            "publisher_id": str(PUB),
            "provider_scope": {
                "scope_id": "pecem-standard",
                "schema_version": 1,
                "capabilities": ["maneuvers", "weather"],
            },
        },
    )
    repo.verify_session_publisher_scope(PUB)

    secret = "must-not-echo"
    response = client.post(
        "/api/v1/devices/pecem-01/webpilot-session-leases",
        headers=_device_headers(),
        json={
            "realm_id": "webpilot-pecem",
            "publisher_id": str(PUB),
            "local_generation": 1,
            "expires_at": None,
            "cookies": [
                {"name": "session", "value": secret, "expiry": None},
                {"name": "session", "value": "other", "expiry": None},
            ],
        },
    )

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "invalid_request_payload"
    assert secret not in response.text


def test_session_broker_rejects_whitespace_scope_and_cookie_name_as_422():
    initial_client, repo = _setup()
    client = TestClient(initial_client.app, raise_server_exceptions=False)

    scope_response = client.put(
        "/api/v1/devices/pecem-01/webpilot-session-publisher",
        headers=_device_headers(),
        json={
            "realm_id": "webpilot-pecem",
            "publisher_id": str(PUB),
            "provider_scope": {
                "scope_id": "   ",
                "schema_version": 1,
                "capabilities": ["maneuvers", "weather"],
            },
        },
    )
    assert scope_response.status_code == 422
    assert scope_response.json()["detail"]["code"] == "invalid_request_payload"

    valid = client.put(
        "/api/v1/devices/pecem-01/webpilot-session-publisher",
        headers=_device_headers(),
        json={
            "realm_id": "webpilot-pecem",
            "publisher_id": str(PUB),
            "provider_scope": {
                "scope_id": "pecem-standard",
                "schema_version": 1,
                "capabilities": ["maneuvers", "weather"],
            },
        },
    )
    assert valid.status_code == 200
    assert repo.verify_session_publisher_scope(PUB) is not None

    secret = "wire-secret-must-not-echo"
    cookie_response = client.post(
        "/api/v1/devices/pecem-01/webpilot-session-leases",
        headers=_device_headers(),
        json={
            "realm_id": "webpilot-pecem",
            "publisher_id": str(PUB),
            "local_generation": 1,
            "expires_at": None,
            "cookies": [
                {"name": "   ", "value": secret, "expiry": None},
            ],
        },
    )
    assert cookie_response.status_code == 422
    assert cookie_response.json()["detail"]["code"] == "invalid_request_payload"
    assert secret not in cookie_response.text


def test_session_broker_rejects_total_payload_above_limit_before_persistence():
    client, repo = _setup()
    valid = client.put(
        "/api/v1/devices/pecem-01/webpilot-session-publisher",
        headers=_device_headers(),
        json={
            "realm_id": "webpilot-pecem",
            "publisher_id": str(PUB),
            "provider_scope": {
                "scope_id": "pecem-standard",
                "schema_version": 1,
                "capabilities": ["maneuvers", "weather"],
            },
        },
    )
    assert valid.status_code == 200
    assert repo.verify_session_publisher_scope(PUB) is not None

    marker = "oversize-secret-marker"
    cookies = [
        {
            "name": f"cookie-{index:02d}",
            "value": marker + ("x" * (4096 - len(marker))),
            "expiry": None,
        }
        for index in range(64)
    ]
    response = client.post(
        "/api/v1/devices/pecem-01/webpilot-session-leases",
        headers=_device_headers(),
        json={
            "realm_id": "webpilot-pecem",
            "publisher_id": str(PUB),
            "local_generation": 1,
            "expires_at": None,
            "cookies": cookies,
        },
    )

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "session_lease_payload_too_large"
    assert marker not in response.text
    assert repo.get_current_session_lease("webpilot-pecem", now=NOW) is None


def test_session_broker_reusing_revoked_publisher_id_returns_409():
    client, repo = _setup()
    request = {
        "realm_id": "webpilot-pecem",
        "publisher_id": str(PUB),
        "provider_scope": {
            "scope_id": "pecem-standard",
            "schema_version": 1,
            "capabilities": ["maneuvers", "weather"],
        },
    }
    created = client.put(
        "/api/v1/devices/pecem-01/webpilot-session-publisher",
        headers=_device_headers(),
        json=request,
    )
    assert created.status_code == 200

    revoked = client.request(
        "DELETE",
        "/api/v1/devices/pecem-01/webpilot-session-publisher",
        headers=_device_headers(),
        json={
            "realm_id": "webpilot-pecem",
            "publisher_id": str(PUB),
        },
    )
    assert revoked.status_code == 200

    conflict = client.put(
        "/api/v1/devices/pecem-01/webpilot-session-publisher",
        headers=_device_headers(),
        json=request,
    )
    assert conflict.status_code == 409
    assert conflict.json()["detail"]["code"] == "session_publisher_conflict"
