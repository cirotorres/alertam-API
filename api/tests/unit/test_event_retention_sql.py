from __future__ import annotations

from pathlib import Path


MIGRATION = (
    Path(__file__).parents[2]
    / "supabase"
    / "migrations"
    / "006_event_retention.sql"
)


def migration_sql() -> str:
    return MIGRATION.read_text(encoding="utf-8").lower()


def test_retention_sql_keeps_thirty_day_window_and_deletes_deliveries_first():
    sql = migration_sql()

    assert "interval '30 days'" in sql
    deliveries_delete = sql.index("delete from public.push_deliveries")
    events_delete = sql.index("delete from public.maneuver_events")
    assert deliveries_delete < events_delete

def test_retention_sql_never_deletes_push_installations():
    sql = migration_sql()

    assert "delete from public.push_installations" not in sql


def test_retention_cleanup_is_explicit_service_role_function():
    sql = migration_sql()

    assert "cleanup_event_retention" in sql
    assert "security definer" in sql
    assert "grant execute" in sql
    assert "to service_role" in sql
