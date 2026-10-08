from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import time

import psycopg
import pytest

from app.repositories.cloud_bindings import CloudBindingConflictError, CloudBindingStatus
from app.repositories.devices import DeviceAuthRecord
from app.repositories.postgres import PostgresDeviceRepository


DSN = os.getenv("TEST_POSTGRES_DSN")
MIGRATIONS = Path(__file__).parents[2] / "supabase" / "migrations"
pytestmark = pytest.mark.skipif(not DSN, reason="TEST_POSTGRES_DSN não configurado")


def _ensure_roles(conn) -> None:
    conn.execute(
        """
        do $$ begin create role anon noinherit;
        exception when duplicate_object then null; end $$;
        do $$ begin create role authenticated noinherit;
        exception when duplicate_object then null; end $$;
        do $$ begin create role service_role noinherit bypassrls;
        exception when duplicate_object then null; end $$;
        """
    )


@pytest.fixture(autouse=True)
def reset_database():
    assert DSN is not None
    with psycopg.connect(DSN, autocommit=True) as conn:
        _ensure_roles(conn)
        conn.execute("drop schema if exists public cascade")
        conn.execute("create schema public")
        for name in ("001_devices.sql", "018_device_admin_metadata.sql", "019_cloud_binding_realm.sql"):
            conn.execute((MIGRATIONS / name).read_text(encoding="utf-8"))
    yield


def _repo() -> PostgresDeviceRepository:
    assert DSN is not None
    return PostgresDeviceRepository(DSN)


def _seed(repo: PostgresDeviceRepository) -> None:
    repo.create_device(DeviceAuthRecord("pecem-01", "device-hash", enabled=True))
    realm = repo.ensure_webpilot_auth_realm("webpilot-pecem")
    assert realm is not None and realm.active
    auth = repo.authorize_realm_device("webpilot-pecem", "pecem-01")
    assert auth is not None and auth.active


def _install_binding_write_pause(advisory_key: int) -> None:
    assert DSN is not None
    with psycopg.connect(DSN, autocommit=True) as conn:
        conn.execute(
            f"""
            create or replace function public.pause_cloud_binding_write()
            returns trigger
            language plpgsql
            as $$
            begin
                perform pg_advisory_lock({advisory_key});
                perform pg_advisory_unlock({advisory_key});
                return new;
            end;
            $$;

            create trigger pause_cloud_binding_write
            before insert or update on public.cloud_bindings
            for each row execute function public.pause_cloud_binding_write();
            """
        )


def _wait_for_advisory_waiter(timeout: float = 5.0) -> None:
    assert DSN is not None
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        with psycopg.connect(DSN, autocommit=True) as conn:
            waiting = conn.execute(
                """
                select exists (
                    select 1
                    from pg_locks
                    where locktype = 'advisory'
                      and granted = false
                )
                """
            ).fetchone()
        if waiting is not None and bool(waiting[0]):
            return
        time.sleep(0.02)
    raise AssertionError("binding mutation did not pause at advisory trigger")


def _run_paused_binding_race(
    advisory_key: int,
    binding_operation,
    admin_operation,
):
    assert DSN is not None
    _install_binding_write_pause(advisory_key)
    control = psycopg.connect(DSN, autocommit=True)
    control.execute("select pg_advisory_lock(%s)", (advisory_key,))
    try:
        with ThreadPoolExecutor(max_workers=2) as executor:
            binding_future = executor.submit(binding_operation)
            _wait_for_advisory_waiter()
            admin_future = executor.submit(admin_operation)
            time.sleep(0.25)
            admin_completed_while_binding_paused = admin_future.done()
            control.execute("select pg_advisory_unlock(%s)", (advisory_key,))
            binding_result = binding_future.result(timeout=5)
            admin_result = admin_future.result(timeout=5)
    finally:
        try:
            control.execute("select pg_advisory_unlock(%s)", (advisory_key,))
        finally:
            control.close()

    return (
        admin_completed_while_binding_paused,
        binding_result,
        admin_result,
    )


