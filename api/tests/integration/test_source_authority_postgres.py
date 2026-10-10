from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import os
from pathlib import Path
import time
from uuid import UUID

import psycopg
import pytest

from app.models.source_authority import (
    AuthorityMode,
    AuthorityReasonCode,
    AuthorityStatus,
    ManagedSnapshotCandidate,
    PublishUnderCurrentGrant,
    SideEffectPolicy,
    Source,
    TransitionCandidate,
)
from app.repositories.devices import (
    AcceptSnapshotStatus,
    DeviceAuthRecord,
    PersistenceUnavailableError,
    SnapshotCandidate,
)
from app.repositories.postgres import PostgresDeviceRepository
from app.repositories.session_broker import ProviderScopeProfile, ScopeStatus


DSN = os.getenv("TEST_POSTGRES_DSN")
MIGRATIONS = Path(__file__).parents[2] / "supabase" / "migrations"
pytestmark = pytest.mark.skipif(not DSN, reason="TEST_POSTGRES_DSN não configurado")

BOOT_A = UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
BOOT_B = UUID("bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb")
CLOUD_A = UUID("cccccccc-cccc-4ccc-8ccc-cccccccccccc")
PUB_A = UUID("11111111-1111-4111-8111-111111111111")
PUB_B = UUID("22222222-2222-4222-8222-222222222222")
SESSION_A = UUID("33333333-3333-4333-8333-333333333333")
SESSION_B = UUID("44444444-4444-4444-8444-444444444444")


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
            "002_accept_snapshot_rpc.sql",
            "018_device_admin_metadata.sql",
            "019_cloud_binding_realm.sql",
            "020_webpilot_session_broker.sql",
            "021_source_authority_snapshots.sql",
        ):
            conn.execute((MIGRATIONS / name).read_text(encoding="utf-8"))
    yield


def _repo() -> PostgresDeviceRepository:
    assert DSN is not None
    return PostgresDeviceRepository(DSN)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _body(
    *,
    boot_id: UUID,
    sequence: int,
    generated_at: datetime,
    marker: str,
    schema_version: int = 2,
) -> dict:
    return {
        "schema_version": schema_version,
        "boot_id": str(boot_id),
        "sequence": sequence,
        "generated_at": generated_at.isoformat(),
        "marker": marker,
    }


def _legacy_snapshot(
    repo: PostgresDeviceRepository,
    device_id: str,
    *,
    boot_id: UUID = BOOT_A,
    sequence: int = 1,
    marker: str = "legacy",
):
    generated_at = _now()
    result = repo.accept_snapshot_atomic(
        SnapshotCandidate(
            device_id=device_id,
            snapshot=_body(
                boot_id=boot_id,
                sequence=sequence,
                generated_at=generated_at,
                marker=marker,
            ),
            snapshot_schema_version=2,
            boot_id=boot_id,
            sequence=sequence,
            generated_at=generated_at,
        )
    )
    assert result.status is AcceptSnapshotStatus.ACCEPTED
    return result


def _heartbeat(
    device_id: str,
    source: Source,
    instance_id: UUID,
    *,
    reason: AuthorityReasonCode,
    persistent_state_ready: bool | None = None,
) -> None:
    assert DSN is not None
    with psycopg.connect(DSN, autocommit=True) as conn:
        conn.execute(
            """
            insert into public.device_source_heartbeats(
                device_id, source, instance_id, last_heartbeat_at,
                process_healthy, collection_healthy, healthy_since,
                consecutive_healthy, last_collection_ok_at,
                last_reason_code, persistent_state_ready, updated_at
            )
            values (
                %s, %s, %s, clock_timestamp(), true, true,
                clock_timestamp(), 3, clock_timestamp(), %s, %s,
                clock_timestamp()
            )
            on conflict (device_id, source, instance_id) do update
            set last_heartbeat_at = clock_timestamp(),
                process_healthy = true,
                collection_healthy = true,
                healthy_since = clock_timestamp(),
                consecutive_healthy = 3,
                last_collection_ok_at = clock_timestamp(),
                last_reason_code = excluded.last_reason_code,
                persistent_state_ready = excluded.persistent_state_ready,
                updated_at = clock_timestamp()
            """,
            (
                device_id,
                source.value,
                instance_id,
                reason.value,
                persistent_state_ready,
            ),
        )


def _candidate(
    device_id: str,
    source: Source,
    instance_id: UUID,
    *,
    sequence: int,
    marker: str,
) -> ManagedSnapshotCandidate:
    generated_at = _now()
    return ManagedSnapshotCandidate(
        device_id=device_id,
        source=source,
        holder_instance_id=instance_id,
        boot_id=instance_id,
        sequence=sequence,
        generated_at=generated_at,
        snapshot_schema_version=2,
        snapshot=_body(
            boot_id=instance_id,
            sequence=sequence,
            generated_at=generated_at,
            marker=marker,
        ),
    )


def _create_device(repo: PostgresDeviceRepository, device_id: str) -> None:
    repo.create_device(DeviceAuthRecord(device_id, "device-hash", enabled=True))


def _bootstrap(
    repo: PostgresDeviceRepository,
    device_id: str = "pecem-a",
    *,
    boot_id: UUID = BOOT_A,
):
    _heartbeat(
        device_id,
        Source.DESKTOP,
        boot_id,
        reason=AuthorityReasonCode.DESKTOP_HEALTHY,
    )
    result = repo.bootstrap_managed_source_authority(device_id)
    assert result.status is AuthorityStatus.ACCEPTED
    assert result.grant is not None
    return result


def _seed_cloud_auth(
    repo: PostgresDeviceRepository,
    *,
    owner_device: str = "pecem-a",
    provider_device: str | None = None,
    publisher_id: UUID = PUB_A,
    session_id: UUID = SESSION_A,
    generation: int = 1,
):
    provider_device = provider_device or owner_device
    realm = repo.ensure_webpilot_auth_realm("webpilot-pecem")
    assert realm is not None
    for device_id in {owner_device, provider_device}:
        assert repo.authorize_realm_device("webpilot-pecem", device_id) is not None

    binding = repo.get_active_cloud_binding(owner_device)
    if binding is None:
        binding = repo.ensure_cloud_binding(owner_device, "webpilot-pecem", "hash-v1")
    assert binding is not None

    profile = ProviderScopeProfile(
        scope_id="pecem-standard",
        schema_version=1,
        capabilities=("maneuvers", "weather"),
    )
    assert repo.set_required_provider_scope("webpilot-pecem", profile) is not None
    publisher = repo.ensure_session_publisher(
        device_id=provider_device,
        realm_id="webpilot-pecem",
        publisher_id=publisher_id,
        provider_scope=profile,
    )
    assert publisher is not None
    verified = repo.verify_session_publisher_scope(publisher_id)
    assert verified is not None and verified.scope_status is ScopeStatus.VERIFIED
    accepted = repo.accept_session_lease_atomic(
        device_id=provider_device,
        realm_id="webpilot-pecem",
        publisher_id=publisher_id,
        lease_id=session_id,
        local_generation=generation,
        payload_fingerprint=(str(generation) * 64)[:64],
        ciphertext=f"cipher-{session_id}",
        nonce=f"nonce-{session_id}",
        key_version=1,
        payload_schema_version=1,
        expires_at=_now() + timedelta(hours=1),
    )
    assert accepted is not None
    return binding, accepted




def _prepare_server_failover_gate() -> None:
    """Only test state setup is synthetic; the gate itself is DB-computed."""
    _age_authoritative_snapshot("pecem-a", 181)
    result = _source_heartbeat_rpc(
        "pecem-a", Source.CLOUD, CLOUD_A,
        candidate_at=_now(), ready=True,
    )
    assert result[0] == "accepted"
    assert _source_decision_rpc("pecem-a", Source.CLOUD, CLOUD_A) == "failover_granted"


def _prepare_server_failback_gate() -> None:
    assert DSN is not None
    with psycopg.connect(DSN, autocommit=True) as conn:
        conn.execute("""
            update public.device_source_authority
            set granted_at=clock_timestamp()-interval '121 seconds'
            where device_id='pecem-a'
        """)
    for _ in range(3):
        _source_heartbeat_rpc("pecem-a", Source.DESKTOP, BOOT_A)
    with psycopg.connect(DSN, autocommit=True) as conn:
        conn.execute("""
            update public.device_source_heartbeats
            set healthy_since=clock_timestamp()-interval '121 seconds'
            where device_id='pecem-a' and source='desktop'
        """)
    assert _source_decision_rpc("pecem-a", Source.DESKTOP, BOOT_A) == "failback_granted"

def _transition_cloud(
    repo: PostgresDeviceRepository,
    *,
    sequence: int = 1,
    marker: str = "cloud",
):
    _prepare_server_failover_gate()
    return repo.accept_transition_candidate(
        TransitionCandidate(
            candidate=_candidate(
                "pecem-a",
                Source.CLOUD,
                CLOUD_A,
                sequence=sequence,
                marker=marker,
            )
        )
    )


def test_c3b_migration_defaults_legacy_and_preserves_legacy_snapshot_path():
    repo = _repo()
    _create_device(repo, "pecem-a")

    authority = repo.get_source_authority("pecem-a")
    assert authority is not None
    assert authority.mode is AuthorityMode.LEGACY
    assert authority.active_source is None
    assert authority.authority_epoch == 0
    assert repo.get_current_grant("pecem-a") is None

    first = _legacy_snapshot(repo, "pecem-a")
    assert first.received_at is not None
    authority_after = repo.get_source_authority("pecem-a")
    assert authority_after == authority

    assert DSN is not None
    with psycopg.connect(DSN, autocommit=True) as conn:
        row = conn.execute(
            """
            select snapshot_source, snapshot_authority_epoch,
                   snapshot_authority_lease_id, snapshot_writer_instance_id
            from public.devices where device_id='pecem-a'
            """
        ).fetchone()
    assert row == (None, None, None, None)


def test_c3b_bootstrap_requires_explicit_desktop_health_and_creates_epoch_one_atomically():
    repo = _repo()
    _create_device(repo, "pecem-a")
    _legacy_snapshot(repo, "pecem-a")

    blocked = repo.bootstrap_managed_source_authority("pecem-a")
    assert blocked.status is AuthorityStatus.INELIGIBLE
    assert blocked.reason_code is AuthorityReasonCode.BOOTSTRAP_NOT_ELIGIBLE
    assert repo.get_source_authority("pecem-a").mode is AuthorityMode.LEGACY

    bootstrapped = _bootstrap(repo)
    grant = bootstrapped.grant
    assert grant is not None
    assert grant.source is Source.DESKTOP
    assert grant.authority_epoch == 1
    assert grant.holder_instance_id == BOOT_A

    authority = repo.get_source_authority("pecem-a")
    assert authority is not None
    assert authority.mode is AuthorityMode.MANAGED
    assert authority.active_source is Source.DESKTOP
    assert authority.authority_epoch == 1

    with pytest.raises(PersistenceUnavailableError):
        _legacy_snapshot(repo, "pecem-a", sequence=2, marker="legacy-bypass")

    stored = repo.get_snapshot("pecem-a")
    assert stored is not None
    assert stored.sequence == 1


def test_c3b_current_grant_write_fences_wrong_tokens_and_allows_recovery_write():
    repo = _repo()
    _create_device(repo, "pecem-a")
    _legacy_snapshot(repo, "pecem-a")
    bootstrapped = _bootstrap(repo)
    grant = bootstrapped.grant
    assert grant is not None

    assert DSN is not None
    with psycopg.connect(DSN, autocommit=True) as conn:
        conn.execute(
            """
            update public.device_source_authority
            set authoritative_snapshot_stale_since=clock_timestamp()-interval '30 seconds',
                last_authoritative_snapshot_at=clock_timestamp()-interval '150 seconds'
            where device_id='pecem-a'
            """
        )

    candidate = _candidate(
        "pecem-a", Source.DESKTOP, BOOT_A, sequence=2, marker="recovery"
    )
    command = PublishUnderCurrentGrant(
        candidate=candidate,
        authority_epoch=grant.authority_epoch,
        authority_lease_id=grant.authority_lease_id,
        holder_instance_id=BOOT_A,
    )
    accepted = repo.accept_current_grant_snapshot(command)
    assert accepted.status is AuthorityStatus.ACCEPTED
    assert accepted.grant == grant
    assert accepted.side_effect_policy is SideEffectPolicy.DESKTOP_CONTINUITY
    assert accepted.previous_snapshot_for_side_effects is not None

    authority = repo.get_source_authority("pecem-a")
    assert authority is not None
    assert authority.authority_epoch == 1
    assert authority.authority_lease_id == grant.authority_lease_id
    assert authority.authoritative_snapshot_stale_since is None

    retry = repo.accept_current_grant_snapshot(command)
    assert retry.status is AuthorityStatus.IDEMPOTENT
    assert retry.side_effect_policy is SideEffectPolicy.NONE

    mismatch = repo.accept_current_grant_snapshot(
        command.model_copy(
            update={
                "candidate": _candidate(
                    "pecem-a", Source.DESKTOP, BOOT_A,
                    sequence=2, marker="different",
                )
            }
        )
    )
    assert mismatch.status is AuthorityStatus.REJECTED
    assert mismatch.reason_code is AuthorityReasonCode.SNAPSHOT_SEQUENCE_MISMATCH

    wrong_epoch = repo.accept_current_grant_snapshot(
        command.model_copy(update={"authority_epoch": grant.authority_epoch + 1})
    )
    assert wrong_epoch.status is AuthorityStatus.FENCED

    wrong_lease = repo.accept_current_grant_snapshot(
        command.model_copy(
            update={
                "authority_lease_id": UUID(
                    "99999999-9999-4999-8999-999999999999"
                )
            }
        )
    )
    assert wrong_lease.status is AuthorityStatus.FENCED

    restarted_writer = PublishUnderCurrentGrant(
        candidate=_candidate(
            "pecem-a",
            Source.DESKTOP,
            BOOT_B,
            sequence=3,
            marker="restarted-with-old-grant",
        ),
        authority_epoch=grant.authority_epoch,
        authority_lease_id=grant.authority_lease_id,
        holder_instance_id=BOOT_B,
    )
    wrong_instance = repo.accept_current_grant_snapshot(restarted_writer)
    assert wrong_instance.status is AuthorityStatus.FENCED

    stored = repo.get_snapshot("pecem-a")
    assert stored is not None
    assert stored.snapshot == candidate.snapshot


