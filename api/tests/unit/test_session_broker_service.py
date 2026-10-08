from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
from uuid import UUID

import pytest

from app.core.errors import ApiError, PersistenceUnavailableApiError
from app.models.session_broker import (
    ProviderScopeRequest,
    SessionCookieIn,
    SessionLeasePublishRequest,
    SessionPublisherRequest,
)
from app.repositories.cloud_bindings import WebPilotAuthRealmRecord
from app.repositories.devices import DeviceAuthRecord
from app.repositories.memory import MemoryDeviceRepository
from app.repositories.session_broker import ProviderScopeProfile, ScopeStatus
from app.security.credentials import hash_secret
from app.security.session_crypto import SessionCryptoKeyring
from app.services.session_broker_service import SessionBrokerService


NOW = datetime(2026, 10, 8, 12, 0, tzinfo=timezone.utc)
PUB = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
DEVICE_SECRET = "desktop-secret"
CLOUD_CREDENTIAL = "C" * 43


def _repo() -> MemoryDeviceRepository:
    repo = MemoryDeviceRepository(clock=lambda: NOW)
    repo.put_device(DeviceAuthRecord("pecem-01", hash_secret(DEVICE_SECRET), enabled=True))
    repo.put_webpilot_auth_realm(
        WebPilotAuthRealmRecord(
            realm_id="webpilot-pecem",
            active=True,
            created_at=NOW,
            updated_at=NOW,
        )
    )
    repo.authorize_realm_device("webpilot-pecem", "pecem-01")
    return repo


def _service(repo: MemoryDeviceRepository) -> SessionBrokerService:
    return SessionBrokerService(
        repo,
        crypto=SessionCryptoKeyring(keys={1: b"K" * 32}, active_key_version=1),
        fingerprint_key=b"F" * 32,
        clock=lambda: NOW,
    )


def _scope() -> ProviderScopeRequest:
    return ProviderScopeRequest(
        scope_id="pecem-standard",
        schema_version=1,
        capabilities=("maneuvers", "weather"),
    )


def test_service_encrypts_at_rest_and_consumes_only_through_binding():
    repo = _repo()
    service = _service(repo)
    repo.set_required_provider_scope(
        "webpilot-pecem",
        ProviderScopeProfile(
            "pecem-standard",
            1,
            ("maneuvers", "weather"),
        ),
    )
    publisher = service.ensure_publisher(
        "pecem-01",
        SessionPublisherRequest(
            realm_id="webpilot-pecem",
            publisher_id=PUB,
            provider_scope=_scope(),
        ),
    )
    assert publisher.scope_status == ScopeStatus.UNVERIFIED.value
    repo.verify_session_publisher_scope(PUB)

    accepted = service.publish(
        "pecem-01",
        SessionLeasePublishRequest(
            realm_id="webpilot-pecem",
            publisher_id=PUB,
            local_generation=1,
            expires_at=None,
            cookies=(
                SessionCookieIn(name="session", value="top-secret-cookie", expiry=None),
            ),
        ),
    )
    stored = repo.get_session_lease(accepted.lease_id)
    assert stored is not None
    assert "top-secret-cookie" not in stored.ciphertext
    assert "top-secret-cookie" not in repr(stored)

    binding = repo.ensure_cloud_binding(
        "pecem-01",
        "webpilot-pecem",
        hash_secret(CLOUD_CREDENTIAL),
    )
    assert binding is not None
    consumed = service.consume(
        binding.cloud_binding_id,
        CLOUD_CREDENTIAL,
    )
    assert consumed.realm_epoch == accepted.realm_epoch
    assert consumed.cookies[0].name == "session"
    assert consumed.cookies[0].value == "top-secret-cookie"


