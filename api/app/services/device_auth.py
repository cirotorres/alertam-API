from __future__ import annotations

from dataclasses import dataclass

from app.core.errors import (
    InvalidDeviceCredentialsError,
    PersistenceUnavailableApiError,
)
from app.repositories.devices import (
    DeviceAuthRecord,
    DevicesRepository,
    PersistenceUnavailableError,
)
from app.security.credentials import verify_secret


@dataclass(frozen=True)
class AuthenticatedDevice:
    device_id: str


@dataclass(frozen=True)
class DeviceOperationalStatus:
    device_id: str
    enabled: bool


class DeviceAuthService:
    def __init__(self, repository: DevicesRepository) -> None:
        self._repository = repository

    def _verified_record(
        self,
        device_id: str,
        device_secret: str,
    ) -> DeviceAuthRecord:
        try:
            auth = self._repository.get_device_auth(device_id)
        except PersistenceUnavailableError as exc:
            raise PersistenceUnavailableApiError() from exc

        if auth is None or not verify_secret(
            device_secret,
            auth.device_secret_hash,
        ):
            raise InvalidDeviceCredentialsError()
        return auth

    def authenticate(
        self,
        device_id: str,
        device_secret: str,
    ) -> AuthenticatedDevice:
        auth = self._verified_record(device_id, device_secret)
        if not auth.enabled:
            raise InvalidDeviceCredentialsError()
        return AuthenticatedDevice(device_id=device_id)

    def authenticate_status(
        self,
        device_id: str,
        device_secret: str,
    ) -> DeviceOperationalStatus:
        auth = self._verified_record(device_id, device_secret)
        return DeviceOperationalStatus(
            device_id=auth.device_id,
            enabled=auth.enabled,
        )
