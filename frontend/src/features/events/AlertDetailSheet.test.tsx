import { fireEvent, render, screen, within } from "@testing-library/react";
import { expect, test, vi } from "vitest";

import type {
  ManeuverEventDetailResponse,
  ManeuverEventFeedItem,
} from "../../api/contract";
import type { AlertDetailState } from "./useAlertDetail";
import { AlertDetailSheet } from "./AlertDetailSheet";


const MANEUVER_ID = "00000000-0000-4000-8000-000000001000";

function event(
  id: string,
  ingestionId: number,
  overrides: Partial<ManeuverEventFeedItem> = {},
): ManeuverEventFeedItem {
  return {
    event_id: id,
    maneuver_id: MANEUVER_ID,
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
    ingestion_id: ingestionId,
    ingested_at: "2026-09-28T15:00:01Z",
    ...overrides,
    operational_at: overrides.operational_at ?? null,
    operational_marker: overrides.operational_marker ?? null,
  };
}

const confirmed = event(
  "00000000-0000-4000-8000-000000001001",
  1,
);
const updated = event(
  "00000000-0000-4000-8000-000000001002",
  2,
  {
    event_type: "UPDATED",
    pob: "28/09 13:30",
    pob_at: "2026-09-28T13:30:00-03:00",
    occurred_at: "2026-09-28T12:20:00-03:00",
    changes: {
      pob: { from: "28/09 12:00", to: "28/09 13:30" },
      berth: { from: 4, to: 5 },
    },
    berth: 5,
  },
);
const completed = event(
  "00000000-0000-4000-8000-000000001003",
  3,
  {
    event_type: "COMPLETED",
    pob: "28/09 13:30",
    pob_at: "2026-09-28T13:30:00-03:00",
    occurred_at: "2026-09-28T13:50:00-03:00",
    berth: 5,
  },
);

function detail(events = [confirmed, updated, completed]): ManeuverEventDetailResponse {
  return {
    selected_event_id: updated.event_id,
    maneuver_id: MANEUVER_ID,
    events,
  };
}

function state(
  status: AlertDetailState["status"],
  value: ManeuverEventDetailResponse | null = null,
): AlertDetailState {
  return {
    status,
    detail: value,
    retry: vi.fn(),
  };
}

test("alert_detail_sheet_renders_loading_error_retry_and_not_found_states", () => {
  const onRetry = vi.fn();
  const { rerender } = render(
    <AlertDetailSheet
      open
      state={state("loading")}
      selectedEventId={updated.event_id}
      onClose={() => undefined}
      onRetry={onRetry}
    />,
  );
  expect(screen.getByText("Carregando detalhes…")).toBeInTheDocument();

  rerender(
    <AlertDetailSheet
      open
      state={state("error")}
      selectedEventId={updated.event_id}
      onClose={() => undefined}
      onRetry={onRetry}
    />,
  );
  fireEvent.click(screen.getByRole("button", { name: "Tentar novamente" }));
  expect(onRetry).toHaveBeenCalledTimes(1);

  rerender(
    <AlertDetailSheet
      open
      state={state("not-found")}
      selectedEventId={updated.event_id}
      onClose={() => undefined}
      onRetry={onRetry}
    />,
  );
  expect(
    screen.getByText(
      "Este alerta não está mais disponível no histórico recente.",
    ),
  ).toBeInTheDocument();
});

test("alert_detail_sheet_renders_summary_and_preserves_api_timeline_order", () => {
  render(
    <AlertDetailSheet
      open
      state={state("ready", detail())}
      selectedEventId={updated.event_id}
      onClose={() => undefined}
      onRetry={() => undefined}
    />,
  );

  expect(screen.getByRole("dialog", { name: "Detalhes do alerta" })).toBeInTheDocument();
  expect(screen.getByText("NAVIO ALFA")).toBeInTheDocument();
  expect(screen.getByText("IMO 9876543")).toBeInTheDocument();
  expect(screen.getAllByText("Atracação atualizada")).toHaveLength(2);
  expect(screen.getAllByText("POB vigente: 28/09 13:30")).toHaveLength(2);

  const items = screen.getAllByTestId("alert-timeline-event");
  expect(items).toHaveLength(3);
  expect(within(items[0]!).getByText("Atracação confirmada")).toBeInTheDocument();
  expect(within(items[1]!).getByText("Atracação atualizada")).toBeInTheDocument();
  expect(
    within(items[2]!).getByText("Atracação concluída"),
  ).toBeInTheDocument();
  expect(items[1]).toHaveAttribute("data-selected", "true");
  expect(items[0]).toHaveAttribute("data-selected", "false");
});

