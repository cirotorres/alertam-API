from pathlib import Path


MIGRATION = (
    Path(__file__).parents[2]
    / "supabase"
    / "migrations"
    / "009_vessel_tracking_retention.sql"
)


def test_tracking_retention_deletes_only_events_older_than_30_days():
    sql = MIGRATION.read_text(encoding="utf-8").lower()

    assert "vessel_tracking_events" in sql
    assert "interval '30 days'" in sql
    assert "ingested_at <" in sql
    assert "tracked_vessels" not in sql
    assert "push_installations" not in sql
    assert "delete from public.maneuver_events" not in sql


def test_tracking_retention_function_is_service_role_only():
    sql = MIGRATION.read_text(encoding="utf-8").lower()

    assert "security definer" in sql
    assert "revoke all on function" in sql
    assert "grant execute on function" in sql
    assert "to service_role" in sql
