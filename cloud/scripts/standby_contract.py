#!/usr/bin/env python3
"""Synthetic standby contract using the canonical Desktop wheel."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path
import sys
from uuid import UUID


CLOUD_DIR = Path(__file__).resolve().parents[1]
if str(CLOUD_DIR) not in sys.path:
    sys.path.insert(0, str(CLOUD_DIR))

from alertam_cloud.broker_session import (  # noqa: E402
    BrokerLease,
    BrokerLeaseUnavailable,
    BrokerSessionProvider,
    InMemoryRejectedIdentityStore,
    SessionCookie,
)
from alertam_cloud.standby import build_canonical_standby  # noqa: E402


GRID_FIXTURE_NAME = "grid_real_2026-09-21.html"
WEATHER_FIXTURE_NAME = "webpilot_weather_pecem.html"
NOW = datetime(2026, 10, 8, 12, 0, tzinfo=timezone.utc)
LEASE_A = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
LEASE_B = UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
PUBLISHER = UUID("cccccccc-cccc-cccc-cccc-cccccccccccc")


class RawResponse:
    def __init__(self, status_code: int, final_url: str, body: bytes) -> None:
        self.status_code = status_code
        self.final_url = final_url
        self.body = body


class FakeBroker:
    def __init__(self, leases: list[BrokerLease]) -> None:
        self._leases = list(leases)
        self.invalidated: list[tuple[UUID, int]] = []
        self.consume_calls = 0

    def consume(self) -> BrokerLease:
        self.consume_calls += 1
        if not self._leases:
            raise BrokerLeaseUnavailable("synthetic unavailable")
        return self._leases.pop(0)

    def invalidate(self, lease_id: UUID, realm_epoch: int) -> None:
        self.invalidated.append((lease_id, realm_epoch))


class FakeTransport:
    def __init__(
        self,
        *,
        grid: bytes,
        weather: bytes,
        login_maneuver_calls: int = 0,
    ) -> None:
        self.grid = grid
        self.weather = weather
        self.login_maneuver_calls = login_maneuver_calls
        self.calls: list[str] = []
        self._maneuver_calls = 0

    def __call__(self, url, headers, timeout):
        self.calls.append(url)
        if "hiPlanilhaManobrasCeara.aspx" in url:
            self._maneuver_calls += 1
            if self._maneuver_calls <= self.login_maneuver_calls:
                return RawResponse(
                    200,
                    "https://webpilot.cearapilots.com.br/WebPilot/admin/login.aspx",
                    b'<input id="tbSenha">',
                )
            return RawResponse(200, url, self.grid)
        if "grEstacaoMeteorologica.aspx" in url:
            return RawResponse(200, url, self.weather)
        raise AssertionError("unexpected synthetic WebPilot URL")


def _lease(lease_id: UUID, epoch: int, cookie: str) -> BrokerLease:
    return BrokerLease(
        lease_id=lease_id,
        realm_id="webpilot-pecem",
        publisher_id=PUBLISHER,
        local_generation=epoch,
        realm_epoch=epoch,
        received_at=NOW,
        expires_at=None,
        status="accepted",
        cookies=(SessionCookie("session", cookie, None),),
    )


def _collector(
    broker: FakeBroker,
    transport: FakeTransport,
):
    provider = BrokerSessionProvider(
        broker, rejection_store=InMemoryRejectedIdentityStore()
    )
    collector = build_canonical_standby(
        provider,
        transport=transport,
        timeout_seconds=1,
        clock=lambda: NOW,
    )
    return provider, collector


def _assert_success_cycle(grid: bytes, weather: bytes) -> None:
    broker = FakeBroker([_lease(LEASE_A, 7, "synthetic-a")])
    transport = FakeTransport(grid=grid, weather=weather)
    provider, collector = _collector(broker, transport)

    status = collector.run_cycle()

    assert status.last_collection_result == "OK"
    assert status.auth_state == "AUTH_READY"
    assert status.realm_id == "webpilot-pecem"
    assert status.realm_epoch == 7
    assert status.maneuver_count == 22
    assert status.weather_ok is True
    assert broker.invalidated == []
    assert provider.current_identity == (LEASE_A, 7)
    assert len(transport.calls) == 2


def _assert_semantic_login_switches_once(grid: bytes, weather: bytes) -> None:
    broker = FakeBroker(
        [
            _lease(LEASE_A, 7, "synthetic-a"),
            _lease(LEASE_B, 8, "synthetic-b"),
        ]
    )
    transport = FakeTransport(
        grid=grid,
        weather=weather,
        login_maneuver_calls=1,
    )
    provider, collector = _collector(broker, transport)

    status = collector.run_cycle()

    assert broker.invalidated == [(LEASE_A, 7)]
    assert broker.consume_calls == 2
    assert provider.current_identity == (LEASE_B, 8)
    assert status.last_collection_result == "OK"
    assert status.realm_epoch == 8
    assert status.maneuver_count == 22
    assert status.weather_ok is True
    assert len(transport.calls) == 3


def _assert_second_login_stops_without_loop(grid: bytes, weather: bytes) -> None:
    broker = FakeBroker(
        [
            _lease(LEASE_A, 7, "synthetic-a"),
            _lease(LEASE_B, 8, "synthetic-b"),
        ]
    )
    transport = FakeTransport(
        grid=grid,
        weather=weather,
        login_maneuver_calls=2,
    )
    provider, collector = _collector(broker, transport)

    status = collector.run_cycle()

    assert broker.invalidated == [(LEASE_A, 7), (LEASE_B, 8)]
    assert broker.consume_calls == 2
    assert provider.current_identity is None
    assert status.auth_state == "AUTH_UNAVAILABLE"
    assert status.last_collection_result == "AUTH_UNAVAILABLE"
    assert len(transport.calls) == 2


def _assert_no_lease_never_calls_webpilot(grid: bytes, weather: bytes) -> None:
    broker = FakeBroker([])
    transport = FakeTransport(grid=grid, weather=weather)
    provider, collector = _collector(broker, transport)

    status = collector.run_cycle()

    assert provider.current_identity is None
    assert status.auth_state == "AUTH_UNAVAILABLE"
    assert status.last_collection_result == "AUTH_UNAVAILABLE"
    assert transport.calls == []


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fixture", type=Path, required=True)
    args = parser.parse_args()

    grid_path = args.fixture
    weather_path = grid_path.with_name(WEATHER_FIXTURE_NAME)
    if grid_path.name != GRID_FIXTURE_NAME or not grid_path.is_file():
        raise AssertionError("historical grid fixture is required")
    if not weather_path.is_file():
        raise AssertionError("historical weather fixture is required")

    grid = grid_path.read_bytes()
    weather = weather_path.read_bytes()

    _assert_success_cycle(grid, weather)
    _assert_semantic_login_switches_once(grid, weather)
    _assert_second_login_stops_without_loop(grid, weather)
    _assert_no_lease_never_calls_webpilot(grid, weather)

    print("standby synthetic contract: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
