from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Protocol
from uuid import UUID


class ScopeStatus(StrEnum):
    UNVERIFIED = "unverified"
    VERIFIED = "verified"
    INCOMPATIBLE = "incompatible"


class SessionPublisherStatus(StrEnum):
    ACTIVE = "active"
    REVOKED = "revoked"


class SessionLeaseStatus(StrEnum):
    ACCEPTED = "accepted"
    REVOKED = "revoked"
    INVALIDATED = "invalidated"


class SessionLeaseGenerationConflictError(Exception):
    pass


class SessionLeaseReplayError(Exception):
    pass


class SessionPublisherConflictError(Exception):
    pass


@dataclass(frozen=True)
class ProviderScopeProfile:
    scope_id: str
    schema_version: int
    capabilities: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        scope_id = self.scope_id.strip()
        if not scope_id:
            raise ValueError("scope_id é obrigatório")
        if self.schema_version < 1:
            raise ValueError("schema_version deve ser positivo")
        normalized = tuple(sorted(self.capabilities))
        if any(not item.strip() for item in normalized):
            raise ValueError("capability vazia")
        if len(set(normalized)) != len(normalized):
            raise ValueError("capabilities duplicadas")
        object.__setattr__(self, "scope_id", scope_id)
        object.__setattr__(self, "capabilities", normalized)


@dataclass(frozen=True)
class RequiredProviderScopeRecord:
    realm_id: str
    profile: ProviderScopeProfile
    updated_at: datetime


@dataclass(frozen=True)
class SessionPublisherRecord:
    publisher_id: UUID
    realm_id: str
    device_id: str
    provider_scope: ProviderScopeProfile
    scope_status: ScopeStatus
    scope_verified_at: datetime | None
    last_generation: int
    status: SessionPublisherStatus
    created_at: datetime
    updated_at: datetime
    revoked_at: datetime | None = None


@dataclass(frozen=True)
class EncryptedSessionLeaseRecord:
    lease_id: UUID
    realm_id: str
    publisher_id: UUID
    local_generation: int
    realm_epoch: int
    payload_fingerprint: str = field(repr=False)
    ciphertext: str = field(repr=False)
    nonce: str = field(repr=False)
    key_version: int = field(repr=False)
    payload_schema_version: int
    received_at: datetime
    expires_at: datetime | None
    status: SessionLeaseStatus
    revoked_at: datetime | None = None
    invalidated_at: datetime | None = None


class SessionBrokerRepository(Protocol):
    def set_required_provider_scope(
        self,
        realm_id: str,
        profile: ProviderScopeProfile,
    ) -> RequiredProviderScopeRecord | None: ...

    def get_required_provider_scope(
        self,
        realm_id: str,
    ) -> RequiredProviderScopeRecord | None: ...

    def ensure_session_publisher(
        self,
        *,
        device_id: str,
        realm_id: str,
        publisher_id: UUID,
        provider_scope: ProviderScopeProfile,
    ) -> SessionPublisherRecord | None: ...

    def get_session_publisher(
        self,
        publisher_id: UUID,
    ) -> SessionPublisherRecord | None: ...

    def verify_session_publisher_scope(
        self,
        publisher_id: UUID,
    ) -> SessionPublisherRecord | None: ...

    def revoke_session_publisher(
        self,
        publisher_id: UUID,
    ) -> SessionPublisherRecord | None: ...

    def accept_session_lease_atomic(
        self,
        *,
        device_id: str,
        realm_id: str,
        publisher_id: UUID,
        lease_id: UUID,
        local_generation: int,
        payload_fingerprint: str,
        ciphertext: str,
        nonce: str,
        key_version: int,
        payload_schema_version: int,
        expires_at: datetime | None,
    ) -> EncryptedSessionLeaseRecord | None: ...

    def get_session_lease(
        self,
        lease_id: UUID,
    ) -> EncryptedSessionLeaseRecord | None: ...

    def get_current_session_lease(
        self,
        realm_id: str,
        *,
        now: datetime,
    ) -> EncryptedSessionLeaseRecord | None: ...

    def revoke_session_lease(
        self,
        *,
        device_id: str,
        realm_id: str,
        lease_id: UUID,
    ) -> EncryptedSessionLeaseRecord | None: ...

    def invalidate_session_lease(
        self,
        *,
        realm_id: str,
        lease_id: UUID,
        realm_epoch: int,
    ) -> EncryptedSessionLeaseRecord | None: ...
