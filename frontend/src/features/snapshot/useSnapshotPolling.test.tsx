import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, expect, test, vi } from "vitest";

import fixture from "../../test/fixtures/mobile_snapshot_v1.json";
import {
  AccessRevokedError,
  SnapshotUnavailableError,
  TemporaryApiError,
  UnsupportedSnapshotError,
} from "../../api/snapshotClient";
import { parseSnapshotReadResponse } from "../../api/contract";
import type { Pairing } from "../pairing/pairing";
import { loadPairing, savePairing } from "../pairing/pairingStorage";
import { useSnapshotPolling } from "./useSnapshotPolling";

const pairing: Pairing = {
  deviceId: "pecem-01",
  viewSecret: "Abcdefghijklmnopqrstuvwxyz0123456789_-ABCDE",
  pairedAt: "2026-09-26T09:40:00-03:00",
};

const ONLINE = parseSnapshotReadResponse({
  snapshot: fixture,
  meta: {
    received_at: "2026-09-25T13:40:15-03:00",
    age_seconds: 3,
    collector_online: true,
    stale_after_seconds: 120,
  },
});

const STALE = parseSnapshotReadResponse({
  snapshot: fixture,
  meta: {
    ...ONLINE.meta,
    age_seconds: 180,
    collector_online: false,
  },
});

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
  });
}

beforeEach(() => {
  vi.useFakeTimers();
  localStorage.clear();
  Object.defineProperty(document, "visibilityState", {
    configurable: true,
    value: "visible",
  });
});

afterEach(() => {
  vi.useRealTimers();
  vi.restoreAllMocks();
});

test("fetches_immediately_then_every_30_seconds_while_visible", async () => {
  const fetcher = vi.fn().mockResolvedValue(ONLINE);

  const { result } = renderHook(() => useSnapshotPolling(pairing, fetcher));
  await flush();

  expect(fetcher).toHaveBeenCalledTimes(1);
  expect(result.current.status).toBe("online");

  await act(async () => {
    await vi.advanceTimersByTimeAsync(30_000);
  });

  expect(fetcher).toHaveBeenCalledTimes(2);
});

test("pauses_when_hidden_and_fetches_immediately_when_visible_again", async () => {
  const fetcher = vi.fn().mockResolvedValue(ONLINE);

  renderHook(() => useSnapshotPolling(pairing, fetcher));
  await flush();
  expect(fetcher).toHaveBeenCalledTimes(1);

  act(() => setVisibility("hidden"));
  await act(async () => {
    await vi.advanceTimersByTimeAsync(60_000);
  });
  expect(fetcher).toHaveBeenCalledTimes(1);

  act(() => setVisibility("visible"));
  await flush();
  expect(fetcher).toHaveBeenCalledTimes(2);
});

test("keeps_single_request_in_flight_and_aborts_on_cleanup", async () => {
  let capturedSignal: AbortSignal | undefined;
  const fetcher = vi.fn((_pairing: Pairing, signal?: AbortSignal) => {
    capturedSignal = signal;
    return new Promise<typeof ONLINE>(() => undefined);
  });

  const { result, unmount } = renderHook(() =>
    useSnapshotPolling(pairing, fetcher),
  );

  expect(fetcher).toHaveBeenCalledTimes(1);

  act(() => result.current.refresh());
  await act(async () => {
    await vi.advanceTimersByTimeAsync(60_000);
  });

  expect(fetcher).toHaveBeenCalledTimes(1);
  expect(capturedSignal?.aborted).toBe(false);

  unmount();
  expect(capturedSignal?.aborted).toBe(true);
});

test("revoked_access_reports_status_without_mutating_pairing_storage", async () => {
  savePairing(pairing);
  const fetcher = vi.fn().mockRejectedValue(new AccessRevokedError());

  const { result } = renderHook(() => useSnapshotPolling(pairing, fetcher));
  await flush();

  expect(result.current.status).toBe("revoked");
  expect(loadPairing()).toEqual(pairing);

  await act(async () => {
    await vi.advanceTimersByTimeAsync(60_000);
  });
  expect(fetcher).toHaveBeenCalledTimes(1);
});

test("temporary_failure_preserves_last_stale_snapshot", async () => {
  const fetcher = vi
    .fn()
    .mockResolvedValueOnce(STALE)
    .mockRejectedValueOnce(new TemporaryApiError());

  const { result } = renderHook(() => useSnapshotPolling(pairing, fetcher));
  await flush();

  expect(result.current.status).toBe("stale");
  expect(result.current.data).toBe(STALE);

  await act(async () => {
    await vi.advanceTimersByTimeAsync(30_000);
  });

  expect(result.current.status).toBe("offline");
  expect(result.current.data).toBe(STALE);
});

test.each([
  [new SnapshotUnavailableError(), "waiting"],
  [new UnsupportedSnapshotError(), "unsupported"],
] as const)("maps_terminal_read_state_to_%s", async (error, expected) => {
  const fetcher = vi.fn().mockRejectedValue(error);

  const { result } = renderHook(() => useSnapshotPolling(pairing, fetcher));
  await flush();

  expect(result.current.status).toBe(expected);
});


test("pairing_change_clears_previous_device_data_before_new_response", async () => {
  const second = new Promise<typeof ONLINE>(() => undefined);
  const fetcher = vi
    .fn()
    .mockResolvedValueOnce(ONLINE)
    .mockReturnValueOnce(second);
  const nextPairing = { ...pairing, deviceId: "pecem-02" };

  const { result, rerender } = renderHook(
    ({ currentPairing }) => useSnapshotPolling(currentPairing, fetcher),
    { initialProps: { currentPairing: pairing } },
  );
  await flush();
  expect(result.current.status).toBe("online");
  expect(result.current.data).toBe(ONLINE);

  rerender({ currentPairing: nextPairing });

  expect(result.current.status).toBe("loading");
  expect(result.current.data).toBeNull();
});

test("aborted_old_request_cannot_unlock_new_request", async () => {
  let resolveFirst!: (value: typeof ONLINE) => void;
  let resolveSecond!: (value: typeof ONLINE) => void;
  const first = new Promise<typeof ONLINE>((resolve) => {
    resolveFirst = resolve;
  });
  const second = new Promise<typeof ONLINE>((resolve) => {
    resolveSecond = resolve;
  });
  const fetcher = vi
    .fn()
    .mockReturnValueOnce(first)
    .mockReturnValueOnce(second)
    .mockResolvedValue(ONLINE);

  renderHook(() => useSnapshotPolling(pairing, fetcher));
  expect(fetcher).toHaveBeenCalledTimes(1);

  act(() => setVisibility("hidden"));
  act(() => setVisibility("visible"));
  expect(fetcher).toHaveBeenCalledTimes(2);

  await act(async () => {
    resolveFirst(ONLINE);
    await Promise.resolve();
  });
  await act(async () => {
    await vi.advanceTimersByTimeAsync(30_000);
  });

  expect(fetcher).toHaveBeenCalledTimes(2);

  await act(async () => {
    resolveSecond(ONLINE);
    await Promise.resolve();
  });
});
