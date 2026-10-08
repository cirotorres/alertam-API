from __future__ import annotations

import base64
import binascii
from dataclasses import dataclass, field
from datetime import datetime, timezone
import hashlib
import hmac
import json
import os
import re
from typing import Mapping
from uuid import UUID

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.models.session_broker import SessionLeasePublishRequest


class SessionCryptoError(Exception):
    pass


class SessionPayloadTooLargeError(ValueError):
    pass


SESSION_LEASE_MAX_CANONICAL_PAYLOAD_BYTES = 262_144


@dataclass(frozen=True)
class EncryptedSessionPayload:
    ciphertext: str = field(repr=False)
    nonce: str = field(repr=False)
    key_version: int = field(repr=False)


def _utc_text(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("datetime precisa de timezone")
    normalized = value.astimezone(timezone.utc)
    return normalized.isoformat(timespec="microseconds").replace("+00:00", "Z")


def canonical_session_payload(request: SessionLeasePublishRequest) -> bytes:
    cookies = sorted(request.cookies, key=lambda item: item.name)
    names = [item.name for item in cookies]
    if len(names) != len(set(names)):
        raise ValueError("cookie names duplicados")
    payload = {
        "cookies": [
            {
                "expiry": item.expiry,
                "name": item.name,
                "value": item.value.get_secret_value(),
            }
            for item in cookies
        ],
        "expires_at": _utc_text(request.expires_at),
        "local_generation": request.local_generation,
        "publisher_id": str(request.publisher_id),
        "realm_id": request.realm_id,
    }
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    if len(encoded) > SESSION_LEASE_MAX_CANONICAL_PAYLOAD_BYTES:
        raise SessionPayloadTooLargeError(
            "SessionLease excede o limite total permitido."
        )
    return encoded


def session_payload_fingerprint(payload: bytes, key: bytes) -> str:
    if not key:
        raise SessionCryptoError("fingerprint key indisponível")
    return hmac.new(key, payload, hashlib.sha256).hexdigest()


_BASE64URL_CANONICAL = re.compile(r"^[A-Za-z0-9_-]+$")


def _b64encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _b64decode(value: str) -> bytes:
    try:
        if (
            not isinstance(value, str)
            or not value
            or _BASE64URL_CANONICAL.fullmatch(value) is None
            or len(value) % 4 == 1
        ):
            raise SessionCryptoError("payload criptográfico inválido")
        padding = "=" * (-len(value) % 4)
        decoded = base64.b64decode(
            (value + padding).encode("ascii"),
            altchars=b"-_",
            validate=True,
        )
        if _b64encode(decoded) != value:
            raise SessionCryptoError("payload criptográfico inválido")
        return decoded
    except (
        binascii.Error,
        ValueError,
        UnicodeError,
        SessionCryptoError,
    ) as exc:
        if isinstance(exc, SessionCryptoError):
            raise
        raise SessionCryptoError("payload criptográfico inválido") from exc


def _aad(
    *,
    lease_id: UUID,
    realm_id: str,
    publisher_id: UUID,
    local_generation: int,
    expires_at: datetime | None,
    key_version: int,
    payload_schema_version: int,
) -> bytes:
    data = {
        "expires_at": _utc_text(expires_at),
        "key_version": key_version,
        "lease_id": str(lease_id),
        "local_generation": local_generation,
        "publisher_id": str(publisher_id),
        "realm_id": realm_id,
        "schema_version": payload_schema_version,
    }
    return json.dumps(
        data,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


class SessionCryptoKeyring:
    def __init__(
        self,
        *,
        keys: Mapping[int, bytes],
        active_key_version: int,
    ) -> None:
        normalized = {int(version): bytes(key) for version, key in keys.items()}
        if (
            not normalized
            or active_key_version not in normalized
            or any(version < 1 for version in normalized)
            or any(len(key) != 32 for key in normalized.values())
        ):
            raise SessionCryptoError("keyring de sessão inválido")
        self._keys = normalized
        self._active_key_version = active_key_version

    @property
    def active_key_version(self) -> int:
        return self._active_key_version

    def encrypt(
        self,
        plaintext: bytes,
        *,
        lease_id: UUID,
        realm_id: str,
        publisher_id: UUID,
        local_generation: int,
        expires_at: datetime | None,
        payload_schema_version: int,
    ) -> EncryptedSessionPayload:
        key_version = self._active_key_version
        nonce = os.urandom(12)
        aad = _aad(
            lease_id=lease_id,
            realm_id=realm_id,
            publisher_id=publisher_id,
            local_generation=local_generation,
            expires_at=expires_at,
            key_version=key_version,
            payload_schema_version=payload_schema_version,
        )
        ciphertext = AESGCM(self._keys[key_version]).encrypt(
            nonce,
            plaintext,
            aad,
        )
        return EncryptedSessionPayload(
            ciphertext=_b64encode(ciphertext),
            nonce=_b64encode(nonce),
            key_version=key_version,
        )

    def decrypt(
        self,
        encrypted: EncryptedSessionPayload,
        *,
        lease_id: UUID,
        realm_id: str,
        publisher_id: UUID,
        local_generation: int,
        expires_at: datetime | None,
        payload_schema_version: int,
    ) -> bytes:
        key = self._keys.get(encrypted.key_version)
        if key is None:
            raise SessionCryptoError("key version indisponível")
        try:
            nonce = _b64decode(encrypted.nonce)
            ciphertext = _b64decode(encrypted.ciphertext)
            if len(nonce) != 12:
                raise SessionCryptoError("nonce inválido")
            aad = _aad(
                lease_id=lease_id,
                realm_id=realm_id,
                publisher_id=publisher_id,
                local_generation=local_generation,
                expires_at=expires_at,
                key_version=encrypted.key_version,
                payload_schema_version=payload_schema_version,
            )
            return AESGCM(key).decrypt(nonce, ciphertext, aad)
        except (InvalidTag, ValueError, SessionCryptoError) as exc:
            raise SessionCryptoError("falha de autenticação da sessão") from exc


def load_session_broker_security(
    *,
    fingerprint_key_encoded: str,
    keyring_json: str,
    active_key_version: int,
) -> tuple[SessionCryptoKeyring | None, bytes | None]:
    fingerprint_text = str(fingerprint_key_encoded)
    keyring_text = str(keyring_json).strip()

    if not fingerprint_text and not keyring_text:
        return None, None
    if not fingerprint_text or not keyring_text:
        raise SessionCryptoError("configuração de sessão incompleta")

    try:
        fingerprint_key = _b64decode(fingerprint_text)
        if len(fingerprint_key) != 32:
            raise SessionCryptoError("fingerprint key inválida")
        parsed = json.loads(keyring_text)
        if not isinstance(parsed, dict) or not parsed:
            raise SessionCryptoError("keyring inválido")
        keys: dict[int, bytes] = {}
        for raw_version, raw_key in parsed.items():
            version = int(raw_version)
            key = _b64decode(str(raw_key))
            if len(key) != 32:
                raise SessionCryptoError("keyring inválido")
            keys[version] = key
        crypto = SessionCryptoKeyring(
            keys=keys,
            active_key_version=active_key_version,
        )
        return crypto, fingerprint_key
    except (
        ValueError,
        TypeError,
        json.JSONDecodeError,
        SessionCryptoError,
    ) as exc:
        if isinstance(exc, SessionCryptoError):
            raise
        raise SessionCryptoError("configuração de sessão inválida") from exc