def test_postgres_realm_membership_and_binding_lifecycle_is_idempotent():
    repo = _repo()
    _seed(repo)

    binding = repo.ensure_cloud_binding("pecem-01", "webpilot-pecem", "hash-v1")
    repeated = repo.ensure_cloud_binding("pecem-01", "webpilot-pecem", "hash-v1")
    assert binding is not None
    assert repeated == binding
    assert binding.status is CloudBindingStatus.ACTIVE
    assert binding.credential_version == 1

    same = repo.rotate_cloud_binding("pecem-01", "hash-v1")
    rotated = repo.rotate_cloud_binding("pecem-01", "hash-v2")
    assert same == binding
    assert rotated is not None
    assert rotated.cloud_binding_id == binding.cloud_binding_id
    assert rotated.credential_version == 2

    revoked = repo.revoke_cloud_binding("pecem-01")
    retry = repo.revoke_cloud_binding("pecem-01")
    assert revoked is not None and revoked.status is CloudBindingStatus.REVOKED
    assert retry == revoked
    assert repo.get_active_cloud_binding("pecem-01") is None
    assert repo.list_cloud_bindings("pecem-01") == (revoked,)


def test_postgres_binding_conflict_and_fail_closed_authority():
    repo = _repo()
    _seed(repo)

    first = repo.ensure_cloud_binding("pecem-01", "webpilot-pecem", "hash-v1")
    assert first is not None
    authority = repo.get_cloud_binding_authority(first.cloud_binding_id)
    assert authority is not None
    assert authority.device_id == "pecem-01"
    assert authority.realm_id == "webpilot-pecem"
    assert authority.device_enabled
    assert authority.realm_active
    assert authority.membership_active
    assert authority.status is CloudBindingStatus.ACTIVE
    assert "hash-v1" not in repr(authority)

    with pytest.raises(CloudBindingConflictError):
        repo.ensure_cloud_binding("pecem-01", "webpilot-pecem", "different")

    inactive = repo.set_webpilot_auth_realm_active("webpilot-pecem", False)
    assert inactive is not None and not inactive.active
    assert repo.rotate_cloud_binding("pecem-01", "hash-v2") is None

    active = repo.set_webpilot_auth_realm_active("webpilot-pecem", True)
    assert active is not None and active.active
    revoked_auth = repo.revoke_realm_device("webpilot-pecem", "pecem-01")
    assert revoked_auth is not None and not revoked_auth.active
    assert repo.rotate_cloud_binding("pecem-01", "hash-v2") is None


def test_postgres_admin_lifecycle_is_idempotent_and_reauthorization_reuses_membership():
    repo = _repo()
    repo.create_device(DeviceAuthRecord("pecem-01", "device-hash"))

    realm1 = repo.ensure_webpilot_auth_realm("webpilot-pecem")
    realm2 = repo.ensure_webpilot_auth_realm("webpilot-pecem")
    assert realm1 == realm2

    auth1 = repo.authorize_realm_device("webpilot-pecem", "pecem-01")
    auth2 = repo.authorize_realm_device("webpilot-pecem", "pecem-01")
    assert auth1 == auth2

    revoked1 = repo.revoke_realm_device("webpilot-pecem", "pecem-01")
    revoked2 = repo.revoke_realm_device("webpilot-pecem", "pecem-01")
    assert revoked1 == revoked2
    assert revoked1 is not None and revoked1.revoked_at is not None

    reauthorized = repo.authorize_realm_device("webpilot-pecem", "pecem-01")
    assert reauthorized is not None and reauthorized.active
    assert reauthorized.authorized_at >= revoked1.authorized_at
    assert repo.get_realm_device_authorization("webpilot-pecem", "pecem-01") == reauthorized


def test_postgres_ensure_serializes_membership_revoke_before_insert():
    repo = _repo()
    _seed(repo)

    paused, binding, revoked = _run_paused_binding_race(
        910001,
        lambda: repo.ensure_cloud_binding(
            "pecem-01",
            "webpilot-pecem",
            "hash-v1",
        ),
        lambda: repo.revoke_realm_device(
            "webpilot-pecem",
            "pecem-01",
        ),
    )

    assert paused is False
    assert binding is not None
    assert binding.status is CloudBindingStatus.ACTIVE
    assert revoked is not None and revoked.active is False


