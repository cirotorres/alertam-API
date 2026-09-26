import fixture from "../../test/fixtures/mobile_snapshot_v1.json";
import { parseSnapshotReadResponse, type MobileSnapshotV1 } from "../../api/contract";
import {
  anchoredVessels,
  arrivalForecast,
  confirmedManeuvers,
  departureForecast,
  maneuverHistory,
  recentAlerts,
  vesselByBerth,
} from "./projections";

function snapshotWith(
  vessels: MobileSnapshotV1["vessels"],
  maneuvers = fixture.recent_maneuvers,
) {
  return parseSnapshotReadResponse({
    snapshot: { ...fixture, vessels, recent_maneuvers: maneuvers },
    meta: {
      received_at: "2026-09-25T13:40:15-03:00",
      age_seconds: 3,
      collector_online: true,
      stale_after_seconds: 120,
    },
  }).snapshot;
}

const base = fixture.vessels[0];
test("projects_footer_lists_like_desktop", () => {
  const vessels: MobileSnapshotV1["vessels"] = [
    { ...base, name: "FUNDEADO A", section: "FUNDEADO", status: "FUNDEADO", eta: "25/09 08:00", etb_ets: "25/09 12:00", berth: 1 },
    { ...base, name: "PREVISTO B", section: "PREVISTO", status: "PREVISTO", etb_ets: "25/09 10:00", berth: 2 },
    { ...base, name: "ATRACADO C", section: "ATRACADO", status: "ATRACADO", etb_ets: "25/09 14:00", berth: 3 },
    { ...base, name: "SEM ETB", section: "PREVISTO", status: "PREVISTO", etb_ets: null, berth: 4 },
  ];
  const snapshot = snapshotWith(vessels);

  expect(confirmedManeuvers(snapshot).map((m) => m.id)).toEqual(["m1"]);
  expect(arrivalForecast(snapshot).map((v) => v.name)).toEqual(["PREVISTO B", "FUNDEADO A"]);
  expect(departureForecast(snapshot).map((v) => v.name)).toEqual(["ATRACADO C"]);
  expect(anchoredVessels(snapshot).map((v) => v.name)).toEqual(["FUNDEADO A"]);
});

test("deduplicates_by_first_vessel_name_and_prioritizes_map_status", () => {
  const vessels: MobileSnapshotV1["vessels"] = [
    { ...base, name: "DUP", section: "FUNDEADO", status: "FUNDEADO", etb_ets: "25/09 11:00", berth: 5 },
    { ...base, name: "DUP", section: "PREVISTO", status: "PREVISTO", etb_ets: "25/09 09:00", berth: 6 },
    { ...base, name: "ATRACADO", section: "ATRACADO", status: "ATRACADO", etb_ets: null, berth: 7 },
    { ...base, name: "ATRACANDO", section: "FUNDEADO", status: "ATRACANDO", etb_ets: null, berth: 7 },
    { ...base, name: "DESATRACANDO", section: "ATRACADO", status: "DESATRACANDO", etb_ets: null, berth: 7 },
  ];
  const snapshot = snapshotWith(vessels);

  expect(arrivalForecast(snapshot).map((v) => [v.name, v.berth])).toEqual([["DUP", 5]]);
  expect(vesselByBerth(snapshot, 7)?.name).toBe("DESATRACANDO");
});
test("alerts_are_short_active_first_and_history_keeps_all_recent_maneuvers", () => {
  const active = Array.from({ length: 3 }, (_, index) => ({
    ...fixture.recent_maneuvers.active[0],
    id: `a${index}`,
    vessel_name: `ATIVO ${index}`,
    detected_at: `2026-09-25T1${index}:00:00-03:00`,
  }));
  const completed = Array.from({ length: 9 }, (_, index) => ({
    ...fixture.recent_maneuvers.completed[0],
    id: `c${index}`,
    vessel_name: `FINAL ${index}`,
    detected_at: `2026-09-24T0${index}:00:00-03:00`,
    completed_at: `2026-09-25T0${index}:30:00-03:00`,
  }));
  const snapshot = snapshotWith([], { active, completed });

  const alerts = recentAlerts(snapshot);
  expect(alerts).toHaveLength(10);
  expect(alerts.slice(0, 3).every((item) => item.status === "ACTIVE")).toBe(true);
  expect(alerts[0]?.id).toBe("a2");
  expect(maneuverHistory(snapshot)).toHaveLength(12);
});
