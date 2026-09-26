from __future__ import annotations

import logging
from time import perf_counter
from typing import Any, Awaitable, Callable


HTTP_LOGGER = logging.getLogger("alertam.api.http")


def configure_logging(level: str) -> None:
    resolved = getattr(logging, level.upper(), logging.INFO)
    HTTP_LOGGER.setLevel(resolved)


class HttpRequestLoggingMiddleware:
    def __init__(self, app: Callable[..., Awaitable[Any]]) -> None:
        self.app = app

    async def __call__(self, scope, receive, send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        started = perf_counter()
        status_code = 500

        async def send_wrapper(message) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = int(message["status"])
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            duration_ms = (perf_counter() - started) * 1000
            HTTP_LOGGER.info(
                "http_request method=%s path=%s status=%s duration_ms=%.2f",
                scope.get("method", ""),
                scope.get("path", ""),
                status_code,
                duration_ms,
            )
