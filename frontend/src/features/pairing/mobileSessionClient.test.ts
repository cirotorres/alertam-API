import { afterEach, expect, test, vi } from "vitest";

import type { Pairing } from "./pairing";
import {
  clearMobileSession,
  createMobileSession,
  recoverMobileSession,
} from "./mobileSessionClient";

const TOKEN = "Abcdefghijklmnopqrstuvwxyz0123456789_-ABCDE";

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

test("creates_cookie_session_without_exposing_secret_in_body", async () => {
  const fetchMock = vi.fn().mockResolvedValue(
    new Response(JSON.stringify({ device_id: "pecem-01" }), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    }),
  );
  vi.stubGlobal("fetch", fetchMock);

  const pairing: Pairing = {
    deviceId: "pecem-01",
    viewSecret: TOKEN,
    pairedAt: "2026-09-26T15:00:00-03:00",
  };

  await createMobileSession(pairing);

  expect(fetchMock).toHaveBeenCalledWith(
    "/api/v1/mobile/session",
    expect.objectContaining({
      method: "POST",
      credentials: "same-origin",
      headers: expect.objectContaining({
        Authorization: `Bearer ${TOKEN}`,
      }),
      body: JSON.stringify({ device_id: "pecem-01" }),
    }),
  );
});

test("recovers_cookie_only_pairing_without_view_secret", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ device_id: "pecem-01" }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    ),
  );

  const recovered = await recoverMobileSession();

  expect(recovered).toEqual(
    expect.objectContaining({
      deviceId: "pecem-01",
      viewSecret: null,
    }),
  );
});

test("returns_null_when_cookie_session_is_missing", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue(new Response("", { status: 401 })),
  );

  await expect(recoverMobileSession()).resolves.toBeNull();
});

test("clears_cookie_session_best_effort", async () => {
  const fetchMock = vi.fn().mockResolvedValue(new Response(null, { status: 204 }));
  vi.stubGlobal("fetch", fetchMock);

  await clearMobileSession();

  expect(fetchMock).toHaveBeenCalledWith(
    "/api/v1/mobile/session",
    expect.objectContaining({
      method: "DELETE",
      credentials: "same-origin",
    }),
  );
});
