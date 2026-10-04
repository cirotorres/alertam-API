from __future__ import annotations

import json
from pathlib import Path

from pydantic import TypeAdapter

from app.models.mobile_snapshot import MobileSnapshot, MobileSnapshotV1


FIXTURE = Path(__file__).parents[1] / "fixtures" / "mobile_snapshot_v1.json"


def test_fixture_generated_by_desktop_matches_api_contract():
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))

    model = MobileSnapshotV1.model_validate(payload)

    assert model.model_dump(mode="json")["schema_version"] == 1
    assert "linhas_brutas" not in repr(payload)
    assert "SEGREDO" not in repr(payload)


def test_vessel_fixture_uses_exact_mobile_v1_whitelist():
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))

    assert set(payload["vessels"][0]) == {
        "name",
        "imo",
        "status",
        "section",

        "berth",
        "side",
        "eta",
        "etb_ets",
        "pob",
        "flag",
        "origin_port",
        "irin",
        "agency",
        "tugs",
    }


def test_root_fixture_uses_exact_mobile_v1_shape():
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))

    assert set(payload) == {
        "schema_version",
        "boot_id",
        "sequence",
        "generated_at",
        "collector",
        "port",
        "vessels",
        "weather",
        "marine",
        "recent_maneuvers",
    }


def test_v2_fixtures_match_union_contract_and_contain_no_session_material():
    fixtures = [
        Path(__file__).parents[1] / "fixtures" / "mobile_snapshot_v2_webpilot.json",
        Path(__file__).parents[1] / "fixtures" / "mobile_snapshot_v2_fallback.json",
    ]
    adapter = TypeAdapter(MobileSnapshot)

    for fixture in fixtures:
        payload = json.loads(fixture.read_text(encoding="utf-8"))
        model = adapter.validate_python(payload)
        dumped = model.model_dump(mode="json")

        assert dumped["schema_version"] == 2
        serialized = json.dumps(dumped).lower()
        for forbidden in (
            "cookie",
            "authorization",
            "session_generation",
            "html",
            "webpilot_token",
        ):
            assert forbidden not in serialized
