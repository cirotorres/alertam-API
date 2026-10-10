"""C3-C pure timing boundaries for deterministic tests and support classification.

The PostgreSQL authority RPCs, not these helpers, arbitrate grants under locks.
"""
from __future__ import annotations

from datetime import datetime


def _age(last: datetime, now: datetime) -> float:
    return (now - last).total_seconds()


def classify_desktop(
    last_heartbeat_at: datetime | None,
    now: datetime,
    *,
    process_healthy: bool = True,
    collection_healthy: bool = True,
) -> str:
    if last_heartbeat_at is None:
        return "desktop_offline"
    age = _age(last_heartbeat_at, now)
    if age >= 300:
        return "desktop_offline"
    if age >= 120:
        return "desktop_stale"
    if age >= 90 or not (process_healthy and collection_healthy):
        return "desktop_degraded"
    return "desktop_healthy"


def classify_cloud(last_heartbeat_at: datetime | None, now: datetime) -> bool:
    return last_heartbeat_at is not None and _age(last_heartbeat_at, now) < 60


def snapshot_fresh(
    source: str, last_authoritative_snapshot_at: datetime | None, now: datetime,
) -> bool:
    threshold = {"desktop": 120, "cloud": 90}[source]
    return (
        last_authoritative_snapshot_at is not None
        and _age(last_authoritative_snapshot_at, now) < threshold
    )


def hysteresis_complete(
    last_heartbeat_or_snapshot: datetime | None,
    now: datetime,
    *,
    stale_after: int = 120,
    hysteresis: int = 60,
) -> bool:
    return (
        last_heartbeat_or_snapshot is not None
        and _age(last_heartbeat_or_snapshot, now) >= stale_after + hysteresis
    )


def failback_stable(
    consecutive_healthy: int,
    healthy_since: datetime | None,
    now: datetime,
) -> bool:
    return (
        consecutive_healthy >= 3
        and healthy_since is not None
        and _age(healthy_since, now) >= 120
    )
