from datetime import datetime
from typing import Callable

from fastapi import APIRouter, Cookie, Header, Response, status

from app.core.errors import InvalidViewCredentialsError
from app.models.mobile_installation import MobileHeartbeatRequest
from app.models.mobile_session import (
    MobileSessionRequest,
    MobileSessionResponse,
    MobileSessionSwitchRequest,
)
from app.repositories.devices import DevicesRepository
from app.security.credentials import parse_bearer_authorization
from app.services.mobile_session_service import (
    MobileSessionPrincipal,
    MobileSessionService,
    SESSION_TTL,
)


COOKIE_NAME = "alertam_mobile_session"
COOKIE_PATH = "/api/v1"


def _session_response(
    principal: MobileSessionPrincipal,
) -> MobileSessionResponse:
    return MobileSessionResponse(
        device_id=principal.device_id,
        installation_id=principal.installation_id,
        display_code=principal.display_code,
        platform=principal.platform,
    )


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
        token, principal = service.create_session(
            request.device_id,
            request.installation_id,
            view_secret,
            platform=request.platform,
        )
        response.set_cookie(
            key=COOKIE_NAME,
            value=token,
            max_age=int(SESSION_TTL.total_seconds()),
            path=COOKIE_PATH,
            secure=cookie_secure,
            httponly=True,
            samesite="strict",
        )
        return _session_response(principal)

    @router.get("", response_model=MobileSessionResponse)
    def recover_session(
        mobile_session: str | None = Cookie(
            default=None,
            alias=COOKIE_NAME,
        ),
    ) -> MobileSessionResponse:
        return _session_response(
            service.resolve_session(mobile_session)
        )

    @router.post("/switch", response_model=MobileSessionResponse)
    def switch_session(
        request: MobileSessionSwitchRequest,
        response: Response,
        authorization: str | None = Header(
            default=None,
            alias="Authorization",
        ),
        mobile_session: str | None = Cookie(
            default=None,
            alias=COOKIE_NAME,
        ),
    ) -> MobileSessionResponse:
        target_view_secret = parse_bearer_authorization(authorization)
        token, principal = service.switch_session(
            mobile_session,
            target_device_id=request.device_id,
            target_installation_id=request.installation_id,
            target_view_secret=target_view_secret,
            platform=request.platform,
            switch_id=request.switch_id,
        )
        response.set_cookie(
            key=COOKIE_NAME,
            value=token,
            max_age=int(SESSION_TTL.total_seconds()),
            path=COOKIE_PATH,
            secure=cookie_secure,
            httponly=True,
            samesite="strict",
        )
        return _session_response(principal)

    @router.post(
        "/heartbeat",
        status_code=status.HTTP_204_NO_CONTENT,
        response_class=Response,
    )
    def heartbeat(
        request: MobileHeartbeatRequest,
        mobile_session: str | None = Cookie(
            default=None,
            alias=COOKIE_NAME,
        ),
    ) -> Response:
        principal = service.resolve_session(mobile_session)
        service.touch_installation(
            principal,
            platform=request.platform,
        )
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    @router.delete("", status_code=status.HTTP_204_NO_CONTENT)
    def delete_session(
        response: Response,
        mobile_session: str | None = Cookie(
            default=None,
            alias=COOKIE_NAME,
        ),
    ) -> Response:
        if mobile_session:
            try:
                principal = service.resolve_session(mobile_session)
                service.invalidate_installation(principal)
            except InvalidViewCredentialsError:
                # Sessão já expirada/revogada: ainda podemos limpar o
                # cookie local sem fingir que houve uma nova revogação.
                pass
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
