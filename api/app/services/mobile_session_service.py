from __future__ import annotations

import base64
from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import json
from typing import Callable

from app.core.errors import (
    InvalidViewCredentialsError,
    PersistenceUnavailableApiError,
)
from app.repositories.devices import (
    DevicesRepository,
    PersistenceUnavailableError,
)
from app.security.credentials import verify_secret


SESSION_TTL = timedelta(days=30)


class MobileSessionService:
    def __init__(
        self,
        repository: DevicesRepository,
        *,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._repository = repository
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def create_session(self, device_id: str, view_secret: str) -> str:
        auth = self._get_auth(device_id)
        if (
            auth is None
            or auth.view_secret_hash is None
            or not verify_secret(view_secret, auth.view_secret_hash)
        ):
            raise InvalidViewCredentialsError()

        expires_at = int((self._clock() + SESSION_TTL).timestamp())
        payload = self._encode_payload(
            {"device_id": device_id, "exp": expires_at}
        )
        signature = self._sign(payload, auth.view_secret_hash)
        return f"{payload}.{signature}"

    def resolve_session(self, token: str | None) -> str:
        if not token:
            raise InvalidViewCredentialsError()

        try:
            payload, signature = token.split(".", 1)
            body = self._decode_payload(payload)
            device_id = str(body["device_id"])
            expires_at = int(body["exp"])
        except (ValueError, KeyError, TypeError, json.JSONDecodeError):
            raise InvalidViewCredentialsError() from None

        if not device_id or expires_at <= int(self._clock().timestamp()):
            raise InvalidViewCredentialsError()

        auth = self._get_auth(device_id)
        if auth is None or auth.view_secret_hash is None:
            raise InvalidViewCredentialsError()

        expected = self._sign(payload, auth.view_secret_hash)
        if not hmac.compare_digest(signature, expected):
            raise InvalidViewCredentialsError()

        return device_id

    def _get_auth(self, device_id: str):
        try:
            return self._repository.get_device_auth(device_id)
        except PersistenceUnavailableError as exc:
            raise PersistenceUnavailableApiError() from exc

    @staticmethod
    def _sign(payload: str, view_secret_hash: str) -> str:
        digest = hmac.new(
            bytes.fromhex(view_secret_hash),
            payload.encode("utf-8"),
            hashlib.sha256,
        ).digest()
        return base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")

    @staticmethod
    def _encode_payload(payload: dict[str, object]) -> str:
        raw = json.dumps(
            payload,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
        return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")

    @staticmethod
    def _decode_payload(payload: str) -> dict[str, object]:
        padding = "=" * (-len(payload) % 4)
        raw = base64.urlsafe_b64decode(payload + padding)
        value = json.loads(raw)
        if not isinstance(value, dict):
            raise ValueError("invalid payload")
        return value
