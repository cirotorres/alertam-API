from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID

from fastapi.testclient import TestClient

from app.main import create_app
from app.models.vessel_tracking_event import VesselTrackingEventIn
from app.repositories.devices import DeviceAuthRecord, StoredSnapshot
from app.repositories.memory import MemoryDeviceRepository
from app.security.credentials import hash_secret


DEVICE = "pecem-01"
SECRET = "V" * 43
INSTALL_A = "20000000-0000-4000-8000-000000000001"
INSTALL_B = "20000000-0000-4000-8000-000000000002"
SNAPSHOT = Path(__file__).parents[1] / "fixtures" / "mobile_snapshot_v1.json"
TRACKING_EVENT = Path(__file__).parents[1] / "fixtures" / "vessel_tracking_event_v1.json"


def repository(with_snapshot=True):
    repo = MemoryDeviceRepository()
    repo.create_device(
        DeviceAuthRecord(DEVICE, "device-hash", hash_secret(SECRET))
    )
    if with_snapshot:
        raw = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
        repo.put_snapshot(StoredSnapshot(
            device_id=DEVICE,
            snapshot=raw,
            snapshot_schema_version=1,
            boot_id=UUID(raw["boot_id"]),
            sequence=raw["sequence"],
            generated_at=datetime.fromisoformat(raw["generated_at"]),
            received_at=datetime(2026, 9, 25, 16, 40, tzinfo=timezone.utc),
        ))
    return repo


def client_for(repo, installation_id):
    client = TestClient(create_app(repository=repo))
    response = client.post(
        "/api/v1/mobile/session",
        headers={"Authorization": f"Bearer {SECRET}"},
        json={"device_id": DEVICE, "installation_id": installation_id},
    )
    assert response.status_code == 200
    return client


def start(client, **overrides):
    body = {
        "vessel_identity": "IMO:1234567",
        "vessel_imo": "1234567",
        "vessel_name": "NAVIO A",
        **overrides,
    }
    return client.post("/api/v1/mobile/tracked-vessels", json=body)


def test_tracking_is_idempotent_per_installation_and_isolated_between_installations():
    repo = repository()
    a = client_for(repo, INSTALL_A)

    first = start(a)
    repeated = start(a)

    assert first.status_code == 200
    assert repeated.status_code == 200
    assert repeated.json()["tracked_vessel_id"] == first.json()["tracked_vessel_id"]
    assert first.json()["current"]["status"] == "ATRACANDO"
    assert first.json()["current"]["berth"] == 2
    assert first.json()["last_seen_at"] is not None

    b = client_for(repo, INSTALL_B)
    second_install = start(b)
    assert second_install.status_code == 200
    assert second_install.json()["tracked_vessel_id"] != first.json()["tracked_vessel_id"]

    assert len(a.get("/api/v1/mobile/tracked-vessels").json()) == 1
    assert len(b.get("/api/v1/mobile/tracked-vessels").json()) == 1


def test_arbitrary_target_not_in_snapshot_or_retained_event_is_rejected():
    repo = repository()
    client = client_for(repo, INSTALL_A)

    response = start(
        client,
        vessel_identity="IMO:9999999",
        vessel_imo="9999999",
        vessel_name="INVENTADO",
    )

    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "vessel_tracking_target_not_found"


def test_retained_tracking_event_can_seed_tracking_without_current_snapshot():
    repo = repository(with_snapshot=False)
    raw = json.loads(TRACKING_EVENT.read_text(encoding="utf-8"))
    event = VesselTrackingEventIn.model_validate(raw)
    repo.accept_vessel_tracking_event_atomic(DEVICE, event)
    client = client_for(repo, INSTALL_A)

    response = start(client)

    assert response.status_code == 200
    body = response.json()
    assert body["current"]["eta"] == "28/09 12:30"
    assert body["last_seen_at"] == raw["occurred_at"]


def test_stop_is_idempotent_and_does_not_delete_tracking_record():
    repo = repository()
    client = client_for(repo, INSTALL_A)
    tracked = start(client).json()
    path = f"/api/v1/mobile/tracked-vessels/{tracked['tracked_vessel_id']}"

    assert client.delete(path).status_code == 204
    assert client.delete(path).status_code == 204

    listed = client.get("/api/v1/mobile/tracked-vessels").json()
    assert listed == []
    stored = repo.get_tracked_vessel(
        DEVICE,
        UUID(INSTALL_A),
        UUID(tracked["tracked_vessel_id"]),
    )
    assert stored is not None
    assert stored.active is False
    assert stored.stopped_at is not None


def test_name_fallback_promotes_same_tracking_to_imo_on_exact_normalized_name():
    repo = repository(with_snapshot=False)
    raw = json.loads(TRACKING_EVENT.read_text(encoding="utf-8"))
    raw["vessel_identity"] = "NAME:NAVIO A"
    raw["vessel_imo"] = None
    event = VesselTrackingEventIn.model_validate(raw)
    repo.accept_vessel_tracking_event_atomic(DEVICE, event)
    client = client_for(repo, INSTALL_A)

    first = start(
        client,
        vessel_identity="NAME:NAVIO A",
        vessel_imo=None,
    ).json()

    snapshot = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    snapshot["vessels"][0]["name"] = "  navio   a "
    repo.put_snapshot(StoredSnapshot(
        device_id=DEVICE,
        snapshot=snapshot,
        snapshot_schema_version=1,
        boot_id=UUID(snapshot["boot_id"]),
        sequence=2,
        generated_at=datetime.fromisoformat(snapshot["generated_at"]),
        received_at=datetime(2026, 9, 25, 16, 45, tzinfo=timezone.utc),
    ))

    promoted = start(client).json()

    assert promoted["tracked_vessel_id"] == first["tracked_vessel_id"]
    assert promoted["vessel_identity"] == "IMO:1234567"
    assert promoted["vessel_imo"] == "1234567"


def test_same_device_other_installation_cannot_stop_tracking():
    repo = repository()
    a = client_for(repo, INSTALL_A)
    tracked = start(a).json()
    b = client_for(repo, INSTALL_B)

    response = b.delete(
        f"/api/v1/mobile/tracked-vessels/{tracked['tracked_vessel_id']}"
    )

    assert response.status_code == 404


def test_tracking_target_identity_must_match_imo_or_normalized_name():
    repo = repository()
    client = client_for(repo, INSTALL_A)

    mismatched_imo = start(
        client,
        vessel_identity="IMO:9999999",
        vessel_imo="1234567",
        vessel_name="NAVIO A",
    )
    mismatched_name = start(
        client,
        vessel_identity="NAME:OUTRO",
        vessel_imo=None,
        vessel_name="  navio   a ",
    )

    assert mismatched_imo.status_code == 422
    assert mismatched_name.status_code == 422
