from __future__ import annotations

from datetime import datetime, timedelta, timezone
import secrets
from typing import Callable
from uuid import UUID

from app.repositories.devices import (
    DevicesRepository,
    MobileInstallationDisplayCodeConflictError,
    MobileInstallationRecord,
    PersistenceUnavailableError,
)


DISPLAY_CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


def normalize_mobile_platform(value: str | None) -> str:
    normalized = (value or "").strip().casefold()
    return normalized if normalized in {"ios", "android", "other"} else "other"


def generate_display_code() -> str:
    return "".join(secrets.choice(DISPLAY_CODE_ALPHABET) for _ in range(6))


class MobileInstallationService:
    def __init__(
        self,
        repository: DevicesRepository,
        *,
        clock: Callable[[], datetime] | None = None,
        code_factory: Callable[[], str] = generate_display_code,
    ) -> None:
        self._repository = repository
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._code_factory = code_factory

    def ensure(
        self,
        device_id: str,
        installation_id: UUID,
        *,
        platform: str | None = None,
    ) -> MobileInstallationRecord | None:
        normalized_platform = normalize_mobile_platform(platform)
        for _attempt in range(8):
            try:
                return self._repository.ensure_mobile_installation(
                    device_id,
                    installation_id,
                    platform=normalized_platform,
                    display_code=self._code_factory(),
                )
            except MobileInstallationDisplayCodeConflictError:
                continue
        raise PersistenceUnavailableError()

    def list_for_device(
        self,
        device_id: str,
    ) -> tuple[MobileInstallationRecord, ...]:
        return self._repository.list_mobile_installations(
            device_id,
            revoked_since=self._clock() - timedelta(days=30),
        )

    def touch(
        self,
        device_id: str,
        installation_id: UUID,
        *,
        platform: str | None = None,
    ) -> MobileInstallationRecord | None:
        return self._repository.touch_mobile_installation(
            device_id,
            installation_id,
            platform=normalize_mobile_platform(platform),
        )

    def revoke(self, device_id: str, installation_id: UUID) -> bool:
        return self._repository.revoke_mobile_installation(
            device_id,
            installation_id,
        )
