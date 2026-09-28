from datetime import datetime, timezone
from uuid import UUID

from app.models.maneuver_event import ManeuverEventIn
from app.repositories.postgres import PostgresDeviceRepository


SELECTED = UUID("00000000-0000-4000-8000-000000000702")
MANEUVER = UUID("00000000-0000-4000-8000-000000000701")
NOW = datetime(2026, 9, 28, 15, 0, tzinfo=timezone.utc)


def payload(event_id: str) -> dict[str, object]:
    return ManeuverEventIn.model_validate({
        "event_id": event_id,
        "maneuver_id": str(MANEUVER),
        "vessel_identity": "NAME:NAVIO A",
        "vessel_imo": None,
        "vessel_name": "NAVIO A",
        "maneuver_type": "ATRACACAO",
        "event_type": "CONFIRMED",
        "berth": 4,
        "pob": "28/09 10:00",
        "occurred_at": "2026-09-28T10:00:00-03:00",
        "changes": None,
    }).canonical_payload()


class Result:
    def __init__(self, *, one=None, many=None):
        self.one = one
        self.many = many if many is not None else []

    def fetchone(self):
        return self.one

    def fetchall(self):
        return self.many


class Connection:
    def __init__(self, selected_row):
        self.selected_row = selected_row
        self.calls = []

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def execute(self, sql, params):
        self.calls.append((sql, params))
        if len(self.calls) == 1:
            return Result(one=self.selected_row)
        return Result(many=[
            (7, "pecem-01", payload(str(SELECTED)), NOW),
            (
                8,
                "pecem-01",
                payload("00000000-0000-4000-8000-000000000703"),
                NOW,
            ),
        ])


def test_postgres_detail_verifies_device_before_loading_cycle(monkeypatch):
    connection = Connection((MANEUVER,))
    monkeypatch.setattr(
        "app.repositories.postgres.psycopg.connect",
        lambda *_args, **_kwargs: connection,
    )
    repo = PostgresDeviceRepository("postgresql://example")

    detail = repo.get_maneuver_event_detail("pecem-01", SELECTED)

    assert detail is not None
    assert detail.selected_event_id == SELECTED
    assert detail.maneuver_id == MANEUVER
    assert [item.ingestion_id for item in detail.events] == [7, 8]
    first_sql, first_params = connection.calls[0]
    second_sql, second_params = connection.calls[1]
    assert "device_id = %s and event_id = %s" in " ".join(first_sql.split())
    assert first_params == ("pecem-01", SELECTED)
    assert "device_id = %s and maneuver_id = %s" in " ".join(second_sql.split())
    assert "order by ingestion_id asc" in " ".join(second_sql.split())
    assert second_params == ("pecem-01", MANEUVER)


def test_postgres_detail_stops_after_foreign_or_unknown_selected_event(monkeypatch):
    connection = Connection(None)
    monkeypatch.setattr(
        "app.repositories.postgres.psycopg.connect",
        lambda *_args, **_kwargs: connection,
    )
    repo = PostgresDeviceRepository("postgresql://example")

    assert repo.get_maneuver_event_detail("pecem-01", SELECTED) is None
    assert len(connection.calls) == 1


def test_postgres_detail_returns_none_if_cycle_expires_between_queries(monkeypatch):
    connection = Connection((MANEUVER,))
    original_execute = connection.execute

    def execute(sql, params):
        result = original_execute(sql, params)
        if len(connection.calls) == 2:
            return Result(many=[])
        return result

    connection.execute = execute
    monkeypatch.setattr(
        "app.repositories.postgres.psycopg.connect",
        lambda *_args, **_kwargs: connection,
    )
    repo = PostgresDeviceRepository("postgresql://example")

    assert repo.get_maneuver_event_detail("pecem-01", SELECTED) is None
