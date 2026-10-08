from pathlib import Path

MIGRATION = Path(__file__).parents[2] / "supabase" / "migrations" / "019_cloud_binding_realm.sql"


def test_cloud_binding_migration_has_tables_constraints_rls_and_hardened_rpcs():
    sql = MIGRATION.read_text(encoding="utf-8").lower()

    for table in (
        "public.webpilot_auth_realms",
        "public.webpilot_auth_realm_devices",
        "public.cloud_bindings",
    ):
        assert f"create table if not exists {table}" in sql
        assert f"alter table {table} enable row level security" in sql

    assert "references public.devices(device_id)" in sql
    assert "references public.webpilot_auth_realms(realm_id)" in sql
    assert "primary key (realm_id, device_id)" in sql
    assert "create unique index" in sql
    assert "where status = 'active'" in sql
    assert "credential_version > 0" in sql
    assert "status = 'active' and revoked_at is null" in sql
    assert "status = 'revoked' and revoked_at is not null" in sql
    assert "revoked_at is null or revoked_at >= authorized_at" in sql

    for fn in (
        "ensure_cloud_binding",
        "rotate_cloud_binding",
        "revoke_cloud_binding",
        "authorize_realm_device",
        "revoke_realm_device",
        "set_webpilot_auth_realm_active",
    ):
        assert f"function public.{fn}" in sql

    assert sql.count("security definer") >= 6
    assert sql.count("set search_path = pg_catalog, public") >= 6

    for token in (
        "public.devices",
        "public.webpilot_auth_realms",
        "public.webpilot_auth_realm_devices",
        "public.cloud_bindings",
    ):
        assert token in sql

    assert "revoke all on table public.webpilot_auth_realms from anon, authenticated" in sql
    assert "revoke all on table public.webpilot_auth_realm_devices from anon, authenticated" in sql
    assert "revoke all on table public.cloud_bindings from anon, authenticated" in sql
    assert "from public, anon, authenticated" in sql
    assert "to service_role" in sql
    assert "create policy" not in sql
    assert "exception when unique_violation" in sql
    assert sql.count("cloud_binding_conflict") >= 2
