from __future__ import annotations

from datetime import datetime, timezone
import json
from uuid import UUID

import pytest
from pydantic import SecretStr

from app.models.session_broker import SessionCookieIn, SessionLeasePublishRequest
from app.security.session_crypto import (
    EncryptedSessionPayload,
    SessionCryptoError,
    SessionCryptoKeyring,
    canonical_session_payload,
    session_payload_fingerprint,
)


LEASE_A = UUID("11111111-1111-1111-1111-111111111111")
LEASE_B = UUID("22222222-2222-2222-2222-222222222222")
PUBLISHER = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
EXPIRES = datetime(2026, 10, 9, 12, 0, tzinfo=timezone.utc)


def _request(*, reverse: bool = False, value: str = "cookie-secret"):
    cookies = [
        SessionCookieIn(name="B", value=SecretStr("second"), expiry=None),
        SessionCookieIn(name="A", value=SecretStr(value), expiry=1791547200),
    ]
    if reverse:
        cookies.reverse()
    return SessionLeasePublishRequest(
        realm_id="webpilot-pecem",
        publisher_id=PUBLISHER,
        local_generation=7,
        expires_at=EXPIRES,
        cookies=cookies,
    )


def test_canonical_payload_and_hmac_are_order_independent_and_keyed():
    left = canonical_session_payload(_request(reverse=False))
    right = canonical_session_payload(_request(reverse=True))
    assert left == right
    assert b"cookie-secret" in left

    fingerprint = session_payload_fingerprint(left, b"fingerprint-key")
    assert fingerprint == session_payload_fingerprint(right, b"fingerprint-key")
    assert fingerprint != session_payload_fingerprint(right, b"other-key")
    assert "cookie-secret" not in fingerprint
    assert len(fingerprint) == 64


def test_session_lease_expiry_requires_timezone_and_normalizes_utc():
    request = SessionLeasePublishRequest(
        realm_id="webpilot-pecem",
        publisher_id=PUBLISHER,
        local_generation=8,
        expires_at="2026-10-09T09:00:00-03:00",
        cookies=[
            SessionCookieIn(name="A", value=SecretStr("one"), expiry=None),
        ],
    )
    assert request.expires_at == EXPIRES

    with pytest.raises(ValueError):
        SessionLeasePublishRequest(
            realm_id="webpilot-pecem",
            publisher_id=PUBLISHER,
            local_generation=8,
            expires_at="2026-10-09T12:00:00",
            cookies=[
                SessionCookieIn(name="A", value=SecretStr("one"), expiry=None),
            ],
        )


def test_duplicate_cookie_names_are_rejected_before_crypto():
    with pytest.raises(ValueError):
        SessionLeasePublishRequest(
            realm_id="webpilot-pecem",
            publisher_id=PUBLISHER,
            local_generation=8,
            expires_at=EXPIRES,
            cookies=[
                SessionCookieIn(name="A", value=SecretStr("one"), expiry=None),
                SessionCookieIn(name="A", value=SecretStr("two"), expiry=None),
            ],
        )


def test_aes_gcm_roundtrip_binds_immutable_aad_and_hides_secret():
    crypto = SessionCryptoKeyring(
        keys={1: b"A" * 32},
        active_key_version=1,
    )
    plaintext = canonical_session_payload(_request())
    encrypted = crypto.encrypt(
        plaintext,
        lease_id=LEASE_A,
        realm_id="webpilot-pecem",
        publisher_id=PUBLISHER,
        local_generation=7,
        expires_at=EXPIRES,
        payload_schema_version=1,
    )

    assert encrypted.key_version == 1
    assert encrypted.nonce
    assert encrypted.ciphertext
    assert "cookie-secret" not in encrypted.ciphertext
    assert "cookie-secret" not in repr(encrypted)

    decrypted = crypto.decrypt(
        encrypted,
        lease_id=LEASE_A,
        realm_id="webpilot-pecem",
        publisher_id=PUBLISHER,
        local_generation=7,
        expires_at=EXPIRES,
        payload_schema_version=1,
    )
    assert decrypted == plaintext

    with pytest.raises(SessionCryptoError):
        crypto.decrypt(
            encrypted,
            lease_id=LEASE_B,
            realm_id="webpilot-pecem",
            publisher_id=PUBLISHER,
            local_generation=7,
            expires_at=EXPIRES,
            payload_schema_version=1,
        )
    with pytest.raises(SessionCryptoError):
        crypto.decrypt(
            encrypted,
            lease_id=LEASE_A,
            realm_id="other-realm",
            publisher_id=PUBLISHER,
            local_generation=7,
            expires_at=EXPIRES,
            payload_schema_version=1,
        )


