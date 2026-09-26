from __future__ import annotations

import hashlib

import pytest

from app.core.errors import (
    InvalidDeviceCredentialsError,
    InvalidViewCredentialsError,
)
from app.security.credentials import (
    hash_secret,
    parse_bearer_authorization,
    parse_device_authorization,
    verify_secret,
)


def test_hash_secret_uses_sha256_hex_digest():
    secret = "segredo-local"

    assert hash_secret(secret) == hashlib.sha256(secret.encode()).hexdigest()


def test_verify_secret_accepts_match_and_rejects_different_secret():
    expected_hash = hash_secret("segredo-correto")

    assert verify_secret("segredo-correto", expected_hash) is True
    assert verify_secret("segredo-incorreto", expected_hash) is False

def test_parse_device_authorization_extracts_only_token():
    assert (
        parse_device_authorization("Device token-seguro")
        == "token-seguro"
    )


def test_parse_bearer_authorization_extracts_only_token():
    assert (
        parse_bearer_authorization("Bearer token-leitura")
        == "token-leitura"
    )


@pytest.mark.parametrize(
    "header",
    [
        None,
        "",
        "Device",
        "Bearer token",
        "Device ",
        "Device token com espaco",
    ],
)
def test_invalid_device_header_returns_generic_401(header):
    with pytest.raises(InvalidDeviceCredentialsError) as exc:
        parse_device_authorization(header)

    assert exc.value.status_code == 401

    assert exc.value.code == "invalid_device_credentials"
    assert exc.value.message == "Credenciais do dispositivo inválidas."


@pytest.mark.parametrize(
    "header",
    [
        None,
        "",
        "Bearer",
        "Device token",
        "Bearer ",
        "Bearer token com espaco",
    ],
)
def test_invalid_bearer_header_returns_generic_401(header):
    with pytest.raises(InvalidViewCredentialsError) as exc:
        parse_bearer_authorization(header)

    assert exc.value.status_code == 401
    assert exc.value.code == "invalid_view_credentials"
    assert exc.value.message == "Credenciais de leitura inválidas."


def test_invalid_header_error_never_echoes_received_secret():
    raw = "Device segredo-que-nao-pode-vazar extra"

    with pytest.raises(InvalidDeviceCredentialsError) as exc:
        parse_device_authorization(raw)

    assert "segredo-que-nao-pode-vazar" not in str(exc.value)