test("alert_detail_completed_uses_operational_duration_not_observation_delay", () => {
  const fernao = event(
    "00000000-0000-4000-8000-000000001050",
    4,
    {
      vessel_name: "FERNAO DE MAGALHAES",
      vessel_imo: "9603221",
      vessel_identity: "IMO:9603221",
      event_type: "COMPLETED",
      pob: "29/09 02:30",
      pob_at: "2026-09-29T02:30:00-03:00",
      operational_at: "2026-09-29T05:28:00-03:00",
      operational_marker: "ATRAC",
      first_observed_at: "2026-09-29T10:45:35-03:00",
      occurred_at: "2026-09-29T10:46:36-03:00",
      changes: null,
    },
  );

  render(
    <AlertDetailSheet
      open
      state={state("ready", {
        selected_event_id: fernao.event_id,
        maneuver_id: fernao.maneuver_id,
        events: [fernao],
      })}
      selectedEventId={fernao.event_id}
      onClose={() => undefined}
      onRetry={() => undefined}
    />,
  );

  expect(screen.getAllByText("Atracação concluída").length).toBeGreaterThan(0);
  expect(screen.getByText("ATRAC informado na planilha")).toBeInTheDocument();
  expect(screen.getByText("05:28")).toBeInTheDocument();
  expect(screen.getByText("Tempo da movimentação")).toBeInTheDocument();
  expect(screen.getByText("2h58")).toBeInTheDocument();
  expect(screen.getByText("Monitoramento do AlertaM")).toBeInTheDocument();
  expect(screen.getByText("Primeira observação")).toBeInTheDocument();
  expect(screen.getAllByText(/29\/09.*10:45/).length).toBeGreaterThan(0);
  expect(screen.getByText("Confirmação")).toBeInTheDocument();
  expect(screen.getAllByText(/29\/09.*10:46/).length).toBeGreaterThan(0);
  expect(screen.queryByText(/Diferença para o POB/i)).not.toBeInTheDocument();
});


test("alert_detail_sheet_close_is_keyboard_accessible", () => {
  const onClose = vi.fn();
  render(
    <AlertDetailSheet
      open
      state={state("ready", detail())}
      selectedEventId={updated.event_id}
      onClose={onClose}
      onRetry={() => undefined}
    />,
  );

  const close = screen.getByRole("button", { name: "Fechar detalhes do alerta" });
  expect(close).toHaveFocus();
  fireEvent.click(close);
  expect(onClose).toHaveBeenCalledTimes(1);
});

test("alert_detail_sheet_explains_retained_cycle_without_confirmed_event", () => {
  render(
    <AlertDetailSheet
      open
      state={state("ready", detail([updated, completed]))}
      selectedEventId={updated.event_id}
      onClose={() => undefined}
      onRetry={() => undefined}
    />,
  );

  expect(
    screen.getByText(
      "Esta manobra já estava em andamento quando o AlertaM iniciou.",
    ),
  ).toBeInTheDocument();
  expect(screen.getAllByTestId("alert-timeline-event")).toHaveLength(2);
});


function alertTrackingControls(tracked = false) {
  const record = tracked
    ? {
        tracked_vessel_id: "30000000-0000-4000-8000-000000000010",
        vessel_identity: "NAME:NAVIO ALFA",
        vessel_imo: null,
        vessel_name: "NAVIO ALFA",
        started_at: "2026-09-29T03:00:00-03:00",
        active: true,
        stopped_at: null,
        last_seen_at: null,
        current: null,
      }
    : null;
  return {
    findTracking: vi.fn().mockReturnValue(record),
    mutationPending: false,
    mutationError: null,
    startTracking: vi.fn().mockResolvedValue(true),
    stopTracking: vi.fn().mockResolvedValue(true),
    clearMutationError: vi.fn(),
  };
}

test("alert_detail_can_track_vessel_using_event_identity_even_if_absent_from_snapshot", () => {
  const controls = alertTrackingControls(false);
  render(
    <AlertDetailSheet
      open
      state={state("ready", detail())}
      selectedEventId={updated.event_id}
      onClose={() => undefined}
      onRetry={() => undefined}
      trackingControls={controls}
    />,
  );

  fireEvent.click(
    screen.getByRole("button", { name: "☆ Acompanhar navio" }),
  );

  expect(controls.startTracking).toHaveBeenCalledWith({
    vessel_identity: "IMO:9876543",
    vessel_imo: "9876543",
    vessel_name: "NAVIO ALFA",
  });
});

test("alert_detail_name_fallback_reuses_existing_tracking_instead_of_starting_second", () => {
  const controls = alertTrackingControls(true);
  const noImo = event(
    "00000000-0000-4000-8000-000000001099",
    9,
    {
      vessel_identity: "NAME:NAVIO ALFA",
      vessel_imo: null,
    },
  );
  render(
    <AlertDetailSheet
      open
      state={state("ready", detail([noImo]))}
      selectedEventId={noImo.event_id}
      onClose={() => undefined}
      onRetry={() => undefined}
      trackingControls={controls}
    />,
  );

  expect(screen.getByText(/identificação por nome exato/i)).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: /Acompanhando/ }));

  expect(controls.startTracking).not.toHaveBeenCalled();
  expect(controls.stopTracking).toHaveBeenCalledWith(
    "30000000-0000-4000-8000-000000000010",
  );
});
