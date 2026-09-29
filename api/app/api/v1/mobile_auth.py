from __future__ import annotations

from datetime import datetime
from typing import Callable

from fastapi import Cookie

from app.api.v1.mobile_session import COOKIE_NAME
from app.repositories.devices import DevicesRepository
from app.services.mobile_session_service import (
    MobileSessionPrincipal,
    MobileSessionService,
)


class MobileSessionAuth:
    def __init__(
        self,
        repository: DevicesRepository,
        *,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._service = MobileSessionService(repository, clock=clock)

    def __call__(
        self,
        mobile_session: str | None = Cookie(
            default=None,
            alias=COOKIE_NAME,
        ),
    ) -> str:
        return self._service.resolve_session(mobile_session).device_id


class MobileInstallationAuth:
    def __init__(
        self,
        repository: DevicesRepository,
        *,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._service = MobileSessionService(repository, clock=clock)

    def __call__(
        self,
        mobile_session: str | None = Cookie(
            default=None,
            alias=COOKIE_NAME,
        ),
    ) -> MobileSessionPrincipal:
        return self._service.resolve_session(mobile_session)
