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
            on conflict (device_id, source) do update
            set instance_id = excluded.instance_id,
                last_heartbeat_at = clock_timestamp(),
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


def _transition_cloud(
    repo: PostgresDeviceRepository,
    *,
    sequence: int = 1,
    marker: str = "cloud",
):
    _heartbeat(
        "pecem-a",
        Source.CLOUD,
        CLOUD_A,
        reason=AuthorityReasonCode.FAILOVER_GRANTED,
        persistent_state_ready=True,
    )
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

    _heartbeat(
        "pecem-a",
        Source.DESKTOP,
        BOOT_A,
        reason=AuthorityReasonCode.FAILBACK_GRANTED,
    )
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
    _heartbeat(
        "pecem-a",
        Source.CLOUD,
        CLOUD_A,
        reason=AuthorityReasonCode.FAILOVER_GRANTED,
        persistent_state_ready=True,
    )

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
    _heartbeat(
        "pecem-a",
        Source.CLOUD,
        CLOUD_A,
        reason=AuthorityReasonCode.FAILOVER_GRANTED,
        persistent_state_ready=True,
    )
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
    _heartbeat(
        "pecem-a",
        Source.CLOUD,
        CLOUD_A,
        reason=AuthorityReasonCode.FAILOVER_GRANTED,
        persistent_state_ready=True,
    )

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

    _heartbeat(
        "pecem-a",
        Source.DESKTOP,
        BOOT_A,
        reason=AuthorityReasonCode.FAILBACK_GRANTED,
    )
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
    _heartbeat(
        "pecem-a",
        Source.CLOUD,
        CLOUD_A,
        reason=AuthorityReasonCode.CLOUD_STANDBY_STALE,
        persistent_state_ready=True,
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
    _set_authority_expiry("pecem-a", _now() - timedelta(seconds=1))
    _heartbeat(
        "pecem-a",
        Source.CLOUD,
        CLOUD_A,
        reason=AuthorityReasonCode.FAILOVER_GRANTED,
        persistent_state_ready=True,
    )

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
    _heartbeat(
        "pecem-a",
        Source.CLOUD,
        CLOUD_A,
        reason=AuthorityReasonCode.FAILOVER_GRANTED,
        persistent_state_ready=True,
    )

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
