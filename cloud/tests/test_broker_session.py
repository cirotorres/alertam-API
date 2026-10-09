from __future__ import annotations

from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import logging
import threading
from urllib.error import HTTPError
from uuid import UUID
import unittest

from alertam_cloud.broker_session import (
    BrokerLease,
    BrokerLeaseUnavailable,
    BrokerSessionError,
    BrokerSessionProvider,
    SessionBrokerClient,
    SessionCookie,
)


BINDING = UUID("11111111-1111-1111-1111-111111111111")
LEASE_A = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
LEASE_B = UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
PUBLISHER = UUID("cccccccc-cccc-cccc-cccc-cccccccccccc")
NOW = datetime(2026, 10, 8, 12, 0, tzinfo=timezone.utc)


class FakeResponse:
    def __init__(self, status=200, payload=None, headers=None):
        self.status = status
        self._payload = payload if payload is not None else {}
        self.headers = headers or {"Cache-Control": "no-store"}

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self):
        return json.dumps(self._payload).encode("utf-8")


def _lease_payload(*, lease_id=LEASE_A, epoch=7, cookie="COOKIE-SECRET"):
    return {
        "lease_id": str(lease_id),
        "realm_id": "webpilot-pecem",
        "publisher_id": str(PUBLISHER),
        "local_generation": 3,
        "realm_epoch": epoch,
        "received_at": "2026-10-08T12:00:00Z",
        "expires_at": None,
        "status": "accepted",
        "cookies": [
            {"name": "session", "value": cookie, "expiry": None},
        ],
    }


class SessionBrokerClientTests(unittest.TestCase):
    def test_consume_uses_cloudbinding_header_and_no_query_string(self):
        observed = []

        def opener(request, timeout):
            observed.append((request, timeout))
            return FakeResponse(payload=_lease_payload())

        client = SessionBrokerClient(
            "https://api.example.test",
            BINDING,
            "CLOUD-CREDENTIAL",
            timeout_seconds=4,
            opener=opener,
        )

        lease = client.consume()

        request, timeout = observed[0]
        self.assertEqual(request.get_method(), "GET")
        self.assertEqual(
            request.full_url,
            f"https://api.example.test/api/v1/cloud-bindings/{BINDING}/webpilot-session-lease",
        )
        self.assertNotIn("?", request.full_url)
        self.assertEqual(
            request.get_header("Authorization"),
            "CloudBinding CLOUD-CREDENTIAL",
        )
        self.assertEqual(timeout, 4)
        self.assertEqual(lease.lease_id, LEASE_A)
        self.assertEqual(lease.realm_epoch, 7)
        self.assertEqual(lease.cookies[0].value, "COOKIE-SECRET")

    def test_invalidate_sends_exact_lease_and_epoch(self):
        observed = []

        def opener(request, timeout):
            observed.append(request)
            payload = {
                key: value
                for key, value in _lease_payload().items()
                if key != "cookies"
            }
            payload["status"] = "invalidated"
            return FakeResponse(payload=payload)

        client = SessionBrokerClient(
            "https://api.example.test",
            BINDING,
            "CLOUD-CREDENTIAL",
            opener=opener,
        )

        client.invalidate(LEASE_A, 7)

        request = observed[0]
        self.assertEqual(request.get_method(), "POST")
        self.assertEqual(
            json.loads(request.data),
            {"lease_id": str(LEASE_A), "realm_epoch": 7},
        )
        self.assertNotIn("?", request.full_url)

    def test_404_is_typed_auth_unavailable_and_errors_do_not_echo_secrets(self):
        secret = "CLOUD-CREDENTIAL"

        def opener(request, timeout):
            raise HTTPError(
                request.full_url,
                404,
                "COOKIE-SECRET " + secret,
                hdrs=None,
                fp=None,
            )

        client = SessionBrokerClient(
            "https://api.example.test",
            BINDING,
            secret,
            opener=opener,
        )

        with self.assertRaises(BrokerLeaseUnavailable) as ctx:
            client.consume()

        self.assertNotIn(secret, str(ctx.exception))
        self.assertNotIn("COOKIE-SECRET", str(ctx.exception))

    def test_secret_material_is_redacted_from_repr(self):
        cookie = SessionCookie("session", "COOKIE-SECRET", None)
        lease = BrokerLease(
            lease_id=LEASE_A,
            realm_id="webpilot-pecem",
            publisher_id=PUBLISHER,
            local_generation=3,
            realm_epoch=7,
            received_at=NOW,
            expires_at=None,
            status="accepted",
            cookies=(cookie,),
        )
        client = SessionBrokerClient(
            "https://api.example.test",
            BINDING,
            "CLOUD-CREDENTIAL",
        )

        self.assertNotIn("COOKIE-SECRET", repr(cookie))
        self.assertNotIn("COOKIE-SECRET", repr(lease))
        self.assertNotIn("CLOUD-CREDENTIAL", repr(client))


