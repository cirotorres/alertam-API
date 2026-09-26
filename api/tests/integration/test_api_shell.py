from __future__ import annotations

import json
import logging
from pathlib import Path

from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app
from app.repositories.memory import MemoryDeviceRepository


FIXTURE = Path(__file__).parents[1] / "fixtures" / "mobile_snapshot_v1.json"


class ExplodingRepository(MemoryDeviceRepository):
    def get_device_auth(self, device_id):
        raise AssertionError("health não deve consultar repository")

    def get_snapshot(self, device_id):
        raise AssertionError("health não deve consultar repository")


def _settings(**overrides) -> Settings:
    values = {
        "persistence_backend": "memory",
        "allowed_origins": "",
        "log_level": "INFO",
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


def test_health_does_not_query_repository():
    client = TestClient(
        create_app(
            repository=ExplodingRepository(),
            settings=_settings(),
        )
    )

    response = client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json() == {"ok": True}

def test_v1_routes_are_mounted_once():
    app = create_app(
        repository=MemoryDeviceRepository(),
        settings=_settings(),
    )

    paths = app.openapi()["paths"]

    assert set(paths["/api/v1/health"]) == {"get"}
    assert set(paths["/api/v1/devices/{device_id}/snapshot"]) == {
        "get",
        "post",
    }
    assert set(paths["/api/v1/devices/{device_id}/view-access"]) == {
        "put",
    }


def test_cors_is_closed_by_default():
    client = TestClient(
        create_app(
            repository=MemoryDeviceRepository(),
            settings=_settings(),
        )
    )

    response = client.options(
        "/api/v1/health",
        headers={
            "Origin": "https://untrusted.example",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert "access-control-allow-origin" not in response.headers

def test_explicit_cors_origin_is_allowed():
    client = TestClient(
        create_app(
            repository=MemoryDeviceRepository(),
            settings=_settings(
                allowed_origins=(
                    "https://mobile.example,"
                    " https://staging.example "
                )
            ),
        )
    )

    response = client.options(
        "/api/v1/health",
        headers={
            "Origin": "https://mobile.example",
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "authorization",
        },
    )

    assert response.status_code == 200
    assert (
        response.headers["access-control-allow-origin"]
        == "https://mobile.example"
    )
    assert "authorization" in response.headers[
        "access-control-allow-headers"
    ].lower()

def test_http_log_contains_method_path_status_and_duration(caplog):
    client = TestClient(
        create_app(
            repository=MemoryDeviceRepository(),
            settings=_settings(),
        )
    )

    with caplog.at_level(logging.INFO, logger="alertam.api.http"):
        response = client.get(
            "/api/v1/devices/pecem-01/snapshot",
            headers={"Authorization": "Bearer SUPER_SECRET_TOKEN"},
        )

    assert response.status_code == 401
    log_text = caplog.text
    assert "method=GET" in log_text
    assert "path=/api/v1/devices/pecem-01/snapshot" in log_text
    assert "status=401" in log_text
    assert "duration_ms=" in log_text
    assert "SUPER_SECRET_TOKEN" not in log_text


def test_http_log_never_contains_request_body(caplog):
    client = TestClient(
        create_app(
            repository=MemoryDeviceRepository(),
            settings=_settings(),
        )
    )
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    payload["sensitive_marker"] = "NEVER_LOG_THIS_BODY"

    with caplog.at_level(logging.INFO, logger="alertam.api.http"):
        client.post(
            "/api/v1/devices/pecem-01/snapshot",
            headers={"Authorization": "Device invalid"},
            json=payload,
        )

    assert "NEVER_LOG_THIS_BODY" not in caplog.text

def test_generic_validation_error_has_sanitized_envelope():
    from app.repositories.devices import DeviceAuthRecord
    from app.security.credentials import hash_secret

    repo = MemoryDeviceRepository()
    repo.create_device(
        DeviceAuthRecord(
            device_id="pecem-01",
            device_secret_hash=hash_secret("device-secret"),
        )
    )
    client = TestClient(
        create_app(
            repository=repo,
            settings=_settings(),
        )
    )

    response = client.put(
        "/api/v1/devices/pecem-01/view-access",
        headers={"Authorization": "Device device-secret"},
        json={"view_secret": ["SHOULD_NOT_LEAK"]},
    )

    assert response.status_code == 422
    assert response.json() == {
        "detail": {
            "code": "invalid_request_payload",
            "message": "Payload inválido.",
        }
    }
    assert "SHOULD_NOT_LEAK" not in response.text


def test_unknown_schema_keeps_specific_422_after_valid_auth():
    from app.repositories.devices import DeviceAuthRecord
    from app.security.credentials import hash_secret

    repo = MemoryDeviceRepository()
    repo.create_device(
        DeviceAuthRecord(
            device_id="pecem-01",
            device_secret_hash=hash_secret("device-secret"),
        )
    )

    client = TestClient(
        create_app(
            repository=repo,
            settings=_settings(),
        )
    )
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    payload["schema_version"] = 999

    response = client.post(
        "/api/v1/devices/pecem-01/snapshot",
        headers={"Authorization": "Device device-secret"},
        json=payload,
    )

    assert response.status_code == 422
    assert response.json() == {
        "detail": {
            "code": "unsupported_snapshot_schema",
            "message": "Versão de snapshot não suportada.",
        }
    }
