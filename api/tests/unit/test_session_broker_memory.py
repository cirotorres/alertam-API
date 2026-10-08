from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID

import pytest

from app.repositories.devices import DeviceAuthRecord
from app.repositories.memory import MemoryDeviceRepository
from app.repositories.session_broker import (
    ProviderScopeProfile,
    ScopeStatus,
    SessionLeaseGenerationConflictError,
    SessionLeaseReplayError,
    SessionLeaseStatus,
    SessionPublisherConflictError,
)


NOW = datetime(2026, 10, 8, 12, 0, tzinfo=timezone.utc)
PUB_A = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
PUB_B = UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
LEASE_A = UUID("11111111-1111-1111-1111-111111111111")
LEASE_B = UUID("22222222-2222-2222-2222-222222222222")


def _repo() -> MemoryDeviceRepository:
    repo = MemoryDeviceRepository(clock=lambda: NOW)
    for device in ("pecem-a", "pecem-b"):
        repo.put_device(DeviceAuthRecord(device, "hash", enabled=True))
    repo.ensure_webpilot_auth_realm("webpilot-pecem")
    repo.authorize_realm_device("webpilot-pecem", "pecem-a")
    repo.authorize_realm_device("webpilot-pecem", "pecem-b")
    repo.set_required_provider_scope(
        "webpilot-pecem",
        ProviderScopeProfile(
            scope_id="pecem-standard",
            schema_version=1,
            capabilities=("maneuvers", "weather"),
        ),
    )
    return repo


def _publisher(repo, publisher_id, device_id):
    publisher = repo.ensure_session_publisher(
        device_id=device_id,
        realm_id="webpilot-pecem",
        publisher_id=publisher_id,
        provider_scope=ProviderScopeProfile(
            scope_id="pecem-standard",
            schema_version=1,
            capabilities=("weather", "maneuvers"),
        ),
    )
    assert publisher is not None
    assert publisher.scope_status is ScopeStatus.UNVERIFIED
    verified = repo.verify_session_publisher_scope(publisher_id)
    assert verified is not None
    assert verified.scope_status is ScopeStatus.VERIFIED
    return verified


def test_publisher_scope_must_be_verified_and_reclassifies_on_requirement_change():
    repo = _repo()
    publisher = repo.ensure_session_publisher(
        device_id="pecem-a",
        realm_id="webpilot-pecem",
        publisher_id=PUB_A,
        provider_scope=ProviderScopeProfile(
            scope_id="other",
            schema_version=1,
            capabilities=("maneuvers",),
        ),
    )
    assert publisher is not None
    assert publisher.scope_status is ScopeStatus.UNVERIFIED

    classified = repo.verify_session_publisher_scope(PUB_A)
    assert classified is not None
    assert classified.scope_status is ScopeStatus.INCOMPATIBLE

    repo.set_required_provider_scope(
        "webpilot-pecem",
        ProviderScopeProfile(
            scope_id="other",
            schema_version=1,
            capabilities=("maneuvers",),
        ),
    )
    classified = repo.verify_session_publisher_scope(PUB_A)
    assert classified is not None
    assert classified.scope_status is ScopeStatus.VERIFIED


def test_same_generation_same_fingerprint_is_idempotent_and_mismatch_conflicts():
    repo = _repo()
    _publisher(repo, PUB_A, "pecem-a")

    first = repo.accept_session_lease_atomic(
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
        expires_at=NOW + timedelta(hours=1),
    )
    retry = repo.accept_session_lease_atomic(
        device_id="pecem-a",
        realm_id="webpilot-pecem",
        publisher_id=PUB_A,
        lease_id=LEASE_B,
        local_generation=1,
        payload_fingerprint="a" * 64,
        ciphertext="different-random-cipher",
        nonce="different-nonce",
        key_version=1,
        payload_schema_version=1,
        expires_at=NOW + timedelta(hours=1),
    )
    assert retry == first
    assert first.realm_epoch == 1

    with pytest.raises(SessionLeaseGenerationConflictError):
        repo.accept_session_lease_atomic(
            device_id="pecem-a",
            realm_id="webpilot-pecem",
            publisher_id=PUB_A,
            lease_id=LEASE_B,
            local_generation=1,
            payload_fingerprint="b" * 64,
            ciphertext="cipher-b",
            nonce="nonce-b",
            key_version=1,
            payload_schema_version=1,
            expires_at=NOW + timedelta(hours=1),
        )

    assert repo.get_session_lease(LEASE_A) == first
    assert repo.get_session_lease(LEASE_B) is None


