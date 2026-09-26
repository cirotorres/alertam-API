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