class FakeAuth:
    def __init__(self):
        self.published = []

    def publish(self, cookies):
        self.published.append(tuple(dict(cookie) for cookie in cookies))
        return object()


class FakeBroker:
    def __init__(self, leases):
        self.leases = list(leases)
        self.invalidated = []
        self.consume_calls = 0

    def consume(self):
        self.consume_calls += 1
        if not self.leases:
            raise BrokerLeaseUnavailable("session lease unavailable")
        item = self.leases.pop(0)
        if isinstance(item, Exception):
            raise item
        return item

    def invalidate(self, lease_id, realm_epoch):
        self.invalidated.append((lease_id, realm_epoch))


def _lease(lease_id, epoch, value):
    return BrokerLease(
        lease_id=lease_id,
        realm_id="webpilot-pecem",
        publisher_id=PUBLISHER,
        local_generation=epoch,
        realm_epoch=epoch,
        received_at=NOW,
        expires_at=None,
        status="accepted",
        cookies=(SessionCookie("session", value, None),),
    )


class BrokerSessionProviderTests(unittest.TestCase):
    def test_prime_publishes_broker_lease_into_local_auth_once(self):
        auth = FakeAuth()
        broker = FakeBroker([_lease(LEASE_A, 7, "COOKIE-A")])
        provider = BrokerSessionProvider(broker)
        provider.attach(auth)

        self.assertTrue(provider.prime())
        self.assertEqual(provider.current_identity, (LEASE_A, 7))
        self.assertEqual(auth.published[0][0]["value"], "COOKIE-A")
        self.assertEqual(broker.consume_calls, 1)

        self.assertTrue(provider.prime())
        self.assertEqual(broker.consume_calls, 1)
        self.assertEqual(len(auth.published), 1)

    def test_semantic_recovery_invalidates_exact_current_and_publishes_only_changed_lease(self):
        auth = FakeAuth()
        broker = FakeBroker(
            [
                _lease(LEASE_A, 7, "COOKIE-A"),
                _lease(LEASE_B, 8, "COOKIE-B"),
            ]
        )
        provider = BrokerSessionProvider(broker)
        provider.attach(auth)
        self.assertTrue(provider.prime())

        self.assertTrue(provider.request_recovery())

        self.assertEqual(broker.invalidated, [(LEASE_A, 7)])
        self.assertEqual(provider.current_identity, (LEASE_B, 8))
        self.assertEqual(len(auth.published), 2)
        self.assertEqual(auth.published[-1][0]["value"], "COOKIE-B")

    def test_invalidate_current_invalidates_exact_identity_without_fetching_replacement(self):
        auth = FakeAuth()
        broker = FakeBroker([_lease(LEASE_A, 7, "COOKIE-A")])
        provider = BrokerSessionProvider(broker)
        provider.attach(auth)
        self.assertTrue(provider.prime())

        self.assertTrue(provider.invalidate_current())

        self.assertEqual(broker.invalidated, [(LEASE_A, 7)])
        self.assertIsNone(provider.current_identity)
        self.assertEqual(broker.consume_calls, 1)
        self.assertEqual(len(auth.published), 1)

    def test_recovery_same_effective_lease_does_not_publish_or_allow_retry(self):
        auth = FakeAuth()
        same = _lease(LEASE_A, 7, "COOKIE-A")
        broker = FakeBroker([same, same])
        provider = BrokerSessionProvider(broker)
        provider.attach(auth)
        self.assertTrue(provider.prime())

        self.assertFalse(provider.request_recovery())

        self.assertEqual(broker.invalidated, [(LEASE_A, 7)])
        self.assertEqual(len(auth.published), 1)
        self.assertIsNone(provider.current_identity)
        self.assertEqual(provider.auth_state, "AUTH_UNAVAILABLE")

    def test_without_valid_lease_remains_auth_unavailable_without_loop(self):
        auth = FakeAuth()
        broker = FakeBroker([])
        provider = BrokerSessionProvider(broker)
        provider.attach(auth)

        self.assertFalse(provider.prime())
        self.assertEqual(provider.auth_state, "AUTH_UNAVAILABLE")
        self.assertEqual(broker.consume_calls, 1)
        self.assertEqual(auth.published, [])

        self.assertFalse(provider.request_recovery())
        self.assertEqual(broker.consume_calls, 1)
        self.assertEqual(broker.invalidated, [])

    def test_broker_failure_logs_only_type_not_secret(self):
        auth = FakeAuth()
        broker = FakeBroker([RuntimeError("COOKIE-SECRET broker exploded")])
        provider = BrokerSessionProvider(broker)
        provider.attach(auth)

        with self.assertLogs("alertam_cloud.broker_session", level=logging.WARNING) as logs:
            self.assertFalse(provider.prime())

        joined = "\n".join(logs.output)
        self.assertNotIn("COOKIE-SECRET", joined)
        self.assertNotIn("broker exploded", joined)


