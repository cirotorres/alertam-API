from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Protocol
from uuid import UUID


class CloudBindingConflictError(Exception):
    pass


class CloudBindingStatus(StrEnum):
    ACTIVE = "active"
    REVOKED = "revoked"


@dataclass(frozen=True)
class WebPilotAuthRealmRecord:
    realm_id: str
    active: bool
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True)
class RealmDeviceAuthorizationRecord:
    realm_id: str
    device_id: str
    authorized_at: datetime
    revoked_at: datetime | None = None

    @property
    def active(self) -> bool:
        return self.revoked_at is None


@dataclass(frozen=True)
class CloudBindingRecord:
    cloud_binding_id: UUID
    device_id: str
    realm_id: str
    credential_hash: str = field(repr=False)
    credential_version: int
    status: CloudBindingStatus
    created_at: datetime
    updated_at: datetime
    revoked_at: datetime | None = None

    def __post_init__(self) -> None:
        if self.credential_version < 1:
            raise ValueError("credential_version must be positive")
        if self.status is CloudBindingStatus.ACTIVE and self.revoked_at is not None:
            raise ValueError("active binding cannot have revoked_at")
        if self.status is CloudBindingStatus.REVOKED and self.revoked_at is None:
            raise ValueError("revoked binding requires revoked_at")


class CloudBindingsRepository(Protocol):
    def get_webpilot_auth_realm(
        self,
        realm_id: str,
    ) -> WebPilotAuthRealmRecord | None: ...

    def authorize_realm_device(
        self,
        realm_id: str,
        device_id: str,
    ) -> RealmDeviceAuthorizationRecord | None: ...

    def get_realm_device_authorization(
        self,
        realm_id: str,
        device_id: str,
    ) -> RealmDeviceAuthorizationRecord | None: ...

    def get_active_cloud_binding(
        self,
        device_id: str,
    ) -> CloudBindingRecord | None: ...

    def list_cloud_bindings(
        self,
        device_id: str,
    ) -> tuple[CloudBindingRecord, ...]: ...

    def ensure_cloud_binding(
        self,
        device_id: str,
        realm_id: str,
        credential_hash: str,
    ) -> CloudBindingRecord | None: ...

    def rotate_cloud_binding(
        self,
        device_id: str,
        credential_hash: str,
    ) -> CloudBindingRecord | None: ...

    def revoke_cloud_binding(
        self,
        device_id: str,
    ) -> CloudBindingRecord | None: ...
