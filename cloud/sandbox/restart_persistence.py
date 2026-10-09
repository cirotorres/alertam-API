from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
from uuid import UUID

from alertam_cloud.broker_session import (
    BrokerLease,
    BrokerLeaseUnavailable,
    BrokerSessionProvider,
    FileRejectedIdentityStore,
    InMemoryRejectedIdentityStore,
    SessionCookie,
)


MODE = os.environ["MODE"]
STATE_DIR = Path(os.environ.get("STATE_DIR", "/state"))
NOW = datetime(2026, 10, 8, 12, 0, tzinfo=timezone.utc)
LEASE_A = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
LEASE_B = UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
PUBLISHER = UUID("cccccccc-cccc-cccc-cccc-cccccccccccc")


class FakeAuth:
    def __init__(self) -> None:
        self.published: list[tuple[dict[str, object], ...]] = []

    def publish(self, cookies):
        self.published.append(tuple(dict(cookie) for cookie in cookies))
        return object()


def lease(lease_id: UUID, epoch: int, value: str, *, expires_at=None) -> BrokerLease:
    return BrokerLease(
        lease_id=lease_id,
        realm_id="webpilot-pecem",
        publisher_id=PUBLISHER,
        local_generation=epoch,
        realm_epoch=epoch,
        received_at=NOW,
        expires_at=expires_at,
        status="accepted",
        cookies=(SessionCookie("session", value, None),),
    )


class OutageBroker:
    def __init__(self, item: BrokerLease) -> None:
        self.item = item

    def consume(self):
        return self.item

    def invalidate(self, lease_id, realm_epoch):
        raise OSError("synthetic invalidation outage")


class SequenceBroker:
    def __init__(self, items) -> None:
        self.items = list(items)

    def consume(self):
        if not self.items:
            raise BrokerLeaseUnavailable("synthetic empty")
        return self.items.pop(0)

    def invalidate(self, lease_id, realm_epoch):
        return None


store_path = STATE_DIR / "restart-rejections.json"

if MODE == "outage":
    auth = FakeAuth()
    rejected = lease(LEASE_A, 77, "SYNTHETIC-COOKIE-A")
    provider = BrokerSessionProvider(
        OutageBroker(rejected),
        rejection_store=FileRejectedIdentityStore(store_path),
    )
    provider.attach(auth)
    assert provider.prime()
    assert provider.current_identity == (LEASE_A, 77)
    assert provider.invalidate_current() is False
    assert provider.current_identity is None
    assert provider.auth_state == "AUTH_UNAVAILABLE"
    raw = store_path.read_text(encoding="utf-8")
    assert str(LEASE_A) in raw
    assert '"realm_epoch":77' in raw
    assert "SYNTHETIC-COOKIE-A" not in raw
    (STATE_DIR / "restart-outage.json").write_text(
        json.dumps({"status": "AUTH_UNAVAILABLE"}, separators=(",", ":")),
        encoding="utf-8",
    )
    print("c2c restart outage tombstone: PASS")

elif MODE == "restart":
    auth = FakeAuth()
    rejected = lease(LEASE_A, 77, "SYNTHETIC-COOKIE-A")
    replacement = lease(LEASE_B, 78, "SYNTHETIC-COOKIE-B")
    provider = BrokerSessionProvider(
        SequenceBroker([rejected, replacement]),
        rejection_store=FileRejectedIdentityStore(store_path),
    )
    provider.attach(auth)

    assert provider.prime() is False
    assert provider.current_identity is None
    assert auth.published == []

    assert provider.prime() is True
    assert provider.current_identity == (LEASE_B, 78)
    assert len(auth.published) == 1
    assert auth.published[0][0]["value"] == "SYNTHETIC-COOKIE-B"
    print("c2c restart rejects stale and accepts new identity: PASS")

elif MODE == "expiry":
    now = [NOW]
    auth = FakeAuth()
    expiring = lease(
        LEASE_A,
        91,
        "SYNTHETIC-COOKIE-EXPIRING",
        expires_at=NOW + timedelta(seconds=10),
    )
    provider = BrokerSessionProvider(
        SequenceBroker([expiring]),
        clock=lambda: now[0],
        rejection_store=InMemoryRejectedIdentityStore(),
    )
    provider.attach(auth)
    assert provider.prime() is True
    now[0] = NOW + timedelta(seconds=30)
    assert provider.prime() is False
    assert provider.current_identity is None
    assert provider.auth_state == "AUTH_UNAVAILABLE"
    assert len(auth.published) == 1
    print("c2c expiry rejects stale lease before reuse: PASS")

else:
    raise AssertionError("unknown MODE")