def test_c3b_transition_candidate_gets_server_side_epoch_and_old_writer_is_fenced():
    repo = _repo()
    _create_device(repo, "pecem-a")
    _legacy_snapshot(repo, "pecem-a")
    desktop = _bootstrap(repo)
    assert desktop.grant is not None
    _seed_cloud_auth(repo)

    cloud = _transition_cloud(repo)
    assert cloud.status is AuthorityStatus.ACCEPTED
    assert cloud.grant is not None
    assert cloud.grant.source is Source.CLOUD
    assert cloud.grant.authority_epoch == 2
    assert cloud.source_transition
    assert cloud.previous_source is Source.DESKTOP
    assert cloud.side_effect_policy is SideEffectPolicy.NONE

    old_desktop = repo.accept_current_grant_snapshot(
        PublishUnderCurrentGrant(
            candidate=_candidate(
                "pecem-a", Source.DESKTOP, BOOT_A,
                sequence=2, marker="old-desktop",
            ),
            authority_epoch=desktop.grant.authority_epoch,
            authority_lease_id=desktop.grant.authority_lease_id,
            holder_instance_id=BOOT_A,
        )
    )
    assert old_desktop.status is AuthorityStatus.FENCED

    authority = repo.get_source_authority("pecem-a")
    assert authority is not None
    assert authority.active_source is Source.CLOUD
    assert authority.authority_epoch == 2
    assert authority.cloud_binding_id is not None
    assert authority.realm_id == "webpilot-pecem"
    assert authority.observed_realm_epoch is not None


def test_c3b_cloud_to_desktop_transition_is_baseline_then_continuity_uses_transactional_previous():
    repo = _repo()
    _create_device(repo, "pecem-a")
    _legacy_snapshot(repo, "pecem-a")
    _bootstrap(repo)
    _seed_cloud_auth(repo)
    cloud = _transition_cloud(repo)
    assert cloud.status is AuthorityStatus.ACCEPTED

    _prepare_server_failback_gate()
    desktop_candidate = _candidate(
        "pecem-a", Source.DESKTOP, BOOT_A, sequence=3, marker="desktop-back"
    )
    back = repo.accept_transition_candidate(
        TransitionCandidate(candidate=desktop_candidate)
    )
    assert back.status is AuthorityStatus.ACCEPTED
    assert back.grant is not None
    assert back.grant.authority_epoch == 3
    assert back.previous_source is Source.CLOUD
    assert back.source_transition
    assert back.side_effect_policy is SideEffectPolicy.BASELINE
    assert back.previous_snapshot_for_side_effects is None

    next_candidate = _candidate(
        "pecem-a", Source.DESKTOP, BOOT_A, sequence=4, marker="desktop-next"
    )
    continuity = repo.accept_current_grant_snapshot(
        PublishUnderCurrentGrant(
            candidate=next_candidate,
            authority_epoch=back.grant.authority_epoch,
            authority_lease_id=back.grant.authority_lease_id,
            holder_instance_id=BOOT_A,
        )
    )
    assert continuity.status is AuthorityStatus.ACCEPTED
    assert continuity.previous_source is Source.DESKTOP
    assert not continuity.source_transition
    assert continuity.side_effect_policy is SideEffectPolicy.DESKTOP_CONTINUITY
    assert continuity.previous_snapshot_for_side_effects == desktop_candidate.snapshot


def test_c3b_recovery_current_grant_racing_transition_has_exactly_one_winner_without_deadlock():
    repo = _repo()
    _create_device(repo, "pecem-a")
    _legacy_snapshot(repo, "pecem-a")
    desktop = _bootstrap(repo)
    assert desktop.grant is not None
    _seed_cloud_auth(repo)
    _prepare_server_failover_gate()

    current = PublishUnderCurrentGrant(
        candidate=_candidate(
            "pecem-a", Source.DESKTOP, BOOT_A,
            sequence=2, marker="desktop-race",
        ),
        authority_epoch=desktop.grant.authority_epoch,
        authority_lease_id=desktop.grant.authority_lease_id,
        holder_instance_id=BOOT_A,
    )
    transition = TransitionCandidate(
        candidate=_candidate(
            "pecem-a", Source.CLOUD, CLOUD_A,
            sequence=1, marker="cloud-race",
        )
    )

    with ThreadPoolExecutor(max_workers=2) as pool:
        a = pool.submit(repo.accept_current_grant_snapshot, current)
        b = pool.submit(repo.accept_transition_candidate, transition)
        results = [a.result(timeout=10), b.result(timeout=10)]

    accepted = [r for r in results if r.status is AuthorityStatus.ACCEPTED]
    assert len(accepted) == 1
    loser = [r for r in results if r.status is not AuthorityStatus.ACCEPTED][0]
    assert loser.status in {AuthorityStatus.FENCED, AuthorityStatus.INELIGIBLE}

    authority = repo.get_source_authority("pecem-a")
    stored = repo.get_snapshot("pecem-a")
    assert authority is not None and stored is not None
    winner = accepted[0]
    assert authority.active_source is winner.source
    assert stored.snapshot == (
        current.candidate.snapshot
        if winner.source is Source.DESKTOP
        else transition.candidate.snapshot
    )


