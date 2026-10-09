from __future__ import annotations

import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
import unittest
from urllib.error import HTTPError
from urllib.request import urlopen


CLOUD_DIR = Path(__file__).resolve().parents[1]
SERVICE_NAME = "alertam-cloud-infra-spike"


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _request_json(url: str) -> tuple[int, dict[str, object]]:
    try:
        with urlopen(url, timeout=1) as response:
            return response.status, json.loads(response.read())
    except HTTPError as exc:
        body = exc.read()
        payload = json.loads(body) if body else {}
        return exc.code, payload


def _wait_until_healthy(port: int, process: subprocess.Popen[str]) -> None:
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        if process.poll() is not None:
            break
        try:
            status, _ = _request_json(f"http://127.0.0.1:{port}/healthz")
            if status == 200:
                return
        except OSError:
            pass
        time.sleep(0.05)
    stdout, _ = process.communicate(timeout=1)
    raise AssertionError(f"cloud service did not become healthy; output={stdout!r}")


class CloudServiceContractTests(unittest.TestCase):
    def _start_service(self, *, extra_env: dict[str, str] | None = None) -> tuple[subprocess.Popen[str], int]:
        port = _free_port()
        env = os.environ.copy()
        env["PORT"] = str(port)
        env.update(extra_env or {})
        process = subprocess.Popen(
            [sys.executable, "-m", "alertam_cloud"],
            cwd=CLOUD_DIR,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        _wait_until_healthy(port, process)
        return process, port

    def test_http_contract_is_health_readiness_only(self) -> None:
        process, port = self._start_service()
        try:
            health_status, health = _request_json(f"http://127.0.0.1:{port}/healthz")
            ready_status, ready = _request_json(f"http://127.0.0.1:{port}/readyz")
            root_status, _ = _request_json(f"http://127.0.0.1:{port}/")
            snapshot_status, _ = _request_json(f"http://127.0.0.1:{port}/api/v1/snapshot")

            self.assertEqual(health_status, 200)
            self.assertEqual(health, {"service": SERVICE_NAME, "status": "ok"})
            self.assertEqual(ready_status, 200)
            self.assertEqual(ready, {"service": SERVICE_NAME, "ready": True})
            self.assertEqual(root_status, 404)
            self.assertEqual(snapshot_status, 404)
        finally:
            process.terminate()
            process.communicate(timeout=3)

    def test_service_uses_required_bind_and_default_port(self) -> None:
        probe = subprocess.run(
            [
                sys.executable,
                "-c",
                "from alertam_cloud.server import BIND_HOST, resolve_port; "
                "print(BIND_HOST); print(resolve_port({}))",
            ],
            cwd=CLOUD_DIR,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(probe.returncode, 0, probe.stderr)
        self.assertEqual(probe.stdout.splitlines(), ["0.0.0.0", "8080"])

    def test_logs_do_not_dump_environment(self) -> None:
        sentinel = "DO_NOT_LOG_THIS_SENTINEL_948271"
        process, _ = self._start_service(extra_env={"SPIKE_TEST_SECRET": sentinel})
        process.terminate()
        stdout, _ = process.communicate(timeout=3)
        self.assertNotIn(sentinel, stdout)
        self.assertIn(SERVICE_NAME, stdout)

    def test_sigterm_exits_cleanly(self) -> None:
        process, _ = self._start_service()
        process.terminate()
        stdout, _ = process.communicate(timeout=3)
        self.assertEqual(process.returncode, 0, stdout)

    def test_default_server_does_not_import_or_start_standby(self) -> None:
        server_source = (CLOUD_DIR / "alertam_cloud" / "server.py").read_text(
            encoding="utf-8"
        ).lower()
        for token in (
            "broker_session",
            "standby",
            "webpilot",
            "sessionlease",
            "cloudbinding",
            "source=cloud",
            "device_secret",
        ):
            self.assertNotIn(token, server_source)

        probe = subprocess.run(
            [
                sys.executable,
                "-c",
                "import sys; import alertam_cloud.server; "
                "print(int('alertam_cloud.broker_session' in sys.modules)); "
                "print(int('alertam_cloud.standby' in sys.modules))",
            ],
            cwd=CLOUD_DIR,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(probe.returncode, 0, probe.stderr)
        self.assertEqual(probe.stdout.splitlines(), ["0", "0"])


if __name__ == "__main__":
    unittest.main()
