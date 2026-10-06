from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Any, Protocol
from uuid import UUID


class DeviceAlreadyExistsError(Exception):
    pass


class PersistenceUnavailableError(Exception):
    def __init__(self) -> None:
        super().__init__("Persistência temporariamente indisponível.")


class MobileInstallationDisplayCodeConflictError(Exception):
    pass


class MobileInstallationSwitchConflictError(Exception):
    pass


class MobilePairingCodeConflictError(Exception):
    pass


class MobilePairingCodeRedeemStatus(StrEnum):
    OK = "ok"
    INVALID = "invalid"
    RATE_LIMITED = "rate_limited"


@dataclass(frozen=True)
class MobilePairingCodeRedeemResult:
    status: MobilePairingCodeRedeemStatus
    device_id: str | None = None
    ticket_expires_at: datetime | None = None


@dataclass(frozen=True)
class DeviceAuthRecord:
    device_id: str
    device_secret_hash: str
    view_secret_hash: str | None = None
    description: str | None = None
    enabled: bool = True


@dataclass(frozen=True)
class MobileInstallationRecord:
    installation_id: UUID
    device_id: str
    active: bool
    created_at: datetime
    last_seen_at: datetime
    revoked_at: datetime | None = None
    platform: str = "other"
    display_code: str = ""


@dataclass(frozen=True)
class StoredSnapshot:
    device_id: str
    snapshot: dict[str, Any]
    snapshot_schema_version: int
    boot_id: UUID
    sequence: int
    generated_at: datetime
    received_at: datetime

class AcceptSnapshotStatus(StrEnum):
    ACCEPTED = "accepted"
    IDEMPOTENT = "idempotent"
    OUT_OF_ORDER = "out_of_order"
    SEQUENCE_REUSE_MISMATCH = "sequence_reuse_mismatch"
    DEVICE_NOT_FOUND = "device_not_found"


@dataclass(frozen=True)
class SnapshotCandidate:
    device_id: str
    snapshot: dict[str, Any]
    snapshot_schema_version: int
    boot_id: UUID
    sequence: int
    generated_at: datetime


@dataclass(frozen=True)
class AcceptSnapshotResult:
    status: AcceptSnapshotStatus
    received_at: datetime | None = None


class DeviceCreator(Protocol):
    def create_device(self, record: DeviceAuthRecord) -> None: ...

class DevicesRepository(DeviceCreator, Protocol):
    def get_device_auth(self, device_id: str) -> DeviceAuthRecord | None: ...

    def ensure_mobile_installation(
        self,
        device_id: str,
        installation_id: UUID,
        *,
        platform: str = "other",
        display_code: str | None = None,
    ) -> MobileInstallationRecord | None: ...

    def get_mobile_installation(
        self,
        device_id: str,
        installation_id: UUID,
    ) -> MobileInstallationRecord | None: ...

    def list_mobile_installations(
        self,
        device_id: str,
        *,
        revoked_since: datetime,
    ) -> tuple[MobileInstallationRecord, ...]: ...

    def touch_mobile_installation(
        self,
        device_id: str,
        installation_id: UUID,
        *,
        platform: str,
    ) -> MobileInstallationRecord | None: ...

    def revoke_mobile_installation(
        self,
        device_id: str,
        installation_id: UUID,
    ) -> bool: ...

    def switch_mobile_installation(
        self,
        from_device_id: str,
        from_installation_id: UUID,
        to_device_id: str,
        to_installation_id: UUID,
        *,
        platform: str,
        display_code: str,
        switch_id: UUID,
    ) -> MobileInstallationRecord | None: ...

    def get_snapshot(self, device_id: str) -> StoredSnapshot | None: ...

    def replace_mobile_pairing_code(
        self,
        device_id: str,
        code_hash: str,
        *,
        expires_at: datetime,
    ) -> bool: ...

    def redeem_mobile_pairing_code(
        self,
        code_hash: str,
        ticket_hash: str,
        *,
        ticket_expires_at: datetime,
        now: datetime,
    ) -> MobilePairingCodeRedeemResult: ...

    def validate_mobile_pairing_ticket(
        self,
        device_id: str,
        ticket_hash: str,
        *,
        now: datetime,
    ) -> bool: ...

    def consume_mobile_pairing_ticket(
        self,
        device_id: str,
        ticket_hash: str,
        purpose: str,
        *,
        now: datetime,
    ) -> bool: ...

    def rotate_view_secret_hash(
        self,
        device_id: str,
        view_secret_hash: str,
    ) -> bool: ...

    def accept_snapshot_atomic(
        self,
        candidate: SnapshotCandidate,
    ) -> AcceptSnapshotResult: ...