if __name__ == "__main__":
    unittest.main()


class RedirectCapture:
    def __init__(self, status_code):
        self.status_code = status_code
        self.redirect_requests = []
        self.destination_requests = []
        self._servers = []
        self._threads = []

    def __enter__(self):
        capture = self

        class DestinationHandler(BaseHTTPRequestHandler):
            def _record(self):
                length = int(self.headers.get("Content-Length", "0") or "0")
                body = self.rfile.read(length) if length else b""
                capture.destination_requests.append(
                    {
                        "method": self.command,
                        "authorization": self.headers.get("Authorization"),
                        "body": body,
                    }
                )
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps(_lease_payload()).encode("utf-8"))

            do_GET = _record
            do_POST = _record

            def log_message(self, *_args):
                return

        destination = ThreadingHTTPServer(("127.0.0.1", 0), DestinationHandler)
        destination_url = (
            f"http://127.0.0.1:{destination.server_address[1]}/redirected"
        )

        class RedirectHandler(BaseHTTPRequestHandler):
            def _redirect(self):
                length = int(self.headers.get("Content-Length", "0") or "0")
                body = self.rfile.read(length) if length else b""
                capture.redirect_requests.append(
                    {
                        "method": self.command,
                        "authorization": self.headers.get("Authorization"),
                        "body": body,
                    }
                )
                self.send_response(capture.status_code)
                self.send_header("Location", destination_url)
                self.end_headers()

            do_GET = _redirect
            do_POST = _redirect

            def log_message(self, *_args):
                return

        redirect = ThreadingHTTPServer(("127.0.0.1", 0), RedirectHandler)
        self.base_url = f"http://127.0.0.1:{redirect.server_address[1]}"

        for server in (destination, redirect):
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            self._servers.append(server)
            self._threads.append(thread)
        return self

    def __exit__(self, *_args):
        for server in self._servers:
            server.shutdown()
            server.server_close()
        for thread in self._threads:
            thread.join(timeout=1)


class SessionBrokerRedirectTests(unittest.TestCase):
    def test_consume_redirect_statuses_fail_closed(self):
        for status_code in (301, 302, 303, 307, 308):
            with self.subTest(status_code=status_code):
                with RedirectCapture(status_code) as capture:
                    client = SessionBrokerClient(
                        capture.base_url,
                        BINDING,
                        "CLOUD-CREDENTIAL",
                    )
                    with self.assertRaises(BrokerSessionError) as ctx:
                        client.consume()

                self.assertTrue(capture.redirect_requests)
                self.assertEqual(capture.destination_requests, [])
                self.assertNotIn("CLOUD-CREDENTIAL", str(ctx.exception))

    def test_invalidate_redirect_statuses_fail_closed(self):
        for status_code in (301, 302, 303, 307, 308):
            with self.subTest(status_code=status_code):
                with RedirectCapture(status_code) as capture:
                    client = SessionBrokerClient(
                        capture.base_url,
                        BINDING,
                        "CLOUD-CREDENTIAL",
                    )
                    with self.assertRaises(BrokerSessionError) as ctx:
                        client.invalidate(LEASE_A, 7)

                self.assertTrue(capture.redirect_requests)
                self.assertEqual(capture.destination_requests, [])
                self.assertNotIn("CLOUD-CREDENTIAL", str(ctx.exception))


