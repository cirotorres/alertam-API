from __future__ import annotations

from datetime import datetime, timezone
import json
from typing import Callable
from uuid import UUID, uuid4

from app.core.errors import (
    CloudRealmUnauthorizedError,
    PersistenceUnavailableApiError,
    SessionLeaseNotAvailableError,
    SessionLeasePayloadTooLargeApiError,
)
from app.models.session_broker import (
    AcceptedSessionLeaseMetadata,
    ProviderScopeRequest,
    SessionCookieOut,
    SessionLeaseConsumeResponse,
    SessionLeasePublishRequest,
    SessionPublisherRequest,
    SessionPublisherResponse,
)
from app.repositories.cloud_bindings import CloudBindingsRepository
from app.repositories.devices import PersistenceUnavailableError
from app.repositories.session_broker import (
    EncryptedSessionLeaseRecord,
    ProviderScopeProfile,
    SessionBrokerRepository,
    SessionLeaseStatus,
    SessionPublisherRecord,
)
from app.security.session_crypto import (
    EncryptedSessionPayload,
    SessionCryptoError,
    SessionCryptoKeyring,
    SessionPayloadTooLargeError,
    canonical_session_payload,
    session_payload_fingerprint,
)
from app.services.cloud_binding_service import CloudBindingService


SESSION_PAYLOAD_SCHEMA_VERSION = 1


