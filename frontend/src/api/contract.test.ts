import fixture from "../test/fixtures/mobile_snapshot_v1.json";
import v2WebPilot from "../test/fixtures/mobile_snapshot_v2_webpilot.json";
import v2Fallback from "../test/fixtures/mobile_snapshot_v2_fallback.json";

import {
  ManeuverEventSchema,
  parseManeuverEventDetailResponse,
  parseSnapshotReadResponse,
} from "./contract";

function responseWith(snapshot: unknown) {
  return {
    snapshot,
    meta: {
      received_at: "2026-09-25T13:40:15-03:00",
      age_seconds: 3,
      collector_online: true,
      stale_after_seconds: 120,
    },
  };
}

test("parses_real_mobile_snapshot_v1", () => {
  const parsed = parseSnapshotReadResponse(responseWith(fixture));

  expect(parsed.snapshot.schema_version).toBe(1);
  expect(parsed.snapshot.vessels[0]?.name).toBe("NAVIO A");
  expect(parsed.snapshot.recent_maneuvers.active[0]?.id).toBe("m1");
  expect(parsed.meta.collector_online).toBe(true);
});

test.each(["source", "authority_epoch", "authority_lease_id", "holder_instance_id"])(
  "C3-A: strict PWA response rejects authority metadata %s at every envelope boundary",
  (field) => {
    for (const base of [
      { ...responseWith(fixture), [field]: "unexpected" },
      { ...responseWith(fixture), meta: { ...responseWith(fixture).meta, [field]: "unexpected" } },
      { ...responseWith(fixture), snapshot: { ...fixture, [field]: "unexpected" } },
    ]) {
      expect(() => parseSnapshotReadResponse(base)).toThrow("Resposta de snapshot inválida.");
    }
  },
);

test("C3-A: existing v1/v2 envelopes still parse without authority metadata", () => {
  for (const snapshot of [fixture, v2WebPilot, v2Fallback]) {
    const result = parseSnapshotReadResponse(responseWith(snapshot));
    expect(Object.keys(result).sort()).toEqual(["meta", "snapshot"]);
    expect(Object.keys(result.meta).sort()).toEqual([
      "age_seconds", "collector_online", "device_enabled", "received_at", "stale_after_seconds",
    ]);
    expect(Object.keys(result.snapshot)).not.toContain("authority_epoch");
    expect(Object.keys(result.snapshot)).not.toContain("authority_lease_id");
    expect(Object.keys(result.snapshot)).not.toContain("holder_instance_id");
  }
});

test("rejects_unknown_schema_version", () => {
  const incompatible = {
    ...fixture,
    schema_version: 3,
  };

  expect(() => parseSnapshotReadResponse(responseWith(incompatible))).toThrow(
    "Versão de snapshot não suportada.",
  );
});


test("parses_mobile_snapshot_v2_webpilot", () => {
  const parsed = parseSnapshotReadResponse(responseWith(v2WebPilot));

  expect(parsed.snapshot.schema_version).toBe(2);
  if (parsed.snapshot.schema_version !== 2) throw new Error("expected v2");
  expect(parsed.snapshot.atmosphere.primary.status).toBe("fresh");
  expect("source" in parsed.snapshot.atmosphere.primary && parsed.snapshot.atmosphere.primary.source).toBe("webpilot");
  expect(parsed.snapshot.marine.status).toBe("fresh");
});

test("parses_mobile_snapshot_v2_open_meteo_fallback", () => {
  const parsed = parseSnapshotReadResponse(responseWith(v2Fallback));

  expect(parsed.snapshot.schema_version).toBe(2);
  if (parsed.snapshot.schema_version !== 2) throw new Error("expected v2");
  expect(parsed.snapshot.atmosphere.primary.status).toBe("stale");
  expect("source" in parsed.snapshot.atmosphere.primary && parsed.snapshot.atmosphere.primary.source).toBe("open_meteo");
  expect(parsed.snapshot.atmosphere.complementary.status).toBe("unavailable");
});

test("rejects_v2_unavailable_with_extra_fields", () => {
  const invalid = structuredClone(v2Fallback);
  Object.assign(invalid.marine, { wave_height_m: null });

  expect(() => parseSnapshotReadResponse(responseWith(invalid))).toThrow();
});

test("rejects_v2_invalid_source_mode_combination", () => {
  const invalid = structuredClone(v2WebPilot);
  invalid.atmosphere.primary.mode = "fallback" as "observed";

  expect(() => parseSnapshotReadResponse(responseWith(invalid))).toThrow();
});

