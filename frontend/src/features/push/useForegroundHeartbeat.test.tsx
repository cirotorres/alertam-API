import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, expect, test, vi } from "vitest";

import { useForegroundHeartbeat } from "./useForegroundHeartbeat";


const INSTALLATION_ID = "11111111-2222-4333-8444-555555555555";

function setVisibility(value: DocumentVisibilityState) {
  Object.defineProperty(document, "visibilityState", {
    configurable: true,
    value,
  });
  document.dispatchEvent(new Event("visibilitychange"));
}


beforeEach(() => {
  vi.useFakeTimers();
  localStorage.clear();
  localStorage.setItem(
    "alertam.mobile.installation.v1",
    INSTALLATION_ID,
  );
  Object.defineProperty(document, "visibilityState", {
    configurable: true,
    value: "visible",
  });
});

afterEach(() => {
  vi.useRealTimers();
});


test("heartbeat_is_immediate_every_30s_and_pauses_hidden", async () => {
  const heartbeat = vi.fn().mockResolvedValue(undefined);

  renderHook(() => useForegroundHeartbeat(true, heartbeat));

  expect(heartbeat).toHaveBeenCalledTimes(1);
  expect(heartbeat).toHaveBeenLastCalledWith(INSTALLATION_ID);

  await act(async () => {
    vi.advanceTimersByTime(29_999);
  });
  expect(heartbeat).toHaveBeenCalledTimes(1);

  await act(async () => {
    vi.advanceTimersByTime(1);
  });
  expect(heartbeat).toHaveBeenCalledTimes(2);

  act(() => setVisibility("hidden"));
  await act(async () => {
    vi.advanceTimersByTime(60_000);
  });
  expect(heartbeat).toHaveBeenCalledTimes(2);

  act(() => setVisibility("visible"));
  expect(heartbeat).toHaveBeenCalledTimes(3);

  await act(async () => {
    vi.advanceTimersByTime(30_000);
  });
  expect(heartbeat).toHaveBeenCalledTimes(4);
});


test("inactive_push_never_sends_heartbeat", async () => {
  const heartbeat = vi.fn().mockResolvedValue(undefined);

  renderHook(() => useForegroundHeartbeat(false, heartbeat));

  await act(async () => {
    vi.advanceTimersByTime(90_000);
  });
  expect(heartbeat).not.toHaveBeenCalled();
});
