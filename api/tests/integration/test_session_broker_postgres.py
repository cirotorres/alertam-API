from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import os
from pathlib import Path
from uuid import UUID

import psycopg
import pytest

from app.repositories.devices import DeviceAuthRecord
from app.repositories.postgres import PostgresDeviceRepository
from app.repositories.session_broker import (
    ProviderScopeProfile,
    ScopeStatus,
    SessionLeaseGenerationConflictError,
    SessionLeaseStatus,
    SessionPublisherConflictError,
)


DSN = os.getenv("TEST_POSTGRES_DSN")
MIGRATIONS = Path(__file__).parents[2] / "supabase" / "migrations"
pytestmark = pytest.mark.skipif(not DSN, reason="TEST_POSTGRES_DSN não configurado")

NOW = datetime(2026, 10, 8, 12, 0, tzinfo=timezone.utc)
PUB_A = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
PUB_B = UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
LEASE_A = UUID("11111111-1111-1111-1111-111111111111")
LEASE_B = UUID("22222222-2222-2222-2222-222222222222")


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
        for name in (
            "001_devices.sql",
            "018_device_admin_metadata.sql",
            "019_cloud_binding_realm.sql",
            "020_webpilot_session_broker.sql",
        ):
            conn.execute((MIGRATIONS / name).read_text(encoding="utf-8"))
    yield


def _repo() -> PostgresDeviceRepository:
    assert DSN is not None
    return PostgresDeviceRepository(DSN)


def _seed(repo: PostgresDeviceRepository) -> None:
    for device in ("pecem-a", "pecem-b"):
        repo.create_device(DeviceAuthRecord(device, "device-hash", enabled=True))
    realm = repo.ensure_webpilot_auth_realm("webpilot-pecem")
    assert realm is not None
    for device in ("pecem-a", "pecem-b"):
        assert repo.authorize_realm_device("webpilot-pecem", device) is not None
    required = repo.set_required_provider_scope(
        "webpilot-pecem",
        ProviderScopeProfile(
            scope_id="pecem-standard",
            schema_version=1,
            capabilities=("maneuvers", "weather"),
        ),
    )
    assert required is not None


def _publisher(
    repo: PostgresDeviceRepository,
    publisher_id: UUID,
    device_id: str,
):
    publisher = repo.ensure_session_publisher(
        device_id=device_id,
        realm_id="webpilot-pecem",
        publisher_id=publisher_id,
        provider_scope=ProviderScopeProfile(
            scope_id="pecem-standard",
            schema_version=1,
            capabilities=("maneuvers", "weather"),
        ),
    )
    assert publisher is not None
    verified = repo.verify_session_publisher_scope(publisher_id)
    assert verified is not None
    assert verified.scope_status is ScopeStatus.VERIFIED
    return verified


def _accept(
    repo: PostgresDeviceRepository,
    *,
    device_id: str,
    publisher_id: UUID,
    lease_id: UUID,
    generation: int,
    fingerprint: str,
):
    return repo.accept_session_lease_atomic(
        device_id=device_id,
        realm_id="webpilot-pecem",
        publisher_id=publisher_id,
        lease_id=lease_id,
        local_generation=generation,
        payload_fingerprint=fingerprint,
        ciphertext=f"cipher-{lease_id}",
        nonce=f"nonce-{lease_id}",
        key_version=1,
        payload_schema_version=1,
        expires_at=NOW + timedelta(hours=1),
    )


def test_postgres_session_broker_lifecycle_and_provider_scope_gate():
    repo = _repo()
    _seed(repo)
    _publisher(repo, PUB_A, "pecem-a")

    accepted = _accept(
        repo,
        device_id="pecem-a",
        publisher_id=PUB_A,
        lease_id=LEASE_A,
        generation=1,
        fingerprint="a" * 64,
    )
    assert accepted is not None
    assert accepted.realm_epoch == 1
    assert repo.get_current_session_lease("webpilot-pecem", now=NOW) == accepted

    changed = repo.set_required_provider_scope(
        "webpilot-pecem",
        ProviderScopeProfile(
            scope_id="different",
            schema_version=2,
            capabilities=("maneuvers",),
        ),
    )
    assert changed is not None
    assert repo.get_current_session_lease("webpilot-pecem", now=NOW) is None
    assert _accept(
        repo,
        device_id="pecem-a",
        publisher_id=PUB_A,
        lease_id=LEASE_B,
        generation=2,
        fingerprint="b" * 64,
    ) is None


