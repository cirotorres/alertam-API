from __future__ import annotations

from pathlib import Path


MIGRATION = (
    Path(__file__).parents[2]
    / "supabase"
    / "migrations"
    / "020_webpilot_session_broker.sql"
)


def test_session_broker_migration_is_hardened_and_atomic():
    sql = MIGRATION.read_text(encoding="utf-8").lower()

    for table in (
        "webpilot_provider_scope_requirements",
        "webpilot_session_publishers",
        "webpilot_session_leases",
        "webpilot_realm_epoch_counters",
    ):
        assert f"create table if not exists public.{table}" in sql
        assert f"alter table public.{table} enable row level security" in sql
        assert f"revoke all on table public.{table} from anon, authenticated" in sql

    assert "unique (publisher_id, local_generation)" in sql
    assert "unique (realm_id, realm_epoch)" in sql
    assert "scope_status in ('unverified', 'verified', 'incompatible')" in sql
    assert "status in ('accepted', 'revoked', 'invalidated')" in sql
    assert "payload_fingerprint" in sql
    assert "key_version" in sql
    assert "payload_schema_version" in sql

    for fn in (
        "set_required_provider_scope",
        "ensure_session_publisher",
        "verify_session_publisher_scope",
        "revoke_session_publisher",
        "accept_session_lease",
        "revoke_session_lease",
        "invalidate_session_lease",
        "get_current_session_lease",
    ):
        assert f"create or replace function public.{fn}" in sql
        assert "security definer" in sql
        assert f"revoke all on function public.{fn}" in sql
        assert f"grant execute on function public.{fn}" in sql

    assert "for update" in sql
    assert "session_lease_generation_conflict" in sql
    assert "session_lease_replay" in sql
    assert "last_epoch = c.last_epoch + 1" in sql
    assert sql.count("to service_role") >= 8
    assert "create policy" not in sql
