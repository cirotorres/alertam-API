from __future__ import annotations

from pathlib import Path


MIGRATION = (
    Path(__file__).parents[2]
    / "supabase"
    / "migrations"
    / "021_source_authority_snapshots.sql"
)


def _sql() -> str:
    return MIGRATION.read_text(encoding="utf-8").lower()


def test_c3b_migration_021_declares_source_authority_schema_and_backend_snapshot_metadata():
    sql = _sql()
    for fragment in (
        "create table if not exists public.device_source_authority",
        "create table if not exists public.device_source_heartbeats",
        "create table if not exists public.device_source_authority_transitions",
        "snapshot_source",
        "snapshot_authority_epoch",
        "snapshot_authority_lease_id",
        "snapshot_writer_instance_id",
        "mode text not null default 'legacy'",
        "authority_epoch bigint not null default 0",
        "observed_realm_epoch bigint",
    ):
        assert fragment in sql


def test_c3b_migration_021_keeps_realm_epoch_out_of_source_fencing():
    sql = _sql()
    authority_block = sql.split(
        "create table if not exists public.device_source_authority", 1
    )[1].split(");", 1)[0]
    assert "authority_epoch" in authority_block
    assert "observed_realm_epoch" in authority_block
    assert "\n    realm_epoch " not in authority_block


def test_c3b_migration_021_has_distinct_current_grant_transition_and_bootstrap_rpcs():
    sql = _sql()
    for name in (
        "public.bootstrap_managed_source_authority",
        "public.accept_managed_snapshot_current_grant",
        "public.accept_managed_snapshot_transition_candidate",
        "public.return_source_authority_to_legacy",
        "public.get_device_source_authority",
    ):
        assert f"function {name}" in sql


def test_c3b_migration_021_hardens_rls_and_security_definer_functions():
    sql = _sql()
    for table in (
        "device_source_authority",
        "device_source_heartbeats",
        "device_source_authority_transitions",
    ):
        assert f"alter table public.{table} enable row level security" in sql
        assert f"revoke all on table public.{table} from anon, authenticated" in sql

    assert "security definer" in sql
    assert "set search_path = pg_catalog, public" in sql
    assert "to service_role" in sql
    assert "from public, anon, authenticated" in sql


def test_c3b_migration_021_has_narrow_administrative_fencing_and_no_session_publisher_trigger():
    sql = _sql()
    for trigger_target in (
        "public.devices",
        "public.cloud_bindings",
        "public.webpilot_auth_realms",
        "public.webpilot_auth_realm_devices",
    ):
        assert trigger_target in sql
    assert "create trigger" in sql
    assert " on public.webpilot_session_publishers" not in sql
    assert " on public.webpilot_session_leases" not in sql


def test_c3b_migration_021_preserves_legacy_snapshot_rpc_with_managed_fail_closed_guard():
    sql = _sql()
    assert "create or replace function public.accept_device_snapshot" in sql
    assert "managed_snapshot_required" in sql
