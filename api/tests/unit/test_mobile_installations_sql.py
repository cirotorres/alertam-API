from pathlib import Path


MIGRATIONS = Path(__file__).parents[2] / "supabase" / "migrations"
MIGRATION_010 = MIGRATIONS / "010_mobile_installations.sql"
MIGRATION_013 = MIGRATIONS / "013_mobile_installation_management.sql"


def test_mobile_installations_migration_is_independent_from_push_subscription():
    sql = MIGRATION_010.read_text(encoding="utf-8").lower()

    assert "create table if not exists public.mobile_installations" in sql
    assert "installation_id uuid primary key" in sql
    assert "device_id text not null" in sql
    assert "active boolean not null" in sql
    table = sql.split(
        "create table if not exists public.mobile_installations", 1
    )[1].split(";", 1)[0]
    assert "endpoint" not in table


def test_mobile_installations_backfills_existing_push_installation_ids():
    sql = MIGRATION_010.read_text(encoding="utf-8").lower()

    assert "insert into public.mobile_installations" in sql
    assert "from public.push_installations" in sql
    assert "on conflict (installation_id)" in sql


def test_management_migration_adds_platform_and_unique_display_code():
    sql = MIGRATION_013.read_text(encoding="utf-8").lower()

    assert "add column if not exists platform" in sql
    assert "add column if not exists display_code" in sql
    assert "set not null" in sql
    assert "mobile_installations_display_code" in sql
    assert "unique" in sql
    assert "abcdefghjklmnpqrstuvwxyz23456789" in sql


def test_management_migration_backfills_legacy_rows():
    sql = MIGRATION_013.read_text(encoding="utf-8").lower()

    assert "where display_code is null" in sql
    assert "platform = 'other'" in sql
    assert "random" in sql


def test_ensure_does_not_reactivate_revoked_installation():
    sql = MIGRATION_013.read_text(encoding="utf-8").lower()
    ensure = sql.split(
        "create or replace function public.ensure_mobile_installation(", 1
    )[1].split("$$;", 1)[0]

    assert "v_existing.active = false" in ensure
    assert "return;" in ensure
    assert "set active = true" not in ensure


def test_management_migration_defines_touch_and_complete_revoke():
    sql = MIGRATION_013.read_text(encoding="utf-8").lower()

    assert "create or replace function public.touch_mobile_installation" in sql
    revoke = sql.split(
        "create or replace function public.revoke_mobile_installation(", 1
    )[1].split("$$;", 1)[0]
    assert "update public.tracked_vessels" in revoke
    assert "update public.push_installations" in revoke
    assert "endpoint = null" in revoke
    assert "active = false" in revoke


def test_management_migration_lists_only_recent_revoked_plus_active():
    sql = MIGRATION_013.read_text(encoding="utf-8").lower()

    assert "create or replace function public.list_mobile_installations" in sql
    list_fn = sql.split(
        "create or replace function public.list_mobile_installations(", 1
    )[1].split("$$;", 1)[0]
    assert "mi.active = true" in list_fn
    assert "mi.revoked_at >= p_revoked_since" in list_fn


def test_rotate_view_secret_still_revokes_mobile_tracking_and_push():
    sql = MIGRATION_013.read_text(encoding="utf-8").lower()
    rotate = sql.split(
        "create or replace function public.rotate_device_view_secret(", 1
    )[1].split("$$;", 1)[0]

    assert "update public.mobile_installations" in rotate
    assert "update public.tracked_vessels" in rotate
    assert "update public.push_installations" in rotate
    assert "endpoint = null" in rotate
