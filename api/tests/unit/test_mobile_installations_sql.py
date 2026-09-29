from pathlib import Path


MIGRATION = (
    Path(__file__).parents[2]
    / "supabase"
    / "migrations"
    / "010_mobile_installations.sql"
)


def test_mobile_installations_migration_is_independent_from_push_subscription():
    sql = MIGRATION.read_text(encoding="utf-8").lower()

    assert "create table if not exists public.mobile_installations" in sql
    assert "installation_id uuid primary key" in sql
    assert "device_id text not null" in sql
    assert "active boolean not null" in sql
    assert "endpoint" not in sql.split("create table if not exists public.mobile_installations", 1)[1].split(";", 1)[0]


def test_mobile_installations_backfills_existing_push_installation_ids():
    sql = MIGRATION.read_text(encoding="utf-8").lower()

    assert "insert into public.mobile_installations" in sql
    assert "from public.push_installations" in sql
    assert "on conflict (installation_id)" in sql


def test_rotate_view_secret_revokes_mobile_installations_and_push_installations():
    sql = MIGRATION.read_text(encoding="utf-8").lower()

    assert "create or replace function public.rotate_device_view_secret" in sql
    assert "update public.mobile_installations" in sql
    assert "update public.push_installations" in sql
    assert "revoke all on function public.ensure_mobile_installation" in sql
    assert "revoke all on function public.revoke_mobile_installation" in sql
    assert "grant execute on function public.ensure_mobile_installation" in sql
    assert "grant execute on function public.revoke_mobile_installation" in sql
    assert "to service_role" in sql
