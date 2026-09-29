from pathlib import Path

MIGRATION = (
    Path(__file__).parents[2] / "supabase" / "migrations"
    / "011_tracked_vessels.sql"
)


def test_tracked_vessels_migration_is_installation_scoped_and_persistent():
    sql = MIGRATION.read_text(encoding="utf-8").lower()

    assert "create table if not exists public.tracked_vessels" in sql
    assert "mobile_installations" in sql
    assert "started_at" in sql
    assert "stopped_at" in sql
    assert "last_seen_at" in sql
    assert "current jsonb" in sql
    assert "on delete cascade" in sql


def test_rotation_and_mobile_revoke_deactivate_trackings():
    sql = MIGRATION.read_text(encoding="utf-8").lower()

    assert "create or replace function public.rotate_device_view_secret" in sql
    assert "create or replace function public.revoke_mobile_installation" in sql
    assert sql.count("update public.tracked_vessels") >= 2
