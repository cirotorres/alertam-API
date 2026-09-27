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
