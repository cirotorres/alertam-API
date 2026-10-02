from __future__ import annotations

import hashlib
import hmac

from app.core.errors import (
    InvalidDeviceCredentialsError,
    InvalidViewCredentialsError,
)


def hash_secret(secret: str) -> str:
    return hashlib.sha256(secret.encode()).hexdigest()


def verify_secret(secret: str, expected_hash: str) -> bool:
    received_hash = hash_secret(secret)
    return hmac.compare_digest(received_hash, expected_hash)


def _parse_authorization(
    header: str | None,
    expected_scheme: str,
    error: Exception,
) -> str:
    if header is None:
        raise error

    parts = header.split()
    if len(parts) != 2 or parts[0].casefold() != expected_scheme.casefold():
        raise error

    token = parts[1].strip()
    if not token:
        raise error
    return token


def parse_device_authorization(header: str | None) -> str:
    return _parse_authorization(
        header,
        "Device",
        InvalidDeviceCredentialsError(),
    )


def parse_bearer_authorization(header: str | None) -> str:
    return _parse_authorization(
        header,
        "Bearer",
        InvalidViewCredentialsError(),
    )


def parse_mobile_pairing_authorization(
    header: str | None,
) -> tuple[str, str]:
    if header is None:
        raise InvalidViewCredentialsError()
    parts = header.split()
    if len(parts) != 2 or not parts[1].strip():
        raise InvalidViewCredentialsError()
    scheme = parts[0].casefold()
    if scheme == "bearer":
        return ("view", parts[1].strip())
    if scheme == "pairing":
        return ("ticket", parts[1].strip())
    raise InvalidViewCredentialsError()
