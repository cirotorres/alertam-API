import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.models.vessel_tracking_event import VesselTrackingEventIn


FIXTURE = Path(__file__).parents[1] / "fixtures" / "vessel_tracking_event_v1.json"


def payload():
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def test_tracking_event_accepts_strict_desktop_contract():
    event = VesselTrackingEventIn.model_validate(payload())

    assert str(event.event_id).endswith("501")
    assert str(event.maneuver_id).endswith("901")
    assert event.current.present is True
    assert event.changes.eta is not None
    assert event.changes.side is not None
    assert event.canonical_payload() == payload()


def test_tracking_event_rejects_unaware_timestamps_and_extra_fields():
    body = payload()
    body["occurred_at"] = "2026-09-28T10:02:00"
    with pytest.raises(ValidationError):
        VesselTrackingEventIn.model_validate(body)

    body = payload()
    body["unexpected"] = "x"
    with pytest.raises(ValidationError):
        VesselTrackingEventIn.model_validate(body)


def test_tracking_event_requires_at_least_one_known_change():
    body = payload()
    body["changes"] = {}
    with pytest.raises(ValidationError):
        VesselTrackingEventIn.model_validate(body)

    body = payload()
    body["changes"] = {"agency": {"from": "A", "to": "B"}}
    with pytest.raises(ValidationError):
        VesselTrackingEventIn.model_validate(body)


def test_tracking_event_current_is_strict_and_rejects_non_boolean_presence():
    body = payload()
    body["current"]["present"] = 1

    with pytest.raises(ValidationError):
        VesselTrackingEventIn.model_validate(body)
