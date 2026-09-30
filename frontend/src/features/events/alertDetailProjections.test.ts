import { expect, test } from "vitest";

import type { ManeuverEventFeedItem } from "../../api/contract";
import {
  formatMovementDuration,
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
    operational_at: overrides.operational_at ?? null,
    operational_marker: overrides.operational_marker ?? null,
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

test("format_movement_duration_omits_negative_operational_interval", () => {
  expect(
    formatMovementDuration(
      "2026-09-29T05:30:00-03:00",
      "2026-09-29T05:28:00-03:00",
    ),
  ).toBeNull();
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

test("completed_projection_uses_operational_duration_not_observation_delay", () => {
  const completed = event({
    vessel_name: "FERNAO DE MAGALHAES",
    event_type: "COMPLETED",
    pob: "29/09 02:30",
    occurred_at: "2026-09-29T10:46:36-03:00",
    pob_at: "2026-09-29T02:30:00-03:00",
    first_observed_at: "2026-09-29T10:45:35-03:00",
    operational_at: "2026-09-29T05:28:00-03:00",
    operational_marker: "ATRAC",
  });

  const projected = projectAlertTimelineItem([completed], 0);

  expect(projected.title).toBe("Atracação concluída");
  expect(projected.lines).toContain("POB vigente: 29/09 02:30");
  expect(projected.lines).toContain("ATRAC informado na planilha: 29/09 05:28");
  expect(projected.lines).toContain("Tempo da movimentação: 2h58");
  expect(projected.lines.some((line) => line.includes("Diferença para o POB"))).toBe(false);
  expect(projected.auxiliary).toBeNull();
  expect(projected.firstObservedAt).toBe("2026-09-29T10:45:35-03:00");
});

test("completed_projection_legacy_event_never_invents_movement_duration", () => {
  const completed = event({
    event_type: "COMPLETED",
    pob_at: "2026-09-28T12:00:00-03:00",
    pob: "28/09 12:00",
    occurred_at: "2026-09-28T12:50:00-03:00",
    operational_at: null,
    operational_marker: null,
  });

  const projected = projectAlertTimelineItem([completed], 0);

  expect(projected.title).toBe("Atracação concluída");
  expect(projected.lines).toContain("POB vigente: 28/09 12:00");
  expect(projected.lines.some((line) => line.includes("Tempo da movimentação"))).toBe(false);
  expect(projected.lines.some((line) => line.includes("Diferença para o POB"))).toBe(false);
  expect(projected.auxiliary).toBe("Horário operacional não disponível neste registro.");
});

test("completed_departure_uses_first_disappearance_as_approximate_duration", () => {
  const completed = event({
    maneuver_type: "DESATRACACAO",
    event_type: "COMPLETED",
    pob: "30/09 12:30",
    pob_at: "2026-09-30T12:30:00-03:00",
    first_observed_at: "2026-09-30T12:45:00-03:00",
    occurred_at: "2026-09-30T12:46:00-03:00",
  });

  const projected = projectAlertTimelineItem([completed], 0);

  expect(projected.title).toBe("Desatracação concluída");
  expect(projected.lines).toContain("Saída observada: 30/09 12:45");
  expect(projected.lines).toContain("Tempo aproximado da desatracação: 15 min");
  expect(projected.auxiliary).toBeNull();
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
