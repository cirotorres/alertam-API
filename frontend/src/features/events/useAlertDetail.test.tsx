import { act, renderHook, waitFor } from "@testing-library/react";
import { expect, test, vi } from "vitest";

import maneuverEventFixture from "../../../../api/tests/fixtures/maneuver_event_v1.json";
import type { ManeuverEventDetailResponse } from "../../api/contract";
import {
  ManeuverEventDetailNotFoundError,
} from "../../api/maneuverEventClient";
import {
  AccessRevokedError,
  TemporaryApiError,
} from "../../api/snapshotClient";
import { useAlertDetail } from "./useAlertDetail";


const detail = {
  selected_event_id: maneuverEventFixture.event_id,
  maneuver_id: maneuverEventFixture.maneuver_id,
  events: [
    {
      ...maneuverEventFixture,
      ingestion_id: 7,
      ingested_at: "2026-09-27T13:05:01-03:00",
    },
  ],
};

test("alert_detail_is_idle_without_event_id", () => {
  const fetcher = vi.fn();

  const { result } = renderHook(() => useAlertDetail(null, fetcher));

  expect(result.current.status).toBe("idle");
  expect(result.current.detail).toBeNull();
  expect(fetcher).not.toHaveBeenCalled();
});

test("alert_detail_loads_direct_detail_and_becomes_ready", async () => {
  const fetcher = vi.fn().mockResolvedValue(detail);

  const { result } = renderHook(() =>
    useAlertDetail(maneuverEventFixture.event_id, fetcher),
  );

  expect(result.current.status).toBe("loading");
  await waitFor(() => expect(result.current.status).toBe("ready"));
  expect(result.current.detail?.selected_event_id).toBe(
    maneuverEventFixture.event_id,
  );
  expect(fetcher).toHaveBeenCalledTimes(1);
});

test("alert_detail_maps_not_found_and_access_revoked", async () => {
  const notFound = vi.fn().mockRejectedValue(
    new ManeuverEventDetailNotFoundError(),
  );
  const { result: missing } = renderHook(() =>
    useAlertDetail("missing", notFound),
  );
  await waitFor(() => expect(missing.current.status).toBe("not-found"));

  const onAccessRevoked = vi.fn();
  const revoked = vi.fn().mockRejectedValue(new AccessRevokedError());
  const { result } = renderHook(() =>
    useAlertDetail("revoked", revoked, onAccessRevoked),
  );
  await waitFor(() => expect(result.current.status).toBe("error"));
  expect(onAccessRevoked).toHaveBeenCalledTimes(1);
});

test("alert_detail_retry_refetches_after_recoverable_error", async () => {
  const fetcher = vi
    .fn()
    .mockRejectedValueOnce(new TemporaryApiError())
    .mockResolvedValueOnce(detail);
  const { result } = renderHook(() =>
    useAlertDetail(maneuverEventFixture.event_id, fetcher),
  );

  await waitFor(() => expect(result.current.status).toBe("error"));

  act(() => result.current.retry());

  expect(result.current.status).toBe("loading");
  await waitFor(() => expect(result.current.status).toBe("ready"));
  expect(fetcher).toHaveBeenCalledTimes(2);
});

test("changing_or_clearing_event_id_aborts_stale_request", async () => {
  const signals: AbortSignal[] = [];
  const fetcher = vi.fn(
    (_eventId: string, signal?: AbortSignal) =>
      new Promise<ManeuverEventDetailResponse>(() => {
        if (signal) signals.push(signal);
      }),
  );

  const { result, rerender } = renderHook(
    ({ eventId }: { eventId: string | null }) =>
      useAlertDetail(eventId, fetcher),
    { initialProps: { eventId: "first" as string | null } },
  );

  await waitFor(() => expect(fetcher).toHaveBeenCalledTimes(1));
  expect(signals[0]?.aborted).toBe(false);

  rerender({ eventId: "second" });
  await waitFor(() => expect(fetcher).toHaveBeenCalledTimes(2));
  expect(signals[0]?.aborted).toBe(true);
  expect(signals[1]?.aborted).toBe(false);

  rerender({ eventId: null });
  await waitFor(() => expect(result.current.status).toBe("idle"));
  expect(signals[1]?.aborted).toBe(true);
  expect(result.current.detail).toBeNull();
});