def test_postgres_same_generation_same_payload_converges_under_concurrency():
    repo = _repo()
    _seed(repo)
    _publisher(repo, PUB_A, "pecem-a")

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [
            executor.submit(
                _accept,
                repo,
                device_id="pecem-a",
                publisher_id=PUB_A,
                lease_id=lease_id,
                generation=1,
                fingerprint="a" * 64,
            )
            for lease_id in (LEASE_A, LEASE_B)
        ]
        results = [future.result(timeout=10) for future in futures]

    assert all(result is not None for result in results)
    assert results[0].lease_id == results[1].lease_id
    assert results[0].realm_epoch == results[1].realm_epoch == 1

    assert DSN is not None
    with psycopg.connect(DSN, autocommit=True) as conn:
        count, epoch = conn.execute(
            """
            select count(*), max(realm_epoch)
            from public.webpilot_session_leases
            where publisher_id = %s
            """,
            (PUB_A,),
        ).fetchone()
    assert count == 1
    assert epoch == 1


def test_postgres_same_generation_different_payload_has_one_winner_and_no_second_epoch():
    repo = _repo()
    _seed(repo)
    _publisher(repo, PUB_A, "pecem-a")

    def attempt(lease_id: UUID, fingerprint: str):
        try:
            return _accept(
                repo,
                device_id="pecem-a",
                publisher_id=PUB_A,
                lease_id=lease_id,
                generation=1,
                fingerprint=fingerprint,
            )
        except SessionLeaseGenerationConflictError as exc:
            return exc

    with ThreadPoolExecutor(max_workers=2) as executor:
        first = executor.submit(attempt, LEASE_A, "a" * 64)
        second = executor.submit(attempt, LEASE_B, "b" * 64)
        outcomes = [first.result(timeout=10), second.result(timeout=10)]

    assert sum(not isinstance(item, Exception) for item in outcomes) == 1
    assert sum(isinstance(item, SessionLeaseGenerationConflictError) for item in outcomes) == 1

    assert DSN is not None
    with psycopg.connect(DSN, autocommit=True) as conn:
        count, last_epoch = conn.execute(
            """
            select
                (select count(*) from public.webpilot_session_leases),
                (select last_epoch from public.webpilot_realm_epoch_counters
                 where realm_id = 'webpilot-pecem')
            """
        ).fetchone()
    assert count == 1
    assert last_epoch == 1


def test_postgres_concurrent_publisher_rotation_leaves_exactly_one_active():
    repo = _repo()
    _seed(repo)
    pub_c = UUID("cccccccc-cccc-cccc-cccc-cccccccccccc")

    def ensure(publisher_id: UUID):
        return repo.ensure_session_publisher(
            device_id="pecem-a",
            realm_id="webpilot-pecem",
            publisher_id=publisher_id,
            provider_scope=ProviderScopeProfile(
                scope_id="pecem-standard",
                schema_version=1,
                capabilities=("maneuvers", "weather"),
            ),
        )

    with ThreadPoolExecutor(max_workers=2) as executor:
        outcomes = [
            executor.submit(ensure, publisher_id)
            for publisher_id in (PUB_A, pub_c)
        ]
        results = [future.result(timeout=10) for future in outcomes]

    assert all(result is not None for result in results)

    assert DSN is not None
    with psycopg.connect(DSN, autocommit=True) as conn:
        active_rows = conn.execute(
            """
            select publisher_id
            from public.webpilot_session_publishers
            where realm_id = 'webpilot-pecem'
              and device_id = 'pecem-a'
              and status = 'active'
            """
        ).fetchall()
    assert len(active_rows) == 1
    assert UUID(str(active_rows[0][0])) in {PUB_A, pub_c}