def test_c3b_two_current_writers_same_sequence_have_one_commit_and_typed_loser():
    repo = _repo()
    _create_device(repo, "pecem-a")
    _legacy_snapshot(repo, "pecem-a")
    boot = _bootstrap(repo)
    assert boot.grant is not None

    def attempt(marker: str):
        return repo.accept_current_grant_snapshot(
            PublishUnderCurrentGrant(
                candidate=_candidate(
                    "pecem-a", Source.DESKTOP, BOOT_A,
                    sequence=2, marker=marker,
                ),
                authority_epoch=boot.grant.authority_epoch,
                authority_lease_id=boot.grant.authority_lease_id,
                holder_instance_id=BOOT_A,
            )
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = [
            pool.submit(attempt, marker).result(timeout=10)
            for marker in ("one", "two")
        ]

    assert sum(r.status is AuthorityStatus.ACCEPTED for r in results) == 1
    assert sum(
        r.reason_code is AuthorityReasonCode.SNAPSHOT_SEQUENCE_MISMATCH
        for r in results
    ) == 1


def test_c3b_administrative_fencing_is_narrow_and_reactivation_does_not_resurrect_token():
    repo = _repo()
    _create_device(repo, "pecem-a")
    _legacy_snapshot(repo, "pecem-a")
    desktop = _bootstrap(repo)
    assert desktop.grant is not None
    _seed_cloud_auth(repo)

    before = repo.get_source_authority("pecem-a")
    assert before is not None
    repo.set_webpilot_auth_realm_active("webpilot-pecem", False)
    desktop_after_realm = repo.get_source_authority("pecem-a")
    assert desktop_after_realm is not None
    assert desktop_after_realm.active_source is Source.DESKTOP
    assert desktop_after_realm.lease_expires_at == before.lease_expires_at

    repo.set_webpilot_auth_realm_active("webpilot-pecem", True)
    _prepare_server_failover_gate()
    cloud = repo.accept_transition_candidate(
        TransitionCandidate(
            candidate=_candidate(
                "pecem-a", Source.CLOUD, CLOUD_A,
                sequence=1, marker="cloud",
            )
        )
    )
    assert cloud.status is AuthorityStatus.ACCEPTED
    assert cloud.grant is not None

    repo.set_webpilot_auth_realm_active("webpilot-pecem", False)
    fenced = repo.get_source_authority("pecem-a")
    assert fenced is not None
    assert fenced.transition_reason is AuthorityReasonCode.REALM_INACTIVE
    expired_at = fenced.lease_expires_at
    assert expired_at is not None and expired_at <= _now()

    repo.set_webpilot_auth_realm_active("webpilot-pecem", True)
    revived = repo.get_source_authority("pecem-a")
    assert revived is not None
    assert revived.lease_expires_at == expired_at
    old_cloud = repo.accept_current_grant_snapshot(
        PublishUnderCurrentGrant(
            candidate=_candidate(
                "pecem-a", Source.CLOUD, CLOUD_A,
                sequence=2, marker="must-stay-fenced",
            ),
            authority_epoch=cloud.grant.authority_epoch,
            authority_lease_id=cloud.grant.authority_lease_id,
            holder_instance_id=CLOUD_A,
        )
    )
    assert old_cloud.status is AuthorityStatus.FENCED


def test_c3b_device_disable_fences_desktop_and_cross_device_authority_is_isolated():
    repo = _repo()
    for device, boot in (("pecem-a", BOOT_A), ("pecem-b", BOOT_B)):
        _create_device(repo, device)
        _legacy_snapshot(repo, device, boot_id=boot)
        _bootstrap(repo, device, boot_id=boot)

    assert DSN is not None
    with psycopg.connect(DSN, autocommit=True) as conn:
        conn.execute("update public.devices set enabled=false where device_id='pecem-a'")

    a = repo.get_source_authority("pecem-a")
    b = repo.get_source_authority("pecem-b")
    assert a is not None and b is not None
    assert a.transition_reason is AuthorityReasonCode.DEVICE_DISABLED
    assert a.lease_expires_at is not None and a.lease_expires_at <= _now()
    assert b.active_source is Source.DESKTOP
    assert b.authority_epoch == 1
    assert b.lease_expires_at is not None and b.lease_expires_at > _now()


def test_c3b_rls_privileges_and_constraints_are_backend_only():
    repo = _repo()
    _create_device(repo, "pecem-a")
    assert DSN is not None

    with psycopg.connect(DSN, autocommit=True) as conn:
        rls = conn.execute(
            """
            select relname, relrowsecurity
            from pg_class
            where oid in (
                'public.device_source_authority'::regclass,
                'public.device_source_heartbeats'::regclass,
                'public.device_source_authority_transitions'::regclass
            )
            order by relname
            """
        ).fetchall()
        assert len(rls) == 3 and all(bool(row[1]) for row in rls)

        assert conn.execute(
            """
            select count(*) from pg_policies
            where schemaname='public'
              and tablename in (
                'device_source_authority',
                'device_source_heartbeats',
                'device_source_authority_transitions'
              )
            """
        ).fetchone()[0] == 0

        signatures = (
            "public.get_device_source_authority(text)",
            "public.bootstrap_managed_source_authority(text)",
            "public.accept_managed_snapshot_current_grant(text,text,bigint,uuid,uuid,jsonb,integer,uuid,bigint,timestamp with time zone)",
            "public.accept_managed_snapshot_transition_candidate(text,text,uuid,jsonb,integer,uuid,bigint,timestamp with time zone)",
        )
        for signature in signatures:
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
                update public.device_source_authority
                set mode='managed', active_source='cloud',
                    authority_epoch=1, authority_lease_id=gen_random_uuid(),
                    holder_instance_id=gen_random_uuid(),
                    lease_expires_at=clock_timestamp()+interval '1 minute',
                    granted_at=clock_timestamp()
                where device_id='pecem-a'
                """
            )


def _install_snapshot_pause(advisory_key: int) -> None:
    assert DSN is not None
    with psycopg.connect(DSN, autocommit=True) as conn:
        conn.execute(
            f"""
            create or replace function public.pause_managed_snapshot_write()
            returns trigger
            language plpgsql
            as $$
            begin
                if new.snapshot is distinct from old.snapshot then
                    perform pg_advisory_lock({advisory_key});
                    perform pg_advisory_unlock({advisory_key});
                end if;
                return new;
            end;
            $$;
            drop trigger if exists pause_managed_snapshot_write on public.devices;
            create trigger pause_managed_snapshot_write
            before update of snapshot on public.devices
            for each row execute function public.pause_managed_snapshot_write();
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
                    where locktype='advisory' and granted=false
                )
                """
            ).fetchone()
        if waiting is not None and bool(waiting[0]):
            return
        time.sleep(0.02)
    raise AssertionError("managed snapshot did not reach pause trigger")


def _run_snapshot_admin_race(
    advisory_key: int,
    snapshot_operation,
    admin_operation,
):
    assert DSN is not None
    _install_snapshot_pause(advisory_key)
    control = psycopg.connect(DSN, autocommit=True)
    control.execute("select pg_advisory_lock(%s)", (advisory_key,))
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            snapshot_future = pool.submit(snapshot_operation)
            _wait_for_advisory_waiter()
            admin_future = pool.submit(admin_operation)
            time.sleep(0.20)
            admin_completed_while_snapshot_paused = admin_future.done()
            control.execute("select pg_advisory_unlock(%s)", (advisory_key,))
            snapshot_result = snapshot_future.result(timeout=10)
            admin_result = admin_future.result(timeout=10)
    finally:
        try:
            control.execute("select pg_advisory_unlock(%s)", (advisory_key,))
        finally:
            control.close()
    return admin_completed_while_snapshot_paused, snapshot_result, admin_result


def test_c3b_two_transition_candidates_have_single_epoch_winner():
    repo = _repo()
    _create_device(repo, "pecem-a")
    _legacy_snapshot(repo, "pecem-a")
    _bootstrap(repo)
    _seed_cloud_auth(repo)
    _prepare_server_failover_gate()

    def attempt(marker: str):
        return repo.accept_transition_candidate(
            TransitionCandidate(
                candidate=_candidate(
                    "pecem-a",
                    Source.CLOUD,
                    CLOUD_A,
                    sequence=1,
                    marker=marker,
                )
            )
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(attempt, marker) for marker in ("cloud-one", "cloud-two")]
        results = [future.result(timeout=10) for future in futures]

    assert sum(r.status is AuthorityStatus.ACCEPTED for r in results) == 1
    assert sum(r.status is AuthorityStatus.INELIGIBLE for r in results) == 1
    authority = repo.get_source_authority("pecem-a")
    assert authority is not None
    assert authority.active_source is Source.CLOUD
    assert authority.authority_epoch == 2
    stored = repo.get_snapshot("pecem-a")
    assert stored is not None
    assert stored.snapshot["marker"] in {"cloud-one", "cloud-two"}


@pytest.mark.parametrize(
    ("kind", "expected_reason", "key"),
    [
        ("binding", AuthorityReasonCode.BINDING_REVOKED, 930101),
        ("realm", AuthorityReasonCode.REALM_INACTIVE, 930102),
        ("membership", AuthorityReasonCode.MEMBERSHIP_REVOKED, 930103),
    ],
)
def test_c3b_cloud_admin_races_serialize_after_inflight_snapshot(
    kind: str,
    expected_reason: AuthorityReasonCode,
    key: int,
):
    repo = _repo()
    _create_device(repo, "pecem-a")
    _legacy_snapshot(repo, "pecem-a")
    _bootstrap(repo)
    _seed_cloud_auth(repo)
    cloud = _transition_cloud(repo)
    assert cloud.status is AuthorityStatus.ACCEPTED
    assert cloud.grant is not None

    command = PublishUnderCurrentGrant(
        candidate=_candidate(
            "pecem-a",
            Source.CLOUD,
            CLOUD_A,
            sequence=2,
            marker=f"cloud-before-{kind}",
        ),
        authority_epoch=cloud.grant.authority_epoch,
        authority_lease_id=cloud.grant.authority_lease_id,
        holder_instance_id=CLOUD_A,
    )

    if kind == "binding":
        admin = lambda: repo.revoke_cloud_binding("pecem-a")
    elif kind == "realm":
        admin = lambda: repo.set_webpilot_auth_realm_active("webpilot-pecem", False)
    else:
        admin = lambda: repo.revoke_realm_device("webpilot-pecem", "pecem-a")

    paused, snapshot_result, admin_result = _run_snapshot_admin_race(
        key,
        lambda: repo.accept_current_grant_snapshot(command),
        admin,
    )
    assert paused is False
    assert snapshot_result.status is AuthorityStatus.ACCEPTED
    assert admin_result is not None

    authority = repo.get_source_authority("pecem-a")
    assert authority is not None
    assert authority.active_source is Source.CLOUD
    assert authority.transition_reason is expected_reason
    assert authority.lease_expires_at is not None
    assert authority.lease_expires_at <= _now()


def test_c3b_device_disable_race_serializes_and_fences_any_source():
    repo = _repo()
    _create_device(repo, "pecem-a")
    _legacy_snapshot(repo, "pecem-a")
    boot = _bootstrap(repo)
    assert boot.grant is not None

    command = PublishUnderCurrentGrant(
        candidate=_candidate(
            "pecem-a",
            Source.DESKTOP,
            BOOT_A,
            sequence=2,
            marker="desktop-before-disable",
        ),
        authority_epoch=boot.grant.authority_epoch,
        authority_lease_id=boot.grant.authority_lease_id,
        holder_instance_id=BOOT_A,
    )

    def disable() -> bool:
        assert DSN is not None
        with psycopg.connect(DSN, autocommit=True) as conn:
            conn.execute(
                "update public.devices set enabled=false where device_id='pecem-a'"
            )
        return True

    paused, snapshot_result, disabled = _run_snapshot_admin_race(
        930104,
        lambda: repo.accept_current_grant_snapshot(command),
        disable,
    )
    assert paused is False
    assert snapshot_result.status is AuthorityStatus.ACCEPTED
    assert disabled is True

    authority = repo.get_source_authority("pecem-a")
    assert authority is not None
    assert authority.transition_reason is AuthorityReasonCode.DEVICE_DISABLED
    assert authority.lease_expires_at is not None
    assert authority.lease_expires_at <= _now()


def test_c3b_cloud_auth_unavailable_blocks_write_then_new_eligible_lease_recovers_same_epoch():
    repo = _repo()
    _create_device(repo, "pecem-a")
    _legacy_snapshot(repo, "pecem-a")
    _bootstrap(repo)
    _, session_a = _seed_cloud_auth(repo)
    cloud = _transition_cloud(repo)
    assert cloud.status is AuthorityStatus.ACCEPTED
    assert cloud.grant is not None

    invalidated = repo.invalidate_session_lease(
        realm_id="webpilot-pecem",
        lease_id=session_a.lease_id,
        realm_epoch=session_a.realm_epoch,
    )
    assert invalidated is not None

    command = PublishUnderCurrentGrant(
        candidate=_candidate(
            "pecem-a", Source.CLOUD, CLOUD_A,
            sequence=2, marker="after-auth-loss",
        ),
        authority_epoch=cloud.grant.authority_epoch,
        authority_lease_id=cloud.grant.authority_lease_id,
        holder_instance_id=CLOUD_A,
    )
    blocked = repo.accept_current_grant_snapshot(command)
    assert blocked.status is AuthorityStatus.INELIGIBLE
    assert blocked.reason_code is AuthorityReasonCode.CLOUD_AUTH_UNAVAILABLE

    _create_device(repo, "pecem-b")
    _, session_b = _seed_cloud_auth(
        repo,
        owner_device="pecem-a",
        provider_device="pecem-b",
        publisher_id=PUB_B,
        session_id=SESSION_B,
        generation=1,
    )
    assert session_b.realm_epoch > session_a.realm_epoch

    recovered = repo.accept_current_grant_snapshot(command)
    assert recovered.status is AuthorityStatus.ACCEPTED
    assert recovered.grant is not None
    assert recovered.grant.authority_epoch == cloud.grant.authority_epoch
    authority = repo.get_source_authority("pecem-a")
    assert authority is not None
    assert authority.observed_realm_epoch == session_b.realm_epoch


def test_c3b_unrelated_publisher_revoke_does_not_fence_cloud_when_another_lease_is_eligible():
    repo = _repo()
    _create_device(repo, "pecem-a")
    _legacy_snapshot(repo, "pecem-a")
    _bootstrap(repo)
    _, session_a = _seed_cloud_auth(repo)
    cloud = _transition_cloud(repo)
    assert cloud.grant is not None

    _create_device(repo, "pecem-b")
    _, session_b = _seed_cloud_auth(
        repo,
        owner_device="pecem-a",
        provider_device="pecem-b",
        publisher_id=PUB_B,
        session_id=SESSION_B,
        generation=1,
    )
    assert session_b.realm_epoch > session_a.realm_epoch
    revoked = repo.revoke_session_publisher(PUB_B)
    assert revoked is not None

    before = repo.get_source_authority("pecem-a")
    assert before is not None
    result = repo.accept_current_grant_snapshot(
        PublishUnderCurrentGrant(
            candidate=_candidate(
                "pecem-a",
                Source.CLOUD,
                CLOUD_A,
                sequence=2,
                marker="fallback-provider-a",
            ),
            authority_epoch=cloud.grant.authority_epoch,
            authority_lease_id=cloud.grant.authority_lease_id,
            holder_instance_id=CLOUD_A,
        )
    )
    assert result.status is AuthorityStatus.ACCEPTED
    after = repo.get_source_authority("pecem-a")
    assert after is not None
    assert after.authority_epoch == before.authority_epoch
    assert after.authority_lease_id == before.authority_lease_id
    assert after.transition_reason is not AuthorityReasonCode.AUTHORITY_FENCED


def test_c3b_return_to_legacy_fences_old_grant_and_restores_legacy_snapshot_path():
    repo = _repo()
    _create_device(repo, "pecem-a")
    _legacy_snapshot(repo, "pecem-a")
    managed = _bootstrap(repo)
    assert managed.grant is not None

    legacy = repo.return_source_authority_to_legacy("pecem-a")
    assert legacy is not None
    assert legacy.mode is AuthorityMode.LEGACY
    assert legacy.active_source is None
    assert legacy.authority_epoch == managed.grant.authority_epoch + 1
    assert repo.get_current_grant("pecem-a") is None

    result = _legacy_snapshot(
        repo,
        "pecem-a",
        sequence=2,
        marker="legacy-restored",
    )
    assert result.status is AcceptSnapshotStatus.ACCEPTED
    assert repo.get_snapshot("pecem-a").snapshot["marker"] == "legacy-restored"

    assert DSN is not None
    with psycopg.connect(DSN, autocommit=True) as conn:
        metadata = conn.execute(
            """
            select snapshot_source, snapshot_authority_epoch,
                   snapshot_authority_lease_id, snapshot_writer_instance_id
            from public.devices where device_id='pecem-a'
            """
        ).fetchone()
    assert metadata == (None, None, None, None)


def test_c3b_stale_external_preread_cannot_promote_failback_baseline_to_continuity():
    repo = _repo()
    _create_device(repo, "pecem-a")
    _legacy_snapshot(repo, "pecem-a", marker="desktop-before")
    _bootstrap(repo)
    stale_pre_read = repo.get_snapshot("pecem-a")
    assert stale_pre_read is not None

    _seed_cloud_auth(repo)
    cloud = _transition_cloud(repo, marker="cloud-winner")
    assert cloud.status is AuthorityStatus.ACCEPTED

    _prepare_server_failback_gate()
    back = repo.accept_transition_candidate(
        TransitionCandidate(
            candidate=_candidate(
                "pecem-a",
                Source.DESKTOP,
                BOOT_A,
                sequence=3,
                marker="desktop-failback",
            )
        )
    )
    assert stale_pre_read.snapshot["marker"] == "desktop-before"
    assert back.status is AuthorityStatus.ACCEPTED
    assert back.previous_source is Source.CLOUD
    assert back.side_effect_policy is SideEffectPolicy.BASELINE
    assert back.previous_snapshot_for_side_effects is None


# R11 regressions: only F1..F6.


def _set_authority_expiry(device_id: str, when: datetime) -> None:
    assert DSN is not None
    with psycopg.connect(DSN, autocommit=True) as conn:
        conn.execute(
            """
            update public.device_source_authority
            set lease_expires_at=%s
            where device_id=%s
            """,
            (when, device_id),
        )


def _wait_for_application_lock(application_name: str, timeout: float = 5.0) -> None:
    assert DSN is not None
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        with psycopg.connect(DSN, autocommit=True) as conn:
            row = conn.execute(
                """
                select wait_event_type
                from pg_stat_activity
                where application_name=%s
                order by backend_start desc
                limit 1
                """,
                (application_name,),
            ).fetchone()
        if row is not None and row[0] == "Lock":
            return
        time.sleep(0.02)
    raise AssertionError(f"{application_name} did not block on a DB lock")


def _direct_legacy_accept(
    *,
    device_id: str,
    boot_id: UUID,
    sequence: int,
    marker: str,
    application_name: str,
):
    assert DSN is not None
    generated_at = _now()
    snapshot = _body(
        boot_id=boot_id,
        sequence=sequence,
        generated_at=generated_at,
        marker=marker,
    )
    with psycopg.connect(
        DSN,
        autocommit=True,
        application_name=application_name,
    ) as conn:
        return conn.execute(
            """
            select status, received_at
            from public.accept_device_snapshot(%s,%s,%s,%s,%s,%s)
            """,
            (
                device_id,
                psycopg.types.json.Jsonb(snapshot),
                2,
                boot_id,
                sequence,
                generated_at,
            ),
        ).fetchone()


def _direct_bootstrap(device_id: str, application_name: str):
    assert DSN is not None
    with psycopg.connect(
        DSN,
        autocommit=True,
        application_name=application_name,
    ) as conn:
        return conn.execute(
            """
            select status, authority_epoch
            from public.bootstrap_managed_source_authority(%s)
            """,
            (device_id,),
        ).fetchone()


def _direct_current_grant(
    *,
    grant,
    source: Source,
    instance_id: UUID,
    snapshot: dict,
    generated_at: datetime,
):
    assert DSN is not None
    with psycopg.connect(DSN, autocommit=True) as conn:
        return conn.execute(
            """
            select status, reason_code
            from public.accept_managed_snapshot_current_grant(
                %s,%s,%s,%s,%s,%s,%s,%s,%s,%s
            )
            """,
            (
                grant.device_id,
                source.value,
                grant.authority_epoch,
                grant.authority_lease_id,
                instance_id,
                psycopg.types.json.Jsonb(snapshot),
                2,
                instance_id,
                int(snapshot["sequence"]),
                generated_at,
            ),
        ).fetchone()


def _direct_transition(
    *,
    device_id: str,
    source: Source,
    instance_id: UUID,
    snapshot: dict,
    generated_at: datetime,
):
    assert DSN is not None
    with psycopg.connect(DSN, autocommit=True) as conn:
        return conn.execute(
            """
            select status, reason_code
            from public.accept_managed_snapshot_transition_candidate(
                %s,%s,%s,%s,%s,%s,%s,%s
            )
            """,
            (
                device_id,
                source.value,
                instance_id,
                psycopg.types.json.Jsonb(snapshot),
                2,
                instance_id,
                int(snapshot["sequence"]),
                generated_at,
            ),
        ).fetchone()


def test_r11_f1_legacy_write_waiting_behind_bootstrap_cannot_bypass_managed():
    repo = _repo()
    _create_device(repo, "pecem-a")
    _legacy_snapshot(repo, "pecem-a", sequence=1, marker="before-bootstrap")
    _heartbeat(
        "pecem-a",
        Source.DESKTOP,
        BOOT_A,
        reason=AuthorityReasonCode.DESKTOP_HEALTHY,
    )

    assert DSN is not None
    blocker = psycopg.connect(DSN, autocommit=False)
    blocker.execute(
        "select device_id from public.devices where device_id='pecem-a' for update"
    )
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            bootstrap = pool.submit(
                _direct_bootstrap,
                "pecem-a",
                "r11_f1_bootstrap",
            )
            _wait_for_application_lock("r11_f1_bootstrap")
            legacy = pool.submit(
                _direct_legacy_accept,
                device_id="pecem-a",
                boot_id=BOOT_A,
                sequence=2,
                marker="legacy-must-not-win-after-bootstrap",
                application_name="r11_f1_legacy",
            )
            _wait_for_application_lock("r11_f1_legacy")
            blocker.commit()
            bootstrap_row = bootstrap.result(timeout=10)
            with pytest.raises(psycopg.errors.RaiseException) as exc:
                legacy.result(timeout=10)
    finally:
        if not blocker.closed:
            blocker.rollback()
            blocker.close()

    assert bootstrap_row == ("accepted", 1)
    assert "managed_snapshot_required" in str(exc.value)
    stored = repo.get_snapshot("pecem-a")
    assert stored is not None
    assert stored.sequence == 1
    assert stored.snapshot["marker"] == "before-bootstrap"


@pytest.mark.parametrize(
    ("heartbeat_age_seconds", "snapshot_age_seconds", "expected"),
    [
        (1, 1, AuthorityStatus.ACCEPTED),
        (91, 1, AuthorityStatus.INELIGIBLE),
        (1, 121, AuthorityStatus.INELIGIBLE),
    ],
)
def test_r11_f2_bootstrap_requires_fresh_heartbeat_and_fresh_snapshot(
    heartbeat_age_seconds: int,
    snapshot_age_seconds: int,
    expected: AuthorityStatus,
):
    repo = _repo()
    _create_device(repo, "pecem-a")
    _legacy_snapshot(repo, "pecem-a")
    _heartbeat(
        "pecem-a",
        Source.DESKTOP,
        BOOT_A,
        reason=AuthorityReasonCode.DESKTOP_HEALTHY,
    )
    assert DSN is not None
    with psycopg.connect(DSN, autocommit=True) as conn:
        conn.execute(
            """
            update public.device_source_heartbeats
            set last_heartbeat_at=clock_timestamp()-(%s * interval '1 second')
            where device_id='pecem-a' and source='desktop'
            """,
            (heartbeat_age_seconds,),
        )
        conn.execute(
            """
            update public.devices
            set received_at=clock_timestamp()-(%s * interval '1 second')
            where device_id='pecem-a'
            """,
            (snapshot_age_seconds,),
        )

    result = repo.bootstrap_managed_source_authority("pecem-a")
    assert result.status is expected
    authority = repo.get_source_authority("pecem-a")
    assert authority is not None
    if expected is AuthorityStatus.ACCEPTED:
        assert authority.mode is AuthorityMode.MANAGED
        assert authority.authority_epoch == 1
    else:
        assert result.reason_code is AuthorityReasonCode.BOOTSTRAP_NOT_ELIGIBLE
        assert authority.mode is AuthorityMode.LEGACY
        assert authority.authority_epoch == 0


def test_r11_f3_initial_bootstrap_cannot_reactivate_after_managed_rollback():
    repo = _repo()
    _create_device(repo, "pecem-a")
    _legacy_snapshot(repo, "pecem-a")
    first = _bootstrap(repo)
    assert first.grant is not None

    rolled_back = repo.return_source_authority_to_legacy("pecem-a")
    assert rolled_back is not None
    assert rolled_back.mode is AuthorityMode.LEGACY
    historical_epoch = rolled_back.authority_epoch
    assert historical_epoch > 0

    _heartbeat(
        "pecem-a",
        Source.DESKTOP,
        BOOT_A,
        reason=AuthorityReasonCode.DESKTOP_HEALTHY,
    )
    retry = repo.bootstrap_managed_source_authority("pecem-a")
    assert retry.status is AuthorityStatus.INELIGIBLE
    assert retry.reason_code is AuthorityReasonCode.BOOTSTRAP_NOT_ELIGIBLE

    after = repo.get_source_authority("pecem-a")
    assert after is not None
    assert after.mode is AuthorityMode.LEGACY
    assert after.authority_epoch == historical_epoch
    assert after.active_source is None


def test_r11_f4_current_grant_waiting_on_lock_rechecks_authority_expiry_after_wait():
    repo = _repo()
    _create_device(repo, "pecem-a")
    _legacy_snapshot(repo, "pecem-a")
    boot = _bootstrap(repo)
    assert boot.grant is not None
    grant = boot.grant
    _set_authority_expiry("pecem-a", _now() + timedelta(milliseconds=700))

    command = PublishUnderCurrentGrant(
        candidate=_candidate(
            "pecem-a",
            Source.DESKTOP,
            BOOT_A,
            sequence=2,
            marker="after-expiry-must-fail",
        ),
        authority_epoch=grant.authority_epoch,
        authority_lease_id=grant.authority_lease_id,
        holder_instance_id=BOOT_A,
    )

    assert DSN is not None
    blocker = psycopg.connect(DSN, autocommit=False)
    blocker.execute(
        "select device_id from public.devices where device_id='pecem-a' for update"
    )
    try:
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(repo.accept_current_grant_snapshot, command)
            time.sleep(1.0)
            blocker.commit()
            result = future.result(timeout=10)
    finally:
        if not blocker.closed:
            blocker.rollback()
            blocker.close()

    assert result.status is AuthorityStatus.FENCED
    assert result.reason_code is AuthorityReasonCode.AUTHORITY_EXPIRED
    stored = repo.get_snapshot("pecem-a")
    assert stored is not None and stored.sequence == 1


def test_r11_f4_cloud_write_waiting_on_lock_rechecks_session_lease_expiry_after_wait():
    repo = _repo()
    _create_device(repo, "pecem-a")
    _legacy_snapshot(repo, "pecem-a")
    _bootstrap(repo)
    _, session = _seed_cloud_auth(repo)
    cloud = _transition_cloud(repo)
    assert cloud.grant is not None
    _set_authority_expiry("pecem-a", _now() + timedelta(seconds=10))

    assert DSN is not None
    with psycopg.connect(DSN, autocommit=True) as conn:
        conn.execute(
            """
            update public.webpilot_session_leases
            set expires_at=clock_timestamp()+interval '700 milliseconds'
            where lease_id=%s
            """,
            (session.lease_id,),
        )

    command = PublishUnderCurrentGrant(
        candidate=_candidate(
            "pecem-a",
            Source.CLOUD,
            CLOUD_A,
            sequence=2,
            marker="expired-auth-must-fail",
        ),
        authority_epoch=cloud.grant.authority_epoch,
        authority_lease_id=cloud.grant.authority_lease_id,
        holder_instance_id=CLOUD_A,
    )

    blocker = psycopg.connect(DSN, autocommit=False)
    blocker.execute(
        "select device_id from public.devices where device_id='pecem-a' for update"
    )
    try:
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(repo.accept_current_grant_snapshot, command)
            time.sleep(1.0)
            blocker.commit()
            result = future.result(timeout=10)
    finally:
        if not blocker.closed:
            blocker.rollback()
            blocker.close()

    assert result.status is AuthorityStatus.INELIGIBLE
    assert result.reason_code is AuthorityReasonCode.CLOUD_AUTH_UNAVAILABLE
    stored = repo.get_snapshot("pecem-a")
    assert stored is not None
    assert stored.snapshot["marker"] == "cloud"


def test_r11_f5_expired_desktop_lease_without_failover_gate_does_not_grant_cloud():
    repo = _repo()
    _create_device(repo, "pecem-a")
    _legacy_snapshot(repo, "pecem-a")
    _bootstrap(repo)
    _seed_cloud_auth(repo)
    _set_authority_expiry("pecem-a", _now() - timedelta(seconds=1))
    _source_heartbeat_rpc(
        "pecem-a", Source.CLOUD, CLOUD_A,
        candidate_at=_now(), ready=True,
    )

    result = repo.accept_transition_candidate(
        TransitionCandidate(
            candidate=_candidate(
                "pecem-a",
                Source.CLOUD,
                CLOUD_A,
                sequence=1,
                marker="cloud-no-gate",
            )
        )
    )
    assert result.status is AuthorityStatus.INELIGIBLE
    assert result.reason_code is AuthorityReasonCode.FAILOVER_WAIT_HYSTERESIS
    authority = repo.get_source_authority("pecem-a")
    assert authority is not None and authority.active_source is Source.DESKTOP


def test_r11_f5_expired_cloud_lease_without_failback_gate_does_not_grant_desktop():
    repo = _repo()
    _create_device(repo, "pecem-a")
    _legacy_snapshot(repo, "pecem-a")
    _bootstrap(repo)
    _seed_cloud_auth(repo)
    cloud = _transition_cloud(repo)
    assert cloud.status is AuthorityStatus.ACCEPTED
    _set_authority_expiry("pecem-a", _now() - timedelta(seconds=1))
    _heartbeat(
        "pecem-a",
        Source.DESKTOP,
        BOOT_A,
        reason=AuthorityReasonCode.DESKTOP_HEALTHY,
    )

    result = repo.accept_transition_candidate(
        TransitionCandidate(
            candidate=_candidate(
                "pecem-a",
                Source.DESKTOP,
                BOOT_A,
                sequence=3,
                marker="desktop-no-gate",
            )
        )
    )
    assert result.status is AuthorityStatus.INELIGIBLE
    assert result.reason_code is AuthorityReasonCode.FAILBACK_WAIT_STABLE
    authority = repo.get_source_authority("pecem-a")
    assert authority is not None and authority.active_source is Source.CLOUD


def test_r11_f5_expired_lease_with_fresh_explicit_cross_source_gate_can_transition():
    repo = _repo()
    _create_device(repo, "pecem-a")
    _legacy_snapshot(repo, "pecem-a")
    _bootstrap(repo)
    _seed_cloud_auth(repo)
    _age_authoritative_snapshot('pecem-a', 181)
    _set_authority_expiry("pecem-a", _now() - timedelta(seconds=1))
    _prepare_server_failover_gate()

    result = repo.accept_transition_candidate(
        TransitionCandidate(
            candidate=_candidate(
                "pecem-a",
                Source.CLOUD,
                CLOUD_A,
                sequence=1,
                marker="cloud-with-gate",
            )
        )
    )
    assert result.status is AuthorityStatus.ACCEPTED
    assert result.grant is not None and result.grant.authority_epoch == 2


def test_r11_f6_current_grant_rpc_rejects_generated_at_mismatch_before_write():
    repo = _repo()
    _create_device(repo, "pecem-a")
    _legacy_snapshot(repo, "pecem-a")
    boot = _bootstrap(repo)
    assert boot.grant is not None

    param_generated_at = _now()
    body_generated_at = param_generated_at - timedelta(seconds=1)
    body = _body(
        boot_id=BOOT_A,
        sequence=2,
        generated_at=body_generated_at,
        marker="mismatch-current",
    )
    row = _direct_current_grant(
        grant=boot.grant,
        source=Source.DESKTOP,
        instance_id=BOOT_A,
        snapshot=body,
        generated_at=param_generated_at,
    )
    assert row == ("rejected", "snapshot_invalid")
    stored = repo.get_snapshot("pecem-a")
    assert stored is not None and stored.sequence == 1


def test_r11_f6_transition_rpc_rejects_invalid_or_mismatched_generated_at_before_transition():
    repo = _repo()
    _create_device(repo, "pecem-a")
    _legacy_snapshot(repo, "pecem-a")
    _bootstrap(repo)
    _seed_cloud_auth(repo)
    _prepare_server_failover_gate()

    param_generated_at = _now()
    for bad_value in (
        (param_generated_at - timedelta(seconds=1)).isoformat(),
        "2026-10-09T12:00:00",
        "not-a-datetime",
    ):
        body = {
            "schema_version": 2,
            "boot_id": str(CLOUD_A),
            "sequence": 1,
            "generated_at": bad_value,
            "marker": f"bad-{bad_value}",
        }
        row = _direct_transition(
            device_id="pecem-a",
            source=Source.CLOUD,
            instance_id=CLOUD_A,
            snapshot=body,
            generated_at=param_generated_at,
        )
        assert row == ("rejected", "snapshot_invalid")

    authority = repo.get_source_authority("pecem-a")
    assert authority is not None
    assert authority.active_source is Source.DESKTOP
    assert authority.authority_epoch == 1


# R11.1-F1: same-source reacquisition remains fail-closed until C3-C policy exists.


def test_r111_f1_desktop_new_instance_cannot_replace_valid_same_source_holder():
    repo = _repo()
    _create_device(repo, "pecem-a")
    _legacy_snapshot(repo, "pecem-a")
    first = _bootstrap(repo)
    assert first.grant is not None
    original = first.grant

    _heartbeat(
        "pecem-a",
        Source.DESKTOP,
        BOOT_B,
        reason=AuthorityReasonCode.DESKTOP_HEALTHY,
    )
    candidate = _candidate(
        "pecem-a",
        Source.DESKTOP,
        BOOT_B,
        sequence=2,
        marker="desktop-restart-must-not-reacquire",
    )
    result = repo.accept_transition_candidate(
        TransitionCandidate(candidate=candidate)
    )

    assert result.status is AuthorityStatus.INELIGIBLE
    assert result.reason_code is AuthorityReasonCode.AUTHORITY_FENCED
    authority = repo.get_source_authority("pecem-a")
    stored = repo.get_snapshot("pecem-a")
    assert authority is not None and stored is not None
    assert authority.authority_epoch == original.authority_epoch
    assert authority.authority_lease_id == original.authority_lease_id
    assert authority.holder_instance_id == BOOT_A
    assert stored.sequence == 1
    assert stored.snapshot["marker"] == "legacy"


def test_r111_f1_cloud_new_instance_cannot_replace_valid_same_source_holder():
    repo = _repo()
    _create_device(repo, "pecem-a")
    _legacy_snapshot(repo, "pecem-a")
    _bootstrap(repo)
    _seed_cloud_auth(repo)
    cloud = _transition_cloud(repo)
    assert cloud.grant is not None
    original = cloud.grant

    _heartbeat(
        "pecem-a",
        Source.CLOUD,
        BOOT_B,
        reason=AuthorityReasonCode.CLOUD_STANDBY_STALE,
        persistent_state_ready=True,
    )
    candidate = _candidate(
        "pecem-a",
        Source.CLOUD,
        BOOT_B,
        sequence=2,
        marker="cloud-restart-must-not-reacquire",
    )
    result = repo.accept_transition_candidate(
        TransitionCandidate(candidate=candidate)
    )

    assert result.status is AuthorityStatus.INELIGIBLE
    assert result.reason_code is AuthorityReasonCode.AUTHORITY_FENCED
    authority = repo.get_source_authority("pecem-a")
    stored = repo.get_snapshot("pecem-a")
    assert authority is not None and stored is not None
    assert authority.authority_epoch == original.authority_epoch
    assert authority.authority_lease_id == original.authority_lease_id
    assert authority.holder_instance_id == CLOUD_A
    assert stored.snapshot["marker"] == "cloud"


@pytest.mark.parametrize("instance_id", [BOOT_A, BOOT_B])
def test_r111_f1_expired_desktop_same_source_candidate_cannot_create_new_grant(
    instance_id: UUID,
):
    repo = _repo()
    _create_device(repo, "pecem-a")
    _legacy_snapshot(repo, "pecem-a")
    first = _bootstrap(repo)
    assert first.grant is not None
    original = first.grant
    _set_authority_expiry("pecem-a", _now() - timedelta(seconds=1))

    _heartbeat(
        "pecem-a",
        Source.DESKTOP,
        instance_id,
        reason=AuthorityReasonCode.DESKTOP_HEALTHY,
    )
    candidate = _candidate(
        "pecem-a",
        Source.DESKTOP,
        instance_id,
        sequence=2,
        marker=f"expired-reacquire-{instance_id}",
    )
    result = repo.accept_transition_candidate(
        TransitionCandidate(candidate=candidate)
    )

    assert result.status is AuthorityStatus.INELIGIBLE
    assert result.reason_code is AuthorityReasonCode.AUTHORITY_FENCED
    authority = repo.get_source_authority("pecem-a")
    stored = repo.get_snapshot("pecem-a")
    assert authority is not None and stored is not None
    assert authority.authority_epoch == original.authority_epoch
    assert authority.authority_lease_id == original.authority_lease_id
    assert authority.holder_instance_id == BOOT_A
    assert authority.lease_expires_at is not None
    assert authority.lease_expires_at <= _now()
    assert stored.sequence == 1
    assert stored.snapshot["marker"] == "legacy"


# SPEC 027 C3-C: server-owned heartbeat, renewal and temporal arbitration.


def _source_heartbeat_rpc(
    device_id: str,
    source: Source,
    instance_id: UUID,
    *,
    process: bool = True,
    collection: bool = True,
    candidate_at: datetime | None = None,
    ready: bool | None = None,
):
    assert DSN is not None
    with psycopg.connect(DSN, autocommit=True) as conn:
        binding_id = None
        if source is Source.CLOUD:
            row = conn.execute(
                "select cloud_binding_id from public.cloud_bindings                 where device_id=%s and status='active'", (device_id,)
            ).fetchone()
            binding_id = None if row is None else row[0]
        return conn.execute(
            """
            select status, reason_code, authority_epoch, authority_lease_id,
                   holder_instance_id, lease_expires_at, renewed
            from public.record_source_heartbeat(
                %s,%s,%s,%s,%s,%s,%s,%s,%s
            )
            """,
            (
                device_id, source.value, instance_id,
                process, collection,
                candidate_at if source is Source.DESKTOP else None,
                candidate_at if source is Source.CLOUD else None,
                ready if source is Source.CLOUD else None,
                binding_id,
            ),
        ).fetchone()


def _age_heartbeat(
    device_id: str, source: Source, *, seconds: float, instance_id: UUID | None = None
) -> None:
    assert DSN is not None
    with psycopg.connect(DSN, autocommit=True) as conn:
        conn.execute(
            """
            update public.device_source_heartbeats
            set last_heartbeat_at=clock_timestamp()-(%s * interval '1 second')
            where device_id=%s and source=%s
              and (%s::uuid is null or instance_id=%s)
            """, (seconds, device_id, source.value, instance_id, instance_id),
        )


def _age_authoritative_snapshot(device_id: str, seconds: float) -> None:
    assert DSN is not None
    with psycopg.connect(DSN, autocommit=True) as conn:
        conn.execute(
            """
            update public.device_source_authority
            set last_authoritative_snapshot_at=clock_timestamp()-(%s * interval '1 second')
            where device_id=%s
            """, (seconds, device_id),
        )


def _source_decision_rpc(
    device_id: str, source: Source, instance_id: UUID,
):
    assert DSN is not None
    with psycopg.connect(DSN, autocommit=True) as conn:
        return conn.execute(
            """
            select public.source_candidate_reason(
                %s,%s,%s,clock_timestamp()
            )
            """,
            (device_id, source.value, instance_id),
        ).fetchone()[0]


def test_r12_server_heartbeat_continuity_and_stale_snapshot_no_renewal():
    repo = _repo()
    _create_device(repo, "pecem-a")
    _legacy_snapshot(repo, "pecem-a")
    initial = _bootstrap(repo)
    assert initial.grant is not None

    assert _source_heartbeat_rpc("pecem-a", Source.DESKTOP, BOOT_A)[-1] is True
    state = repo.get_source_heartbeat("pecem-a", Source.DESKTOP, BOOT_A)
    assert state is not None and state.consecutive_healthy >= 2
    epoch = repo.get_source_authority("pecem-a")
    assert epoch is not None
    assert epoch.authority_epoch == initial.grant.authority_epoch
    assert epoch.authority_lease_id == initial.grant.authority_lease_id

    _age_authoritative_snapshot("pecem-a", 121)
    blocked = _source_heartbeat_rpc("pecem-a", Source.DESKTOP, BOOT_A)
    assert blocked[-1] is False
    assert blocked[1] == "desktop_snapshot_stale"
    authority = repo.get_source_authority("pecem-a")
    assert authority is not None
    assert authority.authoritative_snapshot_stale_since is not None
    assert authority.authority_epoch == initial.grant.authority_epoch


def test_r12_healthy_desktop_heartbeat_cannot_mask_snapshot_stale_hysteresis():
    repo = _repo()
    _create_device(repo, "pecem-a")
    _legacy_snapshot(repo, "pecem-a")
    _bootstrap(repo)
    _seed_cloud_auth(repo)
    _age_authoritative_snapshot("pecem-a", 179)
    _source_heartbeat_rpc("pecem-a", Source.DESKTOP, BOOT_A)
    _source_heartbeat_rpc(
        "pecem-a", Source.CLOUD, CLOUD_A,
        candidate_at=_now(), ready=True,
    )
    assert _source_decision_rpc("pecem-a", Source.CLOUD, CLOUD_A) == "failover_wait_hysteresis"

    _age_authoritative_snapshot("pecem-a", 181)
    _source_heartbeat_rpc(
        "pecem-a", Source.CLOUD, CLOUD_A,
        candidate_at=_now(), ready=True,
    )
    assert _source_decision_rpc("pecem-a", Source.CLOUD, CLOUD_A) == "failover_granted"


def test_r12_desktop_failback_requires_three_heartbeats_120s_cloud_active():
    repo = _repo()
    _create_device(repo, "pecem-a")
    _legacy_snapshot(repo, "pecem-a")
    _bootstrap(repo)
    _seed_cloud_auth(repo)
    _age_authoritative_snapshot("pecem-a", 181)
    _source_heartbeat_rpc("pecem-a", Source.CLOUD, CLOUD_A, candidate_at=_now(), ready=True)
    transition = _transition_cloud(repo)
    assert transition.status is AuthorityStatus.ACCEPTED
    assert DSN is not None
    with psycopg.connect(DSN, autocommit=True) as conn:
        conn.execute(
            """
            update public.device_source_authority
            set granted_at=clock_timestamp()-interval '121 seconds'
            where device_id='pecem-a'
            """
        )
    _source_heartbeat_rpc("pecem-a", Source.DESKTOP, BOOT_A)
    assert _source_decision_rpc("pecem-a", Source.DESKTOP, BOOT_A) == "failback_wait_stable"
    _source_heartbeat_rpc("pecem-a", Source.DESKTOP, BOOT_A)
    assert _source_decision_rpc("pecem-a", Source.DESKTOP, BOOT_A) == "failback_wait_stable"
    assert DSN is not None
    with psycopg.connect(DSN, autocommit=True) as conn:
        conn.execute(
            """
            update public.device_source_heartbeats
            set healthy_since=clock_timestamp()-interval '121 seconds'
            where device_id='pecem-a' and source='desktop'
            """
        )
    _source_heartbeat_rpc("pecem-a", Source.DESKTOP, BOOT_A)
    assert _source_decision_rpc("pecem-a", Source.DESKTOP, BOOT_A) == "failback_granted"
    assert repo.get_source_authority("pecem-a").active_source is Source.CLOUD


def test_r12_same_source_restart_waits_old_holder_liveness_threshold():
    repo = _repo()
    _create_device(repo, "pecem-a")
    _legacy_snapshot(repo, "pecem-a")
    initial = _bootstrap(repo)
    assert initial.grant is not None

    blocked = _source_heartbeat_rpc("pecem-a", Source.DESKTOP, BOOT_B)
    assert blocked[0] == "accepted"
    assert blocked[1] == "authority_fenced"
    assert blocked[3] is None

    _age_heartbeat("pecem-a", Source.DESKTOP, seconds=101, instance_id=BOOT_A)
    _age_authoritative_snapshot("pecem-a", 101)
    permitted = _source_heartbeat_rpc("pecem-a", Source.DESKTOP, BOOT_B)
    assert permitted[0] == "accepted"
    assert permitted[1] == "desktop_reacquire_granted"

    won = repo.accept_transition_candidate(
        TransitionCandidate(
            candidate=_candidate(
                "pecem-a", Source.DESKTOP, BOOT_B,
                sequence=2, marker="reacquired",
            )
        )
    )
    assert won.status is AuthorityStatus.ACCEPTED
    assert won.grant is not None
    assert won.grant.authority_epoch == initial.grant.authority_epoch + 1
    assert won.grant.authority_lease_id != initial.grant.authority_lease_id


def test_r12_client_cannot_set_server_grant_via_reason_in_heartbeat_sql_signature():
    assert DSN is not None
    with psycopg.connect(DSN, autocommit=True) as conn:
        names = conn.execute(
            """
            select pg_get_function_arguments(p.oid)
            from pg_proc p
            join pg_namespace n on n.oid=p.pronamespace
            where n.nspname='public' and p.proname='record_source_heartbeat'
            """
        ).fetchall()
        assert len(names) == 1
        assert "p_reason" not in names[0][0]
        assert "p_authority_epoch" not in names[0][0]
        assert "p_authority_lease_id" not in names[0][0]


def test_r12_desktop_stale_recovery_keeps_grant_and_cancels_hysteresis():
    repo = _repo()
    _create_device(repo, "pecem-a")
    _legacy_snapshot(repo, "pecem-a")
    original = _bootstrap(repo).grant
    assert original is not None
    _seed_cloud_auth(repo)
    _age_authoritative_snapshot("pecem-a", 150)
    stale = _source_heartbeat_rpc("pecem-a", Source.DESKTOP, BOOT_A)
    assert stale[1] == "desktop_snapshot_stale" and stale[-1] is False

    ready = _source_heartbeat_rpc(
        "pecem-a", Source.CLOUD, CLOUD_A, candidate_at=_now(), ready=True,
    )
    assert ready[1] == "failover_wait_hysteresis"

    candidate = _candidate(
        "pecem-a", Source.DESKTOP, BOOT_A, sequence=2, marker="recovery",
    )
    recovered = repo.accept_current_grant_snapshot(
        PublishUnderCurrentGrant(
            candidate=candidate, authority_epoch=original.authority_epoch,
            authority_lease_id=original.authority_lease_id,
            holder_instance_id=BOOT_A,
        )
    )
    assert recovered.status is AuthorityStatus.ACCEPTED
    renewed = _source_heartbeat_rpc("pecem-a", Source.DESKTOP, BOOT_A)
    assert renewed[-1] is True
    updated = repo.get_source_authority("pecem-a")
    assert updated is not None
    assert updated.authority_epoch == original.authority_epoch
    assert updated.authority_lease_id == original.authority_lease_id
    assert updated.authoritative_snapshot_stale_since is None
    assert _source_decision_rpc(
        "pecem-a", Source.CLOUD, CLOUD_A
    ) == "failover_wait_hysteresis"


def test_r12_cloud_holder_snapshot_stale_does_not_renew_but_can_recover():
    repo = _repo()
    _create_device(repo, "pecem-a")
    _legacy_snapshot(repo, "pecem-a")
    _bootstrap(repo)
    _seed_cloud_auth(repo)
    cloud = _transition_cloud(repo)
    assert cloud.grant is not None
    _age_authoritative_snapshot("pecem-a", 95)
    blocked = _source_heartbeat_rpc(
        "pecem-a", Source.CLOUD, CLOUD_A, candidate_at=_now(), ready=True,
    )
    assert blocked[-1] is False
    assert blocked[1] == "cloud_snapshot_stale"

    recovery = repo.accept_current_grant_snapshot(
        PublishUnderCurrentGrant(
            candidate=_candidate(
                "pecem-a", Source.CLOUD, CLOUD_A,
                sequence=2, marker="cloud-recovered",
            ),
            authority_epoch=cloud.grant.authority_epoch,
            authority_lease_id=cloud.grant.authority_lease_id,
            holder_instance_id=CLOUD_A,
        )
    )
    assert recovery.status is AuthorityStatus.ACCEPTED
    renewed = _source_heartbeat_rpc(
        "pecem-a", Source.CLOUD, CLOUD_A, candidate_at=_now(), ready=True,
    )
    assert renewed[-1] is True
    authority = repo.get_source_authority("pecem-a")
    assert authority is not None
    assert authority.authority_epoch == cloud.grant.authority_epoch
    assert authority.authority_lease_id == cloud.grant.authority_lease_id
    assert authority.authoritative_snapshot_stale_since is None


def test_r12_cloud_standby_59_60s_boundaries_and_auth_availability():
    repo = _repo()
    _create_device(repo, "pecem-a")
    _legacy_snapshot(repo, "pecem-a")
    _bootstrap(repo)
    _, session = _seed_cloud_auth(repo)
    _age_authoritative_snapshot("pecem-a", 181)
    _source_heartbeat_rpc(
        "pecem-a", Source.CLOUD, CLOUD_A, candidate_at=_now(), ready=True,
    )
    _age_heartbeat("pecem-a", Source.CLOUD, seconds=59)
    assert _source_decision_rpc("pecem-a", Source.CLOUD, CLOUD_A) == "failover_granted"
    _age_heartbeat("pecem-a", Source.CLOUD, seconds=61)
    assert _source_decision_rpc("pecem-a", Source.CLOUD, CLOUD_A) == "cloud_standby_stale"
    _source_heartbeat_rpc(
        "pecem-a", Source.CLOUD, CLOUD_A, candidate_at=_now(), ready=False,
    )
    assert _source_decision_rpc(
        "pecem-a", Source.CLOUD, CLOUD_A
    ) == "cloud_persistent_state_unavailable"
    _source_heartbeat_rpc(
        "pecem-a", Source.CLOUD, CLOUD_A, candidate_at=_now(), ready=True,
    )
    repo.invalidate_session_lease(
        realm_id="webpilot-pecem",
        lease_id=session.lease_id,
        realm_epoch=session.realm_epoch,
    )
    assert _source_decision_rpc(
        "pecem-a", Source.CLOUD, CLOUD_A
    ) == "cloud_auth_unavailable"


def test_r12_failback_continuity_breaks_on_instance_change_and_degradation():
    repo = _repo()
    _create_device(repo, "pecem-a")
    _legacy_snapshot(repo, "pecem-a")
    _bootstrap(repo)
    _seed_cloud_auth(repo)
    cloud = _transition_cloud(repo)
    assert cloud.grant is not None
    _prepare_server_failback_gate()
    assert _source_decision_rpc(
        "pecem-a", Source.DESKTOP, BOOT_A
    ) == "failback_granted"

    _source_heartbeat_rpc(
        "pecem-a", Source.DESKTOP, BOOT_B, process=True, collection=True,
    )
    changed = repo.get_source_heartbeat("pecem-a", Source.DESKTOP, BOOT_B)
    assert changed is not None
    assert changed.instance_id == BOOT_B
    assert changed.consecutive_healthy == 1
    assert _source_decision_rpc(
        "pecem-a", Source.DESKTOP, BOOT_B
    ) == "failback_wait_stable"
    _source_heartbeat_rpc(
        "pecem-a", Source.DESKTOP, BOOT_B, process=True, collection=False,
    )
    degraded = repo.get_source_heartbeat("pecem-a", Source.DESKTOP, BOOT_B)
    assert degraded is not None
    assert degraded.consecutive_healthy == 0
    assert degraded.healthy_since is None
    _source_heartbeat_rpc("pecem-a", Source.DESKTOP, BOOT_B)
    resumed = repo.get_source_heartbeat("pecem-a", Source.DESKTOP, BOOT_B)
    assert resumed is not None
    assert resumed.consecutive_healthy == 1


def test_r12_continuity_breaks_after_missing_heartbeat_interval():
    repo = _repo()
    _create_device(repo, "pecem-a")
    _legacy_snapshot(repo, "pecem-a")
    _bootstrap(repo)
    for _ in range(3):
        _source_heartbeat_rpc("pecem-a", Source.DESKTOP, BOOT_A)
    _age_heartbeat("pecem-a", Source.DESKTOP, seconds=95)
    _source_heartbeat_rpc("pecem-a", Source.DESKTOP, BOOT_A)
    hb=repo.get_source_heartbeat("pecem-a", Source.DESKTOP, BOOT_A)
    assert hb is not None
    assert hb.consecutive_healthy == 1


def test_r12_cloud_restart_60s_reacquire_and_old_holder_fenced():
    repo = _repo()
    _create_device(repo, "pecem-a")
    _legacy_snapshot(repo, "pecem-a")
    _bootstrap(repo)
    _seed_cloud_auth(repo)
    cloud = _transition_cloud(repo)
    assert cloud.grant is not None
    original = cloud.grant
    blocked = _source_heartbeat_rpc(
        "pecem-a", Source.CLOUD, BOOT_B, candidate_at=_now(), ready=True,
    )
    assert blocked[0] == "accepted"
    assert blocked[1] == "authority_fenced"
    _age_heartbeat("pecem-a", Source.CLOUD, seconds=71, instance_id=CLOUD_A)
    _age_authoritative_snapshot("pecem-a", 71)
    permitted = _source_heartbeat_rpc(
        "pecem-a", Source.CLOUD, BOOT_B, candidate_at=_now(), ready=True,
    )
    assert permitted[1] == "cloud_reacquire_granted"
    won=repo.accept_transition_candidate(
        TransitionCandidate(
            candidate=_candidate(
                "pecem-a", Source.CLOUD, BOOT_B, sequence=1, marker="cloud-new",
            )
        )
    )
    assert won.status is AuthorityStatus.ACCEPTED
    assert won.grant is not None
    assert won.grant.authority_epoch == original.authority_epoch+1
    old=repo.accept_current_grant_snapshot(
        PublishUnderCurrentGrant(
            candidate=_candidate(
                "pecem-a", Source.CLOUD, CLOUD_A, sequence=2, marker="old-cloud",
            ),
            authority_epoch=original.authority_epoch,
            authority_lease_id=original.authority_lease_id,
            holder_instance_id=CLOUD_A,
        )
    )
    assert old.status is AuthorityStatus.FENCED


def test_r12_renewal_expiry_waiting_on_lock_never_resurrects_grant():
    repo = _repo()
    _create_device(repo, "pecem-a")
    _legacy_snapshot(repo, "pecem-a")
    original = _bootstrap(repo).grant
    assert original is not None
    _set_authority_expiry("pecem-a", _now()+timedelta(milliseconds=650))
    assert DSN is not None
    blocker=psycopg.connect(DSN, autocommit=False)
    blocker.execute(
        "select device_id from public.devices where device_id='pecem-a' for update"
    )
    try:
        with ThreadPoolExecutor(max_workers=1) as pool:
            future=pool.submit(_source_heartbeat_rpc, "pecem-a", Source.DESKTOP, BOOT_A)
            time.sleep(.9)
            blocker.commit()
            row=future.result(timeout=10)
    finally:
        if not blocker.closed:
            blocker.rollback()
            blocker.close()
    assert row[-1] is False
    assert row[2] is None and row[3] is None
    assert row[1] == "authority_lease_expired"
    authority=repo.get_source_authority("pecem-a")
    assert authority is not None
    assert authority.authority_epoch == original.authority_epoch
    assert authority.lease_expires_at <= _now()


def test_r12_concurrent_heartbeats_and_other_device_isolation():
    repo=_repo()
    for device, boot in (("pecem-a", BOOT_A), ("pecem-b", BOOT_B)):
        _create_device(repo,device)
        _legacy_snapshot(repo,device,boot_id=boot)
        _bootstrap(repo,device,boot_id=boot)
    previous=repo.get_source_heartbeat("pecem-b", Source.DESKTOP, BOOT_B)
    assert previous is not None
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures=[
            pool.submit(_source_heartbeat_rpc,"pecem-a",Source.DESKTOP,BOOT_A)
            for _ in range(2)
        ]
        results=[f.result(timeout=10) for f in futures]
    assert all(row[-1] is True for row in results)
    a=repo.get_source_heartbeat("pecem-a",Source.DESKTOP,BOOT_A)
    b=repo.get_source_heartbeat("pecem-b",Source.DESKTOP,BOOT_B)
    assert a is not None and b is not None
    assert a.consecutive_healthy >= 3
    assert b.consecutive_healthy == previous.consecutive_healthy
    assert b.last_heartbeat_at == previous.last_heartbeat_at


def test_r12_cloud_renewal_auth_outage_and_recovery_uses_existing_epoch():
    repo = _repo()
    _create_device(repo, "pecem-a")
    _legacy_snapshot(repo, "pecem-a")
    _bootstrap(repo)
    _, session_a = _seed_cloud_auth(repo)
    cloud = _transition_cloud(repo)
    assert cloud.grant is not None
    grant = cloud.grant
    first = _source_heartbeat_rpc(
        "pecem-a", Source.CLOUD, CLOUD_A, candidate_at=_now(), ready=True,
    )
    assert first[-1] is True
    repo.invalidate_session_lease(
        realm_id="webpilot-pecem", lease_id=session_a.lease_id,
        realm_epoch=session_a.realm_epoch,
    )
    blocked = _source_heartbeat_rpc(
        "pecem-a", Source.CLOUD, CLOUD_A, candidate_at=_now(), ready=True,
    )
    assert blocked[-1] is False
    assert blocked[1] == "cloud_auth_unavailable"

    _create_device(repo, "pecem-b")
    _, session_b = _seed_cloud_auth(
        repo, owner_device="pecem-a", provider_device="pecem-b",
        publisher_id=PUB_B, session_id=SESSION_B,
    )
    assert session_b.realm_epoch > session_a.realm_epoch
    recovered = _source_heartbeat_rpc(
        "pecem-a", Source.CLOUD, CLOUD_A, candidate_at=_now(), ready=True,
    )
    assert recovered[-1] is True
    authority = repo.get_source_authority("pecem-a")
    assert authority is not None
    assert authority.authority_epoch == grant.authority_epoch
    assert authority.authority_lease_id == grant.authority_lease_id


def test_r12_renewal_admin_disable_race_never_resurrects_source_lease():
    repo = _repo()
    _create_device(repo, "pecem-a")
    _legacy_snapshot(repo, "pecem-a")
    _bootstrap(repo)

    assert DSN is not None
    blocker = psycopg.connect(DSN, autocommit=False)
    blocker.execute(
        "select device_id from public.devices where device_id='pecem-a' for update"
    )
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            renewal = pool.submit(
                _source_heartbeat_rpc, "pecem-a", Source.DESKTOP, BOOT_A
            )
            def disable():
                with psycopg.connect(DSN, autocommit=True) as conn:
                    conn.execute(
                        "update public.devices set enabled=false where device_id='pecem-a'"
                    )
                return True
            admin = pool.submit(disable)
            blocker.commit()
            hb = renewal.result(timeout=10)
            assert admin.result(timeout=10) is True
    finally:
        if not blocker.closed:
            blocker.rollback()
            blocker.close()

    authority = repo.get_source_authority("pecem-a")
    assert authority is not None
    assert authority.lease_expires_at <= _now()
    assert authority.transition_reason is AuthorityReasonCode.DEVICE_DISABLED
    assert hb[0] in ("accepted", "ineligible")


def test_r12_server_policy_race_snapshot_recovery_vs_cloud_transition_one_winner():
    repo = _repo()
    _create_device(repo, "pecem-a")
    _legacy_snapshot(repo, "pecem-a")
    initial = _bootstrap(repo).grant
    assert initial is not None
    _seed_cloud_auth(repo)
    _prepare_server_failover_gate()

    current = PublishUnderCurrentGrant(
        candidate=_candidate(
            "pecem-a", Source.DESKTOP, BOOT_A,
            sequence=2, marker="desktop-recovery-winner",
        ),
        authority_epoch=initial.authority_epoch,
        authority_lease_id=initial.authority_lease_id,
        holder_instance_id=BOOT_A,
    )
    challenger = TransitionCandidate(
        candidate=_candidate(
            "pecem-a", Source.CLOUD, CLOUD_A,
            sequence=1, marker="cloud-transition-winner",
        )
    )
    with ThreadPoolExecutor(max_workers=2) as pool:
        a=pool.submit(repo.accept_current_grant_snapshot,current)
        b=pool.submit(repo.accept_transition_candidate,challenger)
        results=[a.result(timeout=10),b.result(timeout=10)]
    assert sum(x.status is AuthorityStatus.ACCEPTED for x in results) == 1
    winner=next(x for x in results if x.status is AuthorityStatus.ACCEPTED)
    loser=next(x for x in results if x.status is not AuthorityStatus.ACCEPTED)
    assert loser.status in (AuthorityStatus.FENCED,AuthorityStatus.INELIGIBLE)
    authority=repo.get_source_authority("pecem-a")
    stored=repo.get_snapshot("pecem-a")
    assert authority is not None and stored is not None
    assert authority.active_source is winner.source
    assert stored.snapshot["marker"] == (
        "desktop-recovery-winner"
        if winner.source is Source.DESKTOP else "cloud-transition-winner"
    )


def test_r12_heartbeat_rpc_privileges_are_backend_only():
    assert DSN is not None
    with psycopg.connect(DSN, autocommit=True) as conn:
        signature = (
            "public.record_source_heartbeat(text,text,uuid,boolean,boolean,"
            "timestamp with time zone,timestamp with time zone,boolean,uuid)"
        )
        for role in ("anon", "authenticated"):
            assert conn.execute(
                "select has_function_privilege(%s,%s,'EXECUTE')",
                (role,signature),
            ).fetchone()[0] is False
        assert conn.execute(
            "select has_function_privilege('service_role',%s,'EXECUTE')",
            (signature,),
        ).fetchone()[0] is True


def test_r12_first_cloud_heartbeat_returns_current_server_computed_eligibility():
    """The policy must observe its own just-inserted heartbeat, not a stale SQL snapshot."""
    repo = _repo()
    _create_device(repo, "pecem-a")
    _legacy_snapshot(repo, "pecem-a")
    _bootstrap(repo)
    _seed_cloud_auth(repo)
    _age_authoritative_snapshot("pecem-a", 181)

    first = _source_heartbeat_rpc(
        "pecem-a", Source.CLOUD, CLOUD_A, candidate_at=_now(), ready=True
    )
    assert first[0] == "accepted"
    assert first[1] == "failover_granted"
    assert first[3] is None
    assert _source_decision_rpc("pecem-a", Source.CLOUD, CLOUD_A) == "failover_granted"


def test_r12_restart_new_repository_preserves_persisted_hysteresis_continuity():
    repo = _repo()
    _create_device(repo, "pecem-a")
    _legacy_snapshot(repo, "pecem-a")
    _bootstrap(repo)
    _seed_cloud_auth(repo)
    _age_authoritative_snapshot("pecem-a", 181)
    _source_heartbeat_rpc("pecem-a", Source.DESKTOP, BOOT_A)
    _source_heartbeat_rpc(
        "pecem-a", Source.CLOUD, CLOUD_A, candidate_at=_now(), ready=True
    )

    before = repo.get_source_authority("pecem-a")
    assert before is not None
    assert before.authoritative_snapshot_stale_since is not None
    assert _source_decision_rpc("pecem-a", Source.CLOUD, CLOUD_A) == "failover_granted"

    # New API process/repository instance: only DB state is consulted.
    restarted_repo = _repo()
    after = restarted_repo.get_source_authority("pecem-a")
    assert after is not None
    assert after.authoritative_snapshot_stale_since == before.authoritative_snapshot_stale_since
    assert after.authority_epoch == before.authority_epoch
    assert after.authority_lease_id == before.authority_lease_id
    assert _source_decision_rpc("pecem-a", Source.CLOUD, CLOUD_A) == "failover_granted"


# R12-F1 explicit PostgreSQL REDs: holder/candidate must coexist per instance.
CLOUD_B = UUID("dddddddd-dddd-4ddd-8ddd-dddddddddddd")


def _r12f1_heartbeat_rows(device: str, source: Source):
    assert DSN is not None
    with psycopg.connect(DSN, autocommit=True) as conn:
        return conn.execute(
            """select instance_id, last_heartbeat_at, healthy_since, consecutive_healthy
               from public.device_source_heartbeats
               where device_id=%s and source=%s order by instance_id""",
            (device, source.value),
        ).fetchall()


def _r12f1_set_snapshot_age(device: str, seconds: float):
    _age_authoritative_snapshot(device, seconds)


def test_r12f1_red_a_desktop_candidate_does_not_mask_holder_failover_liveness():
    repo = _repo()
    _create_device(repo, "pecem-a")
    _legacy_snapshot(repo, "pecem-a")
    grant = _bootstrap(repo).grant
    assert grant is not None
    _seed_cloud_auth(repo)
    _age_heartbeat("pecem-a", Source.DESKTOP, seconds=181)
    # Snapshot still fresh: must select heartbeat STALE path, not snapshot path.
    assert repo.get_source_authority("pecem-a").last_authoritative_snapshot_at > _now()-timedelta(seconds=120)
    _source_heartbeat_rpc("pecem-a", Source.DESKTOP, BOOT_B)
    desktop_rows = _r12f1_heartbeat_rows("pecem-a", Source.DESKTOP)
    assert {r[0] for r in desktop_rows} == {BOOT_A, BOOT_B}
    assert next(r for r in desktop_rows if r[0]==BOOT_A)[1] <= _now()-timedelta(seconds=180)
    assert repo.get_source_authority("pecem-a").holder_instance_id == BOOT_A
    result = _source_heartbeat_rpc("pecem-a", Source.CLOUD, CLOUD_A, candidate_at=_now(), ready=True)
    assert result[1] == "failover_granted"
    assert result[3] is None


def test_r12f1_red_b_desktop_gate_invalidates_then_reacquires_after_new_activity_window():
    repo = _repo()
    _create_device(repo, "pecem-a")
    _legacy_snapshot(repo, "pecem-a")
    original = _bootstrap(repo).grant
    assert original is not None
    _age_heartbeat("pecem-a", Source.DESKTOP, seconds=101)
    _r12f1_set_snapshot_age("pecem-a", 101)
    assert _source_heartbeat_rpc("pecem-a", Source.DESKTOP, BOOT_B)[1] == "desktop_reacquire_granted"
    recovered = repo.accept_current_grant_snapshot(
        PublishUnderCurrentGrant(
            candidate=_candidate("pecem-a", Source.DESKTOP, BOOT_A, sequence=2, marker="holder-return"),
            authority_epoch=original.authority_epoch, authority_lease_id=original.authority_lease_id,
            holder_instance_id=BOOT_A,
        )
    )
    assert recovered.status is AuthorityStatus.ACCEPTED
    assert _source_heartbeat_rpc("pecem-a", Source.DESKTOP, BOOT_B)[1] == "authority_fenced"
    assert {r[0] for r in _r12f1_heartbeat_rows("pecem-a", Source.DESKTOP)} == {BOOT_A, BOOT_B}
    # Server-side deterministic time travel, no sleeps: recent snapshot activity blocks.
    _r12f1_set_snapshot_age("pecem-a", 89)
    assert _source_decision_rpc("pecem-a", Source.DESKTOP, BOOT_B) == "authority_fenced"
    _r12f1_set_snapshot_age("pecem-a", 91)
    assert _source_heartbeat_rpc("pecem-a", Source.DESKTOP, BOOT_B)[1] == "desktop_reacquire_granted"
    won = repo.accept_transition_candidate(
        TransitionCandidate(candidate=_candidate("pecem-a", Source.DESKTOP, BOOT_B, sequence=3, marker="desktop-reacquire"))
    )
    assert won.status is AuthorityStatus.ACCEPTED and won.grant is not None
    assert won.grant.authority_epoch == original.authority_epoch + 1
    assert won.grant.authority_lease_id != original.authority_lease_id
    assert repo.get_source_authority("pecem-a").holder_instance_id == BOOT_B
    old = repo.accept_current_grant_snapshot(
        PublishUnderCurrentGrant(
            candidate=_candidate("pecem-a", Source.DESKTOP, BOOT_A, sequence=4, marker="fenced-old"),
            authority_epoch=original.authority_epoch, authority_lease_id=original.authority_lease_id,
            holder_instance_id=BOOT_A,
        )
    )
    assert old.status is AuthorityStatus.FENCED


def test_r12f1_red_b_cloud_gate_invalidates_then_reacquires_after_new_activity_window():
    repo = _repo()
    _create_device(repo, "pecem-a")
    _legacy_snapshot(repo, "pecem-a")
    _bootstrap(repo)
    _seed_cloud_auth(repo)
    original = _transition_cloud(repo).grant
    assert original is not None
    _age_heartbeat("pecem-a", Source.CLOUD, seconds=71)
    _r12f1_set_snapshot_age("pecem-a", 71)
    assert _source_heartbeat_rpc(
        "pecem-a", Source.CLOUD, CLOUD_B, candidate_at=_now(), ready=True
    )[1] == "cloud_reacquire_granted"
    recovered = repo.accept_current_grant_snapshot(
        PublishUnderCurrentGrant(
            candidate=_candidate("pecem-a", Source.CLOUD, CLOUD_A, sequence=2, marker="cloud-old-return"),
            authority_epoch=original.authority_epoch, authority_lease_id=original.authority_lease_id,
            holder_instance_id=CLOUD_A,
        )
    )
    assert recovered.status is AuthorityStatus.ACCEPTED
    assert _source_heartbeat_rpc(
        "pecem-a", Source.CLOUD, CLOUD_B, candidate_at=_now(), ready=True
    )[1] == "authority_fenced"
    assert {r[0] for r in _r12f1_heartbeat_rows("pecem-a", Source.CLOUD)} == {CLOUD_A, CLOUD_B}
    _r12f1_set_snapshot_age("pecem-a", 59)
    assert _source_decision_rpc("pecem-a", Source.CLOUD, CLOUD_B) == "authority_fenced"
    _r12f1_set_snapshot_age("pecem-a", 61)
    assert _source_heartbeat_rpc(
        "pecem-a", Source.CLOUD, CLOUD_B, candidate_at=_now(), ready=True
    )[1] == "cloud_reacquire_granted"
    won = repo.accept_transition_candidate(
        TransitionCandidate(candidate=_candidate("pecem-a", Source.CLOUD, CLOUD_B, sequence=3, marker="cloud-new"))
    )
    assert won.status is AuthorityStatus.ACCEPTED and won.grant is not None
    assert won.grant.authority_epoch == original.authority_epoch + 1
    assert won.grant.authority_lease_id != original.authority_lease_id
    old = repo.accept_current_grant_snapshot(
        PublishUnderCurrentGrant(
            candidate=_candidate("pecem-a", Source.CLOUD, CLOUD_A, sequence=4, marker="cloud-fenced"),
            authority_epoch=original.authority_epoch, authority_lease_id=original.authority_lease_id,
            holder_instance_id=CLOUD_A,
        )
    )
    assert old.status is AuthorityStatus.FENCED


# R12-F1 §28.4: additional fail-closed, bootstrap, restart and concurrency proof.
BOOT_C = UUID("eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee")


def _r12f1_desktop_stale_holder_and_candidates(repo, *, age=101, candidates=(BOOT_B,)):
    _age_heartbeat("pecem-a", Source.DESKTOP, seconds=age, instance_id=BOOT_A)
    _age_authoritative_snapshot("pecem-a", age)
    for candidate in candidates:
        hb = _source_heartbeat_rpc("pecem-a", Source.DESKTOP, candidate)
        assert hb[0] == "accepted"
        assert hb[3] is None
        assert hb[1] == "desktop_reacquire_granted"


def test_r12f1_cloud_standby_unhealthy_blocks_failover_despite_preserved_holder_age():
    repo=_repo()
    _create_device(repo,"pecem-a")
    _legacy_snapshot(repo,"pecem-a")
    _bootstrap(repo)
    _seed_cloud_auth(repo)
    _age_heartbeat("pecem-a",Source.DESKTOP,seconds=181,instance_id=BOOT_A)
    _source_heartbeat_rpc("pecem-a",Source.DESKTOP,BOOT_B)
    blocked=_source_heartbeat_rpc(
        "pecem-a",Source.CLOUD,CLOUD_A,candidate_at=_now(),ready=False,
    )
    assert blocked[3] is None
    assert blocked[1] == "cloud_persistent_state_unavailable"
    assert _source_decision_rpc("pecem-a",Source.CLOUD,CLOUD_A) == "cloud_persistent_state_unavailable"
    assert {x[0] for x in _r12f1_heartbeat_rows("pecem-a",Source.DESKTOP)} == {BOOT_A,BOOT_B}
    assert repo.get_source_authority("pecem-a").active_source is Source.DESKTOP


def test_r12f1_same_source_old_holder_heartbeat_invalidates_candidate_gate():
    repo=_repo()
    _create_device(repo,"pecem-a")
    _legacy_snapshot(repo,"pecem-a")
    original=_bootstrap(repo).grant
    assert original is not None
    _r12f1_desktop_stale_holder_and_candidates(repo)
    _source_heartbeat_rpc("pecem-a",Source.DESKTOP,BOOT_A)
    assert _source_decision_rpc("pecem-a",Source.DESKTOP,BOOT_B) == "authority_fenced"
    attempted=repo.accept_transition_candidate(
        TransitionCandidate(candidate=_candidate(
            "pecem-a",Source.DESKTOP,BOOT_B,sequence=2,marker="fenced-after-holder-hb"
        ))
    )
    assert attempted.status is AuthorityStatus.INELIGIBLE
    auth=repo.get_source_authority("pecem-a")
    assert auth is not None
    assert auth.authority_epoch == original.authority_epoch
    assert auth.holder_instance_id == BOOT_A
    assert {x[0] for x in _r12f1_heartbeat_rows("pecem-a",Source.DESKTOP)} == {BOOT_A,BOOT_B}


def test_r12f1_missing_holder_record_is_fail_closed_for_reacquisition():
    repo=_repo()
    _create_device(repo,"pecem-a")
    _legacy_snapshot(repo,"pecem-a")
    grant=_bootstrap(repo).grant
    assert grant is not None and DSN is not None
    with psycopg.connect(DSN,autocommit=True) as conn:
        conn.execute("""
            delete from public.device_source_heartbeats
            where device_id='pecem-a' and source='desktop' and instance_id=%s
        """,(BOOT_A,))
    hb=_source_heartbeat_rpc("pecem-a",Source.DESKTOP,BOOT_B)
    assert hb[1] == "authority_fenced"
    candidate=repo.accept_transition_candidate(
        TransitionCandidate(candidate=_candidate(
            "pecem-a",Source.DESKTOP,BOOT_B,sequence=2,marker="missing-holder"
        ))
    )
    assert candidate.status is AuthorityStatus.INELIGIBLE
    assert candidate.grant is None
    assert repo.get_source_authority("pecem-a").authority_epoch == grant.authority_epoch


def test_r12f1_legacy_bootstrap_uses_exact_boot_id_not_newer_candidate():
    repo=_repo()
    _create_device(repo,"pecem-a")
    _legacy_snapshot(repo,"pecem-a",boot_id=BOOT_A)
    _heartbeat("pecem-a",Source.DESKTOP,BOOT_A,reason=AuthorityReasonCode.DESKTOP_HEALTHY)
    _heartbeat("pecem-a",Source.DESKTOP,BOOT_B,reason=AuthorityReasonCode.DESKTOP_HEALTHY)
    assert {x[0] for x in _r12f1_heartbeat_rows("pecem-a",Source.DESKTOP)} == {BOOT_A,BOOT_B}
    boot=repo.bootstrap_managed_source_authority("pecem-a")
    assert boot.status is AuthorityStatus.ACCEPTED
    assert boot.grant is not None and boot.grant.holder_instance_id == BOOT_A
    assert repo.get_source_authority("pecem-a").authority_epoch == 1


def test_r12f1_legacy_bootstrap_missing_original_boot_cannot_use_newer_heartbeat():
    repo=_repo()
    _create_device(repo,"pecem-a")
    _legacy_snapshot(repo,"pecem-a",boot_id=BOOT_A)
    _heartbeat("pecem-a",Source.DESKTOP,BOOT_B,reason=AuthorityReasonCode.DESKTOP_HEALTHY)
    boot=repo.bootstrap_managed_source_authority("pecem-a")
    assert boot.status is AuthorityStatus.INELIGIBLE
    assert boot.reason_code is AuthorityReasonCode.BOOTSTRAP_NOT_ELIGIBLE
    assert repo.get_source_authority("pecem-a").authority_epoch == 0


def test_r12f1_two_candidates_concurrent_one_winner_and_rows_persist():
    repo=_repo()
    _create_device(repo,"pecem-a")
    _legacy_snapshot(repo,"pecem-a")
    original=_bootstrap(repo).grant
    assert original is not None
    _r12f1_desktop_stale_holder_and_candidates(repo,candidates=(BOOT_B,BOOT_C))
    with ThreadPoolExecutor(max_workers=2) as pool:
        one=pool.submit(repo.accept_transition_candidate,TransitionCandidate(
            candidate=_candidate("pecem-a",Source.DESKTOP,BOOT_B,sequence=2,marker="winner-b")
        ))
        two=pool.submit(repo.accept_transition_candidate,TransitionCandidate(
            candidate=_candidate("pecem-a",Source.DESKTOP,BOOT_C,sequence=2,marker="winner-c")
        ))
        results=[one.result(timeout=10),two.result(timeout=10)]
    assert sum(x.status is AuthorityStatus.ACCEPTED for x in results) == 1
    assert sum(x.status is AuthorityStatus.INELIGIBLE for x in results) == 1
    authority=repo.get_source_authority("pecem-a")
    assert authority is not None and authority.authority_epoch == original.authority_epoch+1
    assert authority.holder_instance_id in {BOOT_B,BOOT_C}
    assert {x[0] for x in _r12f1_heartbeat_rows("pecem-a",Source.DESKTOP)} == {BOOT_A,BOOT_B,BOOT_C}
    assert repo.get_snapshot("pecem-a").snapshot["marker"] in {"winner-b","winner-c"}


def test_r12f1_old_holder_recovery_races_same_source_transition_without_split_brain():
    repo=_repo()
    _create_device(repo,"pecem-a")
    _legacy_snapshot(repo,"pecem-a")
    original=_bootstrap(repo).grant
    assert original is not None
    _r12f1_desktop_stale_holder_and_candidates(repo)
    recovering=PublishUnderCurrentGrant(
        candidate=_candidate("pecem-a",Source.DESKTOP,BOOT_A,sequence=2,marker="A-recovery"),
        authority_epoch=original.authority_epoch,
        authority_lease_id=original.authority_lease_id,
        holder_instance_id=BOOT_A,
    )
    takeover=TransitionCandidate(candidate=_candidate(
        "pecem-a",Source.DESKTOP,BOOT_B,sequence=2,marker="B-takeover"
    ))
    with ThreadPoolExecutor(max_workers=2) as pool:
        one=pool.submit(repo.accept_current_grant_snapshot,recovering)
        two=pool.submit(repo.accept_transition_candidate,takeover)
        results=[one.result(timeout=10),two.result(timeout=10)]
    assert sum(x.status is AuthorityStatus.ACCEPTED for x in results) == 1
    authority=repo.get_source_authority("pecem-a")
    assert authority is not None
    snapshot=repo.get_snapshot("pecem-a")
    assert snapshot is not None
    if authority.holder_instance_id == BOOT_A:
        assert authority.authority_epoch == original.authority_epoch
        assert snapshot.snapshot["marker"]=="A-recovery"
    else:
        assert authority.holder_instance_id == BOOT_B
        assert authority.authority_epoch == original.authority_epoch+1
        assert snapshot.snapshot["marker"]=="B-takeover"


def test_r12f1_api_restart_preserves_same_source_holder_and_candidate_liveness():
    repo=_repo()
    _create_device(repo,"pecem-a")
    _legacy_snapshot(repo,"pecem-a")
    original=_bootstrap(repo).grant
    assert original is not None
    _r12f1_desktop_stale_holder_and_candidates(repo)
    before=_r12f1_heartbeat_rows("pecem-a",Source.DESKTOP)
    # A new process obtains a repository with no shared Python state.
    new_repo=_repo()
    assert _r12f1_heartbeat_rows("pecem-a",Source.DESKTOP)==before
    assert _source_decision_rpc("pecem-a",Source.DESKTOP,BOOT_B)=="desktop_reacquire_granted"
    assert new_repo.get_source_authority("pecem-a").holder_instance_id==BOOT_A
    assert new_repo.get_source_heartbeat("pecem-a",Source.DESKTOP,BOOT_A).instance_id==BOOT_A
    assert new_repo.get_source_heartbeat("pecem-a",Source.DESKTOP,BOOT_B).instance_id==BOOT_B


def test_r12f1_schema_has_instance_composite_pk_and_no_global_source_lookup():
    assert DSN is not None
    with psycopg.connect(DSN,autocommit=True) as conn:
        columns=conn.execute("""
            select att.attname from pg_constraint c
            join pg_attribute att on att.attrelid=c.conrelid and att.attnum=any(c.conkey)
            where c.conrelid='public.device_source_heartbeats'::regclass and c.contype='p'
            order by array_position(c.conkey,att.attnum)
        """).fetchall()
    assert [c[0] for c in columns] == ["device_id","source","instance_id"]


def test_r12f1_candidate_reason_update_never_mutates_holder_row():
    repo=_repo()
    _create_device(repo,"pecem-a")
    _legacy_snapshot(repo,"pecem-a")
    _bootstrap(repo)
    assert DSN is not None
    with psycopg.connect(DSN,autocommit=True) as conn:
        holder_before=conn.execute("""
            select last_heartbeat_at, healthy_since, consecutive_healthy,
                   last_reason_code, updated_at
            from public.device_source_heartbeats
            where device_id='pecem-a' and source='desktop' and instance_id=%s
        """,(BOOT_A,)).fetchone()
    candidate=_source_heartbeat_rpc("pecem-a",Source.DESKTOP,BOOT_B)
    assert candidate[1] == "authority_fenced"
    with psycopg.connect(DSN,autocommit=True) as conn:
        holder_after=conn.execute("""
            select last_heartbeat_at, healthy_since, consecutive_healthy,
                   last_reason_code, updated_at
            from public.device_source_heartbeats
            where device_id='pecem-a' and source='desktop' and instance_id=%s
        """,(BOOT_A,)).fetchone()
    assert holder_after == holder_before
