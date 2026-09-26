from __future__ import annotations

from dataclasses import dataclass

from app.core.errors import InvalidDeviceCredentialsError
from app.repositories.devices import DevicesRepository
from app.security.credentials import verify_secret


@dataclass(frozen=True)
class AuthenticatedDevice:
    device_id: str


class DeviceAuthService:
    def __init__(self, repository: DevicesRepository) -> None:
        self._repository = repository

    def authenticate(
        self,
        device_id: str,
        device_secret: str,
    ) -> AuthenticatedDevice:
        auth = self._repository.get_device_auth(device_id)
        if auth is None or not verify_secret(
            device_secret,
            auth.device_secret_hash,
        ):
            raise InvalidDeviceCredentialsError()
        return AuthenticatedDevice(device_id=device_id)
