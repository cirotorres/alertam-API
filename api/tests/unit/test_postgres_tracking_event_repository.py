import json
from datetime import datetime, timezone
from pathlib import Path

from app.models.vessel_tracking_event import VesselTrackingEventIn
from app.repositories.postgres import PostgresDeviceRepository
from app.repositories.tracking import AcceptTrackingEventStatus


FIXTURE = Path(__file__).parents[1] / "fixtures" / "vessel_tracking_event_v1.json"
NOW = datetime(2026, 9, 28, 16, 0, tzinfo=timezone.utc)


def event():
    return VesselTrackingEventIn.model_validate(
        json.loads(FIXTURE.read_text(encoding="utf-8"))
    )


class Result:
    def fetchone(self):
        return ("accepted", 21, NOW, event().canonical_payload())


class Connection:
    def __init__(self):
        self.calls = []

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def execute(self, sql, params):
        self.calls.append((sql, params))
        return Result()


def test_postgres_accept_tracking_event_uses_dedicated_rpc(monkeypatch):
    connection = Connection()
    monkeypatch.setattr(
        "app.repositories.postgres.psycopg.connect",
        lambda *_args, **_kwargs: connection,
    )
    repository = PostgresDeviceRepository("postgresql://example")

    result = repository.accept_vessel_tracking_event_atomic(
        "pecem-01", event()
    )

    sql, params = connection.calls[0]
    assert "accept_vessel_tracking_event" in sql
    assert params[0] == "pecem-01"
    assert result.status is AcceptTrackingEventStatus.ACCEPTED
    assert result.stored is not None
    assert result.stored.ingestion_id == 21
