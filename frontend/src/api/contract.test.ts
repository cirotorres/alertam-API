import fixture from "../test/fixtures/mobile_snapshot_v1.json";

import { parseSnapshotReadResponse } from "./contract";

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

test("rejects_unknown_schema_version", () => {
  const incompatible = {
    ...fixture,
    schema_version: 2,
  };

  expect(() => parseSnapshotReadResponse(responseWith(incompatible))).toThrow(
    "Versão de snapshot não suportada.",
  );
});


import maneuverEventFixture from "../../../api/tests/fixtures/maneuver_event_v1.json";
import { ManeuverEventSchema } from "./contract";

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
