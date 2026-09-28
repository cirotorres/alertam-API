from __future__ import annotations

import json
from pathlib import Path

from app.models.maneuver_event import ManeuverEventIn


FIXTURE = Path(__file__).parents[1] / "fixtures" / "maneuver_event_v1.json"


def test_fixture_generated_by_desktop_matches_event_contract():
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))

    model = ManeuverEventIn.model_validate(payload)

    assert model.canonical_payload() == payload
    assert set(payload) == {
        "event_id",
        "maneuver_id",
        "vessel_identity",
        "vessel_imo",
        "vessel_name",
        "maneuver_type",
        "event_type",
        "berth",
        "pob",
        "occurred_at",
        "pob_at",
        "first_observed_at",
        "changes",
    }


def test_event_fixture_contains_no_credentials_or_transport_state():
    payload = FIXTURE.read_text(encoding="utf-8").casefold()

    for forbidden in (
        "device_secret",
        "view_secret",
        "authorization",
        "cookie",
        "session",
        "pushsubscription",
    ):
        assert forbidden not in payload