def test_postgres_revoke_invalidate_expiry_and_privileges():
    repo = _repo()
    _seed(repo)
    _publisher(repo, PUB_A, "pecem-a")
    _publisher(repo, PUB_B, "pecem-b")

    a = _accept(
        repo,
        device_id="pecem-a",
        publisher_id=PUB_A,
        lease_id=LEASE_A,
        generation=1,
        fingerprint="a" * 64,
    )
    b = _accept(
        repo,
        device_id="pecem-b",
        publisher_id=PUB_B,
        lease_id=LEASE_B,
        generation=1,
        fingerprint="b" * 64,
    )
    assert a is not None and b is not None
    assert (a.realm_epoch, b.realm_epoch) == (1, 2)

    invalidated = repo.invalidate_session_lease(
        realm_id="webpilot-pecem",
        lease_id=b.lease_id,
        realm_epoch=b.realm_epoch,
    )
    assert invalidated is not None
    assert invalidated.status is SessionLeaseStatus.INVALIDATED
    assert repo.get_current_session_lease("webpilot-pecem", now=NOW) == a

    revoked = repo.revoke_session_lease(
        device_id="pecem-a",
        realm_id="webpilot-pecem",
        lease_id=a.lease_id,
    )
    assert revoked is not None
    assert revoked.status is SessionLeaseStatus.REVOKED
    assert repo.get_current_session_lease("webpilot-pecem", now=NOW) is None

    assert DSN is not None
    with psycopg.connect(DSN, autocommit=True) as conn:
        signature = (
            "public.accept_session_lease("
            "text,text,uuid,uuid,bigint,text,text,text,integer,integer,"
            "timestamp with time zone)"
        )
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


def test_postgres_reusing_revoked_publisher_id_is_conflict():
    repo = _repo()
    _seed(repo)
    _publisher(repo, PUB_A, "pecem-a")
    revoked = repo.revoke_session_publisher(PUB_A)
    assert revoked is not None

    with pytest.raises(SessionPublisherConflictError):
        repo.ensure_session_publisher(
            device_id="pecem-a",
            realm_id="webpilot-pecem",
            publisher_id=PUB_A,
            provider_scope=ProviderScopeProfile(
                scope_id="pecem-standard",
                schema_version=1,
                capabilities=("maneuvers", "weather"),
            ),
        )


def test_postgres_publisher_id_owner_or_realm_collision_is_conflict():
    repo = _repo()
    _seed(repo)
    _publisher(repo, PUB_A, "pecem-a")
    profile = ProviderScopeProfile(
        scope_id="pecem-standard",
        schema_version=1,
        capabilities=("maneuvers", "weather"),
    )

    with pytest.raises(SessionPublisherConflictError):
        repo.ensure_session_publisher(
            device_id="pecem-b",
            realm_id="webpilot-pecem",
            publisher_id=PUB_A,
            provider_scope=profile,
        )

    realm = repo.ensure_webpilot_auth_realm("webpilot-other")
    assert realm is not None
    auth = repo.authorize_realm_device("webpilot-other", "pecem-a")
    assert auth is not None
    required = repo.set_required_provider_scope("webpilot-other", profile)
    assert required is not None

    with pytest.raises(SessionPublisherConflictError):
        repo.ensure_session_publisher(
            device_id="pecem-a",
            realm_id="webpilot-other",
            publisher_id=PUB_A,
            provider_scope=profile,
        )