class SessionBrokerService:
    def __init__(
        self,
        repository: SessionBrokerRepository & CloudBindingsRepository,
        *,
        crypto: SessionCryptoKeyring | None,
        fingerprint_key: bytes | None,
        clock: Callable[[], datetime] | None = None,
        lease_id_factory: Callable[[], UUID] = uuid4,
    ) -> None:
        self._repository = repository
        self._crypto = crypto
        self._fingerprint_key = fingerprint_key
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._lease_id_factory = lease_id_factory
        self._binding_service = CloudBindingService(repository)

    @staticmethod
    def _profile(value: ProviderScopeRequest) -> ProviderScopeProfile:
        return ProviderScopeProfile(
            scope_id=value.scope_id,
            schema_version=value.schema_version,
            capabilities=tuple(value.capabilities),
        )

    @staticmethod
    def _publisher_response(record: SessionPublisherRecord) -> SessionPublisherResponse:
        return SessionPublisherResponse(
            publisher_id=record.publisher_id,
            realm_id=record.realm_id,
            device_id=record.device_id,
            provider_scope=ProviderScopeRequest(
                scope_id=record.provider_scope.scope_id,
                schema_version=record.provider_scope.schema_version,
                capabilities=record.provider_scope.capabilities,
            ),
            scope_status=record.scope_status.value,
            last_generation=record.last_generation,
            status=record.status.value,
        )

    @staticmethod
    def _lease_metadata(
        record: EncryptedSessionLeaseRecord,
    ) -> AcceptedSessionLeaseMetadata:
        return AcceptedSessionLeaseMetadata(
            lease_id=record.lease_id,
            realm_id=record.realm_id,
            publisher_id=record.publisher_id,
            local_generation=record.local_generation,
            realm_epoch=record.realm_epoch,
            received_at=record.received_at,
            expires_at=record.expires_at,
            status=record.status.value,
        )

    def ensure_publisher(
        self,
        device_id: str,
        request: SessionPublisherRequest,
    ) -> SessionPublisherResponse:
        try:
            record = self._repository.ensure_session_publisher(
                device_id=device_id,
                realm_id=request.realm_id,
                publisher_id=request.publisher_id,
                provider_scope=self._profile(request.provider_scope),
            )
        except PersistenceUnavailableError as exc:
            raise PersistenceUnavailableApiError() from exc
        if record is None:
            raise CloudRealmUnauthorizedError()
        return self._publisher_response(record)

    def revoke_publisher(
        self,
        device_id: str,
        realm_id: str,
        publisher_id: UUID,
    ) -> SessionPublisherResponse:
        try:
            current = self._repository.get_session_publisher(publisher_id)
            if (
                current is None
                or current.device_id != device_id
                or current.realm_id != realm_id
            ):
                raise CloudRealmUnauthorizedError()
            record = self._repository.revoke_session_publisher(publisher_id)
        except PersistenceUnavailableError as exc:
            raise PersistenceUnavailableApiError() from exc
        if record is None:
            raise CloudRealmUnauthorizedError()
        return self._publisher_response(record)

    def _require_crypto(self) -> tuple[SessionCryptoKeyring, bytes]:
        if (
            self._crypto is None
            or self._fingerprint_key is None
            or len(self._fingerprint_key) < 32
        ):
            raise PersistenceUnavailableApiError()
        return self._crypto, self._fingerprint_key

    def publish(
        self,
        device_id: str,
        request: SessionLeasePublishRequest,
    ) -> AcceptedSessionLeaseMetadata:
        crypto, fingerprint_key = self._require_crypto()
        try:
            canonical = canonical_session_payload(request)
            fingerprint = session_payload_fingerprint(
                canonical,
                fingerprint_key,
            )
            lease_id = self._lease_id_factory()
            encrypted = crypto.encrypt(
                canonical,
                lease_id=lease_id,
                realm_id=request.realm_id,
                publisher_id=request.publisher_id,
                local_generation=request.local_generation,
                expires_at=request.expires_at,
                payload_schema_version=SESSION_PAYLOAD_SCHEMA_VERSION,
            )
            record = self._repository.accept_session_lease_atomic(
                device_id=device_id,
                realm_id=request.realm_id,
                publisher_id=request.publisher_id,
                lease_id=lease_id,
                local_generation=request.local_generation,
                payload_fingerprint=fingerprint,
                ciphertext=encrypted.ciphertext,
                nonce=encrypted.nonce,
                key_version=encrypted.key_version,
                payload_schema_version=SESSION_PAYLOAD_SCHEMA_VERSION,
                expires_at=request.expires_at,
            )
        except PersistenceUnavailableError as exc:
            raise PersistenceUnavailableApiError() from exc
        except SessionPayloadTooLargeError as exc:
            raise SessionLeasePayloadTooLargeApiError() from exc
        except (SessionCryptoError, ValueError) as exc:
            raise PersistenceUnavailableApiError() from exc

        if record is None:
            raise CloudRealmUnauthorizedError()
        return self._lease_metadata(record)

    def revoke_lease(
        self,
        device_id: str,
        realm_id: str,
        lease_id: UUID,
    ) -> AcceptedSessionLeaseMetadata:
        try:
            record = self._repository.revoke_session_lease(
                device_id=device_id,
                realm_id=realm_id,
                lease_id=lease_id,
            )
        except PersistenceUnavailableError as exc:
            raise PersistenceUnavailableApiError() from exc
        if record is None:
            raise SessionLeaseNotAvailableError()
        return self._lease_metadata(record)

    def consume(
        self,
        cloud_binding_id: UUID,
        credential: str,
    ) -> SessionLeaseConsumeResponse:
        crypto, _fingerprint_key = self._require_crypto()
        authorized = self._binding_service.authenticate_cloud_binding(
            cloud_binding_id,
            credential,
        )
        try:
            record = self._repository.get_current_session_lease(
                authorized.realm_id,
                now=self._clock(),
            )
        except PersistenceUnavailableError as exc:
            raise PersistenceUnavailableApiError() from exc
        if record is None:
            raise SessionLeaseNotAvailableError()

        try:
            plaintext = crypto.decrypt(
                EncryptedSessionPayload(
                    ciphertext=record.ciphertext,
                    nonce=record.nonce,
                    key_version=record.key_version,
                ),
                lease_id=record.lease_id,
                realm_id=record.realm_id,
                publisher_id=record.publisher_id,
                local_generation=record.local_generation,
                expires_at=record.expires_at,
                payload_schema_version=record.payload_schema_version,
            )
            payload = json.loads(plaintext.decode("utf-8"))
            if (
                payload.get("realm_id") != record.realm_id
                or payload.get("publisher_id") != str(record.publisher_id)
                or payload.get("local_generation") != record.local_generation
            ):
                raise SessionCryptoError("metadata de sessão divergente")
            cookies = tuple(
                SessionCookieOut(
                    name=str(item["name"]),
                    value=str(item["value"]),
                    expiry=item.get("expiry"),
                )
                for item in payload["cookies"]
            )
        except (
            KeyError,
            TypeError,
            ValueError,
            UnicodeError,
            json.JSONDecodeError,
            SessionCryptoError,
        ) as exc:
            raise PersistenceUnavailableApiError() from exc

        return SessionLeaseConsumeResponse(
            **self._lease_metadata(record).model_dump(),
            cookies=cookies,
        )

    def invalidate(
        self,
        cloud_binding_id: UUID,
        credential: str,
        lease_id: UUID,
        realm_epoch: int,
    ) -> AcceptedSessionLeaseMetadata:
        authorized = self._binding_service.authenticate_cloud_binding(
            cloud_binding_id,
            credential,
        )
        try:
            record = self._repository.invalidate_session_lease(
                realm_id=authorized.realm_id,
                lease_id=lease_id,
                realm_epoch=realm_epoch,
            )
        except PersistenceUnavailableError as exc:
            raise PersistenceUnavailableApiError() from exc
        if record is None:
            raise SessionLeaseNotAvailableError()
        return self._lease_metadata(record)
