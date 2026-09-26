from __future__ import annotations

from datetime import datetime, timezone
from typing import Callable

from app.core.errors import (
    InvalidViewCredentialsError,
    PersistenceUnavailableApiError,
    SnapshotNotAvailableError,
)
from app.models.read_snapshot import (
    SnapshotMetaResponse,
    SnapshotReadResponse,
)
from app.repositories.devices import DevicesRepository, PersistenceUnavailableError
from app.security.credentials import verify_secret


class SnapshotReadService:
    def __init__(
        self,
        repository: DevicesRepository,
        *,
        stale_after_seconds: int = 120,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._repository = repository
        self._stale_after_seconds = stale_after_seconds
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def get_snapshot(
        self,
        device_id: str,
        view_secret: str,
    ) -> SnapshotReadResponse:
        try:
            auth = self._repository.get_device_auth(device_id)
        except PersistenceUnavailableError as exc:
            raise PersistenceUnavailableApiError() from exc

        if (
            auth is None
            or auth.view_secret_hash is None
            or not verify_secret(view_secret, auth.view_secret_hash)
        ):
            raise InvalidViewCredentialsError()

        try:
            stored = self._repository.get_snapshot(device_id)
        except PersistenceUnavailableError as exc:
            raise PersistenceUnavailableApiError() from exc

        if stored is None:
            raise SnapshotNotAvailableError()

        age_seconds = int(
            (self._clock() - stored.received_at).total_seconds()
        )
        collector_online = age_seconds < self._stale_after_seconds

        return SnapshotReadResponse(
            snapshot=stored.snapshot,
            meta=SnapshotMetaResponse(
                received_at=stored.received_at,
                age_seconds=age_seconds,
                collector_online=collector_online,
                stale_after_seconds=self._stale_after_seconds,
            ),
        )
