from __future__ import annotations

from uuid import UUID

from app.core.errors import (
    PersistenceUnavailableApiError,
    PushInstallationNotFoundError,
)
from app.repositories.devices import PersistenceUnavailableError
from app.repositories.events import (
    AlertaRepository,
    PushInstallation,
    PushPreferences,
)


class PushInstallationService:
    def __init__(self, repository: AlertaRepository) -> None:
        self._repository = repository

    def register_installation(
        self,
        device_id: str,
        installation_id: UUID,
        *,
        endpoint: str,
        p256dh: str,
        auth: str,
    ) -> PushInstallation:
        try:
            installation = self._repository.upsert_push_installation(
                device_id,
                installation_id,
                endpoint=endpoint,
                p256dh=p256dh,
                auth=auth,
            )
        except PersistenceUnavailableError as exc:
            raise PersistenceUnavailableApiError() from exc
        return self._require(installation)

    def get_installation(
        self,
        device_id: str,
        installation_id: UUID,
    ) -> PushInstallation:
        try:
            installation = self._repository.get_push_installation(
                device_id,
                installation_id,
            )
        except PersistenceUnavailableError as exc:
            raise PersistenceUnavailableApiError() from exc
        return self._require(installation)

    def update_preferences(
        self,
        device_id: str,
        installation_id: UUID,
        changes: dict[str, bool],
    ) -> PushInstallation:
        current = self.get_installation(device_id, installation_id)
        values = {
            "confirmed": current.preferences.confirmed,
            "updated": current.preferences.updated,
            "completed": current.preferences.completed,
            "cancelled": current.preferences.cancelled,
            "anchored": current.preferences.anchored,
        }
        values.update(changes)
        preferences = PushPreferences(**values)
        try:
            updated = self._repository.update_push_preferences(
                device_id,
                installation_id,
                preferences,
            )
        except PersistenceUnavailableError as exc:
            raise PersistenceUnavailableApiError() from exc
        return self._require(updated)

    def touch_foreground(
        self,
        device_id: str,
        installation_id: UUID,
    ) -> PushInstallation:
        try:
            updated = self._repository.touch_push_foreground(
                device_id,
                installation_id,
            )
        except PersistenceUnavailableError as exc:
            raise PersistenceUnavailableApiError() from exc
        return self._require(updated)

    def deactivate_installation(
        self,
        device_id: str,
        installation_id: UUID,
    ) -> None:
        try:
            deactivated = self._repository.deactivate_push_installation(
                device_id,
                installation_id,
            )
        except PersistenceUnavailableError as exc:
            raise PersistenceUnavailableApiError() from exc
        if not deactivated:
            raise PushInstallationNotFoundError()

    @staticmethod
    def _require(
        installation: PushInstallation | None,
    ) -> PushInstallation:
        if installation is None:
            raise PushInstallationNotFoundError()
        return installation
