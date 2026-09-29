from datetime import datetime, timezone
from uuid import UUID

from app.repositories.postgres import PostgresDeviceRepository


INSTALL = UUID("10000000-0000-4000-8000-000000000001")
NOW = datetime(2026, 9, 28, 23, 0, tzinfo=timezone.utc)


class Result:
    def __init__(self, row):
        self._row = row

    def fetchone(self):
        return self._row


class Connection:
    def __init__(self):
        self.calls = []

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def execute(self, sql, params):
        self.calls.append((" ".join(sql.split()), params))
        if "ensure_mobile_installation" in sql:
            return Result((INSTALL, "pecem-01", True, NOW, NOW, None))
        if "from public.mobile_installations" in sql:
            return Result((INSTALL, "pecem-01", True, NOW, NOW, None))
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

    ensured = repo.ensure_mobile_installation("pecem-01", INSTALL)
    loaded = repo.get_mobile_installation("pecem-01", INSTALL)
    revoked = repo.revoke_mobile_installation("pecem-01", INSTALL)

    assert ensured == loaded
    assert ensured is not None and ensured.installation_id == INSTALL
    assert revoked is True
    assert any("ensure_mobile_installation" in sql for sql, _ in connection.calls)
    assert any("revoke_mobile_installation" in sql for sql, _ in connection.calls)
