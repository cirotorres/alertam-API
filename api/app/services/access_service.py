from __future__ import annotations

import re

from app.core.errors import (
    InvalidDeviceCredentialsError,
    InvalidViewSecretError,
    PersistenceUnavailableApiError,
)
from app.repositories.devices import DevicesRepository, PersistenceUnavailableError
from app.security.credentials import hash_secret
from app.services.device_auth import AuthenticatedDevice, DeviceAuthService


_VIEW_SECRET_RE = re.compile(r"^[A-Za-z0-9_-]{43,}$")


class AccessService:
    def __init__(self, repository: DevicesRepository) -> None:
        self._repository = repository
        self._auth = DeviceAuthService(repository)

    def authenticate_device(
        self,
        device_id: str,
        device_secret: str,
    ) -> AuthenticatedDevice:
        return self._auth.authenticate(device_id, device_secret)

    def rotate_view_secret(
        self,
        device_id: str,
        device_secret: str,
        view_secret: str,
    ) -> None:
        device = self.authenticate_device(device_id, device_secret)
        self.rotate_authenticated_view_secret(device, view_secret)

    def rotate_authenticated_view_secret(
        self,
        device: AuthenticatedDevice,
        view_secret: str,
    ) -> None:
        if _VIEW_SECRET_RE.fullmatch(view_secret) is None:
            raise InvalidViewSecretError()

        view_secret_hash = hash_secret(view_secret)
        try:
            updated = self._repository.rotate_view_secret_hash(
                device.device_id,
                view_secret_hash,
            )
        except PersistenceUnavailableError as exc:
            raise PersistenceUnavailableApiError() from exc

        if not updated:
            raise InvalidDeviceCredentialsError()
