from datetime import datetime, timedelta, timezone

import pytest

from app.services.source_timing_policy import (
    classify_desktop,
    classify_cloud,
    snapshot_fresh,
    hysteresis_complete,
    failback_stable,
)

NOW = datetime(2026, 10, 9, 13, 0, tzinfo=timezone.utc)


@pytest.mark.parametrize(
    ("age", "expected"),
    [(89, "desktop_healthy"), (90, "desktop_degraded"),
     (119, "desktop_degraded"), (120, "desktop_stale"),
     (179, "desktop_stale"), (180, "desktop_stale"),
     (299, "desktop_stale"), (300, "desktop_offline")],
)
def test_r12_desktop_liveness_boundaries(age, expected):
    assert classify_desktop(NOW - timedelta(seconds=age), NOW) == expected


@pytest.mark.parametrize("age,expected", [(59, True), (60, False)])
def test_r12_cloud_liveness_boundary(age, expected):
    assert classify_cloud(NOW - timedelta(seconds=age), NOW) == expected


@pytest.mark.parametrize(
    "source,age,expected",
    [("desktop", 119, True), ("desktop", 120, False),
     ("cloud", 89, True), ("cloud", 90, False)],
)
def test_r12_authoritative_snapshot_freshness(source, age, expected):
    assert snapshot_fresh(source, NOW - timedelta(seconds=age), NOW) == expected


@pytest.mark.parametrize(
    "age,expected",
    [(179, False), (180, True)],
)
def test_r12_hysteresis_threshold(age, expected):
    assert hysteresis_complete(NOW-timedelta(seconds=age), NOW, stale_after=120, hysteresis=60) == expected


@pytest.mark.parametrize(
    "count,age,expected",
    [(1, 120, False), (2, 120, False), (3, 119, False), (3, 120, True)],
)
def test_r12_failback_three_samples_and_120s(count, age, expected):
    assert failback_stable(count, NOW-timedelta(seconds=age), NOW) == expected
