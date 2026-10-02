from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import re
import secrets
from typing import Callable

from app.core.errors import (
    InvalidMobilePairingCodeError,
    InvalidViewCredentialsError,
    MobilePairingCodeRateLimitedError,
    PersistenceUnavailableApiError,
)
from app.repositories.devices import (
    DevicesRepository,
    MobilePairingCodeConflictError,
    MobilePairingCodeRedeemStatus,
    PersistenceUnavailableError,
)
from app.security.credentials import hash_secret
from app.services.device_auth import AuthenticatedDevice


PAIRING_CODE_TTL = timedelta(minutes=5)
PAIRING_TICKET_TTL = timedelta(minutes=5)
_CODE_RE = re.compile(r"^\d{6}$")


@dataclass(frozen=True)
class IssuedMobilePairingCode:
    code: str
    expires_at: datetime


@dataclass(frozen=True)
class MobilePairingTicket:
    device_id: str
    ticket: str
    expires_at: datetime


def generate_pairing_code() -> str:
    return f"{secrets.randbelow(1_000_000):06d}"


def generate_pairing_ticket() -> str:
    return secrets.token_urlsafe(32)


def normalize_pairing_code(value: str) -> str:
    return re.sub(r"[\s-]+", "", value or "")


class MobilePairingCodeService:
    def __init__(
        self,
        repository: DevicesRepository,
        *,
        clock: Callable[[], datetime] | None = None,
        code_factory: Callable[[], str] = generate_pairing_code,
        ticket_factory: Callable[[], str] = generate_pairing_ticket,
    ) -> None:
        self._repository = repository
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._code_factory = code_factory
        self._ticket_factory = ticket_factory

    def issue_for_device(
        self,
        device: AuthenticatedDevice,
    ) -> IssuedMobilePairingCode:
        auth = self._repository.get_device_auth(device.device_id)
        if auth is None or auth.view_secret_hash is None:
            raise InvalidViewCredentialsError()

        expires_at = self._clock() + PAIRING_CODE_TTL
        for _ in range(8):
            code = self._code_factory()
            if _CODE_RE.fullmatch(code) is None:
                continue
            try:
                updated = self._repository.replace_mobile_pairing_code(
                    device.device_id,
                    hash_secret(code),
                    expires_at=expires_at,
                )
            except MobilePairingCodeConflictError:
                continue
            except PersistenceUnavailableError as exc:
                raise PersistenceUnavailableApiError() from exc
            if updated:
                return IssuedMobilePairingCode(
                    code=code,
                    expires_at=expires_at,
                )
            raise InvalidViewCredentialsError()
        raise PersistenceUnavailableApiError()

    def redeem(self, raw_code: str) -> MobilePairingTicket:
        code = normalize_pairing_code(raw_code)
        if _CODE_RE.fullmatch(code) is None:
            raise InvalidMobilePairingCodeError()

        now = self._clock()
        ticket = self._ticket_factory()
        expires_at = now + PAIRING_TICKET_TTL
        try:
            result = self._repository.redeem_mobile_pairing_code(
                hash_secret(code),
                hash_secret(ticket),
                ticket_expires_at=expires_at,
                now=now,
            )
        except PersistenceUnavailableError as exc:
            raise PersistenceUnavailableApiError() from exc

        if result.status is MobilePairingCodeRedeemStatus.RATE_LIMITED:
            raise MobilePairingCodeRateLimitedError()
        if (
            result.status is not MobilePairingCodeRedeemStatus.OK
            or not result.device_id
        ):
            raise InvalidMobilePairingCodeError()

        return MobilePairingTicket(
            device_id=result.device_id,
            ticket=ticket,
            expires_at=result.ticket_expires_at or expires_at,
        )
