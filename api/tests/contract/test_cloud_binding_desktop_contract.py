from __future__ import annotations

from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app
from app.repositories.cloud_bindings import WebPilotAuthRealmRecord
from app.repositories.devices import DeviceAuthRecord
from app.repositories.memory import MemoryDeviceRepository
from app.security.credentials import hash_secret


DEVICE_ID = "pecem-01"
DEVICE_SECRET = "desktop-secret"
REALM_ID = "webpilot-pecem"
CREDENTIAL = "A" * 43


def _prepared() -> tuple[TestClient, MemoryDeviceRepository]:
    repo = MemoryDeviceRepository()
    now = repo._clock()
    repo.put_device(
        DeviceAuthRecord(
            DEVICE_ID,
            hash_secret(DEVICE_SECRET),
            enabled=True,
        )
    )
    repo.put_webpilot_auth_realm(
        WebPilotAuthRealmRecord(
            realm_id=REALM_ID,
            active=True,
            created_at=now,
            updated_at=now,
        )
    )
    assert repo.authorize_realm_device(REALM_ID, DEVICE_ID) is not None
    settings = Settings(
        _env_file=None,
        environment="test",
        persistence_backend="memory",
        mock_seed_device=False,
    )
    return (
        TestClient(create_app(settings=settings, repository=repo)),
        repo,
    )


def _headers(secret: str = DEVICE_SECRET) -> dict[str, str]:
    return {"Authorization": f"Device {secret}"}


def test_cloud_binding_openapi_is_desktop_scoped_and_credential_write_only():
    client, _repo = _prepared()
    schema = client.get("/openapi.json").json()

    ensure = schema["components"]["schemas"]["CloudBindingEnsureRequest"]
    rotate = schema["components"]["schemas"]["CloudBindingCredentialRequest"]
    response = schema["components"]["schemas"]["CloudBindingResponse"]

    assert ensure["properties"]["credential"]["writeOnly"] is True
    assert rotate["properties"]["credential"]["writeOnly"] is True
    assert "credential" not in response["properties"]
    assert "credential_hash" not in response["properties"]
    assert set(response["properties"]) == {
        "cloud_binding_id",
        "device_id",
        "realm_id",
        "credential_version",
        "status",
        "device_enabled",
        "realm_authorized",
        "usable",
    }

    cloud_paths = {
        path
        for path in schema["paths"]
        if "cloud-binding" in path
    }
    assert cloud_paths == {
        "/api/v1/devices/{device_id}/cloud-binding",
        "/api/v1/devices/{device_id}/cloud-binding/rotate",
    }
    assert not any(
        "cloud-binding" in path
        for path in schema["paths"]
        if path.startswith("/api/v1/mobile/")
    )


def test_cloud_binding_openapi_documents_desktop_error_contract():
    client, _repo = _prepared()
    paths = client.get("/openapi.json").json()["paths"]
    binding = paths["/api/v1/devices/{device_id}/cloud-binding"]
    rotate = paths["/api/v1/devices/{device_id}/cloud-binding/rotate"]

    assert set(binding["get"]["responses"]) >= {"200", "401", "404", "503"}
    assert set(binding["put"]["responses"]) >= {
        "200",
        "401",
        "403",
        "409",
        "422",
        "503",
    }
    assert set(binding["delete"]["responses"]) >= {
        "200",
        "401",
        "403",
        "404",
        "503",
    }
    assert set(rotate["post"]["responses"]) >= {
        "200",
        "401",
        "403",
        "404",
        "422",
        "503",
    }


def test_cloud_binding_runtime_metadata_shape_and_write_only_credential():
    client, _repo = _prepared()
    path = f"/api/v1/devices/{DEVICE_ID}/cloud-binding"

    created = client.put(
        path,
        headers=_headers(),
        json={"realm_id": REALM_ID, "credential": CREDENTIAL},
    )
    assert created.status_code == 200
    assert set(created.json()) == {
        "cloud_binding_id",
        "device_id",
        "realm_id",
        "credential_version",
        "status",
        "device_enabled",
        "realm_authorized",
        "usable",
    }
    assert CREDENTIAL not in created.text
    assert "credential_hash" not in created.text

    loaded = client.get(path, headers=_headers())
    assert loaded.status_code == 200
    assert loaded.json() == created.json()


def test_cloud_binding_runtime_error_codes_are_predictable_for_desktop():
    client, repo = _prepared()
    path = f"/api/v1/devices/{DEVICE_ID}/cloud-binding"

    assert client.get(path, headers=_headers()).status_code == 404
    assert client.put(
        path,
        headers=_headers("wrong"),
        json={"realm_id": REALM_ID, "credential": CREDENTIAL},
    ).status_code == 401

    repo.revoke_realm_device(REALM_ID, DEVICE_ID)
    assert client.put(
        path,
        headers=_headers(),
        json={"realm_id": REALM_ID, "credential": CREDENTIAL},
    ).status_code == 403

    assert client.post(
        f"{path}/rotate",
        headers=_headers(),
        json={"credential": "short"},
    ).status_code == 422
