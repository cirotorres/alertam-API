from __future__ import annotations

import json
import os
from pathlib import Path

from app.repositories.devices import DeviceAuthRecord
from app.repositories.postgres import PostgresDeviceRepository
from app.repositories.session_broker import ProviderScopeProfile
from app.security.credentials import hash_secret


DATABASE_URL = os.environ["DATABASE_URL"]
STATE_DIR = Path(os.environ.get("STATE_DIR", "/state"))
REALM = "webpilot-pecem"
DEVICE_A = "sandbox-desktop-a"
DEVICE_B = "sandbox-desktop-b"
DEVICE_A_SECRET = os.environ["DEVICE_A_SECRET"]
DEVICE_B_SECRET = os.environ["DEVICE_B_SECRET"]
CLOUD_CREDENTIAL = os.environ["CLOUD_CREDENTIAL"]


repo = PostgresDeviceRepository(DATABASE_URL)
for device_id, secret in (
    (DEVICE_A, DEVICE_A_SECRET),
    (DEVICE_B, DEVICE_B_SECRET),
):
    repo.create_device(
        DeviceAuthRecord(
            device_id=device_id,
            device_secret_hash=hash_secret(secret),
            enabled=True,
        )
    )

assert repo.ensure_webpilot_auth_realm(REALM) is not None
assert repo.authorize_realm_device(REALM, DEVICE_A) is not None
assert repo.authorize_realm_device(REALM, DEVICE_B) is not None
assert repo.set_required_provider_scope(
    REALM,
    ProviderScopeProfile(
        scope_id="pecem-standard",
        schema_version=1,
        capabilities=("maneuvers", "weather"),
    ),
) is not None

binding = repo.ensure_cloud_binding(
    DEVICE_A,
    REALM,
    hash_secret(CLOUD_CREDENTIAL),
)
assert binding is not None

STATE_DIR.mkdir(parents=True, exist_ok=True)
STATE_DIR.chmod(0o777)
(STATE_DIR / "binding.json").write_text(
    json.dumps(
        {
            "cloud_binding_id": str(binding.cloud_binding_id),
            "realm_id": REALM,
        },
        separators=(",", ":"),
    ),
    encoding="utf-8",
)
print("sandbox bootstrap: PASS")
