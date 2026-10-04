import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { expect, test, vi } from "vitest";

import {
  StaticTrackingProvider,
  type TrackingState,
} from "../features/tracking/TrackingProvider";
import { TrackedVesselsPage } from "./TrackedVesselsPage";

const TRACK_ID = "10000000-0000-4000-8000-000000000001";
const EVENT_ID = "20000000-0000-4000-8000-000000000001";
const tracked = {
  tracked_vessel_id: TRACK_ID,
  vessel_identity: "IMO:1234567",
  vessel_imo: "1234567",
  vessel_name: "NAVIO A",
  started_at: "2026-09-29T03:00:00-03:00",
  active: true,
  stopped_at: null,
  last_seen_at: "2026-09-29T03:05:00-03:00",
  current: {
    present: false,
    status: "PREVISTO",
    section: "PREVISTO",
    berth: 4,
    side: "BB",
    eta: "29/09 05:30",
    etb_ets: "29/09 06:30",
    pob: null,
    pob_at: null,
  },
};

const state: TrackingState = {
  trackings: [tracked],
  status: "online",
  newTrackingEvent: null,
  mutationPending: false,
  mutationError: null,
  findTracking: () => tracked,
  isTracked: () => true,
  startTracking: async () => true,
  stopTracking: async () => true,
  refresh: async () => true,
  clearMutationError: () => undefined,
};

const timelineFetcher = vi.fn().mockResolvedValue({
  tracked_vessel_id: TRACK_ID,
  events: [
    {
      kind: "TRACKING",
      ingestion_id: 1,
      ingested_at: "2026-09-29T06:10:01Z",
      event: {
        event_id: EVENT_ID,
        vessel_identity: "IMO:1234567",
        vessel_imo: "1234567",
        vessel_name: "NAVIO A",
        occurred_at: "2026-09-29T03:10:00-03:00",
        first_observed_at: "2026-09-29T03:10:00-03:00",
        maneuver_id: null,
        changes: { eta: { from: "05:00", to: "05:30" } },
        current: {
          present: false,
          status: "PREVISTO",
          section: "PREVISTO",
          berth: 4,
          side: "BB",
          eta: "05:30",
          etb_ets: "06:30",
          pob: null,
          pob_at: null,
        },
      },
    },
  ],
});

function renderPage(
  route = "/acompanhados",
  trackingState: TrackingState = state,
) {
  return render(
    <StaticTrackingProvider state={trackingState}>
      <MemoryRouter initialEntries={[route]}>
        <TrackedVesselsPage timelineFetcher={timelineFetcher} />
      </MemoryRouter>
    </StaticTrackingProvider>,
  );
}

test("lists_absent_tracked_vessel_with_last_known_state", () => {
  renderPage();

  expect(screen.getByRole("heading", { name: "Acompanhados" })).toBeInTheDocument();
  expect(screen.getByText("NAVIO A")).toBeInTheDocument();
  expect(screen.getByText("Ausente · aguardando retorno")).toBeInTheDocument();
  expect(screen.getByText(/Berço 4/)).toBeInTheDocument();
});

test("deep_link_opens_timeline_highlights_event_and_close_keeps_page", async () => {
  renderPage(`/acompanhados?track=${TRACK_ID}&event=${EVENT_ID}&keep=1`);

  expect(
    await screen.findByRole("dialog", { name: "Detalhes do acompanhamento" }),
  ).toBeInTheDocument();
  await waitFor(() => expect(timelineFetcher).toHaveBeenCalledWith(
    TRACK_ID,
    expect.any(AbortSignal),
  ));
  const selected = await screen.findByTestId(`tracking-event-${EVENT_ID}`);
  expect(selected).toHaveClass("is-selected");
  expect(selected).toHaveTextContent(/ETA/);
  expect(screen.getByText("Do mais antigo ao mais recente")).toBeInTheDocument();
  expect(selected).toHaveTextContent(/Registrado pelo AlertaM às/);
  expect(
    selected.closest(".alert-detail-sheet__timeline--connected"),
  ).not.toBeNull();

  fireEvent.click(
    screen.getByRole("button", { name: "Fechar detalhes do acompanhamento" }),
  );

  expect(screen.getByRole("heading", { name: "Acompanhados" })).toBeInTheDocument();
  expect(
    screen.queryByRole("dialog", { name: "Detalhes do acompanhamento" }),
  ).not.toBeInTheDocument();
});

test("unread_tracking_row_is_highlighted_and_opening_marks_only_that_vessel_read", async () => {
  const markTrackingRead = vi.fn();
  const unreadState = {
    ...state,
    isTrackingUnread: (trackedVesselId: string) => trackedVesselId === TRACK_ID,
    markTrackingRead,
  } as TrackingState;

  renderPage("/acompanhados", unreadState);

  const action = screen.getByRole("button", { name: /NAVIO A.*Ausente/i });
  const row = action.closest("li");
  expect(row).toHaveClass("is-unread");

  fireEvent.click(action);

  expect(markTrackingRead).toHaveBeenCalledWith(TRACK_ID);
  await screen.findByRole("dialog", {
    name: "Detalhes do acompanhamento",
  });
});

test("row_action_opens_bottom_sheet_outside_scroll_surface", async () => {
  renderPage();
  fireEvent.click(screen.getByRole("button", { name: /NAVIO A.*Ausente/i }));

  const dialog = await screen.findByRole("dialog", {
    name: "Detalhes do acompanhamento",
  });
  expect(dialog).toBeInTheDocument();
  expect(dialog.closest(".page-stack--continuous-scroll")).toBeNull();
});
