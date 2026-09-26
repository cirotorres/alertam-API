from __future__ import annotations

from datetime import datetime
from typing import Callable

from fastapi import APIRouter

from app.api.v1.access import create_access_router
from app.api.v1.health import create_health_router
from app.api.v1.mobile_session import create_mobile_session_router
from app.api.v1.snapshots import create_snapshot_router
from app.repositories.devices import DevicesRepository


def create_v1_router(
    repository: DevicesRepository,
    *,
    stale_after_seconds: int,
    cookie_secure: bool,
    clock: Callable[[], datetime] | None = None,
) -> APIRouter:
    router = APIRouter(prefix="/api/v1")
    router.include_router(create_health_router())
    router.include_router(
        create_mobile_session_router(
            repository,
            cookie_secure=cookie_secure,
            clock=clock,
        )
    )
    router.include_router(
        create_snapshot_router(
            repository,
            stale_after_seconds=stale_after_seconds,
            clock=clock,
        )
    )
    router.include_router(create_access_router(repository))
    return router
