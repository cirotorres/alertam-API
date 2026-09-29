from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.models.maneuver_event import ManeuverEventIn


FIXTURE = Path(__file__).parents[1] / "fixtures" / "maneuver_event_v1.json"


def payload() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def test_real_desktop_event_validates_and_canonicalizes_without_loss():
    raw = payload()

    event = ManeuverEventIn.model_validate(raw)

    assert event.canonical_payload() == raw


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("event_id", "not-a-uuid"),
        ("maneuver_id", "not-a-uuid"),
        ("occurred_at", "2026-09-27T10:05:00"),
        ("event_type", "REMOVED"),
        ("maneuver_type", "SHIFT"),
    ],
)
def test_rejects_invalid_contract_values(field: str, value: object):
    raw = payload()
    raw[field] = value

    with pytest.raises(ValidationError):
        ManeuverEventIn.model_validate(raw)


def test_rejects_extra_field():
    raw = payload()
    raw["device_secret"] = "must-not-enter-contract"

    with pytest.raises(ValidationError):
        ManeuverEventIn.model_validate(raw)


def test_updated_changes_allow_only_pob_and_berth_pairs():
    raw = payload()
    raw["changes"]["eta"] = {"from": "10:00", "to": "10:30"}

    with pytest.raises(ValidationError):
        ManeuverEventIn.model_validate(raw)


def test_updated_requires_at_least_one_change():
    raw = payload()
    raw["changes"] = None

    with pytest.raises(ValidationError):
        ManeuverEventIn.model_validate(raw)


@pytest.mark.parametrize("event_type", ["CONFIRMED", "COMPLETED", "CANCELLED"])
def test_non_updated_events_require_null_changes(event_type: str):
    raw = payload()
    raw["event_type"] = event_type

    with pytest.raises(ValidationError):
        ManeuverEventIn.model_validate(raw)


def test_change_types_are_specific_to_field():
    raw = payload()
    raw["changes"]["berth"] = {"from": "4", "to": 5}

    with pytest.raises(ValidationError):
        ManeuverEventIn.model_validate(raw)


def test_operational_timing_pair_validates_and_canonicalizes():
    raw = payload()
    raw["event_type"] = "COMPLETED"
    raw["changes"] = None
    raw["operational_at"] = "2026-09-29T05:28:00-03:00"
    raw["operational_marker"] = "ATRAC"

    event = ManeuverEventIn.model_validate(raw)

    assert event.operational_at.isoformat() == "2026-09-29T05:28:00-03:00"
    assert event.operational_marker == "ATRAC"
    assert event.canonical_payload() == raw


@pytest.mark.parametrize(
    ("operational_at", "operational_marker"),
    [
        ("2026-09-29T05:28:00-03:00", None),
        (None, "ATRAC"),
        ("2026-09-29T05:28:00", "ATRAC"),
        ("2026-09-29T05:28:00-03:00", "FUND"),
    ],
)
def test_operational_timing_rejects_orphan_naive_or_unknown_marker(
    operational_at,
    operational_marker,
):
    raw = payload()
    raw["event_type"] = "COMPLETED"
    raw["changes"] = None
    raw["operational_at"] = operational_at
    raw["operational_marker"] = operational_marker

    with pytest.raises(ValidationError):
        ManeuverEventIn.model_validate(raw)


def test_explicit_null_operational_pair_canonicalizes_like_absent_pair():
    absent = payload()
    absent.pop("operational_at", None)
    absent.pop("operational_marker", None)
    explicit_null = dict(absent)
    explicit_null["operational_at"] = None
    explicit_null["operational_marker"] = None

    absent_event = ManeuverEventIn.model_validate(absent)
    explicit_event = ManeuverEventIn.model_validate(explicit_null)

    assert explicit_event.canonical_payload() == absent_event.canonical_payload()
    assert "operational_at" not in explicit_event.canonical_payload()
    assert "operational_marker" not in explicit_event.canonical_payload()


def test_operational_timing_only_allowed_on_completed_atracacao():
    for event_type, maneuver_type in (("CONFIRMED", "ATRACACAO"), ("COMPLETED", "DESATRACACAO")):
        raw = payload()
        raw["event_type"] = event_type
        raw["maneuver_type"] = maneuver_type
        raw["changes"] = None
        raw["operational_at"] = "2026-09-29T05:28:00-03:00"
        raw["operational_marker"] = "ATRAC"

        with pytest.raises(ValidationError):
            ManeuverEventIn.model_validate(raw)


def test_legacy_event_without_optional_timestamps_remains_valid():
    raw = payload()
    raw.pop("pob_at")
    raw.pop("first_observed_at")

    event = ManeuverEventIn.model_validate(raw)

    assert event.pob_at is None
    assert event.first_observed_at is None
    assert event.operational_at is None
    assert event.operational_marker is None
    assert event.canonical_payload() == raw
