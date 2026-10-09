from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from enum import Enum
import unittest

from alertam_cloud.broker_session import (
    InMemoryRejectedIdentityStore,
    BrokerLease,
    BrokerSessionProvider,
    SessionCookie,
)
from alertam_cloud.standby import (
    LeaseExpiryState,
    StandbyCollector,
    StandbyReason,
)


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
        provider = BrokerSessionProvider(
            broker, rejection_store=InMemoryRejectedIdentityStore()
        )
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


class RichLease:
    realm_id = "webpilot-pecem"
    realm_epoch = 42
    publisher_id = __import__("uuid").UUID(
        "cccccccc-cccc-cccc-cccc-cccccccccccc"
    )
    received_at = NOW - timedelta(seconds=30)
    expires_at = NOW + timedelta(minutes=5)


class RichProvider(FakeProvider):
    def __init__(self):
        super().__init__(prime=True)
        self.current_lease = RichLease()


class StandbyObservabilityTests(unittest.TestCase):
    def test_observability_metadata_is_sanitized_and_enumerated(self):
        provider = RichProvider()
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

        self.assertEqual(status.publisher_id, RichLease.publisher_id)
        self.assertEqual(status.realm_epoch, 42)
        self.assertEqual(status.lease_age_seconds, 30)
        self.assertIs(status.lease_expiry_state, LeaseExpiryState.ACTIVE)
        self.assertIs(status.reason_code, StandbyReason.OK)

        serialized = repr(asdict(status))
        for forbidden in (
            "GRID-RAW-SECRET",
            "WEATHER-RAW-SECRET",
            "COOKIE-SECRET",
            "ciphertext",
            "authorization",
            "cloudbinding",
            "device_secret",
            "raw_html",
            "session_payload",
        ):
            self.assertNotIn(forbidden.lower(), serialized.lower())

    def test_observability_auth_unavailable_reason_is_enumerated(self):
        provider = FakeProvider(prime=False)
        collector = StandbyCollector(
            provider,
            FakeHttp([]),
            maneuver_url="https://webpilot/maneuvers",
            weather_url="https://webpilot/weather",
            parse_maneuvers=lambda body, now: ManeuverSnapshot(0),
            parse_weather=lambda body, now: object(),
            clock=lambda: NOW,
        )

        status = collector.run_cycle()

        self.assertIs(status.reason_code, StandbyReason.AUTH_UNAVAILABLE)
        self.assertIs(status.lease_expiry_state, LeaseExpiryState.UNKNOWN)
        self.assertIsNone(status.publisher_id)
        self.assertIsNone(status.lease_age_seconds)


class ExpiringBroker:
    def __init__(self, lease):
        self.lease = lease
        self.consume_calls = 0

    def consume(self):
        self.consume_calls += 1
        if self.consume_calls == 1:
            return self.lease
        raise RuntimeError("no replacement")

    def invalidate(self, lease_id, realm_epoch):
        raise AssertionError("expiry must not depend on semantic invalidation")


class StandbyLeaseExpiryTests(unittest.TestCase):
    def test_expired_current_is_rejected_before_any_next_cycle_webpilot_call(self):
        now = [NOW]
        lease = BrokerLease(
            lease_id=__import__("uuid").UUID(
                "dddddddd-dddd-dddd-dddd-dddddddddddd"
            ),
            realm_id="webpilot-pecem",
            publisher_id=__import__("uuid").UUID(
                "eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee"
            ),
            local_generation=1,
            realm_epoch=9,
            received_at=NOW,
            expires_at=NOW + timedelta(seconds=10),
            status="accepted",
            cookies=(SessionCookie("session", "COOKIE-EXPIRING", None),),
        )
        broker = ExpiringBroker(lease)
        provider = BrokerSessionProvider(
            broker,
            clock=lambda: now[0],
            rejection_store=InMemoryRejectedIdentityStore(),
        )
        provider.attach(RecordingAuth())
        http = FakeHttp(
            [
                Result(Status.OK, b"GRID"),
                Result(Status.OK, b"WEATHER"),
            ]
        )
        collector = StandbyCollector(
            provider,
            http,
            maneuver_url="https://webpilot/maneuvers",
            weather_url="https://webpilot/weather",
            parse_maneuvers=lambda body, current: ManeuverSnapshot(22),
            parse_weather=lambda body, current: object(),
            clock=lambda: now[0],
        )

        first = collector.run_cycle()
        self.assertEqual(first.last_collection_result, "OK")
        self.assertEqual(len(http.calls), 2)

        now[0] = NOW + timedelta(seconds=30)
        second = collector.run_cycle()

        self.assertEqual(second.auth_state, "AUTH_UNAVAILABLE")
        self.assertEqual(second.last_collection_result, "AUTH_UNAVAILABLE")
        self.assertEqual(len(http.calls), 2)
        self.assertEqual(broker.consume_calls, 2)
        self.assertIsNone(provider.current_identity)