def test_aes_gcm_rejects_nonce_ciphertext_expiry_and_key_version_swap():
    crypto = SessionCryptoKeyring(
        keys={1: b"A" * 32, 2: b"B" * 32},
        active_key_version=1,
    )
    first = crypto.encrypt(
        b"first",
        lease_id=LEASE_A,
        realm_id="webpilot-pecem",
        publisher_id=PUBLISHER,
        local_generation=7,
        expires_at=EXPIRES,
        payload_schema_version=1,
    )
    second = crypto.encrypt(
        b"second",
        lease_id=LEASE_B,
        realm_id="webpilot-pecem",
        publisher_id=PUBLISHER,
        local_generation=8,
        expires_at=EXPIRES,
        payload_schema_version=1,
    )

    with pytest.raises(SessionCryptoError):
        crypto.decrypt(
            EncryptedSessionPayload(
                ciphertext=first.ciphertext,
                nonce=second.nonce,
                key_version=first.key_version,
            ),
            lease_id=LEASE_A,
            realm_id="webpilot-pecem",
            publisher_id=PUBLISHER,
            local_generation=7,
            expires_at=EXPIRES,
            payload_schema_version=1,
        )

    with pytest.raises(SessionCryptoError):
        crypto.decrypt(
            first,
            lease_id=LEASE_A,
            realm_id="webpilot-pecem",
            publisher_id=PUBLISHER,
            local_generation=7,
            expires_at=datetime(2026, 10, 9, 12, 1, tzinfo=timezone.utc),
            payload_schema_version=1,
        )

    with pytest.raises(SessionCryptoError):
        crypto.decrypt(
            EncryptedSessionPayload(
                ciphertext=first.ciphertext,
                nonce=first.nonce,
                key_version=2,
            ),
            lease_id=LEASE_A,
            realm_id="webpilot-pecem",
            publisher_id=PUBLISHER,
            local_generation=7,
            expires_at=EXPIRES,
            payload_schema_version=1,
        )

    tampered = first.ciphertext[:-1] + (
        "A" if first.ciphertext[-1] != "A" else "B"
    )
    with pytest.raises(SessionCryptoError):
        crypto.decrypt(
            EncryptedSessionPayload(
                ciphertext=tampered,
                nonce=first.nonce,
                key_version=first.key_version,
            ),
            lease_id=LEASE_A,
            realm_id="webpilot-pecem",
            publisher_id=PUBLISHER,
            local_generation=7,
            expires_at=EXPIRES,
            payload_schema_version=1,
        )


def test_keyring_rotation_uses_active_key_and_old_key_is_decrypt_only():
    old = SessionCryptoKeyring(keys={1: b"A" * 32}, active_key_version=1)
    encrypted_old = old.encrypt(
        b"payload",
        lease_id=LEASE_A,
        realm_id="webpilot-pecem",
        publisher_id=PUBLISHER,
        local_generation=1,
        expires_at=None,
        payload_schema_version=1,
    )

    rotated = SessionCryptoKeyring(
        keys={1: b"A" * 32, 2: b"B" * 32},
        active_key_version=2,
    )
    assert rotated.decrypt(
        encrypted_old,
        lease_id=LEASE_A,
        realm_id="webpilot-pecem",
        publisher_id=PUBLISHER,
        local_generation=1,
        expires_at=None,
        payload_schema_version=1,
    ) == b"payload"

    encrypted_new = rotated.encrypt(
        b"new",
        lease_id=LEASE_B,
        realm_id="webpilot-pecem",
        publisher_id=PUBLISHER,
        local_generation=2,
        expires_at=None,
        payload_schema_version=1,
    )
    assert encrypted_new.key_version == 2

    wrong = SessionCryptoKeyring(keys={2: b"B" * 32}, active_key_version=2)
    with pytest.raises(SessionCryptoError):
        wrong.decrypt(
            encrypted_old,
            lease_id=LEASE_A,
            realm_id="webpilot-pecem",
            publisher_id=PUBLISHER,
            local_generation=1,
            expires_at=None,
            payload_schema_version=1,
        )


