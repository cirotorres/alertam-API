from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
import signal
from collections.abc import Mapping
from typing import Any

from . import SERVICE_NAME


BIND_HOST = "0.0.0.0"
DEFAULT_PORT = 8080


def resolve_port(env: Mapping[str, str]) -> int:
    raw_port = env.get("PORT", str(DEFAULT_PORT))
    port = int(raw_port)
    if not 1 <= port <= 65535:
        raise ValueError("PORT must be between 1 and 65535")
    return port


def _json_bytes(payload: dict[str, Any]) -> bytes:
    return json.dumps(payload, separators=(",", ":")).encode("utf-8")


class InfrastructureHandler(BaseHTTPRequestHandler):
    server_version = "AlertaMCloudInfra/0"

    def do_GET(self) -> None:  # noqa: N802 - stdlib handler contract
        if self.path == "/healthz":
            self._send_json(200, {"service": SERVICE_NAME, "status": "ok"})
            return
        if self.path == "/readyz":
            self._send_json(200, {"service": SERVICE_NAME, "ready": True})
            return
        self._send_json(404, {"detail": "not_found"})

    def _send_json(self, status: int, payload: dict[str, Any]) -> None:
        body = _json_bytes(payload)
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: object) -> None:
        print(
            json.dumps(
                {
                    "event": "http_request",
                    "service": SERVICE_NAME,
                    "message": format % args,
                },
                separators=(",", ":"),
            ),
            flush=True,
        )


def run() -> None:
    port = resolve_port(os.environ)

    def exit_cleanly_on_sigterm(_signum: int, _frame: object) -> None:
        raise SystemExit(0)

    signal.signal(signal.SIGTERM, exit_cleanly_on_sigterm)

    with ThreadingHTTPServer((BIND_HOST, port), InfrastructureHandler) as server:
        print(
            json.dumps(
                {
                    "event": "startup",
                    "service": SERVICE_NAME,
                    "host": BIND_HOST,
                    "port": port,
                },
                separators=(",", ":"),
            ),
            flush=True,
        )
        server.serve_forever()