class FailingInvalidateBroker(FakeBroker):
    def invalidate(self, lease_id, realm_epoch):
        self.invalidated.append((lease_id, realm_epoch))
        raise OSError("COOKIE-SECRET invalidation backend down")


class SequenceInvalidateBroker(FakeBroker):
    def __init__(self, leases):
        super().__init__(leases)
        self.invalidate_attempts = 0

    def invalidate(self, lease_id, realm_epoch):
        self.invalidate_attempts += 1
        self.invalidated.append((lease_id, realm_epoch))
        if self.invalidate_attempts == 1:
            raise OSError("first invalidation outage")


class BrokerSessionFailClosedTests(unittest.TestCase):
    def test_invalidate_current_clears_local_identity_even_when_remote_fails(self):
        auth = FakeAuth()
        same = _lease(LEASE_A, 7, "COOKIE-A")
        broker = FailingInvalidateBroker([same, same])
        provider = BrokerSessionProvider(broker)
        provider.attach(auth)
        self.assertTrue(provider.prime())

        self.assertFalse(provider.invalidate_current())

        self.assertEqual(broker.invalidated, [(LEASE_A, 7)])
        self.assertIsNone(provider.current_identity)
        self.assertEqual(provider.auth_state, "AUTH_UNAVAILABLE")

        self.assertFalse(provider.prime())
        self.assertEqual(broker.consume_calls, 2)
        self.assertIsNone(provider.current_identity)
        self.assertEqual(len(auth.published), 1)

    def test_recovery_never_resurrects_tombstoned_identity(self):
        auth = FakeAuth()
        lease_b = _lease(LEASE_B, 7, "COOKIE-B")
        lease_a = _lease(LEASE_A, 8, "COOKIE-A")
        broker = SequenceInvalidateBroker(
            [
                lease_b,
                lease_a,
                lease_b,
            ]
        )
        provider = BrokerSessionProvider(broker)
        provider.attach(auth)

        self.assertTrue(provider.prime())
        self.assertEqual(provider.current_identity, (LEASE_B, 7))

        self.assertFalse(provider.invalidate_current())
        self.assertIsNone(provider.current_identity)
        self.assertEqual(provider.auth_state, "AUTH_UNAVAILABLE")

        self.assertTrue(provider.prime())
        self.assertEqual(provider.current_identity, (LEASE_A, 8))

        self.assertFalse(provider.request_recovery())

        self.assertEqual(
            broker.invalidated,
            [
                (LEASE_B, 7),
                (LEASE_A, 8),
            ],
        )
        self.assertEqual(broker.consume_calls, 3)
        self.assertIsNone(provider.current_identity)
        self.assertEqual(provider.auth_state, "AUTH_UNAVAILABLE")
        self.assertEqual(
            [entry[0]["value"] for entry in auth.published],
            ["COOKIE-B", "COOKIE-A"],
        )

    def test_recovery_clears_local_identity_when_remote_invalidation_fails(self):
        auth = FakeAuth()
        same = _lease(LEASE_A, 7, "COOKIE-A")
        broker = FailingInvalidateBroker([same, same])
        provider = BrokerSessionProvider(broker)
        provider.attach(auth)
        self.assertTrue(provider.prime())

        self.assertFalse(provider.request_recovery())

        self.assertEqual(broker.invalidated, [(LEASE_A, 7)])
        self.assertIsNone(provider.current_identity)
        self.assertEqual(provider.auth_state, "AUTH_UNAVAILABLE")
        self.assertEqual(broker.consume_calls, 1)

        self.assertFalse(provider.prime())
        self.assertEqual(broker.consume_calls, 2)
        self.assertIsNone(provider.current_identity)
        self.assertEqual(len(auth.published), 1)