@pytest.mark.parametrize(
    "keys, active",
    [
        ({}, 1),
        ({1: b"short"}, 1),
        ({1: b"A" * 32}, 2),
    ],
)
def test_invalid_keyring_is_fail_closed(keys, active):
    with pytest.raises(SessionCryptoError):
        SessionCryptoKeyring(keys=keys, active_key_version=active)


SESSION_PAYLOAD_LIMIT = 262_144


def _raw_canonical_payload_for_test(request: SessionLeasePublishRequest) -> bytes:
    payload = {
        "cookies": [
            {
                "expiry": item.expiry,
                "name": item.name,
                "value": item.value.get_secret_value(),
            }
            for item in sorted(request.cookies, key=lambda item: item.name)
        ],
        "expires_at": (
            None
            if request.expires_at is None
            else request.expires_at.astimezone(timezone.utc)
            .isoformat(timespec="microseconds")
            .replace("+00:00", "Z")
        ),
        "local_generation": request.local_generation,
        "publisher_id": str(request.publisher_id),
        "realm_id": request.realm_id,
    }
    return json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _request_at_canonical_size(target_size: int) -> SessionLeasePublishRequest:
    fixed = [
        SessionCookieIn(
            name=f"cookie-{index:02d}",
            value=SecretStr("x" * 4096),
            expiry=None,
        )
        for index in range(63)
    ]
    probe = SessionLeasePublishRequest(
        realm_id="webpilot-pecem",
        publisher_id=PUBLISHER,
        local_generation=99,
        expires_at=None,
        cookies=tuple(
            fixed
            + [
                SessionCookieIn(
                    name="cookie-63",
                    value=SecretStr("x"),
                    expiry=None,
                )
            ]
        ),
    )
    base_size = len(_raw_canonical_payload_for_test(probe))
    last_length = 1 + (target_size - base_size)
    assert 1 <= last_length <= 4096
    return SessionLeasePublishRequest(
        realm_id="webpilot-pecem",
        publisher_id=PUBLISHER,
        local_generation=99,
        expires_at=None,
        cookies=tuple(
            fixed
            + [
                SessionCookieIn(
                    name="cookie-63",
                    value=SecretStr("x" * last_length),
                    expiry=None,
                )
            ]
        ),
    )


def test_canonical_payload_total_limit_boundaries():
    below = _request_at_canonical_size(SESSION_PAYLOAD_LIMIT - 1)
    on_limit = _request_at_canonical_size(SESSION_PAYLOAD_LIMIT)
    above = _request_at_canonical_size(SESSION_PAYLOAD_LIMIT + 1)

    assert len(canonical_session_payload(below)) == SESSION_PAYLOAD_LIMIT - 1
    assert len(canonical_session_payload(on_limit)) == SESSION_PAYLOAD_LIMIT

    with pytest.raises(ValueError):
        canonical_session_payload(above)


@pytest.mark.parametrize(
    ("field", "mutation"),
    [
        ("nonce", lambda value: "!" + value),
        ("nonce", lambda value: value + "\n"),
        ("nonce", lambda value: value + "="),
        ("ciphertext", lambda value: "!" + value),
        ("ciphertext", lambda value: value + "\n"),
        ("ciphertext", lambda value: value + "="),
    ],
)
def test_aes_gcm_rejects_malformed_base64url(field, mutation):
    crypto = SessionCryptoKeyring(
        keys={1: b"A" * 32},
        active_key_version=1,
    )
    encrypted = crypto.encrypt(
        b"strict-base64url",
        lease_id=LEASE_A,
        realm_id="webpilot-pecem",
        publisher_id=PUBLISHER,
        local_generation=1,
        expires_at=None,
        payload_schema_version=1,
    )
    malformed = EncryptedSessionPayload(
        ciphertext=(
            mutation(encrypted.ciphertext)
            if field == "ciphertext"
            else encrypted.ciphertext
        ),
        nonce=(
            mutation(encrypted.nonce)
            if field == "nonce"
            else encrypted.nonce
        ),
        key_version=encrypted.key_version,
    )

    with pytest.raises(SessionCryptoError):
        crypto.decrypt(
            malformed,
            lease_id=LEASE_A,
            realm_id="webpilot-pecem",
            publisher_id=PUBLISHER,
            local_generation=1,
            expires_at=None,
            payload_schema_version=1,
        )
