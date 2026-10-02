from pathlib import Path


MIGRATION = (
    Path(__file__).parents[2]
    / "supabase"
    / "migrations"
    / "015_event_retention_cron.sql"
)


def migration_sql() -> str:
    return MIGRATION.read_text(encoding="utf-8").lower()


def test_retention_cron_installs_pg_cron_and_schedules_named_daily_job():
    sql = migration_sql()

    assert "create extension if not exists pg_cron" in sql
    assert "cron.schedule" in sql
    assert "alertam-cleanup-event-retention" in sql
    assert "select public.cleanup_event_retention();" in sql
    assert "15 3 * * *" in sql


def test_retention_cron_does_not_change_thirty_day_cleanup_contract():
    sql = migration_sql()

    assert "delete from public.maneuver_events" not in sql
    assert "delete from public.push_deliveries" not in sql
    assert "interval '30 days'" not in sql
