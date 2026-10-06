from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
from uuid import UUID

import pytest

from app.core.errors import (
    InvalidViewCredentialsError,
    PersistenceUnavailableApiError,
    SnapshotNotAvailableError,
)
from app.repositories.devices import (
    DeviceAuthRecord,
    PersistenceUnavailableError,
    StoredSnapshot,
)
from app.repositories.memory import MemoryDeviceRepository
from app.security.credentials import hash_secret
from app.services.snapshot_read_service import SnapshotReadService


FIXTURE = Path(__file__).parents[1] / "fixtures" / "mobile_snapshot_v1.json"
DEVICE_ID = "pecem-01"
VIEW_SECRET = "V" * 43
RECEIVED_AT = datetime(2026, 9, 25, 16, 0, tzinfo=timezone.utc)


def _payload() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def _repo(*, with_view_secret: bool = True, with_snapshot: bool = True):
    repo = MemoryDeviceRepository()
    repo.create_device(
        DeviceAuthRecord(
            device_id=DEVICE_ID,
            device_secret_hash="device-hash",
            view_secret_hash=(
                hash_secret(VIEW_SECRET)
                if with_view_secret
                else None
            ),
        )
    )

    if with_snapshot:
        payload = _payload()
        repo.put_snapshot(
            StoredSnapshot(
                device_id=DEVICE_ID,
                snapshot=payload,
                snapshot_schema_version=1,
                boot_id=UUID(payload["boot_id"]),
                sequence=payload["sequence"],
                generated_at=datetime.fromisoformat(
                    payload["generated_at"]
                ),
                received_at=RECEIVED_AT,
            )
        )
    return repo


def test_missing_view_secret_hash_is_generic_401():
    service = SnapshotReadService(
        _repo(with_view_secret=False),
        stale_after_seconds=120,
        clock=lambda: RECEIVED_AT,
    )

    with pytest.raises(InvalidViewCredentialsError):
        service.get_snapshot(DEVICE_ID, VIEW_SECRET)


def test_wrong_view_secret_is_generic_401():
    service = SnapshotReadService(
        _repo(),
        stale_after_seconds=120,
        clock=lambda: RECEIVED_AT,
    )

    with pytest.raises(InvalidViewCredentialsError):
        service.get_snapshot(DEVICE_ID, "X" * 43)

def test_missing_snapshot_after_valid_auth_is_404():
    service = SnapshotReadService(
        _repo(with_snapshot=False),
        stale_after_seconds=120,
        clock=lambda: RECEIVED_AT,
    )

    with pytest.raises(SnapshotNotAvailableError):
        service.get_snapshot(DEVICE_ID, VIEW_SECRET)


@pytest.mark.parametrize(
    ("age", "online"),
    [
        (119, True),
        (120, False),
    ],
)
def test_online_boundary_uses_received_at(age, online):
    now = RECEIVED_AT + timedelta(seconds=age)
    service = SnapshotReadService(
        _repo(),
        stale_after_seconds=120,
        clock=lambda: now,
    )

    result = service.get_snapshot(DEVICE_ID, VIEW_SECRET)

    assert result.meta.age_seconds == age
    assert result.meta.collector_online is online
    assert result.meta.stale_after_seconds == 120

def test_offline_snapshot_is_still_returned():
    now = RECEIVED_AT + timedelta(minutes=10)
    service = SnapshotReadService(
        _repo(),
        stale_after_seconds=120,
        clock=lambda: now,
    )

    result = service.get_snapshot(DEVICE_ID, VIEW_SECRET)

    assert result.meta.collector_online is False
    assert result.snapshot.sequence == 1


def test_generated_at_does_not_affect_online_status():
    repo = _repo()
    stored = repo.get_snapshot(DEVICE_ID)
    ancient = stored.snapshot.copy()
    ancient["generated_at"] = "2000-01-01T00:00:00-03:00"
    repo.put_snapshot(
        StoredSnapshot(
            device_id=stored.device_id,
            snapshot=ancient,
            snapshot_schema_version=stored.snapshot_schema_version,
            boot_id=stored.boot_id,
            sequence=stored.sequence,
            generated_at=datetime.fromisoformat(
                ancient["generated_at"]
            ),
            received_at=stored.received_at,
        )
    )

    service = SnapshotReadService(
        repo,
        stale_after_seconds=120,
        clock=lambda: RECEIVED_AT + timedelta(seconds=10),
    )

    result = service.get_snapshot(DEVICE_ID, VIEW_SECRET)

    assert result.meta.age_seconds == 10
    assert result.meta.collector_online is True

class BrokenReadRepository(MemoryDeviceRepository):
    def get_snapshot(self, device_id):
        raise PersistenceUnavailableError()


def test_read_persistence_failure_maps_to_503():
    repo = BrokenReadRepository(
        devices=[
            DeviceAuthRecord(
                device_id=DEVICE_ID,
                device_secret_hash="device-hash",
                view_secret_hash=hash_secret(VIEW_SECRET),
            )
        ]
    )
    service = SnapshotReadService(
        repo,
        stale_after_seconds=120,
        clock=lambda: RECEIVED_AT,
    )

    with pytest.raises(PersistenceUnavailableApiError) as exc:
        service.get_snapshot(DEVICE_ID, VIEW_SECRET)

    assert exc.value.status_code == 503


def test_disabled_device_keeps_view_secret_read_and_reports_disabled_meta():
    repo = _repo()
    current = repo.get_device_auth(DEVICE_ID)
    repo._devices[DEVICE_ID] = DeviceAuthRecord(
        device_id=current.device_id,
        device_secret_hash=current.device_secret_hash,
        view_secret_hash=current.view_secret_hash,
        description="Notebook do pai",
        enabled=False,
    )
    service = SnapshotReadService(
        repo,
        stale_after_seconds=120,
        clock=lambda: RECEIVED_AT,
    )

    result = service.get_snapshot(DEVICE_ID, VIEW_SECRET)

    assert result.meta.device_enabled is False
    assert result.snapshot.sequence == 1
