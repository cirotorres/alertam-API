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
