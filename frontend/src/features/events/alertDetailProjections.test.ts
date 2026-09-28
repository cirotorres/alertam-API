import { expect, test } from "vitest";

import type { ManeuverEventFeedItem } from "../../api/contract";
import {
  formatObservedDelta,
  formatPobUpdateDelta,
  projectAlertTimelineItem,
} from "./alertDetailProjections";


function event(
  overrides: Partial<ManeuverEventFeedItem> = {},
): ManeuverEventFeedItem {
  return {
    event_id: "00000000-0000-4000-8000-000000000901",
    maneuver_id: "00000000-0000-4000-8000-000000000900",
    vessel_identity: "IMO:9876543",
    vessel_imo: "9876543",
    vessel_name: "NAVIO ALFA",
    maneuver_type: "ATRACACAO",
    event_type: "CONFIRMED",
    berth: 4,
    pob: "28/09 12:00",
    occurred_at: "2026-09-28T12:00:00-03:00",
    pob_at: "2026-09-28T12:00:00-03:00",
    first_observed_at: "2026-09-28T11:59:00-03:00",
    changes: null,
    ingestion_id: 1,
    ingested_at: "2026-09-28T15:00:01Z",
    ...overrides,
  };
}

test("format_observed_delta_uses_only_canonical_aware_timestamps", () => {
  expect(
    formatObservedDelta(
      "2026-09-28T12:00:00-03:00",
      "2026-09-28T12:50:00-03:00",
    ),
  ).toBe("50 min depois");
  expect(
    formatObservedDelta(
      "2026-09-28T12:00:00-03:00",
      "2026-09-28T11:30:00-03:00",
    ),
  ).toBe("30 min antes");
  expect(
    formatObservedDelta(
      "2026-09-28T12:00:00-03:00",
      "2026-09-28T12:00:00-03:00",
    ),
  ).toBe("0 min");

  expect(formatObservedDelta(null, "2026-09-28T12:50:00-03:00")).toBeNull();
  expect(formatObservedDelta("28/09 12:00", "2026-09-28T12:50:00-03:00")).toBeNull();
  expect(formatObservedDelta("2026-09-28T12:00:00", "2026-09-28T12:50:00-03:00")).toBeNull();
});

test("format_pob_update_delta_compares_current_and_previous_canonical_pob", () => {
  const events = [
    event({ pob_at: "2026-09-28T12:00:00-03:00" }),
    event({
      event_id: "00000000-0000-4000-8000-000000000902",
      event_type: "UPDATED",
      pob_at: "2026-09-28T13:30:00-03:00",
      changes: { pob: { from: "28/09 12:00", to: "28/09 13:30" } },
      ingestion_id: 2,
    }),
  ];

  expect(formatPobUpdateDelta(events, 1)).toBe("1h30 depois");

  const withoutPreviousCanonical = [
    event({ pob_at: null, pob: "texto que não deve ser interpretado" }),
    events[1]!,
  ];
  expect(formatPobUpdateDelta(withoutPreviousCanonical, 1)).toBeNull();
});

test("completed_projection_uses_safe_observed_language_and_approximate_note", () => {
  const completed = event({
    event_type: "COMPLETED",
    occurred_at: "2026-09-28T12:50:00-03:00",
    pob_at: "2026-09-28T12:00:00-03:00",
    first_observed_at: "2026-09-28T12:49:00-03:00",
  });

  const projected = projectAlertTimelineItem([completed], 0);

  expect(projected.title).toBe("Conclusão observada pelo AlertaM");
  expect(projected.lines).toContain("POB vigente: 28/09 12:00");
  expect(projected.lines).toContain("Diferença para o POB: 50 min depois");
  expect(projected.auxiliary).toBe(
    "Horário aproximado baseado na atualização da planilha.",
  );
  expect(projected.firstObservedAt).toBe("2026-09-28T12:49:00-03:00");
});

test("completed_projection_omits_delta_when_canonical_pob_is_unavailable", () => {
  const completed = event({
    event_type: "COMPLETED",
    pob_at: null,
    pob: "28/09 12:00",
    occurred_at: "2026-09-28T12:50:00-03:00",
  });

  const projected = projectAlertTimelineItem([completed], 0);

  expect(projected.lines).toContain("POB vigente: 28/09 12:00");
  expect(projected.lines.some((line) => line.includes("Diferença"))).toBe(false);
});

test("updated_projection_shows_pob_berth_and_optional_canonical_delta", () => {
  const events = [
    event({ pob_at: "2026-09-28T12:00:00-03:00" }),
    event({
      event_id: "00000000-0000-4000-8000-000000000903",
      event_type: "UPDATED",
      berth: 5,
      pob: "28/09 13:30",
      pob_at: "2026-09-28T13:30:00-03:00",
      first_observed_at: null,
      changes: {
        pob: { from: "28/09 12:00", to: "28/09 13:30" },
        berth: { from: 4, to: 5 },
      },
      ingestion_id: 2,
    }),
  ];

  const projected = projectAlertTimelineItem(events, 1);

  expect(projected.lines).toContain("POB: 28/09 12:00 → 28/09 13:30");
  expect(projected.lines).toContain("Diferença do POB: 1h30 depois");
  expect(projected.lines).toContain("Berço: 4 → 5");
  expect(projected.firstObservedAt).toBeNull();
});
