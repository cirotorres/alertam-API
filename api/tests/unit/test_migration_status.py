from __future__ import annotations

from pathlib import Path

from scripts.migration_status import (
    MigrationStatus,
    build_status,
    list_local_migrations,
    render_status,
)


def test_list_local_migrations_returns_sorted_sql_filenames(tmp_path: Path):
    (tmp_path / "010_last.sql").write_text("-- 10", encoding="utf-8")
    (tmp_path / "002_second.sql").write_text("-- 2", encoding="utf-8")
    (tmp_path / "README.md").write_text("ignore", encoding="utf-8")
    (tmp_path / "001_first.sql").write_text("-- 1", encoding="utf-8")

    assert list_local_migrations(tmp_path) == (
        "001_first.sql",
        "002_second.sql",
        "010_last.sql",
    )


def test_build_status_reports_database_up_to_date():
    status = build_status(
        ("001_devices.sql", "002_rpc.sql"),
        ("001_devices.sql", "002_rpc.sql"),
    )

    assert status == MigrationStatus(
        local=("001_devices.sql", "002_rpc.sql"),
        applied=("001_devices.sql", "002_rpc.sql"),
        pending=(),
        unknown=(),
        migration_table_exists=True,
    )
    assert status.is_synced is True


def test_build_status_reports_pending_and_unknown_migrations():
    status = build_status(
        ("001_devices.sql", "002_rpc.sql", "003_new.sql"),
        ("001_devices.sql", "099_removed.sql"),
    )

    assert status.pending == ("002_rpc.sql", "003_new.sql")
    assert status.unknown == ("099_removed.sql",)
    assert status.is_synced is False


def test_build_status_treats_missing_schema_migrations_as_fresh_database():
    status = build_status(
        ("001_devices.sql", "002_rpc.sql"),
        (),
        migration_table_exists=False,
    )

    assert status.pending == ("001_devices.sql", "002_rpc.sql")
    assert status.unknown == ()
    assert status.migration_table_exists is False
    assert status.is_synced is False


def test_render_status_explains_up_to_date_database():
    status = build_status(
        ("001_devices.sql", "002_rpc.sql"),
        ("001_devices.sql", "002_rpc.sql"),
    )

    output = render_status(status)

    assert "Migrations locais:    2" in output
    assert "Migrations aplicadas: 2" in output
    assert "Pendentes:            0" in output
    assert "Banco atualizado" in output


def test_render_status_lists_pending_and_unknown_migrations():
    status = build_status(
        ("001_devices.sql", "002_rpc.sql", "003_new.sql"),
        ("001_devices.sql", "099_removed.sql"),
    )

    output = render_status(status)

    assert "PENDENTES:" in output
    assert "002_rpc.sql" in output
    assert "003_new.sql" in output
    assert "DESCONHECIDAS NO BANCO:" in output
    assert "099_removed.sql" in output
    assert "make prod-migrate" in output
