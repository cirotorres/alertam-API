import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, expect, test, vi } from "vitest";

import type {
  TrackingForegroundFeedResponse,
} from "../../api/trackingClient";
import {
  AccessRevokedError,
  TemporaryApiError,
} from "../../api/snapshotClient";
import { useTrackingPolling } from "./useTrackingPolling";

const TRACK_ID = "10000000-0000-4000-8000-000000000001";

function event(n: number) {
  return {
    tracked_vessel_id: TRACK_ID,
    ingestion_id: n,
    ingested_at: "2026-09-29T06:10:01Z",
    event: {
      event_id: `20000000-0000-4000-8000-${String(n).padStart(12, "0")}`,
      vessel_identity: "IMO:1234567",
      vessel_imo: "1234567",
      vessel_name: "NAVIO A",
      occurred_at: "2026-09-29T03:10:00-03:00",
      first_observed_at: "2026-09-29T03:10:00-03:00",
      maneuver_id: null,
      changes: {
        eta: { from: "05:00", to: "05:30" },
      },
      current: {
        present: true,
        status: "PREVISTO",
        section: "PREVISTO",
        berth: 4,
        side: "BB",
        eta: "05:30",
        etb_ets: "06:00",
        pob: null,
        pob_at: null,
      },
    },
  };
}

function page(
  events: ReturnType<typeof event>[],
  cursor: number | null,
): TrackingForegroundFeedResponse {
  return { events, newest_cursor: cursor };
}

async function flush() {
  await act(async () => {
    await Promise.resolve();
    await Promise.resolve();
    await Promise.resolve();
  });
}

beforeEach(() => {
  vi.useFakeTimers();
  Object.defineProperty(document, "visibilityState", {
    configurable: true,
    value: "visible",
  });
});

afterEach(() => {
  vi.useRealTimers();
  vi.restoreAllMocks();
});

test("baseline_does_not_replay_and_next_poll_emits_new_event", async () => {
  const fetcher = vi
    .fn()
    .mockResolvedValueOnce(page([], 5))
    .mockResolvedValueOnce(page([event(6)], 6));
  const { result } = renderHook(() => useTrackingPolling(true, fetcher));

  await flush();
  expect(result.current.newTrackingEvent).toBeNull();
  expect(fetcher).toHaveBeenNthCalledWith(
    1,
    { limit: 100 },
    expect.any(AbortSignal),
  );

  await act(async () => vi.advanceTimersByTimeAsync(30_000));
  await flush();

  expect(fetcher).toHaveBeenNthCalledWith(
    2,
    { after: 5, limit: 100 },
    expect.any(AbortSignal),
  );
  expect(result.current.newTrackingEvent?.ingestion_id).toBe(6);
});

test("saved_cursor_replays_events_that_arrived_while_pwa_was_closed", async () => {
  const fetcher = vi.fn().mockResolvedValueOnce(page([event(6), event(7)], 7));
  const { result } = renderHook(() =>
    useTrackingPolling(true, fetcher, undefined, 5),
  );

  await flush();

  expect(fetcher).toHaveBeenCalledWith(
    { after: 5, limit: 100 },
    expect.any(AbortSignal),
  );
  expect(result.current.newTrackingEvents.map((item) => item.ingestion_id)).toEqual([
    6,
    7,
  ]);
  expect(result.current.cursor).toBe(7);
  expect(result.current.newTrackingEvent?.ingestion_id).toBe(7);
});

test("empty_baseline_uses_zero_cursor_so_first_future_event_is_not_lost", async () => {
  const fetcher = vi
    .fn()
    .mockResolvedValueOnce(page([], null))
    .mockResolvedValueOnce(page([event(1)], 1));
  const { result } = renderHook(() => useTrackingPolling(true, fetcher));
  await flush();

  await act(async () => vi.advanceTimersByTimeAsync(30_000));
  await flush();

  expect(fetcher).toHaveBeenNthCalledWith(
    2,
    { after: 0, limit: 100 },
    expect.any(AbortSignal),
  );
  expect(result.current.newTrackingEvent?.ingestion_id).toBe(1);
});

test("drains_full_pages_using_returned_cursor", async () => {
  const burst = Array.from({ length: 100 }, (_, index) => event(index + 1));
  const fetcher = vi
    .fn()
    .mockResolvedValueOnce(page([], 0))
    .mockResolvedValueOnce(page(burst, 100))
    .mockResolvedValueOnce(page([event(101)], 101));
  const { result } = renderHook(() => useTrackingPolling(true, fetcher));
  await flush();

  await act(async () => vi.advanceTimersByTimeAsync(30_000));
  await flush();

  expect(fetcher).toHaveBeenCalledTimes(3);
  expect(result.current.newTrackingEvent?.ingestion_id).toBe(101);
});

test("401_revokes_and_temporary_error_is_recoverable", async () => {
  const revoked = vi.fn();
  const fetcher = vi
    .fn()
    .mockResolvedValueOnce(page([], 2))
    .mockRejectedValueOnce(new TemporaryApiError())
    .mockRejectedValueOnce(new AccessRevokedError());
  const { result } = renderHook(() =>
    useTrackingPolling(true, fetcher, revoked),
  );
  await flush();

  await act(async () => vi.advanceTimersByTimeAsync(30_000));
  await flush();
  expect(result.current.status).toBe("offline");

  await act(async () => vi.advanceTimersByTimeAsync(30_000));
  await flush();
  expect(result.current.status).toBe("revoked");
  expect(revoked).toHaveBeenCalledOnce();
});
