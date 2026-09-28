from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from typing import Any

from pywebpush import WebPushException, webpush
from requests import exceptions as requests_exceptions

from app.repositories.events import PushInstallation


class PermanentPushError(Exception):
    def __init__(self) -> None:
        super().__init__("Falha permanente ao enviar Web Push.")


class TransientPushError(Exception):
    def __init__(self) -> None:
        super().__init__("Falha transitória ao enviar Web Push.")


WebPushSender = Callable[..., Any]
_SAFE_PAYLOAD_KEYS = ("event_id", "title", "body", "url")


class WebPushGateway:
    def __init__(
        self,
        *,
        vapid_private_key: str,
        vapid_subject: str,
        sender: WebPushSender = webpush,
        timeout_seconds: float = 5.0,
    ) -> None:
        self._vapid_private_key = vapid_private_key
        self._vapid_subject = vapid_subject
        self._sender = sender
        self._timeout_seconds = timeout_seconds

    def __repr__(self) -> str:
        return (
            "WebPushGateway("
            f"vapid_subject={self._vapid_subject!r}, "
            f"timeout_seconds={self._timeout_seconds!r})"
        )

    def send(
        self,
        installation: PushInstallation,
        payload: Mapping[str, object],
    ) -> None:
        subscription_info = {
            "endpoint": installation.endpoint,
            "keys": {
                "p256dh": installation.p256dh,
                "auth": installation.auth,
            },
        }
        safe_payload = {
            key: payload[key]
            for key in _SAFE_PAYLOAD_KEYS
        }

        try:
            self._sender(
                subscription_info=subscription_info,
                data=json.dumps(
                    safe_payload,
                    ensure_ascii=False,
                    separators=(",", ":"),
                ),
                vapid_private_key=self._vapid_private_key,
                vapid_claims={"sub": self._vapid_subject},
                timeout=self._timeout_seconds,
            )
        except WebPushException as exc:
            self._raise_provider_error(exc)
        except (
            requests_exceptions.RequestException,
            TimeoutError,
        ):
            raise TransientPushError() from None

    @staticmethod
    def _raise_provider_error(exc: WebPushException) -> None:
        status_code = exc.status_code
        if status_code == 429 or (
            status_code is not None and status_code >= 500
        ):
            raise TransientPushError() from None
        if status_code is not None and 400 <= status_code < 500:
            raise PermanentPushError() from None
        raise TransientPushError() from None
