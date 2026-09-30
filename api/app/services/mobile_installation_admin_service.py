from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Callable
from uuid import UUID

from app.core.errors import (
    MobileInstallationNotFoundError,
    PersistenceUnavailableApiError,
)
from app.repositories.devices import (
    DevicesRepository,
    MobileInstallationRecord,
    PersistenceUnavailableError,
)
from app.services.device_auth import AuthenticatedDevice, DeviceAuthService
from app.services.mobile_installation_service import MobileInstallationService


@dataclass(frozen=True)
class MobileInstallationAdminSnapshot:
    active: tuple[MobileInstallationRecord, ...]
    recently_revoked: tuple[MobileInstallationRecord, ...]

    @property
    def active_count(self) -> int:
        return len(self.active)


class MobileInstallationAdminService:
    def __init__(
        self,
        repository: DevicesRepository,
        *,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._repository = repository
        self._auth = DeviceAuthService(repository)
        self._installations = MobileInstallationService(
            repository,
            clock=clock,
        )

    def authenticate(
        self,
        device_id: str,
        device_secret: str,
    ) -> AuthenticatedDevice:
        try:
            return self._auth.authenticate(device_id, device_secret)
        except PersistenceUnavailableError as exc:
            raise PersistenceUnavailableApiError() from exc

    def list_for_device(
        self,
        device: AuthenticatedDevice,
    ) -> MobileInstallationAdminSnapshot:
        try:
            items = self._installations.list_for_device(device.device_id)
        except PersistenceUnavailableError as exc:
            raise PersistenceUnavailableApiError() from exc
        return MobileInstallationAdminSnapshot(
            active=tuple(item for item in items if item.active),
            recently_revoked=tuple(item for item in items if not item.active),
        )

    def revoke(
        self,
        device: AuthenticatedDevice,
        installation_id: UUID,
    ) -> None:
        try:
            current = self._repository.get_mobile_installation(
                device.device_id,
                installation_id,
            )
            if current is None:
                raise MobileInstallationNotFoundError()
            updated = self._installations.revoke(
                device.device_id,
                installation_id,
            )
        except PersistenceUnavailableError as exc:
            raise PersistenceUnavailableApiError() from exc

        if not updated:
            raise MobileInstallationNotFoundError()
