import { afterEach, beforeEach, expect, test, vi } from "vitest";

import type { Pairing } from "./pairing";
import {
  INSTALLATION_ID_STORAGE_KEY,
  loadInstallationId,
} from "../push/installationId";
import {
  clearMobileSession,
  createMobileSession,
  recoverMobileSession,
} from "./mobileSessionClient";

const TOKEN = "Abcdefghijklmnopqrstuvwxyz0123456789_-ABCDE";
const INSTALLATION_ID = "11111111-2222-4333-8444-555555555555";

beforeEach(() => {
  localStorage.clear();
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

test("creates_cookie_session_with_stable_installation_id", async () => {
  localStorage.setItem(INSTALLATION_ID_STORAGE_KEY, INSTALLATION_ID);
  const fetchMock = vi.fn().mockResolvedValue(
    new Response(
      JSON.stringify({
        device_id: "pecem-01",
        installation_id: INSTALLATION_ID,
      }),
      {
        status: 200,
        headers: { "Content-Type": "application/json" },
      },
    ),
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
      body: JSON.stringify({
        device_id: "pecem-01",
        installation_id: INSTALLATION_ID,
      }),
    }),
  );
});

test("creates_installation_id_during_pairing_without_push_enablement", async () => {
  const fetchMock = vi.fn().mockImplementation(
    async (_url: string, options?: RequestInit) => {
      const body = JSON.parse(String(options?.body));
      return new Response(
        JSON.stringify({
          device_id: body.device_id,
          installation_id: body.installation_id,
        }),
        {
          status: 200,
          headers: { "Content-Type": "application/json" },
        },
      );
    },
  );
  vi.stubGlobal("fetch", fetchMock);

  await createMobileSession({
    deviceId: "pecem-01",
    viewSecret: TOKEN,
    pairedAt: "2026-09-26T15:00:00-03:00",
  });

  const installationId = loadInstallationId();
  expect(installationId).not.toBeNull();
  expect(JSON.parse(String(fetchMock.mock.calls[0]?.[1]?.body))).toEqual({
    device_id: "pecem-01",
    installation_id: installationId,
  });
});

test("recovers_cookie_only_pairing_without_view_secret", async () => {
  localStorage.setItem(INSTALLATION_ID_STORAGE_KEY, INSTALLATION_ID);
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          device_id: "pecem-01",
          installation_id: INSTALLATION_ID,
        }),
        {
          status: 200,
          headers: { "Content-Type": "application/json" },
        },
      ),
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


test("recovers_server_installation_id_into_local_storage", async () => {
  localStorage.clear();
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue(
      new Response(JSON.stringify({
        device_id: "pecem-01",
        installation_id: INSTALLATION_ID,
      }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    ),
  );

  await recoverMobileSession();

  expect(loadInstallationId()).toBe(INSTALLATION_ID);
});
