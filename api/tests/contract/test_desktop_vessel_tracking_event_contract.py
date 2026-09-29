import json
from pathlib import Path

from app.models.vessel_tracking_event import VesselTrackingEventIn


FIXTURE = Path(__file__).parents[1] / "fixtures" / "vessel_tracking_event_v1.json"


def test_real_desktop_vessel_tracking_event_v1_round_trips_canonically():
    raw = json.loads(FIXTURE.read_text(encoding="utf-8"))
    parsed = VesselTrackingEventIn.model_validate(raw)

    assert parsed.canonical_payload() == raw
