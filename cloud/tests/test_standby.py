from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
from enum import Enum
import unittest

from alertam_cloud.broker_session import (
    BrokerLease,
    BrokerSessionProvider,
    SessionCookie,
)
from alertam_cloud.standby import StandbyCollector


NOW = datetime(2026, 10, 8, 12, 0, tzinfo=timezone.utc)


class Status(Enum):
    OK = "OK"
    SESSION_EXPIRED = "SESSION_EXPIRED"
    HTTP_ERROR = "HTTP_ERROR"


class Result:
    def __init__(self, status, body=b""):
        self.status = status
        self.body = body


class FakeLease:
    realm_id = "webpilot-pecem"
    realm_epoch = 8


class FakeProvider:
    def __init__(self, *, prime=True):
        self.prime_result = prime
        self.current_lease = FakeLease() if prime else None
        self.prime_calls = 0
        self.invalidate_calls = 0

    def prime(self):
        self.prime_calls += 1
        return self.prime_result

    def invalidate_current(self):
        self.invalidate_calls += 1
        self.current_lease = None
        return True


class FakeHttp:
    def __init__(self, results):
        self.results = list(results)
        self.calls = []

    def get(self, url):
        self.calls.append(url)
        return self.results.pop(0)


class ManeuverSnapshot:
    def __init__(self, count):
        self.navios = [object()] * count


class StandbyCollectorTests(unittest.TestCase):
    def test_no_lease_is_auth_unavailable_and_never_touches_webpilot(self):
        provider = FakeProvider(prime=False)
        http = FakeHttp([])
        collector = StandbyCollector(
            provider,
            http,
            maneuver_url="https://webpilot/maneuvers",
            weather_url="https://webpilot/weather",
            parse_maneuvers=lambda body, now: ManeuverSnapshot(0),
            parse_weather=lambda body, now: object(),
            clock=lambda: NOW,
        )

        status = collector.run_cycle()

        self.assertEqual(status.auth_state, "AUTH_UNAVAILABLE")
        self.assertEqual(status.last_collection_result, "AUTH_UNAVAILABLE")
        self.assertEqual(http.calls, [])
        self.assertEqual(provider.prime_calls, 1)

    def test_successful_cycle_keeps_only_sanitized_metadata(self):
        provider = FakeProvider()
        http = FakeHttp(
            [
                Result(Status.OK, b"GRID-RAW-SECRET"),
                Result(Status.OK, b"WEATHER-RAW-SECRET"),
            ]
        )
        collector = StandbyCollector(
            provider,
            http,
            maneuver_url="https://webpilot/maneuvers",
            weather_url="https://webpilot/weather",
            parse_maneuvers=lambda body, now: ManeuverSnapshot(22),
            parse_weather=lambda body, now: object(),
            clock=lambda: NOW,
        )

        status = collector.run_cycle()

        self.assertEqual(status.auth_state, "AUTH_READY")
        self.assertEqual(status.realm_id, "webpilot-pecem")
        self.assertEqual(status.realm_epoch, 8)
        self.assertEqual(status.maneuver_count, 22)
        self.assertTrue(status.weather_ok)
        self.assertEqual(status.last_collection_result, "OK")
        serialized = repr(asdict(status))
        self.assertNotIn("GRID-RAW-SECRET", serialized)
        self.assertNotIn("WEATHER-RAW-SECRET", serialized)
        self.assertNotIn("cookie", serialized.lower())
        self.assertNotIn("snapshot", serialized.lower())
        self.assertNotIn("source", serialized.lower())

    def test_final_semantic_login_invalidates_current_without_retry_loop(self):
        provider = FakeProvider()
        http = FakeHttp([Result(Status.SESSION_EXPIRED, b"LOGIN")])
        collector = StandbyCollector(
            provider,
            http,
            maneuver_url="https://webpilot/maneuvers",
            weather_url="https://webpilot/weather",
            parse_maneuvers=lambda body, now: ManeuverSnapshot(0),
            parse_weather=lambda body, now: object(),
            clock=lambda: NOW,
        )

        status = collector.run_cycle()

        self.assertEqual(provider.invalidate_calls, 1)
        self.assertEqual(len(http.calls), 1)
        self.assertEqual(status.auth_state, "AUTH_UNAVAILABLE")
        self.assertEqual(status.last_collection_result, "AUTH_UNAVAILABLE")

    def test_http_or_parse_failure_never_exposes_raw_payload(self):
        provider = FakeProvider()
        http = FakeHttp([Result(Status.HTTP_ERROR, b"RAW-SECRET")])
        collector = StandbyCollector(
            provider,
            http,
            maneuver_url="https://webpilot/maneuvers",
            weather_url="https://webpilot/weather",
            parse_maneuvers=lambda body, now: ManeuverSnapshot(0),
            parse_weather=lambda body, now: object(),
            clock=lambda: NOW,
        )

        status = collector.run_cycle()

        self.assertEqual(status.last_collection_result, "HTTP_ERROR")
        self.assertNotIn("RAW-SECRET", repr(status))


if __name__ == "__main__":
    unittest.main()


class OutageBroker:
    def __init__(self):
        self.consume_calls = 0
        self.invalidated = []

    def consume(self):
        self.consume_calls += 1
        return BrokerLease(
            lease_id=__import__("uuid").UUID(
                "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
            ),
            realm_id="webpilot-pecem",
            publisher_id=__import__("uuid").UUID(
                "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"
            ),
            local_generation=1,
            realm_epoch=7,
            received_at=NOW,
            expires_at=None,
            status="accepted",
            cookies=(SessionCookie("session", "COOKIE-SECRET", None),),
        )

    def invalidate(self, lease_id, realm_epoch):
        self.invalidated.append((lease_id, realm_epoch))
        raise OSError("COOKIE-SECRET broker unavailable")


class RecordingAuth:
    def publish(self, cookies):
        return object()


class StandbyFailClosedTests(unittest.TestCase):
    def test_semantic_login_with_invalidation_outage_is_fail_closed(self):
        broker = OutageBroker()
        provider = BrokerSessionProvider(broker)
        provider.attach(RecordingAuth())
        self.assertTrue(provider.prime())

        http = FakeHttp([Result(Status.SESSION_EXPIRED, b"LOGIN")])
        collector = StandbyCollector(
            provider,
            http,
            maneuver_url="https://webpilot/maneuvers",
            weather_url="https://webpilot/weather",
            parse_maneuvers=lambda body, now: ManeuverSnapshot(0),
            parse_weather=lambda body, now: object(),
            clock=lambda: NOW,
        )

        status = collector.run_cycle()

        self.assertIsNone(provider.current_identity)
        self.assertEqual(provider.auth_state, "AUTH_UNAVAILABLE")
        self.assertEqual(status.auth_state, "AUTH_UNAVAILABLE")
        self.assertEqual(status.last_collection_result, "AUTH_UNAVAILABLE")
        self.assertEqual(broker.consume_calls, 1)
        self.assertEqual(len(http.calls), 1)

        second = collector.run_cycle()

        self.assertIsNone(provider.current_identity)
        self.assertEqual(provider.auth_state, "AUTH_UNAVAILABLE")
        self.assertEqual(second.auth_state, "AUTH_UNAVAILABLE")
        self.assertEqual(second.last_collection_result, "AUTH_UNAVAILABLE")
        self.assertEqual(broker.consume_calls, 2)
        self.assertEqual(len(http.calls), 1)
