import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, expect, test, vi } from "vitest";

import {
  AccessRevokedError,
  TemporaryApiError,
} from "../../api/snapshotClient";
import { useMobileSessionHeartbeat } from "./useMobileSessionHeartbeat";

function setVisibility(value: DocumentVisibilityState): void {
  Object.defineProperty(document, "visibilityState", {
    configurable: true,
    value,
  });
  document.dispatchEvent(new Event("visibilitychange"));
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

test("heartbeat is immediate every five minutes and pauses while hidden", async () => {
  const heartbeat = vi.fn().mockResolvedValue(undefined);

  renderHook(() =>
    useMobileSessionHeartbeat(
      true,
      heartbeat,
      undefined,
      () => "ios",
    ),
  );

  expect(heartbeat).toHaveBeenCalledTimes(1);
  expect(heartbeat).toHaveBeenLastCalledWith("ios");

  await act(async () => {
    await vi.advanceTimersByTimeAsync(299_999);
  });
  expect(heartbeat).toHaveBeenCalledTimes(1);

  await act(async () => {
    await vi.advanceTimersByTimeAsync(1);
  });
  expect(heartbeat).toHaveBeenCalledTimes(2);

  act(() => setVisibility("hidden"));
  await act(async () => {
    await vi.advanceTimersByTimeAsync(600_000);
  });
  expect(heartbeat).toHaveBeenCalledTimes(2);

  act(() => setVisibility("visible"));
  expect(heartbeat).toHaveBeenCalledTimes(3);
});

test("temporary failure does not disable the next heartbeat", async () => {
  const heartbeat = vi
    .fn()
    .mockRejectedValueOnce(new TemporaryApiError())
    .mockResolvedValue(undefined);

  renderHook(() =>
    useMobileSessionHeartbeat(
      true,
      heartbeat,
      undefined,
      () => "android",
    ),
  );

  await act(async () => {
    await Promise.resolve();
    await vi.advanceTimersByTimeAsync(300_000);
  });

  expect(heartbeat).toHaveBeenCalledTimes(2);
  expect(heartbeat).toHaveBeenNthCalledWith(1, "android");
  expect(heartbeat).toHaveBeenNthCalledWith(2, "android");
});

test("revoked access calls revocation callback only once", async () => {
  const heartbeat = vi
    .fn()
    .mockRejectedValue(new AccessRevokedError());
  const onAccessRevoked = vi.fn();

  renderHook(() =>
    useMobileSessionHeartbeat(
      true,
      heartbeat,
      onAccessRevoked,
      () => "ios",
    ),
  );

  await act(async () => {
    await Promise.resolve();
    await Promise.resolve();
    await vi.advanceTimersByTimeAsync(600_000);
  });

  expect(heartbeat).toHaveBeenCalledTimes(1);
  expect(onAccessRevoked).toHaveBeenCalledTimes(1);
});

test("disabled session never sends heartbeat", async () => {
  const heartbeat = vi.fn().mockResolvedValue(undefined);

  renderHook(() =>
    useMobileSessionHeartbeat(
      false,
      heartbeat,
      undefined,
      () => "other",
    ),
  );

  await act(async () => {
    await vi.advanceTimersByTimeAsync(600_000);
  });

  expect(heartbeat).not.toHaveBeenCalled();
});
