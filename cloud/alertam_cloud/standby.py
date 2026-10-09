"""Headless Cloud collector kept strictly in standby."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable, Protocol


class SessionProvider(Protocol):
    @property
    def current_lease(self): ...

    def prime(self) -> bool: ...
    def invalidate_current(self) -> bool: ...


class HttpClient(Protocol):
    def get(self, url: str): ...


@dataclass(frozen=True)
class StandbyStatus:
    realm_id: str | None
    realm_epoch: int | None
    auth_state: str
    last_collection_at: datetime | None
    last_collection_result: str
    maneuver_count: int
    weather_ok: bool


def _status_name(result: object) -> str:
    status = getattr(result, "status", None)
    name = getattr(status, "name", None)
    if isinstance(name, str):
        return name
    value = getattr(status, "value", None)
    if isinstance(value, str):
        return value
    return str(status)


class StandbyCollector:
    def __init__(
        self,
        session_provider: SessionProvider,
        http_client: HttpClient,
        *,
        maneuver_url: str,
        weather_url: str,
        parse_maneuvers: Callable[[bytes, datetime], object],
        parse_weather: Callable[[bytes, datetime], object],
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self.session_provider = session_provider
        self.http_client = http_client
        self.maneuver_url = maneuver_url
        self.weather_url = weather_url
        self.parse_maneuvers = parse_maneuvers
        self.parse_weather = parse_weather
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def run_cycle(self) -> StandbyStatus:
        now = self._clock()
        if not self.session_provider.prime():
            return self._status(
                now=now,
                result="AUTH_UNAVAILABLE",
                maneuver_count=0,
                weather_ok=False,
            )

        maneuvers = self.http_client.get(self.maneuver_url)
        maneuver_status = _status_name(maneuvers)
        if maneuver_status == "SESSION_EXPIRED":
            self.session_provider.invalidate_current()
            return self._status(
                now=now,
                result="AUTH_UNAVAILABLE",
                maneuver_count=0,
                weather_ok=False,
            )
        if maneuver_status != "OK":
            return self._status(
                now=now,
                result="HTTP_ERROR",
                maneuver_count=0,
                weather_ok=False,
            )

        try:
            maneuver_snapshot = self.parse_maneuvers(
                bytes(getattr(maneuvers, "body", b"")),
                now,
            )
        except Exception:  # noqa: BLE001
            return self._status(
                now=now,
                result="PARSE_ERROR",
                maneuver_count=0,
                weather_ok=False,
            )

        weather = self.http_client.get(self.weather_url)
        weather_status = _status_name(weather)
        if weather_status == "SESSION_EXPIRED":
            self.session_provider.invalidate_current()
            return self._status(
                now=now,
                result="AUTH_UNAVAILABLE",
                maneuver_count=len(getattr(maneuver_snapshot, "navios", ())),
                weather_ok=False,
            )
        if weather_status != "OK":
            return self._status(
                now=now,
                result="HTTP_ERROR",
                maneuver_count=len(getattr(maneuver_snapshot, "navios", ())),
                weather_ok=False,
            )

        try:
            self.parse_weather(
                bytes(getattr(weather, "body", b"")),
                now,
            )
        except Exception:  # noqa: BLE001
            return self._status(
                now=now,
                result="PARSE_ERROR",
                maneuver_count=len(getattr(maneuver_snapshot, "navios", ())),
                weather_ok=False,
            )

        return self._status(
            now=now,
            result="OK",
            maneuver_count=len(getattr(maneuver_snapshot, "navios", ())),
            weather_ok=True,
        )

    def _status(
        self,
        *,
        now: datetime,
        result: str,
        maneuver_count: int,
        weather_ok: bool,
    ) -> StandbyStatus:
        lease = self.session_provider.current_lease
        return StandbyStatus(
            realm_id=(getattr(lease, "realm_id", None) if lease is not None else None),
            realm_epoch=(
                getattr(lease, "realm_epoch", None)
                if lease is not None
                else None
            ),
            auth_state="AUTH_READY" if lease is not None else "AUTH_UNAVAILABLE",
            last_collection_at=now,
            last_collection_result=result,
            maneuver_count=max(0, int(maneuver_count)),
            weather_ok=bool(weather_ok),
        )


def build_canonical_standby(
    session_provider: object,
    *,
    transport: object,
    timeout_seconds: float = 5.0,
    clock: Callable[[], datetime] | None = None,
) -> StandbyCollector:
    """Compose the canonical Desktop HTTP/parser wheel without importing UI/browser."""
    from alertam.application.webpilot_auth import (
        WEBPILOT_AUTH_REALM,
        WebPilotAuthCoordinator,
    )
    from alertam.domain import parse_grid_rows
    from alertam.domain.webpilot_weather_parser import parse_webpilot_weather
    from alertam.infrastructure.webpilot_grid_html import extract_grid_rows
    from alertam.infrastructure.webpilot_http import WebPilotHttpClient
    from alertam.infrastructure.webpilot_weather import WEBPILOT_WEATHER_URL
    from alertam.settings import WEBPILOT_URL

    auth = WebPilotAuthCoordinator(
        WEBPILOT_AUTH_REALM,
        session_provider,
    )
    session_provider.attach(auth)
    http_client = WebPilotHttpClient(
        auth,
        timeout=timeout_seconds,
        transport=transport,
        recovery_wait_seconds=0,
    )

    def parse_maneuvers(body: bytes, now: datetime):
        return parse_grid_rows(
            extract_grid_rows(body),
            agora=now,
        )

    def parse_weather(body: bytes, now: datetime):
        return parse_webpilot_weather(body, consulted_at=now)

    return StandbyCollector(
        session_provider,
        http_client,
        maneuver_url=WEBPILOT_URL,
        weather_url=WEBPILOT_WEATHER_URL,
        parse_maneuvers=parse_maneuvers,
        parse_weather=parse_weather,
        clock=clock,
    )
