from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app
from app.models.source_authority import AuthorityStatus, Source
from app.models.source_heartbeat import SourceHeartbeatResponse
from app.repositories.devices import DeviceAuthRecord, PersistenceUnavailableError
from app.repositories.memory import MemoryDeviceRepository
from app.security.credentials import hash_secret

DEVICE = "pecem-c3c"
SECRET = "device-c3c-secret"
CLOUD_SECRET = "A" * 43
BOOT = UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")


def _setup():
    repo = MemoryDeviceRepository()
    repo.put_device(DeviceAuthRecord(DEVICE, hash_secret(SECRET), enabled=True))
    repo.ensure_webpilot_auth_realm("webpilot-c3c")
    repo.authorize_realm_device("webpilot-c3c", DEVICE)
    binding = repo.ensure_cloud_binding(DEVICE, "webpilot-c3c", hash_secret(CLOUD_SECRET))
    assert binding is not None
    calls = []

    def record(device_id, source, request, *, cloud_binding_id=None):
        calls.append((device_id, source, request, cloud_binding_id))
        return SourceHeartbeatResponse(
            status=AuthorityStatus.ACCEPTED, source=source,
            instance_id=request.instance_id, reason_code=None,
            grant=None, renewed=False,
        )
    repo.record_source_heartbeat = record
    settings = Settings(
        _env_file=None, environment="test",
        persistence_backend="memory", mock_seed_device=False,
    )
    return TestClient(create_app(settings=settings, repository=repo)), repo, binding, calls


def test_r12_desktop_heartbeat_requires_device_auth_and_forbids_reason_spoof():
    client, repo, binding, calls = _setup()
    path = f"/api/v1/devices/{DEVICE}/source-heartbeat"
    payload = {"instance_id":str(BOOT), "collection_healthy":True}
    assert client.post(path,json=payload).status_code == 401
    assert client.post(path,json=payload,headers={"Authorization":"Bearer wrong"}).status_code == 401
    attempted = client.post(
        path,
        json={**payload,"last_reason_code":"failover_granted"},
        headers={"Authorization":f"Device {SECRET}"},
    )
    assert attempted.status_code == 422
    assert not calls

    result = client.post(
        path,json=payload,headers={"Authorization":f"Device {SECRET}"},
    )
    assert result.status_code == 200
    assert result.json()["source"] == "desktop"
    assert result.json()["grant"] is None
    assert not result.json()["renewed"]
    assert calls[0][3] is None


def test_r12_cloud_heartbeat_requires_cloudbinding_auth_and_forbids_future_grant():
    client, repo, binding, calls = _setup()
    path = f"/api/v1/cloud-bindings/{binding.cloud_binding_id}/source-heartbeat"
    payload = {
        "instance_id":str(BOOT),"collection_healthy":True,
        "last_candidate_generated_at":datetime.now(timezone.utc).isoformat(),
        "persistent_state_ready":True,
    }
    assert client.post(path,json=payload).status_code == 403
    assert client.post(
        path,json=payload,headers={"Authorization":f"Device {SECRET}"}
    ).status_code == 403
    assert client.post(
        path,json={**payload,"renew_allowed":True},
        headers={"Authorization":f"CloudBinding {CLOUD_SECRET}"},
    ).status_code == 422
    result=client.post(
        path,json=payload,headers={"Authorization":f"CloudBinding {CLOUD_SECRET}"},
    )
    assert result.status_code == 200
    assert result.json()["source"] == "cloud"
    assert result.json()["grant"] is None
    assert calls[-1][3] == binding.cloud_binding_id


def test_r12_heartbeat_persistence_error_is_sanitized():
    client, repo, _, calls = _setup()
    def failure(*a, **kw):
        raise PersistenceUnavailableError()
    repo.record_source_heartbeat = failure
    res=client.post(
        f"/api/v1/devices/{DEVICE}/source-heartbeat",
        headers={"Authorization":f"Device {SECRET}"},
        json={"instance_id":str(BOOT),"collection_healthy":True},
    )
    assert res.status_code == 503
    assert "password" not in res.text
