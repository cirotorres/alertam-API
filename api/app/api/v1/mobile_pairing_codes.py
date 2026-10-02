from datetime import datetime
from typing import Callable

from fastapi import APIRouter, Depends, Header

from app.models.mobile_pairing_code import (
    MobilePairingCodeRedeemRequest,
    MobilePairingCodeResponse,
    MobilePairingTicketResponse,
)
from app.repositories.devices import DevicesRepository
from app.security.credentials import parse_device_authorization
from app.services.device_auth import AuthenticatedDevice, DeviceAuthService
from app.services.mobile_pairing_code_service import MobilePairingCodeService


def create_mobile_pairing_code_router(
    repository: DevicesRepository,
    *,
    clock: Callable[[], datetime] | None = None,
) -> APIRouter:
    router = APIRouter()
    auth_service = DeviceAuthService(repository)
    service = MobilePairingCodeService(repository, clock=clock)

    def require_device(
        device_id: str,
        authorization: str | None = Header(
            default=None,
            alias="Authorization",
        ),
    ) -> AuthenticatedDevice:
        secret = parse_device_authorization(authorization)
        return auth_service.authenticate(device_id, secret)

    @router.post(
        "/devices/{device_id}/pairing-code",
        response_model=MobilePairingCodeResponse,
    )
    def create_pairing_code(
        device: AuthenticatedDevice = Depends(require_device),
    ) -> MobilePairingCodeResponse:
        issued = service.issue_for_device(device)
        return MobilePairingCodeResponse(
            code=issued.code,
            expires_at=issued.expires_at,
        )

    @router.post(
        "/mobile/pairing/code",
        response_model=MobilePairingTicketResponse,
    )
    def redeem_pairing_code(
        request: MobilePairingCodeRedeemRequest,
    ) -> MobilePairingTicketResponse:
        ticket = service.redeem(request.code)
        return MobilePairingTicketResponse(
            device_id=ticket.device_id,
            pairing_ticket=ticket.ticket,
            expires_at=ticket.expires_at,
        )

    return router