def test_postgres_rotate_serializes_realm_deactivation_before_update():
    repo = _repo()
    _seed(repo)
    binding = repo.ensure_cloud_binding(
        "pecem-01",
        "webpilot-pecem",
        "hash-v1",
    )
    assert binding is not None

    paused, rotated, realm = _run_paused_binding_race(
        910002,
        lambda: repo.rotate_cloud_binding("pecem-01", "hash-v2"),
        lambda: repo.set_webpilot_auth_realm_active(
            "webpilot-pecem",
            False,
        ),
    )

    assert paused is False
    assert rotated is not None
    assert rotated.credential_version == 2
    assert realm is not None and realm.active is False


def test_postgres_revoke_serializes_device_disable_before_update():
    assert DSN is not None
    repo = _repo()
    _seed(repo)
    binding = repo.ensure_cloud_binding(
        "pecem-01",
        "webpilot-pecem",
        "hash-v1",
    )
    assert binding is not None

    def disable_device() -> bool:
        assert DSN is not None
        with psycopg.connect(DSN, autocommit=True) as conn:
            conn.execute(
                """
                update public.devices
                set enabled = false
                where device_id = %s
                """,
                ("pecem-01",),
            )
        return True

    paused, revoked, disabled = _run_paused_binding_race(
        910003,
        lambda: repo.revoke_cloud_binding("pecem-01"),
        disable_device,
    )

    assert paused is False
    assert revoked is not None
    assert revoked.status is CloudBindingStatus.REVOKED
    assert disabled is True


def test_postgres_migration_enforces_rls_privileges_and_binding_constraints():
    assert DSN is not None
    repo = _repo()
    _seed(repo)

    with psycopg.connect(DSN, autocommit=True) as conn:
        rls = conn.execute(
            """
            select relname, relrowsecurity
            from pg_class
            where oid in (
                'public.webpilot_auth_realms'::regclass,
                'public.webpilot_auth_realm_devices'::regclass,
                'public.cloud_bindings'::regclass
            )
            order by relname
            """
        ).fetchall()
        assert len(rls) == 3
        assert all(bool(row[1]) for row in rls)

        policies = conn.execute(
            """
            select count(*)
            from pg_policies
            where schemaname = 'public'
              and tablename in (
                  'webpilot_auth_realms',
                  'webpilot_auth_realm_devices',
                  'cloud_bindings'
              )
            """
        ).fetchone()
        assert policies is not None and policies[0] == 0

        for signature in (
            "public.ensure_cloud_binding(text,text,text)",
            "public.get_cloud_binding_authority(uuid)",
        ):
            assert conn.execute(
                "select has_function_privilege('anon', %s, 'EXECUTE')",
                (signature,),
            ).fetchone()[0] is False
            assert conn.execute(
                "select has_function_privilege('authenticated', %s, 'EXECUTE')",
                (signature,),
            ).fetchone()[0] is False
            assert conn.execute(
                "select has_function_privilege('service_role', %s, 'EXECUTE')",
                (signature,),
            ).fetchone()[0] is True

        with pytest.raises(psycopg.errors.CheckViolation):
            conn.execute(
                """
                insert into public.cloud_bindings (
                    device_id, realm_id, credential_hash,
                    credential_version, status, revoked_at
                )
                values (%s, %s, %s, 1, 'active', clock_timestamp())
                """,
                ("pecem-01", "webpilot-pecem", "invalid"),
            )

        with pytest.raises(psycopg.errors.CheckViolation):
            conn.execute(
                """
                insert into public.cloud_bindings (
                    device_id, realm_id, credential_hash,
                    credential_version, status, revoked_at
                )
                values (%s, %s, %s, 0, 'active', null)
                """,
                ("pecem-01", "webpilot-pecem", "invalid"),
            )
