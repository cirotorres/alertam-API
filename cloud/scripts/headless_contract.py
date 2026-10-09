#!/usr/bin/env python3
"""Contract probe for the canonical Desktop wheel in a headless Cloud env."""
from __future__ import annotations

import argparse
from datetime import datetime
import importlib
import importlib.util
from pathlib import Path
import sys


HISTORICAL_FIXTURE_NAME = "grid_real_2026-09-21.html"
_FORBIDDEN_DISTRIBUTIONS = ("selenium", "webdriver_manager", "PIL", "pyttsx3")
_FORBIDDEN_IMPORTED_PREFIXES = (
    "selenium",
    "webdriver_manager",
    "PIL",
    "pyttsx3",
    "tkinter",
    "alertam.ui",
    "alertam.infrastructure.browser",
    "alertam.infrastructure.driver_manager",
)


def _assert_optional_desktop_stack_absent() -> None:
    present = [
        name
        for name in _FORBIDDEN_DISTRIBUTIONS
        if importlib.util.find_spec(name) is not None
    ]
    if present:
        raise AssertionError(
            "unexpected Desktop dependency in headless environment: "
            + ",".join(sorted(present))
        )


def _assert_import_closure() -> tuple[object, object, object, object]:
    auth_module = importlib.import_module("alertam.application.webpilot_auth")
    http_module = importlib.import_module("alertam.infrastructure.webpilot_http")
    grid_module = importlib.import_module(
        "alertam.infrastructure.webpilot_grid_html"
    )
    domain_module = importlib.import_module("alertam.domain")
    importlib.import_module("alertam.domain.webpilot_weather_parser")
    importlib.import_module("alertam.infrastructure.webpilot_weather")

    forbidden = sorted(
        name
        for name in sys.modules
        if any(
            name == prefix or name.startswith(prefix + ".")
            for prefix in _FORBIDDEN_IMPORTED_PREFIXES
        )
    )
    if forbidden:
        raise AssertionError(
            "forbidden module imported by headless closure: "
            + ",".join(forbidden)
        )
    return auth_module, http_module, grid_module, domain_module


def _assert_fixture_equivalence(
    fixture: Path,
    grid_module: object,
    domain_module: object,
) -> None:
    if fixture.name != HISTORICAL_FIXTURE_NAME or not fixture.is_file():
        raise AssertionError("historical grid fixture is required")

    rows = grid_module.extract_grid_rows(fixture.read_bytes())
    now = datetime(2026, 9, 21, 12, 0)
    snapshot = domain_module.parse_grid_rows(rows, agora=now)
    summary = domain_module.resumo(snapshot)

    if len(snapshot.navios) != 22:
        raise AssertionError("historical fixture vessel count changed")
    if summary != {"ATRACADO": 4, "FUNDEADO": 2, "PREVISTO": 16}:
        raise AssertionError("historical fixture summary changed")

    nord = next(
        (item for item in snapshot.navios if item.nome == "NORD TOPAZ"),
        None,
    )
    if nord is None:
        raise AssertionError("historical fixture lost NORD TOPAZ")
    if (
        nord.berco != 5
        or nord.eta != "ATRAC: 18/09 - 14:35"
        or nord.etb_ets != "21/PM"
        or nord.imo != "9992268"
    ):
        raise AssertionError("historical fixture normalized fields changed")


def _assert_http_contract(auth_module: object, http_module: object) -> None:
    realm = auth_module.WEBPILOT_AUTH_REALM

    class RecoveryProvider:
        def __init__(self) -> None:
            self.auth = None
            self.calls = 0

        def request_recovery(self) -> bool:
            self.calls += 1
            assert self.auth is not None
            self.auth.publish(
                ({"name": "session", "value": "synthetic-new"},)
            )
            return True

    provider = RecoveryProvider()
    auth = auth_module.WebPilotAuthCoordinator(realm, provider)
    provider.auth = auth
    auth.publish(({"name": "session", "value": "synthetic-old"},))

    calls: list[str] = []

    def transport(url, headers, timeout):
        calls.append(headers.get("Cookie", ""))
        if len(calls) == 1:
            return http_module.RawHttpResponse(
                200,
                "https://webpilot.cearapilots.com.br/WebPilot/admin/login.aspx",
                b'<input id="tbSenha">',
            )
        return http_module.RawHttpResponse(
            200,
            url,
            b"<html>synthetic-ok</html>",
        )

    client = http_module.WebPilotHttpClient(
        auth,
        timeout=1,
        transport=transport,
        recovery_wait_seconds=0,
    )
    result = client.get(
        "https://webpilot.cearapilots.com.br/"
        "WebPilot/consultas/hiPlanilhaManobrasCeara.aspx"
    )
    if result.status is not http_module.WebPilotHttpStatus.OK:
        raise AssertionError("login detection/recovery contract changed")
    if provider.calls != 1 or len(calls) != 2:
        raise AssertionError("WebPilotHttpClient must perform exactly one retry")

    before = len(calls)
    bad = client.get("https://example.invalid/not-webpilot")
    if bad.status is not http_module.WebPilotHttpStatus.HTTP_ERROR:
        raise AssertionError("same-origin guard changed")
    if len(calls) != before:
        raise AssertionError("same-origin rejection touched transport")

    class AlwaysLoginProvider:
        def __init__(self) -> None:
            self.auth = None
            self.calls = 0

        def request_recovery(self) -> bool:
            self.calls += 1
            assert self.auth is not None
            self.auth.publish(
                ({"name": "session", "value": "synthetic-next"},)
            )
            return True

    always_provider = AlwaysLoginProvider()
    always_auth = auth_module.WebPilotAuthCoordinator(realm, always_provider)
    always_provider.auth = always_auth
    always_auth.publish(
        ({"name": "session", "value": "synthetic-start"},)
    )
    always_calls = 0

    def always_login(url, headers, timeout):
        nonlocal always_calls
        always_calls += 1
        return http_module.RawHttpResponse(
            200,
            "https://webpilot.cearapilots.com.br/WebPilot/admin/login.aspx",
            b'<input id="tbSenha">',
        )

    always_client = http_module.WebPilotHttpClient(
        always_auth,
        timeout=1,
        transport=always_login,
        recovery_wait_seconds=0,
    )
    final = always_client.get(
        "https://webpilot.cearapilots.com.br/"
        "WebPilot/consultas/hiPlanilhaManobrasCeara.aspx"
    )
    if final.status is not http_module.WebPilotHttpStatus.SESSION_EXPIRED:
        raise AssertionError("second semantic login must remain expired")
    if always_calls != 2:
        raise AssertionError("semantic login must not create retry loop")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fixture", type=Path, required=True)
    args = parser.parse_args()

    _assert_optional_desktop_stack_absent()
    modules = _assert_import_closure()
    _assert_fixture_equivalence(args.fixture, modules[2], modules[3])
    _assert_http_contract(modules[0], modules[1])
    _assert_import_closure()
    print("headless wheel contract: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
