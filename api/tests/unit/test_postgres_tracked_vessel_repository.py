from datetime import datetime, timezone
from uuid import UUID

from app.repositories.postgres import PostgresDeviceRepository
from app.repositories.tracking import VesselEvidence


TRACK_ID = UUID("30000000-0000-4000-8000-000000000001")
INSTALL = UUID("20000000-0000-4000-8000-000000000001")
NOW = datetime(2026, 9, 28, 23, 10, tzinfo=timezone.utc)
CURRENT = {
    "present": True,
    "status": "PREVISTO",
    "section": "PREVISTO",
    "berth": 4,
    "side": "BB",
    "eta": "28/09 12:30",
    "etb_ets": "28/09 13:00",
    "pob": None,
    "pob_at": None,
}


class Result:
    def __init__(self, row=None, rows=None):
        self.row = row
        self.rows = rows or []

    def fetchone(self):
        return self.row

    def fetchall(self):
        return self.rows


class Connection:
    def __init__(self):
        self.calls = []

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def execute(self, sql, params):
        compact = " ".join(sql.split())
        self.calls.append((compact, params))
        row = (
            TRACK_ID,
            "pecem-01",
            INSTALL,
            "IMO:1234567",
            "1234567",
            "NAVIO A",
            NOW,
            True,
            None,
            NOW,
            CURRENT,
        )
        if "upsert_tracked_vessel" in sql:
            return Result(row=row)
        if "deactivate_tracked_vessel" in sql:
            return Result(row=(
                *row[:7],
                False,
                NOW,
                *row[9:],
            ))
        if "from public.tracked_vessels" in sql:
            if "tracked_vessel_id = %s" in compact:
                return Result(row=row)
            return Result(rows=[row])
        raise AssertionError(compact)


def test_postgres_tracked_vessel_crud_contract(monkeypatch):
    connection = Connection()
    monkeypatch.setattr(
        "app.repositories.postgres.psycopg.connect",
        lambda *_args, **_kwargs: connection,
    )
    repo = PostgresDeviceRepository("postgresql://example")
    evidence = VesselEvidence(
        vessel_identity="IMO:1234567",
        vessel_imo="1234567",
        vessel_name="NAVIO A",
        current=CURRENT,
        observed_at=NOW,
    )

    created = repo.upsert_tracked_vessel("pecem-01", INSTALL, evidence)
    listed = repo.list_tracked_vessels("pecem-01", INSTALL)
    loaded = repo.get_tracked_vessel("pecem-01", INSTALL, TRACK_ID)
    stopped = repo.deactivate_tracked_vessel("pecem-01", INSTALL, TRACK_ID)

    assert created is not None and created.tracked_vessel_id == TRACK_ID
    assert listed == (created,)
    assert loaded == created
    assert stopped is not None and stopped.active is False
    assert any("upsert_tracked_vessel" in sql for sql, _ in connection.calls)
    assert any("deactivate_tracked_vessel" in sql for sql, _ in connection.calls)
