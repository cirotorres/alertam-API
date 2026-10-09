from __future__ import annotations

import json
import os
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from uuid import UUID

from app.repositories.postgres import PostgresDeviceRepository
from app.repositories.session_broker import ScopeStatus


API_URL = os.environ["API_URL"].rstrip("/")
DATABASE_URL = os.environ["DATABASE_URL"]
DEVICE_ID = os.environ["DEVICE_ID"]
DEVICE_SECRET = os.environ["DEVICE_SECRET"]
PUBLISHER_ID = UUID(os.environ["PUBLISHER_ID"])
GENERATION = int(os.environ["GENERATION"])
COOKIE_VALUE = os.environ["COOKIE_VALUE"]
STATE_FILE = Path(os.environ["STATE_FILE"])
EXPECT_CONFLICT = os.environ.get("EXPECT_CONFLICT", "false").lower() == "true"


def request(method: str, path: str, payload: dict) -> tuple[int, dict]:
    data = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    req = Request(
        API_URL + path,
        data=data,
        method=method,
        headers={
            "Authorization": f"Device {DEVICE_SECRET}",
            "Content-Type": "application/json",
        },
    )
    try:
        with urlopen(req, timeout=5) as response:
            return response.status, json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        body = exc.read()
        try:
            decoded = json.loads(body.decode("utf-8"))
        except Exception:
            decoded = {}
        return int(exc.code), decoded


publisher_payload = {
    "realm_id": "webpilot-pecem",
    "publisher_id": str(PUBLISHER_ID),
    "provider_scope": {
        "scope_id": "pecem-standard",
        "schema_version": 1,
        "capabilities": ["maneuvers", "weather"],
    },
}
status, response = request(
    "PUT",
    f"/api/v1/devices/{DEVICE_ID}/webpilot-session-publisher",
    publisher_payload,
)
assert status == 200, status
assert response["scope_status"] == "unverified"

repo = PostgresDeviceRepository(DATABASE_URL)
verified = repo.verify_session_publisher_scope(PUBLISHER_ID)
assert verified is not None
assert verified.scope_status is ScopeStatus.VERIFIED

lease_payload = {
    "realm_id": "webpilot-pecem",
    "publisher_id": str(PUBLISHER_ID),
    "local_generation": GENERATION,
    "expires_at": None,
    "cookies": [
        {
            "name": "session",
            "value": COOKIE_VALUE,
            "expiry": None,
        }
    ],
}
status, accepted = request(
    "POST",
    f"/api/v1/devices/{DEVICE_ID}/webpilot-session-leases",
    lease_payload,
)
assert status == 200, status

if EXPECT_CONFLICT:
    conflict_payload = {
        **lease_payload,
        "cookies": [
            {
                "name": "session",
                "value": COOKIE_VALUE + "-different",
                "expiry": None,
            }
        ],
    }
    conflict_status, conflict = request(
        "POST",
        f"/api/v1/devices/{DEVICE_ID}/webpilot-session-leases",
        conflict_payload,
    )
    assert conflict_status == 409, conflict_status
    assert conflict.get("detail", {}).get("code") == "session_lease_generation_conflict"

STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
STATE_FILE.write_text(
    json.dumps(
        {
            "publisher_id": str(PUBLISHER_ID),
            "local_generation": GENERATION,
            "lease_id": accepted["lease_id"],
            "realm_epoch": accepted["realm_epoch"],
        },
        separators=(",", ":"),
    ),
    encoding="utf-8",
)
print(f"sandbox publisher {DEVICE_ID}: PASS")
