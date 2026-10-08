from __future__ import annotations

import base64
import json

import pytest

from app.security.session_crypto import (
    SessionCryptoError,
    load_session_broker_security,
)


def _b64(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def test_session_broker_security_config_is_absent_by_default():
    crypto, fingerprint = load_session_broker_security(
        fingerprint_key_encoded="",
        keyring_json="",
        active_key_version=1,
    )
    assert crypto is None
    assert fingerprint is None


def test_session_broker_security_config_loads_versioned_keyring():
    crypto, fingerprint = load_session_broker_security(
        fingerprint_key_encoded=_b64(b"F" * 32),
        keyring_json=json.dumps(
            {
                "1": _b64(b"A" * 32),
                "2": _b64(b"B" * 32),
            }
        ),
        active_key_version=2,
    )
    assert crypto is not None
    assert crypto.active_key_version == 2
    assert fingerprint == b"F" * 32


@pytest.mark.parametrize(
    ("fingerprint", "keyring"),
    [
        ("", json.dumps({"1": _b64(b"A" * 32)})),
        (_b64(b"F" * 32), ""),
        (_b64(b"short"), json.dumps({"1": _b64(b"A" * 32)})),
        (_b64(b"F" * 32), json.dumps({"1": _b64(b"short")})),
        (_b64(b"F" * 32), "{not-json"),
    ],
)
def test_session_broker_security_config_invalid_is_fail_closed(
    fingerprint: str,
    keyring: str,
):
    with pytest.raises(SessionCryptoError):
        load_session_broker_security(
            fingerprint_key_encoded=fingerprint,
            keyring_json=keyring,
            active_key_version=1,
        )


_BASE64URL_ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_"


def _make_noncanonical_same_bytes(value: str) -> str:
    index = _BASE64URL_ALPHABET.index(value[-1])
    assert index % 4 == 0
    return value[:-1] + _BASE64URL_ALPHABET[index + 1]


@pytest.mark.parametrize(
    "mutate",
    [
        lambda value: "!" + value,
        lambda value: value + "\n",
        lambda value: value + "=",
        _make_noncanonical_same_bytes,
    ],
)
def test_session_broker_security_config_rejects_noncanonical_fingerprint_key(
    mutate,
):
    valid = _b64(b"F" * 32)
    with pytest.raises(SessionCryptoError):
        load_session_broker_security(
            fingerprint_key_encoded=mutate(valid),
            keyring_json=json.dumps({"1": _b64(b"A" * 32)}),
            active_key_version=1,
        )


@pytest.mark.parametrize(
    "mutate",
    [
        lambda value: "!" + value,
        lambda value: value + "\n",
        lambda value: value + "=",
        _make_noncanonical_same_bytes,
    ],
)
def test_session_broker_security_config_rejects_noncanonical_keyring_key(
    mutate,
):
    valid = _b64(b"A" * 32)
    with pytest.raises(SessionCryptoError):
        load_session_broker_security(
            fingerprint_key_encoded=_b64(b"F" * 32),
            keyring_json=json.dumps({"1": mutate(valid)}),
            active_key_version=1,
        )