def test_c2c_multi_provider_scope_matrix_and_global_epoch_order():
    repo = _repo()
    _seed(repo)

    incompatible = repo.ensure_session_publisher(
        device_id="pecem-b",
        realm_id="webpilot-pecem",
        publisher_id=PUB_B,
        provider_scope=ProviderScopeProfile(
            scope_id="other-profile",
            schema_version=1,
            capabilities=("maneuvers",),
        ),
    )
    assert incompatible is not None
    checked = repo.verify_session_publisher_scope(PUB_B)
    assert checked is not None
    assert checked.scope_status is ScopeStatus.INCOMPATIBLE
    assert _accept(
        repo,
        device_id="pecem-b",
        publisher_id=PUB_B,
        lease_id=LEASE_B,
        generation=1,
        fingerprint="b" * 64,
    ) is None

    assert DSN is not None
    with psycopg.connect(DSN, autocommit=True) as conn:
        assert conn.execute(
            "select count(*) from public.webpilot_session_leases"
        ).fetchone()[0] == 0
        assert conn.execute(
            "select count(*) from public.webpilot_realm_epoch_counters"
        ).fetchone()[0] == 0

    compatible_b = repo.ensure_session_publisher(
        device_id="pecem-b",
        realm_id="webpilot-pecem",
        publisher_id=PUB_B,
        provider_scope=ProviderScopeProfile(
            scope_id="pecem-standard",
            schema_version=1,
            capabilities=("maneuvers", "weather"),
        ),
    )
    assert compatible_b is not None
    assert compatible_b.scope_status is ScopeStatus.UNVERIFIED
    verified_b = repo.verify_session_publisher_scope(PUB_B)
    assert verified_b is not None
    assert verified_b.scope_status is ScopeStatus.VERIFIED
    _publisher(repo, PUB_A, "pecem-a")

    with psycopg.connect(DSN, autocommit=True) as conn:
        conn.execute(
            """
            insert into public.webpilot_realm_epoch_counters(realm_id, last_epoch)
            values ('webpilot-pecem', 100)
            on conflict (realm_id) do update set last_epoch = excluded.last_epoch
            """
        )

    lease_a_37 = _accept(
        repo,
        device_id="pecem-a",
        publisher_id=PUB_A,
        lease_id=LEASE_A,
        generation=37,
        fingerprint="a" * 64,
    )
    lease_b_1 = _accept(
        repo,
        device_id="pecem-b",
        publisher_id=PUB_B,
        lease_id=LEASE_B,
        generation=1,
        fingerprint="b" * 64,
    )
    lease_a_38_id = UUID("33333333-3333-3333-3333-333333333333")
    assert lease_a_37 is not None and lease_b_1 is not None
    assert (lease_a_37.realm_epoch, lease_b_1.realm_epoch) == (101, 102)

    with pytest.raises(SessionLeaseGenerationConflictError):
        _accept(
            repo,
            device_id="pecem-a",
            publisher_id=PUB_A,
            lease_id=UUID("44444444-4444-4444-4444-444444444444"),
            generation=37,
            fingerprint="different".ljust(64, "d"),
        )

    lease_a_38 = _accept(
        repo,
        device_id="pecem-a",
        publisher_id=PUB_A,
        lease_id=lease_a_38_id,
        generation=38,
        fingerprint="c" * 64,
    )
    assert lease_a_38 is not None
    assert lease_a_38.realm_epoch == 103
    assert repo.get_current_session_lease("webpilot-pecem", now=NOW) == lease_a_38

    revoked_b = repo.revoke_session_publisher(PUB_B)
    assert revoked_b is not None
    assert repo.get_current_session_lease("webpilot-pecem", now=NOW) == lease_a_38
    assert _accept(
        repo,
        device_id="pecem-b",
        publisher_id=PUB_B,
        lease_id=UUID("55555555-5555-5555-5555-555555555555"),
        generation=2,
        fingerprint="e" * 64,
    ) is None

    pub_a2 = UUID("cccccccc-cccc-cccc-cccc-cccccccccccc")
    rotated = repo.ensure_session_publisher(
        device_id="pecem-a",
        realm_id="webpilot-pecem",
        publisher_id=pub_a2,
        provider_scope=ProviderScopeProfile(
            scope_id="pecem-standard",
            schema_version=1,
            capabilities=("maneuvers", "weather"),
        ),
    )
    assert rotated is not None
    assert repo.verify_session_publisher_scope(pub_a2).scope_status is ScopeStatus.VERIFIED
    assert repo.get_session_publisher(PUB_A).status.value == "revoked"
    assert _accept(
        repo,
        device_id="pecem-a",
        publisher_id=PUB_A,
        lease_id=UUID("66666666-6666-6666-6666-666666666666"),
        generation=39,
        fingerprint="f" * 64,
    ) is None


