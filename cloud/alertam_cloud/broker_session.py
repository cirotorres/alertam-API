"""Cloud-side SessionLease broker adapter for standby collection only."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import json
import logging
import os
from pathlib import Path
import tempfile
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


class RejectedIdentityStoreError(BrokerSessionError):
    pass


RejectedIdentity = tuple[UUID, int]


class RejectedIdentityStore(Protocol):
    def contains(self, identity: RejectedIdentity) -> bool: ...
    def add(self, identity: RejectedIdentity) -> None: ...


class InMemoryRejectedIdentityStore:
    def __init__(self, *, max_entries: int = 256) -> None:
        self._max_entries = max(1, int(max_entries))
        self._items: list[RejectedIdentity] = []

    def contains(self, identity: RejectedIdentity) -> bool:
        return identity in self._items

    def add(self, identity: RejectedIdentity) -> None:
        normalized = (UUID(str(identity[0])), int(identity[1]))
        self._items = [item for item in self._items if item != normalized]
        self._items.append(normalized)
        if len(self._items) > self._max_entries:
            self._items = self._items[-self._max_entries:]


class FileRejectedIdentityStore:
    VERSION = 1

    def __init__(
        self,
        path: str | os.PathLike[str],
        *,
        max_entries: int = 256,
    ) -> None:
        self.path = Path(path)
        self.max_entries = max(1, int(max_entries))

    @classmethod
    def from_environment(cls) -> "FileRejectedIdentityStore":
        raw = os.environ.get(
            "ALERTAM_CLOUD_SESSION_TOMBSTONES_PATH",
            "/tmp/alertam-cloud/session-rejections.json",
        )
        return cls(raw)

    def contains(self, identity: RejectedIdentity) -> bool:
        normalized = (UUID(str(identity[0])), int(identity[1]))
        return normalized in self._load()

    def add(self, identity: RejectedIdentity) -> None:
        normalized = (UUID(str(identity[0])), int(identity[1]))
        items = [item for item in self._load() if item != normalized]
        items.append(normalized)
        self._write(items[-self.max_entries:])

    def _load(self) -> list[RejectedIdentity]:
        if not self.path.exists():
            return []
        try:
            decoded = json.loads(self.path.read_text(encoding="utf-8"))
            if (
                not isinstance(decoded, dict)
                or decoded.get("version") != self.VERSION
                or not isinstance(decoded.get("identities"), list)
            ):
                raise ValueError
            items: list[RejectedIdentity] = []
            for item in decoded["identities"]:
                if not isinstance(item, dict):
                    raise ValueError
                lease_id = UUID(str(item["lease_id"]))
                realm_epoch = int(item["realm_epoch"])
                if realm_epoch <= 0:
                    raise ValueError
                identity = (lease_id, realm_epoch)
                if identity not in items:
                    items.append(identity)
            return items[-self.max_entries:]
        except (
            OSError,
            UnicodeError,
            json.JSONDecodeError,
            KeyError,
            TypeError,
            ValueError,
        ) as exc:
            raise RejectedIdentityStoreError(
                "SessionLease rejection store inválido"
            ) from exc

    def _write(self, items: Sequence[RejectedIdentity]) -> None:
        payload = {
            "version": self.VERSION,
            "identities": [
                {
                    "lease_id": str(lease_id),
                    "realm_epoch": int(realm_epoch),
                }
                for lease_id, realm_epoch in items
            ],
        }
        parent = self.path.parent
        temp_path: Path | None = None
        try:
            parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            with tempfile.NamedTemporaryFile(
                "w",
                encoding="utf-8",
                dir=parent,
                prefix=f".{self.path.name}.",
                suffix=".tmp",
                delete=False,
            ) as handle:
                temp_path = Path(handle.name)
                json.dump(
                    payload,
                    handle,
                    ensure_ascii=False,
                    separators=(",", ":"),
                    sort_keys=True,
                )
                handle.flush()
                os.fsync(handle.fileno())
            os.chmod(temp_path, 0o600)
            os.replace(temp_path, self.path)
        except OSError as exc:
            raise RejectedIdentityStoreError(
                "SessionLease rejection store indisponível"
            ) from exc
        finally:
            if temp_path is not None and temp_path.exists():
                try:
                    temp_path.unlink()
                except OSError:
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

    def __init__(
        self,
        broker: object,
        *,
        clock: Callable[[], datetime] | None = None,
        rejection_store: RejectedIdentityStore | None = None,
    ) -> None:
        self._broker = broker
        self._auth: LocalAuthCoordinator | None = None
        self._current: BrokerLease | None = None
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._rejection_store = (
            rejection_store or FileRejectedIdentityStore.from_environment()
        )

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
        current = self._current
        if current is not None:
            if self._lease_time_valid(current):
                return True
            self._current = None

        lease = self._consume_safe()
        if lease is None:
            return False
        return self._accept_candidate(lease)

    def invalidate_current(self) -> bool:
        current = self._current
        if current is None:
            return False
        identity = (current.lease_id, current.realm_epoch)
        self._current = None
        if not self._remember_rejected(identity):
            return False
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
        self._current = None
        if not self._remember_rejected(identity):
            return False
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
        if not self._lease_time_valid(lease):
            self._current = None
            return False
        identity = (lease.lease_id, lease.realm_epoch)
        if self._is_rejected(identity):
            self._current = None
            return False
        return self._publish(lease)

    def _lease_time_valid(self, lease: BrokerLease) -> bool:
        expires_at = lease.expires_at
        if expires_at is None:
            return True
        if expires_at.tzinfo is None or expires_at.utcoffset() is None:
            log.warning("SessionLease expiry inválido")
            return False
        try:
            now = self._clock()
        except Exception as exc:  # noqa: BLE001
            log.warning("SessionLease clock indisponível: %s", type(exc).__name__)
            return False
        if (
            not isinstance(now, datetime)
            or now.tzinfo is None
            or now.utcoffset() is None
        ):
            log.warning("SessionLease clock inválido")
            return False
        return expires_at.astimezone(timezone.utc) > now.astimezone(timezone.utc)

    def _is_rejected(self, identity: RejectedIdentity) -> bool:
        try:
            return self._rejection_store.contains(identity)
        except Exception as exc:  # noqa: BLE001
            log.warning(
                "SessionLease rejection store unavailable: %s",
                type(exc).__name__,
            )
            return True

    def _remember_rejected(self, identity: RejectedIdentity) -> bool:
        try:
            self._rejection_store.add(identity)
            return True
        except Exception as exc:  # noqa: BLE001
            log.warning(
                "SessionLease rejection store unavailable: %s",
                type(exc).__name__,
            )
            return False

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
