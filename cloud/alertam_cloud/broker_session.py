"""Cloud-side SessionLease broker adapter for standby collection only."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
import json
import logging
from typing import Any, Callable, Mapping, Protocol, Sequence
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import HTTPRedirectHandler, Request, build_opener
from uuid import UUID


log = logging.getLogger(__name__)
_LOOPBACK_HOSTS = {"localhost", "127.0.0.1", "::1"}


class _RejectRedirects(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


_DEFAULT_OPENER = build_opener(_RejectRedirects()).open


class BrokerSessionError(RuntimeError):
    pass


class BrokerLeaseUnavailable(BrokerSessionError):
    pass


class BrokerUnauthorized(BrokerSessionError):
    pass


@dataclass(frozen=True)
class SessionCookie:
    name: str
    value: str = field(repr=False)
    expiry: int | None = None


@dataclass(frozen=True)
class BrokerLease:
    lease_id: UUID
    realm_id: str
    publisher_id: UUID
    local_generation: int
    realm_epoch: int
    received_at: datetime
    expires_at: datetime | None
    status: str
    cookies: tuple[SessionCookie, ...] = field(repr=False)


class _Response(Protocol):
    status: int
    headers: Mapping[str, str]

    def __enter__(self) -> "_Response": ...
    def __exit__(self, *args: object) -> bool | None: ...
    def read(self) -> bytes: ...


class LocalAuthCoordinator(Protocol):
    def publish(
        self,
        cookies: Sequence[Mapping[str, object]],
    ) -> object: ...


def _parse_datetime(value: object, *, nullable: bool = False) -> datetime | None:
    if value is None and nullable:
        return None
    if not isinstance(value, str) or not value:
        raise BrokerSessionError("Session broker payload inválido")
    raw = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        parsed = datetime.fromisoformat(raw)
    except ValueError as exc:
        raise BrokerSessionError("Session broker payload inválido") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise BrokerSessionError("Session broker payload inválido")
    return parsed


class SessionBrokerClient:
    def __init__(
        self,
        api_base_url: str,
        cloud_binding_id: UUID,
        credential: str,
        *,
        timeout_seconds: float = 5.0,
        opener: Callable[..., _Response] | None = None,
    ) -> None:
        self.api_base_url = str(api_base_url).rstrip("/")
        self.cloud_binding_id = UUID(str(cloud_binding_id))
        self._credential = str(credential)
        self.timeout_seconds = min(max(float(timeout_seconds), 0.1), 10.0)
        self._opener = opener or _DEFAULT_OPENER
        if not self._credential:
            raise ValueError("CloudBinding credential é obrigatória")
        self._validate_base_url()

    def __repr__(self) -> str:
        return (
            f"{type(self).__name__}("
            f"api_base_url={self.api_base_url!r}, "
            f"cloud_binding_id={self.cloud_binding_id!r}, "
            f"timeout_seconds={self.timeout_seconds!r})"
        )

    def _validate_base_url(self) -> None:
        parsed = urlparse(self.api_base_url)
        if parsed.scheme == "https" and parsed.hostname:
            return
        if parsed.scheme == "http" and parsed.hostname in _LOOPBACK_HOSTS:
            return
        raise ValueError("Session broker exige HTTPS fora de localhost/loopback")

    def _url(self, suffix: str = "") -> str:
        base = (
            f"{self.api_base_url}/api/v1/cloud-bindings/"
            f"{self.cloud_binding_id}/webpilot-session-lease"
        )
        return base + suffix

    def consume(self) -> BrokerLease:
        payload = self._request("GET", self._url())
        try:
            raw_cookies = payload["cookies"]
            if not isinstance(raw_cookies, list):
                raise TypeError
            cookies = tuple(
                SessionCookie(
                    name=str(item["name"]),
                    value=str(item["value"]),
                    expiry=item.get("expiry"),
                )
                for item in raw_cookies
            )
            lease = BrokerLease(
                lease_id=UUID(str(payload["lease_id"])),
                realm_id=str(payload["realm_id"]),
                publisher_id=UUID(str(payload["publisher_id"])),
                local_generation=int(payload["local_generation"]),
                realm_epoch=int(payload["realm_epoch"]),
                received_at=_parse_datetime(payload["received_at"]),
                expires_at=_parse_datetime(
                    payload.get("expires_at"),
                    nullable=True,
                ),
                status=str(payload["status"]),
                cookies=cookies,
            )
        except (
            KeyError,
            TypeError,
            ValueError,
            AttributeError,
            BrokerSessionError,
        ) as exc:
            raise BrokerSessionError("Session broker payload inválido") from exc

        if (
            not lease.realm_id
            or lease.local_generation <= 0
            or lease.realm_epoch <= 0
            or lease.status != "accepted"
            or not lease.cookies
        ):
            raise BrokerSessionError("Session broker payload inválido")
        return lease

    def invalidate(
        self,
        lease_id: UUID,
        realm_epoch: int,
    ) -> Mapping[str, Any]:
        return self._request(
            "POST",
            self._url("/invalidate"),
            {
                "lease_id": str(UUID(str(lease_id))),
                "realm_epoch": int(realm_epoch),
            },
        )

    def _request(
        self,
        method: str,
        url: str,
        payload: Mapping[str, object] | None = None,
    ) -> dict[str, Any]:
        body = None
        headers = {
            "Authorization": f"CloudBinding {self._credential}",
        }
        if payload is not None:
            body = json.dumps(
                dict(payload),
                ensure_ascii=False,
                separators=(",", ":"),
            ).encode("utf-8")
            headers["Content-Type"] = "application/json"

        request = Request(
            url,
            data=body,
            headers=headers,
            method=method,
        )
        try:
            with self._opener(
                request,
                timeout=self.timeout_seconds,
            ) as response:
                raw = response.read()
        except HTTPError as exc:
            code = int(exc.code)
            exc.close()
            if code == 404:
                raise BrokerLeaseUnavailable(
                    "SessionLease indisponível"
                ) from None
            if code == 403:
                raise BrokerUnauthorized(
                    "CloudBinding não autorizado"
                ) from None
            raise BrokerSessionError(
                f"Session broker HTTP {code}"
            ) from None
        except (URLError, TimeoutError, OSError):
            raise BrokerSessionError("Session broker indisponível") from None

        try:
            decoded = json.loads(raw.decode("utf-8"))
        except (UnicodeError, json.JSONDecodeError) as exc:
            raise BrokerSessionError("Session broker payload inválido") from exc
        if not isinstance(decoded, dict):
            raise BrokerSessionError("Session broker payload inválido")
        return decoded


class BrokerSessionProvider:
    """Adapta SessionLease do broker ao WebPilotAuthCoordinator canônico."""

    def __init__(self, broker: object) -> None:
        self._broker = broker
        self._auth: LocalAuthCoordinator | None = None
        self._current: BrokerLease | None = None
        self._rejected_identities: set[tuple[UUID, int]] = set()

    @property
    def current_identity(self) -> tuple[UUID, int] | None:
        current = self._current
        if current is None:
            return None
        return current.lease_id, current.realm_epoch

    @property
    def current_lease(self) -> BrokerLease | None:
        return self._current

    @property
    def auth_state(self) -> str:
        return "AUTH_READY" if self._current is not None else "AUTH_UNAVAILABLE"

    def attach(self, auth: LocalAuthCoordinator) -> None:
        self._auth = auth

    def prime(self) -> bool:
        if self._current is not None:
            return True
        lease = self._consume_safe()
        if lease is None:
            return False
        return self._accept_candidate(lease)

    def invalidate_current(self) -> bool:
        current = self._current
        if current is None:
            return False
        identity = (current.lease_id, current.realm_epoch)
        self._rejected_identities.add(identity)
        self._current = None
        try:
            self._broker.invalidate(*identity)
        except Exception as exc:  # noqa: BLE001
            log.warning(
                "SessionLease invalidation failed: %s",
                type(exc).__name__,
            )
            return False
        return True

    def request_recovery(self) -> bool:
        current = self._current
        if current is None:
            return False
        identity = (current.lease_id, current.realm_epoch)
        self._rejected_identities.add(identity)
        self._current = None
        try:
            self._broker.invalidate(*identity)
        except Exception as exc:  # noqa: BLE001
            log.warning(
                "SessionLease invalidation failed: %s",
                type(exc).__name__,
            )
            return False

        replacement = self._consume_safe()
        if replacement is None:
            self._current = None
            return False
        return self._accept_candidate(replacement)

    def _accept_candidate(self, lease: BrokerLease) -> bool:
        identity = (lease.lease_id, lease.realm_epoch)
        if identity in self._rejected_identities:
            self._current = None
            return False
        return self._publish(lease)

    def _consume_safe(self) -> BrokerLease | None:
        try:
            return self._broker.consume()
        except Exception as exc:  # noqa: BLE001
            log.warning(
                "SessionLease consume unavailable: %s",
                type(exc).__name__,
            )
            return None

    def _publish(self, lease: BrokerLease) -> bool:
        auth = self._auth
        if auth is None:
            log.warning("SessionLease provider sem auth coordinator")
            return False
        cookies = tuple(
            {
                "name": cookie.name,
                "value": cookie.value,
                "expiry": cookie.expiry,
            }
            for cookie in lease.cookies
        )
        auth.publish(cookies)
        self._current = lease
        return True
