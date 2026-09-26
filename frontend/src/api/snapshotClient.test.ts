import fixture from "../test/fixtures/mobile_snapshot_v1.json";
import { afterEach, expect, test, vi } from "vitest";

import type { Pairing } from "../features/pairing/pairing";
import {
  AccessRevokedError,
  SnapshotUnavailableError,
  TemporaryApiError,
  UnsupportedSnapshotError,
  getSnapshot,
} from "./snapshotClient";

const TOKEN = "Abcdefghijklmnopqrstuvwxyz0123456789_-ABCDE";

const pairing: Pairing = {
  deviceId: "pecem/01",
  viewSecret: TOKEN,
  pairedAt: "2026-09-26T09:40:00-03:00",
};

const validResponse = {
  snapshot: fixture,
  meta: {
    received_at: "2026-09-25T13:40:15-03:00",
    age_seconds: 3,
    collector_online: true,
    stale_after_seconds: 120,
  },
};

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

test("sends_same_origin_bearer_request_without_cache", async () => {
  const fetchMock = vi.fn().mockResolvedValue(
    new Response(JSON.stringify(validResponse), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    }),
  );
  vi.stubGlobal("fetch", fetchMock);

  const result = await getSnapshot(pairing);

  expect(result.snapshot.schema_version).toBe(1);
  expect(fetchMock).toHaveBeenCalledTimes(1);
  expect(fetchMock).toHaveBeenCalledWith(
    "/api/v1/devices/pecem%2F01/snapshot",
    expect.objectContaining({
      cache: "no-store",
      headers: {
        Authorization: `Bearer ${TOKEN}`,
      },
    }),
  );
});

test.each([
  [401, AccessRevokedError],
  [404, SnapshotUnavailableError],
  [503, TemporaryApiError],
] as const)("maps_http_%s_to_safe_error", async (status, ErrorType) => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue(new Response("server body with secret", { status })),
  );

  await expect(getSnapshot(pairing)).rejects.toBeInstanceOf(ErrorType);

  try {
    await getSnapshot(pairing);
  } catch (error) {
    expect(String(error)).not.toContain(TOKEN);
    expect(String(error)).not.toContain("server body with secret");
  }
});

test("maps_network_failure_to_temporary_error_without_logging_token", async () => {
  const consoleSpy = vi.spyOn(console, "error").mockImplementation(() => undefined);
  vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError(`failed ${TOKEN}`)));

  await expect(getSnapshot(pairing)).rejects.toBeInstanceOf(TemporaryApiError);

  expect(consoleSpy).not.toHaveBeenCalled();
});

test("maps_incompatible_snapshot_to_unsupported_error", async () => {
  const incompatible = {
    ...validResponse,
    snapshot: { ...fixture, schema_version: 2 },
  };
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue(
      new Response(JSON.stringify(incompatible), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    ),
  );

  await expect(getSnapshot(pairing)).rejects.toBeInstanceOf(UnsupportedSnapshotError);
});
