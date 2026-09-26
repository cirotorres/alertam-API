from __future__ import annotations

from datetime import datetime
from typing import Callable

from fastapi import APIRouter, Cookie, Header, Response, status

from app.models.mobile_session import (
    MobileSessionRequest,
    MobileSessionResponse,
)
from app.repositories.devices import DevicesRepository
from app.security.credentials import parse_bearer_authorization
from app.services.mobile_session_service import (
    MobileSessionService,
    SESSION_TTL,
)


COOKIE_NAME = "alertam_mobile_session"
COOKIE_PATH = "/api/v1"


def create_mobile_session_router(
    repository: DevicesRepository,
    *,
    cookie_secure: bool,
    clock: Callable[[], datetime] | None = None,
) -> APIRouter:
    router = APIRouter(prefix="/mobile/session")
    service = MobileSessionService(repository, clock=clock)

    @router.post("", response_model=MobileSessionResponse)
    def create_session(
        request: MobileSessionRequest,
        response: Response,
        authorization: str | None = Header(
            default=None,
            alias="Authorization",
        ),
    ) -> MobileSessionResponse:
        view_secret = parse_bearer_authorization(authorization)
        token = service.create_session(request.device_id, view_secret)
        response.set_cookie(
            key=COOKIE_NAME,
            value=token,
            max_age=int(SESSION_TTL.total_seconds()),
            path=COOKIE_PATH,
            secure=cookie_secure,
            httponly=True,
            samesite="strict",
        )
        return MobileSessionResponse(device_id=request.device_id)

    @router.get("", response_model=MobileSessionResponse)
    def recover_session(
        mobile_session: str | None = Cookie(
            default=None,
            alias=COOKIE_NAME,
        ),
    ) -> MobileSessionResponse:
        device_id = service.resolve_session(mobile_session)
        return MobileSessionResponse(device_id=device_id)

    @router.delete("", status_code=status.HTTP_204_NO_CONTENT)
    def delete_session(response: Response) -> Response:
        response.delete_cookie(
            key=COOKIE_NAME,
            path=COOKIE_PATH,
            secure=cookie_secure,
            httponly=True,
            samesite="strict",
        )
        response.status_code = status.HTTP_204_NO_CONTENT
        return response

    return router
