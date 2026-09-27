import fixture from "../../test/fixtures/mobile_snapshot_v1.json";
import { parseSnapshotReadResponse } from "../../api/contract";
import { BERTH_POSITIONS, selectMapVessels } from "./berthMap";

test("converts_desktop_500px_coordinates_to_percentages", () => {
  expect(BERTH_POSITIONS[1]).toEqual({ xPct: 37, yPct: 75 });
  expect(BERTH_POSITIONS[10]).toEqual({ xPct: 24, yPct: 12 });
});

test("selects_one_vessel_per_berth_by_priority_and_sprite", () => {
  const base = fixture.vessels[0];
  const snapshot = parseSnapshotReadResponse({
    snapshot: {
      ...fixture,
      vessels: [
        { ...base, name: "A", status: "ATRACADO", section: "ATRACADO", berth: 7 },
        { ...base, name: "B", status: "ATRACANDO", section: "FUNDEADO", berth: 7 },
        { ...base, name: "C", status: "DESATRACANDO", section: "ATRACADO", berth: 7 },
        { ...base, name: "D", status: "FUNDEADO", section: "FUNDEADO", berth: 8 },
      ],
    },
    meta: { received_at: "2026-09-25T13:40:15-03:00", age_seconds: 3, collector_online: true, stale_after_seconds: 120 },
  }).snapshot;

  expect(selectMapVessels(snapshot)).toEqual([
    expect.objectContaining({
      berth: 7,
      vessel: expect.objectContaining({ name: "C" }),
      sprite: "/assets/navio_red.png",
      position: BERTH_POSITIONS[7],
      moving: true,
    }),
  ]);
});