def test_epoch_orders_different_publishers_but_generation_is_local():
    repo = _repo()
    _publisher(repo, PUB_A, "pecem-a")
    _publisher(repo, PUB_B, "pecem-b")

    a = repo.accept_session_lease_atomic(
        device_id="pecem-a",
        realm_id="webpilot-pecem",
        publisher_id=PUB_A,
        lease_id=LEASE_A,
        local_generation=37,
        payload_fingerprint="a" * 64,
        ciphertext="a",
        nonce="a",
        key_version=1,
        payload_schema_version=1,
        expires_at=None,
    )
    b = repo.accept_session_lease_atomic(
        device_id="pecem-b",
        realm_id="webpilot-pecem",
        publisher_id=PUB_B,
        lease_id=LEASE_B,
        local_generation=1,
        payload_fingerprint="b" * 64,
        ciphertext="b",
        nonce="b",
        key_version=1,
        payload_schema_version=1,
        expires_at=None,
    )
    assert a.realm_epoch == 1
    assert b.realm_epoch == 2
    assert repo.get_current_session_lease("webpilot-pecem", now=NOW) == b


def test_replay_and_revoked_generation_are_fail_closed():
    repo = _repo()
    _publisher(repo, PUB_A, "pecem-a")

    accepted = repo.accept_session_lease_atomic(
        device_id="pecem-a",
        realm_id="webpilot-pecem",
        publisher_id=PUB_A,
        lease_id=LEASE_A,
        local_generation=2,
        payload_fingerprint="a" * 64,
        ciphertext="a",
        nonce="a",
        key_version=1,
        payload_schema_version=1,
        expires_at=None,
    )
    with pytest.raises(SessionLeaseReplayError):
        repo.accept_session_lease_atomic(
            device_id="pecem-a",
            realm_id="webpilot-pecem",
            publisher_id=PUB_A,
            lease_id=LEASE_B,
            local_generation=1,
            payload_fingerprint="b" * 64,
            ciphertext="b",
            nonce="b",
            key_version=1,
            payload_schema_version=1,
            expires_at=None,
        )

    revoked = repo.revoke_session_lease(
        device_id="pecem-a",
        realm_id="webpilot-pecem",
        lease_id=accepted.lease_id,
    )
    assert revoked is not None
    assert revoked.status is SessionLeaseStatus.REVOKED

    with pytest.raises(SessionLeaseReplayError):
        repo.accept_session_lease_atomic(
            device_id="pecem-a",
            realm_id="webpilot-pecem",
            publisher_id=PUB_A,
            lease_id=LEASE_B,
            local_generation=2,
            payload_fingerprint="a" * 64,
            ciphertext="x",
            nonce="x",
            key_version=1,
            payload_schema_version=1,
            expires_at=None,
        )


def test_memory_reusing_revoked_publisher_id_is_conflict():
    repo = _repo()
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


def test_memory_publisher_id_owner_or_realm_collision_is_conflict():
    repo = _repo()
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

    repo.ensure_webpilot_auth_realm("webpilot-other")
    repo.authorize_realm_device("webpilot-other", "pecem-a")
    repo.set_required_provider_scope("webpilot-other", profile)

    with pytest.raises(SessionPublisherConflictError):
        repo.ensure_session_publisher(
            device_id="pecem-a",
            realm_id="webpilot-other",
            publisher_id=PUB_A,
            provider_scope=profile,
        )
