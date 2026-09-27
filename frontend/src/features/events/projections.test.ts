import { expect, test } from "vitest";

import type { ManeuverEventFeedItem } from "../../api/contract";
import {
  alertItems,
  formatManeuverEvent,
  maneuverCycles,
} from "./projections";


function event(
  ingestion_id: number,
  event_type: ManeuverEventFeedItem["event_type"],
  overrides: Partial<ManeuverEventFeedItem> = {},
): ManeuverEventFeedItem {
  return {
    event_id: `00000000-0000-4000-8000-${String(ingestion_id).padStart(12, "0")}`,
    maneuver_id: "00000000-0000-4000-8000-000000000701",
    vessel_identity: "NAME:NAVIO A",
    vessel_imo: null,
    vessel_name: "NAVIO A",
    maneuver_type: "ATRACACAO",
    event_type,
    berth: 4,
    pob: "27/09 10:00",
    occurred_at: `2026-09-27T10:0${Math.min(ingestion_id, 9)}:00-03:00`,
    changes: null,
    ingestion_id,
    ingested_at: `2026-09-27T13:0${Math.min(ingestion_id, 9)}:00-03:00`,
    ...overrides,
  };
}

test("alert_items_are_newest_first_by_ingestion_not_occurred_at", () => {
  const items = alertItems([
    event(1, "CONFIRMED", { occurred_at: "2026-09-27T12:00:00-03:00" }),
    event(3, "COMPLETED", { occurred_at: "2026-09-27T10:00:00-03:00" }),
    event(2, "UPDATED"),
  ]);

  expect(items.map((item) => item.ingestion_id)).toEqual([3, 2, 1]);
});

test.each([
  ["CONFIRMED", "Atracação confirmada"],
  ["UPDATED", "Atracação atualizada"],
  ["COMPLETED", "Atracação concluída"],
  ["CANCELLED", "Atracação cancelada"],
] as const)("formats_%s_with_operational_title", (kind, title) => {
  const item = event(1, kind, {
    changes:
      kind === "UPDATED"
        ? { pob: { from: "09:30", to: "10:00" } }
        : null,
  });

  expect(formatManeuverEvent(item).title).toBe(title);
});

test("updated_formats_pob_and_berth_changes_in_one_event", () => {
  const item = event(2, "UPDATED", {
    berth: 5,
    pob: "10:30",
    changes: {
      pob: { from: "10:00", to: "10:30" },
      berth: { from: 4, to: 5 },
    },
  });

  const formatted = formatManeuverEvent(item);

  expect(formatted.detail).toContain("POB 10:00 → 10:30");
  expect(formatted.detail).toContain("Berço 4 → 5");
});

test("missing_pob_and_berth_are_omitted_not_replaced_by_fake_values", () => {
  const formatted = formatManeuverEvent(
    event(1, "COMPLETED", { pob: null, berth: null }),
  );

  expect(formatted.detail).not.toMatch(/POB|Berço|—|\?/);
});

test("history_groups_by_maneuver_id_and_keeps_shift_as_two_cycles", () => {
  const firstManeuver = "00000000-0000-4000-8000-000000000701";
  const secondManeuver = "00000000-0000-4000-8000-000000000702";
  const events = [
    event(1, "CONFIRMED", { maneuver_id: firstManeuver }),
    event(2, "UPDATED", {
      maneuver_id: firstManeuver,
      changes: { berth: { from: 4, to: 5 } },
    }),
    event(3, "COMPLETED", { maneuver_id: firstManeuver }),
    event(4, "CONFIRMED", {
      maneuver_id: secondManeuver,
      maneuver_type: "DESATRACACAO",
    }),
  ];

  const cycles = maneuverCycles(events);

  expect(cycles).toHaveLength(2);
  expect(cycles[0]?.maneuver_id).toBe(secondManeuver);
  expect(cycles[1]?.events.map((item) => item.ingestion_id)).toEqual([1, 2, 3]);
});
