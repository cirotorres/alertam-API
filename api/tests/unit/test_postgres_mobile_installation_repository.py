from datetime import datetime, timedelta, timezone
from uuid import UUID

from app.repositories.postgres import PostgresDeviceRepository


INSTALL = UUID("10000000-0000-4000-8000-000000000001")
NOW = datetime(2026, 9, 28, 23, 0, tzinfo=timezone.utc)
SINCE = NOW - timedelta(days=30)
ROW = (
    INSTALL,
    "pecem-01",
    True,
    NOW,
    NOW,
    None,
    "ios",
    "K7M4Q2",
)


class Result:
    def __init__(self, row=None, rows=None):
        self._row = row
        self._rows = rows if rows is not None else ([] if row is None else [row])

    def fetchone(self):
        return self._row

    def fetchall(self):
        return self._rows


class Connection:
    def __init__(self):
        self.calls = []

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def execute(self, sql, params):
        normalized = " ".join(sql.split())
        self.calls.append((normalized, params))
        if "ensure_mobile_installation" in sql:
            return Result(ROW)
        if "touch_mobile_installation" in sql:
            return Result(ROW)
        if "list_mobile_installations" in sql:
            return Result(rows=[ROW])
        if "from public.mobile_installations" in sql:
            return Result(ROW)
        if "revoke_mobile_installation" in sql:
            return Result((True,))
        raise AssertionError(sql)


def test_postgres_mobile_installation_repository_contract(monkeypatch):
    connection = Connection()
    monkeypatch.setattr(
        "app.repositories.postgres.psycopg.connect",
        lambda *_args, **_kwargs: connection,
    )
    repo = PostgresDeviceRepository("postgresql://example")

    ensured = repo.ensure_mobile_installation(
        "pecem-01",
        INSTALL,
        platform="ios",
        display_code="K7M4Q2",
    )
    loaded = repo.get_mobile_installation("pecem-01", INSTALL)
    touched = repo.touch_mobile_installation(
        "pecem-01",
        INSTALL,
        platform="android",
    )
    listed = repo.list_mobile_installations(
        "pecem-01",
        revoked_since=SINCE,
    )
    revoked = repo.revoke_mobile_installation("pecem-01", INSTALL)

    assert ensured == loaded == touched == listed[0]
    assert ensured is not None
    assert ensured.platform == "ios"
    assert ensured.display_code == "K7M4Q2"
    assert revoked is True

    ensure_call = next(
        call for call in connection.calls
        if "ensure_mobile_installation" in call[0]
    )
    assert ensure_call[1] == ("pecem-01", INSTALL, "ios", "K7M4Q2")
    touch_call = next(
        call for call in connection.calls
        if "touch_mobile_installation" in call[0]
    )
    assert touch_call[1] == ("pecem-01", INSTALL, "android")
    list_call = next(
        call for call in connection.calls
        if "list_mobile_installations" in call[0]
    )
    assert list_call[1] == ("pecem-01", SINCE)


def test_postgres_maps_display_code_unique_violation(monkeypatch):
    import psycopg
    import pytest

    from app.repositories.devices import (
        MobileInstallationDisplayCodeConflictError,
    )

    class ConflictConnection(Connection):
        def execute(self, _sql, _params):
            raise psycopg.errors.UniqueViolation(
                'duplicate key value violates unique constraint '
                '"mobile_installations_display_code_unique"'
            )

    monkeypatch.setattr(
        "app.repositories.postgres.psycopg.connect",
        lambda *_args, **_kwargs: ConflictConnection(),
    )
    repo = PostgresDeviceRepository("postgresql://example")

    with pytest.raises(MobileInstallationDisplayCodeConflictError):
        repo.ensure_mobile_installation(
            "pecem-01",
            INSTALL,
            platform="ios",
            display_code="K7M4Q2",
        )
