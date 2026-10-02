import base64
from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import json
from dataclasses import dataclass
from typing import Callable
from uuid import UUID

from app.core.errors import (
    InvalidViewCredentialsError,
    MobileSessionSwitchConflictError,
    PersistenceUnavailableApiError,
)
from app.repositories.devices import (
    DeviceAuthRecord,
    DevicesRepository,
    MobileInstallationDisplayCodeConflictError,
    MobileInstallationSwitchConflictError,
    PersistenceUnavailableError,
)
from app.security.credentials import hash_secret, verify_secret
from app.services.mobile_installation_service import (
    MobileInstallationService,
    generate_display_code,
    normalize_mobile_platform,
)


SESSION_TTL = timedelta(days=30)


@dataclass(frozen=True)
class MobileSessionIdentity:
    device_id: str
    installation_id: UUID


@dataclass(frozen=True)
class MobileSessionPrincipal:
    device_id: str
    installation_id: UUID
    display_code: str
    platform: str


class MobileSessionService:
    def __init__(
        self,
        repository: DevicesRepository,
        *,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._repository = repository
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._installations = MobileInstallationService(
            repository,
            clock=self._clock,
        )

    def create_session(
        self,
        device_id: str,
        installation_id: UUID,
        view_secret: str,
        *,
        platform: str | None = None,
        credential_kind: str = "view",
    ) -> tuple[str, MobileSessionPrincipal]:
        auth = self._require_pairing_auth(
            device_id,
            view_secret,
            credential_kind=credential_kind,
            purpose=(
                str(installation_id)
                if credential_kind == "ticket"
                else None
            ),
        )

        try:
            installation = self._installations.ensure(
                device_id,
                installation_id,
                platform=platform,
            )
        except PersistenceUnavailableError as exc:
            raise PersistenceUnavailableApiError() from exc
        if installation is None:
            raise InvalidViewCredentialsError()

        principal = MobileSessionPrincipal(
            device_id=device_id,
            installation_id=installation.installation_id,
            display_code=installation.display_code,
            platform=installation.platform,
        )
        assert auth.view_secret_hash is not None
        return (
            self._issue_token(
                principal.device_id,
                principal.installation_id,
                auth.view_secret_hash,
            ),
            principal,
        )

    def validate_pairing(
        self,
        device_id: str,
        view_secret: str,
        *,
        credential_kind: str = "view",
    ) -> None:
        self._require_pairing_auth(
            device_id,
            view_secret,
            credential_kind=credential_kind,
        )

    def resolve_session(
        self,
        token: str | None,
    ) -> MobileSessionPrincipal:
        identity = self._resolve_signed_identity(token)

        try:
            installation = self._repository.get_mobile_installation(
                identity.device_id,
                identity.installation_id,
            )
        except PersistenceUnavailableError as exc:
            raise PersistenceUnavailableApiError() from exc
        if installation is None or not installation.active:
            raise InvalidViewCredentialsError()

        return MobileSessionPrincipal(
            device_id=identity.device_id,
            installation_id=identity.installation_id,
            display_code=installation.display_code,
            platform=installation.platform,
        )

    def switch_session(
        self,
        token: str | None,
        *,
        target_device_id: str,
        target_installation_id: UUID,
        target_view_secret: str,
        platform: str,
        switch_id: UUID,
        target_credential_kind: str = "view",
    ) -> tuple[str, MobileSessionPrincipal]:
        source = self._resolve_signed_identity(token)
        target_auth = self._require_pairing_auth(
            target_device_id,
            target_view_secret,
            credential_kind=target_credential_kind,
            purpose=(
                str(switch_id)
                if target_credential_kind == "ticket"
                else None
            ),
        )
        normalized_platform = normalize_mobile_platform(platform)

        for _attempt in range(8):
            try:
                installation = self._repository.switch_mobile_installation(
                    source.device_id,
                    source.installation_id,
                    target_device_id,
                    target_installation_id,
                    platform=normalized_platform,
                    display_code=generate_display_code(),
                    switch_id=switch_id,
                )
            except MobileInstallationDisplayCodeConflictError:
                continue
            except MobileInstallationSwitchConflictError as exc:
                raise MobileSessionSwitchConflictError() from exc
            except PersistenceUnavailableError as exc:
                raise PersistenceUnavailableApiError() from exc

            if installation is None:
                raise InvalidViewCredentialsError()

            principal = MobileSessionPrincipal(
                device_id=installation.device_id,
                installation_id=installation.installation_id,
                display_code=installation.display_code,
                platform=installation.platform,
            )
            assert target_auth.view_secret_hash is not None
            return (
                self._issue_token(
                    principal.device_id,
                    principal.installation_id,
                    target_auth.view_secret_hash,
                ),
                principal,
            )

        raise PersistenceUnavailableApiError()

    def touch_installation(
        self,
        principal: MobileSessionPrincipal,
        *,
        platform: str | None = None,
    ) -> MobileSessionPrincipal:
        try:
            installation = self._installations.touch(
                principal.device_id,
                principal.installation_id,
                platform=platform,
            )
        except PersistenceUnavailableError as exc:
            raise PersistenceUnavailableApiError() from exc
        if installation is None:
            raise InvalidViewCredentialsError()
        return MobileSessionPrincipal(
            device_id=installation.device_id,
            installation_id=installation.installation_id,
            display_code=installation.display_code,
            platform=installation.platform,
        )

    def invalidate_installation(
        self,
        principal: MobileSessionPrincipal,
    ) -> None:
        try:
            self._installations.revoke(
                principal.device_id,
                principal.installation_id,
            )
        except PersistenceUnavailableError as exc:
            raise PersistenceUnavailableApiError() from exc

    def _resolve_signed_identity(
        self,
        token: str | None,
    ) -> MobileSessionIdentity:
        if not token:
            raise InvalidViewCredentialsError()

        try:
            payload, signature = token.split(".", 1)
            body = self._decode_payload(payload)
            device_id = str(body["device_id"])
            installation_id = UUID(str(body["installation_id"]))
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

        return MobileSessionIdentity(
            device_id=device_id,
            installation_id=installation_id,
        )

    def _require_pairing_auth(
        self,
        device_id: str,
        secret: str,
        *,
        credential_kind: str,
        purpose: str | None = None,
    ) -> DeviceAuthRecord:
        if credential_kind == "view":
            return self._require_view_auth(device_id, secret)
        if credential_kind != "ticket":
            raise InvalidViewCredentialsError()

        try:
            if purpose is None:
                valid = self._repository.validate_mobile_pairing_ticket(
                    device_id,
                    hash_secret(secret),
                    now=self._clock(),
                )
            else:
                valid = self._repository.consume_mobile_pairing_ticket(
                    device_id,
                    hash_secret(secret),
                    purpose,
                    now=self._clock(),
                )
        except PersistenceUnavailableError as exc:
            raise PersistenceUnavailableApiError() from exc

        if not valid:
            raise InvalidViewCredentialsError()

        auth = self._get_auth(device_id)
        if auth is None or auth.view_secret_hash is None:
            raise InvalidViewCredentialsError()
        return auth

    def _require_view_auth(
        self,
        device_id: str,
        view_secret: str,
    ) -> DeviceAuthRecord:
        auth = self._get_auth(device_id)
        if (
            auth is None
            or auth.view_secret_hash is None
            or not verify_secret(view_secret, auth.view_secret_hash)
        ):
            raise InvalidViewCredentialsError()
        return auth

    def _get_auth(self, device_id: str) -> DeviceAuthRecord | None:
        try:
            return self._repository.get_device_auth(device_id)
        except PersistenceUnavailableError as exc:
            raise PersistenceUnavailableApiError() from exc

    def _issue_token(
        self,
        device_id: str,
        installation_id: UUID,
        view_secret_hash: str,
    ) -> str:
        expires_at = int((self._clock() + SESSION_TTL).timestamp())
        payload = self._encode_payload({
            "device_id": device_id,
            "installation_id": str(installation_id),
            "exp": expires_at,
        })
        signature = self._sign(payload, view_secret_hash)
        return f"{payload}.{signature}"

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
