from __future__ import annotations

import json
import logging
from pathlib import Path

import pytest

from app.core.errors import (
    EventIdPayloadMismatchError,
    InvalidDeviceCredentialsError,
    PersistenceUnavailableApiError,
)
from app.models.maneuver_event import ManeuverEventIn
from app.repositories.devices import (
    DeviceAuthRecord,
    PersistenceUnavailableError,
)
from app.repositories.memory import MemoryDeviceRepository
from app.security.credentials import hash_secret
from app.services.maneuver_event_service import ManeuverEventService


FIXTURE = Path(__file__).parents[1] / "fixtures" / "maneuver_event_v1.json"
DEVICE_ID = "pecem-01"
DEVICE_SECRET = "device-secret"


def event() -> ManeuverEventIn:
    return ManeuverEventIn.model_validate(
        json.loads(FIXTURE.read_text(encoding="utf-8"))
    )


def repo() -> MemoryDeviceRepository:
    repository = MemoryDeviceRepository()
    repository.create_device(
        DeviceAuthRecord(
            DEVICE_ID,
            hash_secret(DEVICE_SECRET),
        )
    )
    return repository


def test_invalid_device_is_rejected_before_event_persistence():
    service = ManeuverEventService(repo())

    with pytest.raises(InvalidDeviceCredentialsError):
        service.accept_event(
            DEVICE_ID,
            "wrong-secret",
            event(),
        )


def test_accept_and_idempotent_retry_return_same_ingestion_ack():
    service = ManeuverEventService(repo())

    first = service.accept_event(DEVICE_ID, DEVICE_SECRET, event())
    retry = service.accept_event(DEVICE_ID, DEVICE_SECRET, event())

    assert first.ok is True
    assert first.status == "accepted"
    assert retry.status == "idempotent"
    assert retry.ingestion_id == first.ingestion_id
    assert retry.received_at == first.received_at


def test_same_event_id_with_different_content_maps_to_conflict():
    service = ManeuverEventService(repo())
    original = event()
    service.accept_event(DEVICE_ID, DEVICE_SECRET, original)
    changed = original.model_copy(update={"vessel_name": "OUTRO NAVIO"})

    with pytest.raises(EventIdPayloadMismatchError):
        service.accept_event(DEVICE_ID, DEVICE_SECRET, changed)


def test_dispatch_hook_runs_for_accepted_and_idempotent_but_never_breaks_ack():
    dispatched = []

    def dispatch(stored):
        dispatched.append(stored.ingestion_id)
        if len(dispatched) == 2:
            raise RuntimeError("push layer unavailable")

    service = ManeuverEventService(repo(), dispatch_event=dispatch)

    first = service.accept_event(DEVICE_ID, DEVICE_SECRET, event())
    retry = service.accept_event(DEVICE_ID, DEVICE_SECRET, event())

    assert first.status == "accepted"
    assert retry.status == "idempotent"
    assert dispatched == [first.ingestion_id, first.ingestion_id]


class BrokenRepository(MemoryDeviceRepository):
    def accept_maneuver_event_atomic(self, device_id, event):
        raise PersistenceUnavailableError()


def test_repository_failure_maps_to_503():
    repository = BrokenRepository()
    repository.create_device(
        DeviceAuthRecord(DEVICE_ID, hash_secret(DEVICE_SECRET))
    )
    service = ManeuverEventService(repository)

    with pytest.raises(PersistenceUnavailableApiError):
        service.accept_event(DEVICE_ID, DEVICE_SECRET, event())


def test_dispatch_failure_log_never_echoes_sensitive_exception_message(caplog):
    sensitive = (
        "https://push.example/private-endpoint "
        "p256dh-private vapid-private-secret"
    )

    def dispatch(_stored):
        raise RuntimeError(sensitive)

    service = ManeuverEventService(repo(), dispatch_event=dispatch)

    with caplog.at_level(
        logging.ERROR,
        logger="app.services.maneuver_event_service",
    ):
        result = service.accept_event(
            DEVICE_ID,
            DEVICE_SECRET,
            event(),
        )

    assert result.status == "accepted"
    assert sensitive not in caplog.text
    assert "private-endpoint" not in caplog.text
    assert "vapid-private-secret" not in caplog.text
