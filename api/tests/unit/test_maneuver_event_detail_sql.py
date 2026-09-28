from pathlib import Path


MIGRATION = (
    Path(__file__).parents[2]
    / "supabase"
    / "migrations"
    / "007_maneuver_event_detail_index.sql"
)


def test_detail_migration_adds_only_device_cycle_ingestion_index():
    sql = MIGRATION.read_text(encoding="utf-8").lower()

    assert "create index if not exists" in sql
    assert "(device_id, maneuver_id, ingestion_id)" in sql
    assert "create table" not in sql
    assert "alter table" not in sql
