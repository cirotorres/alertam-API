import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { expect, test, vi } from "vitest";

import type {
  TrackedVessel,
  TrackingTarget,
} from "../../api/trackingClient";
import { TemporaryApiError } from "../../api/snapshotClient";
import {
  TrackingProvider,
  useTracking,
} from "./TrackingProvider";

const TARGET: TrackingTarget = {
  vessel_identity: "IMO:1234567",
  vessel_imo: "1234567",
  vessel_name: "NAVIO A",
};

const TRACKED: TrackedVessel = {
  tracked_vessel_id: "10000000-0000-4000-8000-000000000001",
  vessel_identity: "IMO:1234567",
  vessel_imo: "1234567",
  vessel_name: "NAVIO A",
  started_at: "2026-09-29T03:00:00-03:00",
  active: true,
  stopped_at: null,
  last_seen_at: "2026-09-29T03:05:00-03:00",
  current: {
    present: true,
    status: "PREVISTO",
    section: "PREVISTO",
    berth: 4,
    side: "BB",
    eta: null,
    etb_ets: null,
    pob: null,
    pob_at: null,
  },
};

function Probe() {
  const state = useTracking();
  return (
    <>
      <div data-testid="summary">
        {state.status}:{state.trackings.length}:{state.mutationPending ? "busy" : "ready"}
      </div>
      <div data-testid="tracked">{state.isTracked(TARGET) ? "yes" : "no"}</div>
      <div data-testid="error">{state.mutationError ?? ""}</div>
      <button type="button" onClick={() => void state.startTracking(TARGET)}>
        start
      </button>
      <button
        type="button"
        onClick={() => void state.stopTracking(TRACKED.tracked_vessel_id)}
      >
        stop
      </button>
    </>
  );
}

const feedFetcher = vi.fn().mockResolvedValue({
  events: [],
  newest_cursor: 0,
});

test("provider_waits_for_session_and_does_not_depend_on_push_state", async () => {
  const listFetcher = vi.fn().mockResolvedValue([]);
  const { rerender } = render(
    <TrackingProvider
      sessionReady={false}
      listFetcher={listFetcher}
      eventFetcher={feedFetcher}
    >
      <Probe />
    </TrackingProvider>,
  );

  expect(screen.getByTestId("summary")).toHaveTextContent("idle:0");
  expect(listFetcher).not.toHaveBeenCalled();

  rerender(
    <TrackingProvider
      sessionReady
      listFetcher={listFetcher}
      eventFetcher={feedFetcher}
    >
      <Probe />
    </TrackingProvider>,
  );

  await waitFor(() => expect(listFetcher).toHaveBeenCalledOnce());
  expect(screen.getByTestId("summary")).toHaveTextContent("online:0");
});

test("start_and_stop_change_state_only_after_server_confirmation", async () => {
  let resolveStart!: (value: TrackedVessel) => void;
  const startFetcher = vi.fn().mockReturnValue(
    new Promise<TrackedVessel>((resolve) => {
      resolveStart = resolve;
    }),
  );
  const stopFetcher = vi.fn().mockResolvedValue(undefined);
  render(
    <TrackingProvider
      sessionReady
      listFetcher={vi.fn().mockResolvedValue([])}
      startFetcher={startFetcher}
      stopFetcher={stopFetcher}
      eventFetcher={feedFetcher}
    >
      <Probe />
    </TrackingProvider>,
  );
  await waitFor(() =>
    expect(screen.getByTestId("summary")).toHaveTextContent("online:0"),
  );

  fireEvent.click(screen.getByRole("button", { name: "start" }));
  expect(screen.getByTestId("tracked")).toHaveTextContent("no");
  await waitFor(() =>
    expect(screen.getByTestId("summary")).toHaveTextContent("busy"),
  );

  await act(async () => resolveStart(TRACKED));
  await waitFor(() => expect(screen.getByTestId("tracked")).toHaveTextContent("yes"));

  fireEvent.click(screen.getByRole("button", { name: "stop" }));
  await waitFor(() => expect(screen.getByTestId("tracked")).toHaveTextContent("no"));
});

test("temporary_mutation_failure_preserves_confirmed_state_and_surfaces_error", async () => {
  render(
    <TrackingProvider
      sessionReady
      listFetcher={vi.fn().mockResolvedValue([TRACKED])}
      startFetcher={vi.fn()}
      stopFetcher={vi.fn().mockRejectedValue(new TemporaryApiError())}
      eventFetcher={feedFetcher}
    >
      <Probe />
    </TrackingProvider>,
  );
  await waitFor(() => expect(screen.getByTestId("tracked")).toHaveTextContent("yes"));

  fireEvent.click(screen.getByRole("button", { name: "stop" }));

  await waitFor(() =>
    expect(screen.getByTestId("error")).toHaveTextContent(/não foi possível/i),
  );
  expect(screen.getByTestId("tracked")).toHaveTextContent("yes");
});

test("exact_name_fallback_matches_promoted_imo_target_without_duplicate", async () => {
  const fallback = {
    ...TRACKED,
    vessel_identity: "NAME:NAVIO A",
    vessel_imo: null,
  };
  render(
    <TrackingProvider
      sessionReady
      listFetcher={vi.fn().mockResolvedValue([fallback])}
      eventFetcher={feedFetcher}
    >
      <Probe />
    </TrackingProvider>,
  );

  await waitFor(() => expect(screen.getByTestId("tracked")).toHaveTextContent("yes"));
});
