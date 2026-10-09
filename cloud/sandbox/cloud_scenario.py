from __future__ import annotations

import json
import os
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.parse import urlsplit
from uuid import UUID

from alertam.infrastructure.webpilot_http import RawHttpResponse
from alertam.settings import WEBPILOT_LOGIN_PATH, WEBPILOT_URL
from alertam_cloud.broker_session import (
    BrokerSessionProvider,
    FileRejectedIdentityStore,
    SessionBrokerClient,
)
from alertam_cloud.standby import StandbyReason, build_canonical_standby


MODE = os.environ["SCENARIO_MODE"]
API_INTERNAL_URL = os.environ["API_INTERNAL_URL"].rstrip("/")
FAKE_WEBPILOT_URL = os.environ["FAKE_WEBPILOT_URL"].rstrip("/")
CLOUD_CREDENTIAL = os.environ["CLOUD_CREDENTIAL"]
STATE_DIR = Path(os.environ.get("STATE_DIR", "/state"))

binding_payload = json.loads((STATE_DIR / "binding.json").read_text(encoding="utf-8"))
binding_id = UUID(binding_payload["cloud_binding_id"])


def api_opener(request, timeout):
    parsed = urlsplit(request.full_url)
    target = API_INTERNAL_URL + parsed.path
    if parsed.query:
        target += "?" + parsed.query
    forwarded = Request(
        target,
        data=request.data,
        method=request.get_method(),
        headers=dict(request.header_items()),
    )
    return urlopen(forwarded, timeout=timeout)


class SyntheticWebPilotTransport:
    def __init__(self, *, login_once: bool) -> None:
        self.login_once = login_once
        self.maneuver_calls = 0

    def _fetch(self, path: str, timeout: float) -> bytes:
        with urlopen(FAKE_WEBPILOT_URL + path, timeout=timeout) as response:
            return response.read()

    def __call__(self, url, headers, timeout):
        if "hiPlanilhaManobrasCeara.aspx" in url:
            self.maneuver_calls += 1
            if self.login_once and self.maneuver_calls == 1:
                canonical = urlsplit(WEBPILOT_URL)
                login_url = (
                    f"{canonical.scheme}://{canonical.netloc}"
                    f"{WEBPILOT_LOGIN_PATH}"
                )
                return RawHttpResponse(
                    200,
                    login_url,
                    self._fetch("/login", timeout),
                )
            return RawHttpResponse(200, url, self._fetch("/maneuvers", timeout))
        if "grEstacaoMeteorologica.aspx" in url:
            return RawHttpResponse(200, url, self._fetch("/weather", timeout))
        raise AssertionError("unexpected canonical WebPilot URL")


client = SessionBrokerClient(
    "https://api.synthetic.invalid",
    binding_id,
    CLOUD_CREDENTIAL,
    timeout_seconds=5,
    opener=api_opener,
)
provider = BrokerSessionProvider(
    client,
    rejection_store=FileRejectedIdentityStore(
        STATE_DIR / "session-rejections.json"
    ),
)
transport = SyntheticWebPilotTransport(login_once=False)
collector = build_canonical_standby(
    provider,
    transport=transport,
    timeout_seconds=2,
)

if MODE == "initial":
    status = collector.run_cycle()
    assert status.reason_code is StandbyReason.OK
    assert status.realm_epoch == 1
    assert status.maneuver_count == 22
    assert status.weather_ok is True
    result = {
        "stage": "initial",
        "realm_epoch": status.realm_epoch,
        "maneuver_count": status.maneuver_count,
        "weather_ok": status.weather_ok,
        "reason_code": status.reason_code.value,
    }
elif MODE == "recovery":
    first = collector.run_cycle()
    assert first.reason_code is StandbyReason.OK
    assert first.realm_epoch == 2
    assert first.maneuver_count == 22
    assert first.weather_ok is True

    transport.login_once = True
    transport.maneuver_calls = 0
    second = collector.run_cycle()
    assert second.reason_code is StandbyReason.OK
    assert second.realm_epoch == 1
    assert second.maneuver_count == 22
    assert second.weather_ok is True

    transport.login_once = True
    transport.maneuver_calls = 0
    final = collector.run_cycle()
    assert final.reason_code is StandbyReason.AUTH_UNAVAILABLE
    assert final.realm_epoch is None
    assert final.auth_state == "AUTH_UNAVAILABLE"

    result = {
        "stage": "recovery",
        "before_epoch": first.realm_epoch,
        "after_epoch": second.realm_epoch,
        "final_reason": final.reason_code.value,
        "maneuver_count": second.maneuver_count,
        "weather_ok": second.weather_ok,
        "reason_code": second.reason_code.value,
    }
else:
    raise AssertionError("unknown sandbox scenario mode")

(STATE_DIR / f"cloud-{MODE}.json").write_text(
    json.dumps(result, separators=(",", ":")),
    encoding="utf-8",
)
print(f"c2c cloud sandbox {MODE}: PASS")
