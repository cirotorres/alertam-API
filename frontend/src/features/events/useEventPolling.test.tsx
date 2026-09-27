import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, expect, test, vi } from "vitest";

import type { ManeuverEventFeedResponse } from "../../api/contract";
import {
  AccessRevokedError,
  TemporaryApiError,
} from "../../api/snapshotClient";
import { useEventPolling } from "./useEventPolling";

function event(n: number) {
  return {
    event_id: `00000000-0000-4000-8000-${String(n).padStart(12, "0")}`,
    maneuver_id: "00000000-0000-4000-8000-000000000901",
    vessel_identity: "NAME:NAVIO A",
    vessel_imo: null,
    vessel_name: "NAVIO A",
    maneuver_type: "ATRACACAO" as const,
    event_type: "CONFIRMED" as const,
    berth: 4,
    pob: "27/09 10:00",
    occurred_at: "2026-09-27T10:00:00-03:00",
    changes: null,
    ingestion_id: n,
    ingested_at: "2026-09-27T13:00:00-03:00",
  };
}

function page(
  events: ReturnType<typeof event>[],
  hasMore = false,
): ManeuverEventFeedResponse {
  return {
    events,
    oldest_cursor: events[0]?.ingestion_id ?? null,
    newest_cursor: events.at(-1)?.ingestion_id ?? null,
    has_more_before: hasMore,
  };
}

function setVisibility(value: "visible" | "hidden") {
  Object.defineProperty(document, "visibilityState", {
    configurable: true,
    value,
  });
  document.dispatchEvent(new Event("visibilitychange"));
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

test("does_not_fetch_until_enabled_and_initial_page_does_not_emit_new_event", async () => {
  const fetcher = vi.fn().mockResolvedValue(page([event(1)]));
  const { result, rerender } = renderHook(
    ({ enabled }) => useEventPolling(enabled, fetcher),
    { initialProps: { enabled: false } },
  );

  expect(fetcher).not.toHaveBeenCalled();
  rerender({ enabled: true });
  await flush();

  expect(fetcher).toHaveBeenCalledTimes(1);
  expect(result.current.events).toHaveLength(1);
  expect(result.current.newEvent).toBeNull();
});

test("polls_every_30s_pauses_hidden_and_emits_only_post_baseline_event", async () => {
  const fetcher = vi
    .fn()
    .mockResolvedValueOnce(page([event(1)]))
    .mockResolvedValueOnce(page([event(2)]))
    .mockResolvedValueOnce(page([event(3)]));
  const { result } = renderHook(() => useEventPolling(true, fetcher));
  await flush();

  await act(async () => {
    await vi.advanceTimersByTimeAsync(30_000);
  });
  await flush();
  expect(result.current.newEvent?.ingestion_id).toBe(2);

  act(() => setVisibility("hidden"));
  await act(async () => {
    await vi.advanceTimersByTimeAsync(60_000);
  });
  expect(fetcher).toHaveBeenCalledTimes(2);

  act(() => setVisibility("visible"));
  await flush();
  expect(fetcher).toHaveBeenCalledTimes(3);
  expect(result.current.newEvent?.ingestion_id).toBe(3);
});

test("drains_burst_pages_of_100_without_gap_or_duplicates", async () => {
  const burst = Array.from({ length: 100 }, (_, i) => event(i + 2));
  const fetcher = vi
    .fn()
    .mockResolvedValueOnce(page([event(1)]))
    .mockResolvedValueOnce(page(burst))
    .mockResolvedValueOnce(page([event(102), event(103)]));
  const { result } = renderHook(() => useEventPolling(true, fetcher));
  await flush();

  await act(async () => {
    await vi.advanceTimersByTimeAsync(30_000);
  });
  await flush();

  expect(fetcher).toHaveBeenCalledTimes(3);
  expect(result.current.events).toHaveLength(103);
  expect(result.current.events.at(-1)?.ingestion_id).toBe(103);
  expect(new Set(result.current.events.map((item) => item.event_id)).size).toBe(103);
});

test("keeps_single_request_in_flight_and_aborts_when_hidden", async () => {
  let signal: AbortSignal | undefined;
  const fetcher = vi.fn((_query, nextSignal?: AbortSignal) => {
    signal = nextSignal;
    return new Promise<ManeuverEventFeedResponse>(() => undefined);
  });

  renderHook(() => useEventPolling(true, fetcher));
  expect(fetcher).toHaveBeenCalledTimes(1);

  await act(async () => {
    await vi.advanceTimersByTimeAsync(60_000);
  });
  expect(fetcher).toHaveBeenCalledTimes(1);

  act(() => setVisibility("hidden"));
  expect(signal?.aborted).toBe(true);
});

test("access_revoked_calls_callback_and_temporary_failure_keeps_events", async () => {
  const revoked = vi.fn();
  const fetcher = vi
    .fn()
    .mockResolvedValueOnce(page([event(1)]))
    .mockRejectedValueOnce(new TemporaryApiError())
    .mockRejectedValueOnce(new AccessRevokedError());
  const { result } = renderHook(() =>
    useEventPolling(true, fetcher, revoked),
  );
  await flush();

  await act(async () => {
    await vi.advanceTimersByTimeAsync(30_000);
  });
  await flush();
  expect(result.current.status).toBe("offline");
  expect(result.current.events).toHaveLength(1);

  await act(async () => {
    await vi.advanceTimersByTimeAsync(30_000);
  });
  await flush();
  expect(result.current.status).toBe("revoked");
  expect(revoked).toHaveBeenCalledTimes(1);
});
