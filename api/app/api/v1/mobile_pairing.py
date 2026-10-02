from datetime import datetime
from typing import Callable

from fastapi import APIRouter, Header

from app.models.mobile_installation import (
    PairingValidationRequest,
    PairingValidationResponse,
)
from app.repositories.devices import DevicesRepository
from app.security.credentials import parse_mobile_pairing_authorization
from app.services.mobile_session_service import MobileSessionService


def create_mobile_pairing_router(
    repository: DevicesRepository,
    *,
    clock: Callable[[], datetime] | None = None,
) -> APIRouter:
    router = APIRouter(prefix="/mobile/pairing")
    service = MobileSessionService(repository, clock=clock)

    @router.post(
        "/validate",
        response_model=PairingValidationResponse,
    )
    def validate_pairing(
        request: PairingValidationRequest,
        authorization: str | None = Header(
            default=None,
            alias="Authorization",
        ),
    ) -> PairingValidationResponse:
        credential_kind, secret = parse_mobile_pairing_authorization(
            authorization
        )
        service.validate_pairing(
            request.device_id,
            secret,
            credential_kind=credential_kind,
        )
        return PairingValidationResponse(device_id=request.device_id)

    return router
