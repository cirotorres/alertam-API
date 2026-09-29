from __future__ import annotations

from uuid import UUID

from fastapi.testclient import TestClient

from app.main import create_app
from app.models.maneuver_event import ManeuverEventIn
from app.repositories.devices import (
    DeviceAuthRecord,
    PersistenceUnavailableError,
)
from app.repositories.memory import MemoryDeviceRepository
from app.security.credentials import hash_secret


DEVICE_ID = "pecem-01"
OTHER_ID = "other-01"
VIEW_SECRET = "V" * 43
MANEUVER_ID = "00000000-0000-4000-8000-000000000801"
SELECTED_ID = "00000000-0000-4000-8000-000000000803"
FOREIGN_ID = "00000000-0000-4000-8000-000000000899"


def event(
    event_id: str,
    event_type: str,
    *,
    maneuver_id: str = MANEUVER_ID,
    changes=None,
    operational_at=None,
    operational_marker=None,
) -> ManeuverEventIn:
    raw = {
        "event_id": event_id,
        "maneuver_id": maneuver_id,
        "vessel_identity": "NAME:NAVIO A",
        "vessel_imo": None,
        "vessel_name": "NAVIO A",
        "maneuver_type": "ATRACACAO",
        "event_type": event_type,
        "berth": 4,
        "pob": "28/09 10:00",
        "occurred_at": "2026-09-28T10:05:00-03:00",
        "pob_at": "2026-09-28T10:00:00-03:00",
        "first_observed_at": "2026-09-28T10:04:00-03:00",
        "changes": changes,
    }
    if operational_at is not None or operational_marker is not None:
        raw["operational_at"] = operational_at
        raw["operational_marker"] = operational_marker
    return ManeuverEventIn.model_validate(raw)


def prepared(repository_cls=MemoryDeviceRepository):
    repository = repository_cls()
    repository.create_device(
        DeviceAuthRecord(
            DEVICE_ID,
            "device-hash",
            hash_secret(VIEW_SECRET),
        )
    )
    repository.create_device(
        DeviceAuthRecord(
            OTHER_ID,
            "device-hash",
            hash_secret("O" * 43),
        )
    )
    repository.accept_maneuver_event_atomic(
        DEVICE_ID,
        event(
            "00000000-0000-4000-8000-000000000802",
            "CONFIRMED",
        ),
    )
    repository.accept_maneuver_event_atomic(
        DEVICE_ID,
        event(
            SELECTED_ID,
            "UPDATED",
            changes={"pob": {"from": "28/09 09:30", "to": "28/09 10:00"}},
        ),
    )
    repository.accept_maneuver_event_atomic(
        DEVICE_ID,
        event(
            "00000000-0000-4000-8000-000000000804",
            "COMPLETED",
            operational_at="2026-09-28T10:03:00-03:00",
            operational_marker="ATRAC",
        ),
    )
    repository.accept_maneuver_event_atomic(
        OTHER_ID,
        event(FOREIGN_ID, "CONFIRMED"),
    )
    return repository, TestClient(create_app(repository=repository))


def authenticate(client: TestClient) -> None:
    response = client.post(
        "/api/v1/mobile/session",
        headers={"Authorization": f"Bearer {VIEW_SECRET}"},
        json={"device_id": DEVICE_ID, "installation_id": "10000000-0000-4000-8000-000000000099"},
    )
    assert response.status_code == 200


def test_detail_requires_mobile_session_cookie():
    _, client = prepared()

    response = client.get(
        f"/api/v1/mobile/events/{SELECTED_ID}/detail"
    )

    assert response.status_code == 401


def test_detail_returns_selected_event_and_retained_cycle_in_ingestion_order():
    _, client = prepared()
    authenticate(client)

    response = client.get(
        f"/api/v1/mobile/events/{SELECTED_ID}/detail"
    )

    assert response.status_code == 200
    body = response.json()
    assert body["selected_event_id"] == SELECTED_ID
    assert body["maneuver_id"] == MANEUVER_ID
    assert [item["event_id"] for item in body["events"]] == [
        "00000000-0000-4000-8000-000000000802",
        SELECTED_ID,
        "00000000-0000-4000-8000-000000000804",
    ]
    assert body["events"][1]["pob_at"] == "2026-09-28T10:00:00-03:00"
    assert body["events"][2]["operational_at"] == "2026-09-28T10:03:00-03:00"
    assert body["events"][2]["operational_marker"] == "ATRAC"


def test_detail_foreign_and_unknown_ids_return_same_generic_404():
    _, client = prepared()
    authenticate(client)

    foreign = client.get(
        f"/api/v1/mobile/events/{FOREIGN_ID}/detail"
    )
    unknown = client.get(
        "/api/v1/mobile/events/"
        "00000000-0000-4000-8000-000000000888/detail"
    )

    assert foreign.status_code == 404
    assert unknown.status_code == 404
    assert foreign.json() == unknown.json()
    assert foreign.json()["detail"]["code"] == "maneuver_event_not_found"
    assert "NAVIO A" not in foreign.text


class FailingDetailRepository(MemoryDeviceRepository):
    def get_maneuver_event_detail(self, device_id: str, event_id: UUID):
        raise PersistenceUnavailableError()


def test_detail_maps_repository_failure_to_503():
    _, client = prepared(FailingDetailRepository)
    authenticate(client)

    response = client.get(
        f"/api/v1/mobile/events/{SELECTED_ID}/detail"
    )

    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "persistence_unavailable"