test("rejects_v2_fresh_block_missing_required_structural_field", () => {
  const invalid = structuredClone(v2WebPilot) as Record<string, any>;
  delete invalid.atmosphere.primary.consulted_at;

  expect(() => parseSnapshotReadResponse(responseWith(invalid))).toThrow();
});

test("rejects_v2_open_meteo_primary_with_complementary_data", () => {
  const invalid = structuredClone(v2Fallback);
  invalid.atmosphere.complementary = structuredClone(v2WebPilot.atmosphere.complementary) as typeof invalid.atmosphere.complementary;

  expect(() => parseSnapshotReadResponse(responseWith(invalid))).toThrow();
});


import maneuverEventFixture from "../../../api/tests/fixtures/maneuver_event_v1.json";

test("parses_real_desktop_maneuver_event_v1", () => {
  const parsed = ManeuverEventSchema.parse(maneuverEventFixture);

  expect(parsed.event_type).toBe("UPDATED");
  expect(parsed.changes?.pob?.from).toBe("27/09 10:00");
  expect(parsed.changes?.berth?.to).toBe(5);
});

test("maneuver_event_contract_rejects_extra_fields_and_invalid_changes", () => {
  expect(() =>
    ManeuverEventSchema.parse({
      ...maneuverEventFixture,
      extra: "forbidden",
    }),
  ).toThrow();

  expect(() =>
    ManeuverEventSchema.parse({
      ...maneuverEventFixture,
      changes: {
        eta: { from: "10:00", to: "10:30" },
      },
    }),
  ).toThrow();
});

test("maneuver_event_contract_requires_null_changes_outside_updated", () => {
  expect(() =>
    ManeuverEventSchema.parse({
      ...maneuverEventFixture,
      event_type: "CONFIRMED",
    }),
  ).toThrow();
});


test("maneuver_event_contract_normalizes_legacy_missing_timestamps_to_null", () => {
  const {
    pob_at: _pobAt,
    first_observed_at: _firstObservedAt,
    ...legacy
  } = maneuverEventFixture;

  const parsed = ManeuverEventSchema.parse(legacy);

  expect(parsed.pob_at).toBeNull();
  expect(parsed.first_observed_at).toBeNull();
});

test("maneuver_event_contract_accepts_aware_canonical_timestamps", () => {
  const parsed = ManeuverEventSchema.parse(maneuverEventFixture);

  expect(parsed.pob_at).toBe("2026-09-27T10:30:00-03:00");
  expect(parsed.first_observed_at).toBe("2026-09-27T10:04:00-03:00");
  expect(parsed.operational_at).toBeNull();
  expect(parsed.operational_marker).toBeNull();
});


test("maneuver_event_contract_accepts_operational_atrac_pair", () => {
  const parsed = ManeuverEventSchema.parse({
    ...maneuverEventFixture,
    event_type: "COMPLETED",
    changes: null,
    operational_at: "2026-09-29T05:28:00-03:00",
    operational_marker: "ATRAC",
  });

  expect(parsed.operational_at).toBe("2026-09-29T05:28:00-03:00");
  expect(parsed.operational_marker).toBe("ATRAC");
});


test("maneuver_event_contract_rejects_invalid_operational_pair", () => {
  expect(() => ManeuverEventSchema.parse({
    ...maneuverEventFixture,
    event_type: "COMPLETED",
    changes: null,
    operational_at: "2026-09-29T05:28:00-03:00",
    operational_marker: null,
  })).toThrow();

  expect(() => ManeuverEventSchema.parse({
    ...maneuverEventFixture,
    event_type: "CONFIRMED",
    changes: null,
    operational_at: "2026-09-29T05:28:00-03:00",
    operational_marker: "ATRAC",
  })).toThrow();
});

test("maneuver_event_detail_response_parses_enriched_timeline", () => {
  const parsed = parseManeuverEventDetailResponse({
    selected_event_id: maneuverEventFixture.event_id,
    maneuver_id: maneuverEventFixture.maneuver_id,
    events: [
      {
        ...maneuverEventFixture,
        ingestion_id: 7,
        ingested_at: "2026-09-27T13:05:01-03:00",
      },
    ],
  });

  expect(parsed.events[0]?.pob_at).toBe("2026-09-27T10:30:00-03:00");
  expect(parsed.selected_event_id).toBe(maneuverEventFixture.event_id);
});

test("maneuver_event_detail_response_rejects_extra_fields", () => {
  expect(() =>
    parseManeuverEventDetailResponse({
      selected_event_id: maneuverEventFixture.event_id,
      maneuver_id: maneuverEventFixture.maneuver_id,
      events: [],
      device_id: "forbidden",
    }),
  ).toThrow();
});
