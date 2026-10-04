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
      <div data-testid="eta">{state.trackings[0]?.current?.eta ?? ""}</div>
      <div data-testid="unread">
        {state.isTrackingUnread?.(TRACKED.tracked_vessel_id) ? "unread" : "read"}
      </div>
      <button type="button" onClick={() => void state.startTracking(TARGET)}>
        start
      </button>
      <button
        type="button"
        onClick={() => void state.stopTracking(TRACKED.tracked_vessel_id)}
      >
        stop
      </button>
      <button
        type="button"
        onClick={() => state.markTrackingRead?.(TRACKED.tracked_vessel_id)}
      >
        mark-read
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


test("new_tracking_event_refreshes_authoritative_tracked_vessel_projection", async () => {
  const refreshed = {
    ...TRACKED,
    last_seen_at: "2026-09-29T03:10:00-03:00",
    current: {
      ...TRACKED.current!,
      eta: "29/09 05:30",
    },
  };
  const listFetcher = vi
    .fn()
    .mockResolvedValueOnce([TRACKED])
    .mockResolvedValueOnce([refreshed]);
  const eventFetcher = vi
    .fn()
    .mockResolvedValueOnce({ events: [], newest_cursor: 0 })
    .mockResolvedValueOnce({
      events: [
        {
          tracked_vessel_id: TRACKED.tracked_vessel_id,
          ingestion_id: 1,
          ingested_at: "2026-09-29T06:10:01Z",
          event: {
            event_id: "20000000-0000-4000-8000-000000000099",
            vessel_identity: TRACKED.vessel_identity,
            vessel_imo: TRACKED.vessel_imo,
            vessel_name: TRACKED.vessel_name,
            occurred_at: "2026-09-29T03:10:00-03:00",
            first_observed_at: "2026-09-29T03:10:00-03:00",
            maneuver_id: null,
            changes: { eta: { from: null, to: "29/09 05:30" } },
            current: {
              present: true,
              status: "PREVISTO",
              section: "PREVISTO",
              berth: 4,
              side: "BB",
              eta: "29/09 05:30",
              etb_ets: null,
              pob: null,
              pob_at: null,
            },
          },
        },
      ],
      newest_cursor: 1,
    });

  Object.defineProperty(document, "visibilityState", {
    configurable: true,
    value: "visible",
  });
  render(
    <TrackingProvider
      sessionReady
      listFetcher={listFetcher}
      eventFetcher={eventFetcher}
    >
      <Probe />
    </TrackingProvider>,
  );

  await waitFor(() => expect(listFetcher).toHaveBeenCalledTimes(1));
  expect(screen.getByTestId("eta")).toHaveTextContent("");

  Object.defineProperty(document, "visibilityState", {
    configurable: true,
    value: "hidden",
  });
  document.dispatchEvent(new Event("visibilitychange"));
  Object.defineProperty(document, "visibilityState", {
    configurable: true,
    value: "visible",
  });
  document.dispatchEvent(new Event("visibilitychange"));

  await waitFor(() => expect(eventFetcher).toHaveBeenCalledTimes(2));
  await waitFor(() => expect(listFetcher).toHaveBeenCalledTimes(2));
  expect(screen.getByTestId("eta")).toHaveTextContent("29/09 05:30");
});


test("saved_cursor_marks_missed_tracking_as_unread_and_read_action_persists_clear", async () => {
  const scope = "pecem-01:11111111-2222-4333-8444-555555555555";
  const storageKey = "alertam.mobile.tracking.unread.v1:" + scope;
  localStorage.setItem(
    storageKey,
    JSON.stringify({ cursor: 5, unreadTrackedVesselIds: [] }),
  );
  const eventFetcher = vi.fn().mockResolvedValueOnce({
    events: [
      {
        tracked_vessel_id: TRACKED.tracked_vessel_id,
        ingestion_id: 6,
        ingested_at: "2026-09-29T06:10:01Z",
        event: {
          event_id: "20000000-0000-4000-8000-000000000106",
          vessel_identity: TRACKED.vessel_identity,
          vessel_imo: TRACKED.vessel_imo,
          vessel_name: TRACKED.vessel_name,
          occurred_at: "2026-09-29T03:10:00-03:00",
          first_observed_at: "2026-09-29T03:10:00-03:00",
          maneuver_id: null,
          changes: { eta: { from: null, to: "29/09 05:30" } },
          current: {
            present: true,
            status: "PREVISTO",
            section: "PREVISTO",
            berth: 4,
            side: "BB",
            eta: "29/09 05:30",
            etb_ets: null,
            pob: null,
            pob_at: null,
          },
        },
      },
    ],
    newest_cursor: 6,
  });

  render(
    <TrackingProvider
      sessionReady
      storageScope={scope}
      listFetcher={vi.fn().mockResolvedValue([TRACKED])}
      eventFetcher={eventFetcher}
    >
      <Probe />
    </TrackingProvider>,
  );

  await waitFor(() =>
    expect(screen.getByTestId("unread")).toHaveTextContent("unread"),
  );
  expect(eventFetcher).toHaveBeenCalledWith(
    { after: 5, limit: 100 },
    expect.any(AbortSignal),
  );
  expect(JSON.parse(localStorage.getItem(storageKey) ?? "{}")).toEqual({
    cursor: 6,
    unreadTrackedVesselIds: [TRACKED.tracked_vessel_id],
  });

  fireEvent.click(screen.getByRole("button", { name: "mark-read" }));

  expect(screen.getByTestId("unread")).toHaveTextContent("read");
  expect(JSON.parse(localStorage.getItem(storageKey) ?? "{}")).toEqual({
    cursor: 6,
    unreadTrackedVesselIds: [],
  });
});
