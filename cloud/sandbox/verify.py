from __future__ import annotations

import json
import os
from pathlib import Path

import psycopg


DATABASE_URL = os.environ["DATABASE_URL"]
STATE_DIR = Path(os.environ.get("STATE_DIR", "/state"))

initial = json.loads((STATE_DIR / "cloud-initial.json").read_text(encoding="utf-8"))
recovery = json.loads((STATE_DIR / "cloud-recovery.json").read_text(encoding="utf-8"))
pub_a = json.loads((STATE_DIR / "publisher-a.json").read_text(encoding="utf-8"))
pub_b = json.loads((STATE_DIR / "publisher-b.json").read_text(encoding="utf-8"))

assert initial == {
    "stage": "initial",
    "realm_epoch": 1,
    "maneuver_count": 22,
    "weather_ok": True,
    "reason_code": "OK",
}
assert recovery == {
    "stage": "recovery",
    "before_epoch": 2,
    "after_epoch": 1,
    "final_reason": "AUTH_UNAVAILABLE",
    "maneuver_count": 22,
    "weather_ok": True,
    "reason_code": "OK",
}
assert pub_a["realm_epoch"] == 1
assert pub_b["realm_epoch"] == 2

with psycopg.connect(DATABASE_URL, autocommit=True) as conn:
    rows = conn.execute(
        """
        select realm_epoch, status
        from public.webpilot_session_leases
        order by realm_epoch
        """
    ).fetchall()
    assert rows == [(1, "invalidated"), (2, "invalidated")], rows

    last_epoch = conn.execute(
        """
        select last_epoch
        from public.webpilot_realm_epoch_counters
        where realm_id='webpilot-pecem'
        """
    ).fetchone()[0]
    assert last_epoch == 2

    snapshots = conn.execute(
        """
        select count(*)
        from public.devices
        where snapshot is not null
           or snapshot_schema_version is not null
           or boot_id is not null
           or sequence is not null
           or generated_at is not null
           or received_at is not null
        """
    ).fetchone()[0]
    assert snapshots == 0

print("c2c docker sandbox verification: PASS")
