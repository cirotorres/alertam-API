from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import TypeAdapter, ValidationError

import app.models.mobile_snapshot as snapshot_models

MobileSnapshotV1 = snapshot_models.MobileSnapshotV1


FIXTURE = Path(__file__).parents[1] / "fixtures" / "mobile_snapshot_v1.json"
V2_WEBPILOT = Path(__file__).parents[1] / "fixtures" / "mobile_snapshot_v2_webpilot.json"
V2_FALLBACK = Path(__file__).parents[1] / "fixtures" / "mobile_snapshot_v2_fallback.json"


def _payload() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def test_accepts_real_desktop_mobile_snapshot_v1():
    model = MobileSnapshotV1.model_validate(_payload())

    assert model.schema_version == 1
    assert str(model.boot_id) == "550e8400-e29b-41d4-a716-446655440000"
    assert model.sequence == 1

def test_rejects_unsupported_schema_version():
    payload = _payload()
    payload["schema_version"] = 2

    with pytest.raises(ValidationError) as exc:
        MobileSnapshotV1.model_validate(payload)

    assert any(error["loc"] == ("schema_version",) for error in exc.value.errors())


def test_rejects_extra_fields_anywhere_in_contract():
    payload = _payload()
    payload["unexpected"] = True

    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        MobileSnapshotV1.model_validate(payload)


def test_nullable_vessel_fields_are_still_required():
    payload = _payload()
    payload["vessels"][0].pop("imo")

    with pytest.raises(ValidationError) as exc:
        MobileSnapshotV1.model_validate(payload)

    assert any(error["loc"][-1] == "imo" for error in exc.value.errors())

@pytest.mark.parametrize("block", ["weather", "marine"])
def test_weather_and_marine_reject_partial_blocks(block):
    payload = _payload()
    first_key = next(iter(payload[block]))
    payload[block].pop(first_key)

    with pytest.raises(ValidationError):
        MobileSnapshotV1.model_validate(payload)


def test_weather_and_marine_accept_empty_blocks():
    payload = _payload()
    payload["weather"] = {}
    payload["marine"] = {}

    model = MobileSnapshotV1.model_validate(payload)

    assert model.model_dump(mode="json")["weather"] == {}
    assert model.model_dump(mode="json")["marine"] == {}


@pytest.mark.parametrize(
    ("path", "value"),
    [
        (("generated_at",), "2026-09-25T13:40:12"),
        (("collector", "last_collection_at"), "2026-09-25T13:40:12"),
    ],
)
def test_required_contract_timestamps_need_timezone(path, value):
    payload = _payload()

    target = payload
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value

    with pytest.raises(ValidationError):
        MobileSnapshotV1.model_validate(payload)


def test_weather_timestamp_when_present_needs_timezone():
    payload = _payload()
    payload["weather"]["observed_at"] = "2026-09-25T13:35:00"

    with pytest.raises(ValidationError):
        MobileSnapshotV1.model_validate(payload)


def test_active_maneuver_must_be_active_and_incomplete():
    payload = _payload()
    item = payload["recent_maneuvers"]["active"][0]
    item["status"] = "COMPLETED"
    item["completed_at"] = "2026-09-25T13:00:00-03:00"

    with pytest.raises(ValidationError):
        MobileSnapshotV1.model_validate(payload)

def test_completed_maneuver_must_have_completed_timestamp():
    payload = _payload()
    payload["recent_maneuvers"]["completed"][0]["completed_at"] = None

    with pytest.raises(ValidationError):
        MobileSnapshotV1.model_validate(payload)


def test_detected_at_needs_timezone():
    payload = _payload()
    payload["recent_maneuvers"]["active"][0]["detected_at"] = "2026-09-25T12:00:00"

    with pytest.raises(ValidationError):
        MobileSnapshotV1.model_validate(payload)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("boot_id", "not-a-uuid"),
        ("sequence", 0),
    ],
)
def test_rejects_invalid_boot_id_and_non_positive_sequence(field, value):
    payload = _payload()
    payload[field] = value

    with pytest.raises(ValidationError):
        MobileSnapshotV1.model_validate(payload)

def test_numeric_measurements_do_not_accept_numeric_strings():
    payload = _payload()
    payload["weather"]["air_temperature_c"] = "29.5"

    with pytest.raises(ValidationError):
        MobileSnapshotV1.model_validate(payload)


def _fixture(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _v2_type():
    model = getattr(snapshot_models, "MobileSnapshotV2", None)
    assert model is not None, "MobileSnapshotV2 ainda não implementado"
    return model


def _union_type():
    model = getattr(snapshot_models, "MobileSnapshot", None)
    assert model is not None, "MobileSnapshot union ainda não implementado"
    return model


def test_accepts_mobile_snapshot_v2_webpilot():
    model = _v2_type().model_validate(_fixture(V2_WEBPILOT))

    assert model.schema_version == 2
    assert model.atmosphere.primary.source == "webpilot"
    assert model.atmosphere.primary.mode == "observed"
    assert model.atmosphere.complementary.source == "open_meteo"
    assert model.marine.source == "open_meteo"


def test_accepts_mobile_snapshot_v2_open_meteo_fallback():
    model = _v2_type().model_validate(_fixture(V2_FALLBACK))

    assert model.atmosphere.primary.source == "open_meteo"
    assert model.atmosphere.primary.mode == "fallback"
    assert model.atmosphere.complementary.status == "unavailable"
    assert model.marine.status == "unavailable"


def test_union_still_accepts_v1_fixture():
    model = TypeAdapter(_union_type()).validate_python(_payload())

    assert isinstance(model, MobileSnapshotV1)
    assert model.schema_version == 1


def test_union_still_accepts_v1_with_empty_weather_and_marine_blocks():
    payload = _payload()
    payload["weather"] = {}
    payload["marine"] = {}

    model = TypeAdapter(_union_type()).validate_python(payload)

    assert isinstance(model, MobileSnapshotV1)
    assert model.model_dump(mode="json")["weather"] == {}
    assert model.model_dump(mode="json")["marine"] == {}


def test_v2_unavailable_block_rejects_extra_fields():
    payload = _fixture(V2_FALLBACK)
    payload["marine"]["wave_height_m"] = None

    with pytest.raises(ValidationError):
        _v2_type().model_validate(payload)


def test_v2_rejects_webpilot_fallback_pair():
    payload = _fixture(V2_WEBPILOT)
    payload["atmosphere"]["primary"]["mode"] = "fallback"

    with pytest.raises(ValidationError):
        _v2_type().model_validate(payload)


def test_v2_rejects_open_meteo_observed_pair():
    payload = _fixture(V2_FALLBACK)
    payload["atmosphere"]["primary"]["mode"] = "observed"

    with pytest.raises(ValidationError):
        _v2_type().model_validate(payload)


def test_v2_open_meteo_primary_requires_complementary_unavailable():
    payload = _fixture(V2_FALLBACK)
    payload["atmosphere"]["complementary"] = _fixture(V2_WEBPILOT)["atmosphere"]["complementary"]

    with pytest.raises(ValidationError):
        _v2_type().model_validate(payload)


def test_v2_required_timestamps_are_aware():
    payload = _fixture(V2_WEBPILOT)
    payload["atmosphere"]["primary"]["observed_at"] = "2026-09-28T20:30:26"

    with pytest.raises(ValidationError):
        _v2_type().model_validate(payload)


def test_v2_measurements_reject_numeric_strings():
    payload = _fixture(V2_WEBPILOT)
    payload["atmosphere"]["primary"]["wind_speed_current_kn"] = "16.95"

    with pytest.raises(ValidationError):
        _v2_type().model_validate(payload)
