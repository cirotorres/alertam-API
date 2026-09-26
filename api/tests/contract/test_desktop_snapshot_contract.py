from __future__ import annotations

import json
from pathlib import Path

from app.models.mobile_snapshot import MobileSnapshotV1


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