def test_service_invalidate_removes_lease_from_selection():
    repo = _repo()
    service = _service(repo)
    repo.set_required_provider_scope(
        "webpilot-pecem",
        ProviderScopeProfile(
            "pecem-standard",
            1,
            ("maneuvers", "weather"),
        ),
    )
    service.ensure_publisher(
        "pecem-01",
        SessionPublisherRequest(
            realm_id="webpilot-pecem",
            publisher_id=PUB,
            provider_scope=_scope(),
        ),
    )
    repo.verify_session_publisher_scope(PUB)
    accepted = service.publish(
        "pecem-01",
        SessionLeasePublishRequest(
            realm_id="webpilot-pecem",
            publisher_id=PUB,
            local_generation=1,
            expires_at=None,
            cookies=(SessionCookieIn(name="session", value="secret", expiry=None),),
        ),
    )
    binding = repo.ensure_cloud_binding(
        "pecem-01",
        "webpilot-pecem",
        hash_secret(CLOUD_CREDENTIAL),
    )
    assert binding is not None

    invalidated = service.invalidate(
        binding.cloud_binding_id,
        CLOUD_CREDENTIAL,
        accepted.lease_id,
        accepted.realm_epoch,
    )
    assert invalidated.status == "invalidated"
    with pytest.raises(Exception) as exc:
        service.consume(binding.cloud_binding_id, CLOUD_CREDENTIAL)
    assert "secret" not in str(exc.value)


def test_service_schema_version_tamper_fails_closed():
    repo = _repo()
    service = _service(repo)
    repo.set_required_provider_scope(
        "webpilot-pecem",
        ProviderScopeProfile(
            "pecem-standard",
            1,
            ("maneuvers", "weather"),
        ),
    )
    service.ensure_publisher(
        "pecem-01",
        SessionPublisherRequest(
            realm_id="webpilot-pecem",
            publisher_id=PUB,
            provider_scope=_scope(),
        ),
    )
    repo.verify_session_publisher_scope(PUB)
    accepted = service.publish(
        "pecem-01",
        SessionLeasePublishRequest(
            realm_id="webpilot-pecem",
            publisher_id=PUB,
            local_generation=1,
            expires_at=None,
            cookies=(
                SessionCookieIn(
                    name="session",
                    value="schema-bound-secret",
                    expiry=None,
                ),
            ),
        ),
    )
    binding = repo.ensure_cloud_binding(
        "pecem-01",
        "webpilot-pecem",
        hash_secret(CLOUD_CREDENTIAL),
    )
    assert binding is not None

    stored = repo.get_session_lease(accepted.lease_id)
    assert stored is not None
    repo._session_leases[accepted.lease_id] = replace(
        stored,
        payload_schema_version=99,
    )

    with pytest.raises(PersistenceUnavailableApiError) as exc:
        service.consume(binding.cloud_binding_id, CLOUD_CREDENTIAL)
    assert "schema-bound-secret" not in str(exc.value)


def test_service_oversize_payload_stops_before_fingerprint_encrypt_persistence(
    monkeypatch,
):
    repo = _repo()
    repo.set_required_provider_scope(
        "webpilot-pecem",
        ProviderScopeProfile(
            "pecem-standard",
            1,
            ("maneuvers", "weather"),
        ),
    )
    service = _service(repo)
    service.ensure_publisher(
        "pecem-01",
        SessionPublisherRequest(
            realm_id="webpilot-pecem",
            publisher_id=PUB,
            provider_scope=_scope(),
        ),
    )
    repo.verify_session_publisher_scope(PUB)

    fingerprint_calls = 0

    def forbidden_fingerprint(_payload: bytes, _key: bytes) -> str:
        nonlocal fingerprint_calls
        fingerprint_calls += 1
        raise AssertionError("fingerprint não deveria ser chamado")

    monkeypatch.setattr(
        "app.services.session_broker_service.session_payload_fingerprint",
        forbidden_fingerprint,
    )

    marker = "oversize-service-secret"
    request = SessionLeasePublishRequest(
        realm_id="webpilot-pecem",
        publisher_id=PUB,
        local_generation=1,
        expires_at=None,
        cookies=tuple(
            SessionCookieIn(
                name=f"cookie-{index:02d}",
                value=marker + ("x" * (4096 - len(marker))),
                expiry=None,
            )
            for index in range(64)
        ),
    )

    with pytest.raises(ApiError) as exc:
        service.publish("pecem-01", request)

    assert exc.value.status_code == 422
    assert exc.value.code == "session_lease_payload_too_large"
    assert marker not in str(exc.value)
    assert fingerprint_calls == 0
    assert repo.get_current_session_lease("webpilot-pecem", now=NOW) is None
