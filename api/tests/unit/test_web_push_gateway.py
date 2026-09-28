from __future__ import annotations

from datetime import datetime, timezone
import json
from uuid import UUID

from pywebpush import WebPushException
from requests import exceptions as requests_exceptions

from app.infrastructure.web_push import (
    PermanentPushError,
    TransientPushError,
    WebPushGateway,
)
from app.repositories.events import PushInstallation, PushPreferences


NOW = datetime(2026, 9, 27, 18, 0, tzinfo=timezone.utc)
INSTALL_ID = UUID("70000000-0000-4000-8000-000000000001")
ENDPOINT = "https://push.example/private-subscription-token"


def installation() -> PushInstallation:
    return PushInstallation(
        installation_id=INSTALL_ID,
        device_id="pecem-01",
        endpoint=ENDPOINT,
        p256dh="p256dh-secret",
        auth="auth-secret",
        preferences=PushPreferences(),
        push_enabled_at=NOW,
        last_seen_at=NOW,
        last_foreground_at=None,
        active=True,
        created_at=NOW,
        updated_at=NOW,
    )


def payload(**extra):
    value = {
        "event_id": "70000000-0000-4000-8000-000000000010",
        "title": "Atracação confirmada",
        "body": "NAVIO A · Berço 4",
        "url": "/alertas?event=70000000-0000-4000-8000-000000000010",
    }
    value.update(extra)
    return value


def test_gateway_sends_only_safe_payload_with_vapid_and_five_second_timeout():
    observed = {}

    def sender(**kwargs):
        observed.update(kwargs)

    gateway = WebPushGateway(
        vapid_private_key="private-vapid",
        vapid_subject="mailto:alerts@example.com",
        sender=sender,
    )

    assert "private-vapid" not in repr(gateway)

    gateway.send(
        installation(),
        payload(internal_secret="must-not-be-sent"),
    )

    assert observed["subscription_info"] == {
        "endpoint": ENDPOINT,
        "keys": {
            "p256dh": "p256dh-secret",
            "auth": "auth-secret",
        },
    }
    assert json.loads(observed["data"]) == payload()
    assert observed["vapid_private_key"] == "private-vapid"
    assert observed["vapid_claims"] == {
        "sub": "mailto:alerts@example.com"
    }
    assert observed["timeout"] == 5.0


class FakeResponse:
    def __init__(self, status_code: int) -> None:
        self.status_code = status_code


def web_push_failure(status_code: int) -> WebPushException:
    return WebPushException(
        "provider details that must stay internal",
        response=FakeResponse(status_code),
    )

def test_gateway_classifies_non_retryable_4xx_as_permanent():
    for status_code in (400, 404, 410):
        def sender(**_kwargs):
            raise web_push_failure(status_code)

        gateway = WebPushGateway(
            vapid_private_key="private-vapid",
            vapid_subject="mailto:alerts@example.com",
            sender=sender,
        )

        try:
            gateway.send(installation(), payload())
        except PermanentPushError as exc:
            assert ENDPOINT not in str(exc)
            assert "p256dh-secret" not in str(exc)
            assert "provider details" not in str(exc)
        else:
            raise AssertionError(f"{status_code} deveria ser permanente")


def test_gateway_classifies_429_and_5xx_as_transient():
    for status_code in (429, 500, 503):
        def sender(**_kwargs):
            raise web_push_failure(status_code)

        gateway = WebPushGateway(
            vapid_private_key="private-vapid",
            vapid_subject="mailto:alerts@example.com",
            sender=sender,
        )

        try:
            gateway.send(installation(), payload())
        except TransientPushError as exc:
            assert ENDPOINT not in str(exc)
            assert "provider details" not in str(exc)
        else:
            raise AssertionError(f"{status_code} deveria ser transitório")


def test_gateway_classifies_network_and_timeout_as_transient():
    failures = [
        requests_exceptions.ConnectionError("connect failed"),
        requests_exceptions.Timeout("timed out"),
        TimeoutError("timed out"),
    ]

    for failure in failures:
        def sender(**_kwargs):
            raise failure

        gateway = WebPushGateway(
            vapid_private_key="private-vapid",
            vapid_subject="mailto:alerts@example.com",
            sender=sender,
        )

        try:
            gateway.send(installation(), payload())
        except TransientPushError as exc:
            assert ENDPOINT not in str(exc)
            assert "connect failed" not in str(exc)
        else:
            raise AssertionError("falha de rede deveria ser transitória")