def test_c2c_required_scope_change_and_authority_disable_are_immediate_fail_closed():
    repo = _repo()
    _seed(repo)
    _publisher(repo, PUB_A, "pecem-a")
    accepted = _accept(
        repo,
        device_id="pecem-a",
        publisher_id=PUB_A,
        lease_id=LEASE_A,
        generation=1,
        fingerprint="a" * 64,
    )
    assert accepted is not None

    changed = repo.set_required_provider_scope(
        "webpilot-pecem",
        ProviderScopeProfile(
            scope_id="pecem-v2",
            schema_version=2,
            capabilities=("maneuvers", "weather"),
        ),
    )
    assert changed is not None
    assert repo.get_session_publisher(PUB_A).scope_status is ScopeStatus.INCOMPATIBLE
    assert repo.get_current_session_lease("webpilot-pecem", now=NOW) is None
    assert _accept(
        repo,
        device_id="pecem-a",
        publisher_id=PUB_A,
        lease_id=LEASE_B,
        generation=2,
        fingerprint="b" * 64,
    ) is None

    assert DSN is not None
    with psycopg.connect(DSN, autocommit=True) as conn:
        assert conn.execute(
            "select last_epoch from public.webpilot_realm_epoch_counters "
            "where realm_id='webpilot-pecem'"
        ).fetchone()[0] == 1

        conn.execute(
            "update public.webpilot_provider_scope_requirements "
            "set scope_id='pecem-standard', schema_version=1, "
            "capabilities=array['maneuvers','weather'] "
            "where realm_id='webpilot-pecem'"
        )
        conn.execute(
            "update public.webpilot_session_publishers "
            "set scope_status='verified', scope_verified_at=clock_timestamp() "
            "where publisher_id=%s",
            (PUB_A,),
        )
        conn.execute("update public.devices set enabled=false where device_id='pecem-a'")

    assert repo.get_current_session_lease("webpilot-pecem", now=NOW) is None
    assert _accept(
        repo,
        device_id="pecem-a",
        publisher_id=PUB_A,
        lease_id=LEASE_B,
        generation=2,
        fingerprint="b" * 64,
    ) is None

    with psycopg.connect(DSN, autocommit=True) as conn:
        conn.execute("update public.devices set enabled=true where device_id='pecem-a'")
        conn.execute(
            "update public.webpilot_auth_realms set active=false "
            "where realm_id='webpilot-pecem'"
        )
    assert repo.get_current_session_lease("webpilot-pecem", now=NOW) is None

    with psycopg.connect(DSN, autocommit=True) as conn:
        conn.execute(
            "update public.webpilot_auth_realms set active=true "
            "where realm_id='webpilot-pecem'"
        )
        conn.execute(
            "update public.webpilot_auth_realm_devices "
            "set revoked_at=clock_timestamp() "
            "where realm_id='webpilot-pecem' and device_id='pecem-a'"
        )
    assert repo.get_current_session_lease("webpilot-pecem", now=NOW) is None


def test_c2c_expiry_invalidation_fallback_and_repository_restart_preserve_epoch():
    repo = _repo()
    _seed(repo)
    _publisher(repo, PUB_A, "pecem-a")
    _publisher(repo, PUB_B, "pecem-b")

    expired = repo.accept_session_lease_atomic(
        device_id="pecem-a",
        realm_id="webpilot-pecem",
        publisher_id=PUB_A,
        lease_id=LEASE_A,
        local_generation=1,
        payload_fingerprint="a" * 64,
        ciphertext="cipher-a",
        nonce="nonce-a",
        key_version=1,
        payload_schema_version=1,
        expires_at=NOW - timedelta(seconds=1),
    )
    valid_b = _accept(
        repo,
        device_id="pecem-b",
        publisher_id=PUB_B,
        lease_id=LEASE_B,
        generation=1,
        fingerprint="b" * 64,
    )
    assert expired is not None and valid_b is not None
    assert repo.get_current_session_lease("webpilot-pecem", now=NOW) == valid_b

    valid_a2 = _accept(
        repo,
        device_id="pecem-a",
        publisher_id=PUB_A,
        lease_id=UUID("33333333-3333-3333-3333-333333333333"),
        generation=2,
        fingerprint="c" * 64,
    )
    assert valid_a2 is not None
    assert repo.get_current_session_lease("webpilot-pecem", now=NOW) == valid_a2

    invalidated = repo.invalidate_session_lease(
        realm_id="webpilot-pecem",
        lease_id=valid_a2.lease_id,
        realm_epoch=valid_a2.realm_epoch,
    )
    assert invalidated is not None
    assert repo.get_current_session_lease("webpilot-pecem", now=NOW) == valid_b

    restarted = _repo()
    assert restarted.get_current_session_lease("webpilot-pecem", now=NOW) == valid_b
    with pytest.raises(SessionLeaseGenerationConflictError):
        restarted.accept_session_lease_atomic(
            device_id="pecem-b",
            realm_id="webpilot-pecem",
            publisher_id=PUB_B,
            lease_id=UUID("77777777-7777-7777-7777-777777777777"),
            local_generation=1,
            payload_fingerprint="different".ljust(64, "d"),
            ciphertext="cipher-different",
            nonce="nonce-different",
            key_version=1,
            payload_schema_version=1,
            expires_at=NOW + timedelta(hours=1),
        )

    new_b = _accept(
        restarted,
        device_id="pecem-b",
        publisher_id=PUB_B,
        lease_id=UUID("88888888-8888-8888-8888-888888888888"),
        generation=2,
        fingerprint="e" * 64,
    )
    assert new_b is not None
    assert new_b.realm_epoch == valid_a2.realm_epoch + 1
