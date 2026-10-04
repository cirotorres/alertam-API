from pathlib import Path

MIGRATION = (
    Path(__file__).parents[2]
    / "supabase"
    / "migrations"
    / "017_anchorage_notifications.sql"
)


def test_anchorage_preference_migration_defaults_existing_installations_on():
    sql = MIGRATION.read_text(encoding="utf-8").lower()

    assert "pref_anchored boolean not null default true" in sql
    assert "p_anchored boolean" in sql
    assert "pref_anchored = p_anchored" in sql
    assert "drop function if exists public.update_push_preferences" not in sql
    assert "grant execute on function public.update_push_preferences" in sql
