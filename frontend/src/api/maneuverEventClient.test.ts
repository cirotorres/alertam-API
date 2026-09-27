import { beforeEach, expect, test, vi } from "vitest";

import maneuverEventFixture from "../../../api/tests/fixtures/maneuver_event_v1.json";
import {
  AccessRevokedError,
  TemporaryApiError,
} from "./snapshotClient";
import { getManeuverEvents } from "./maneuverEventClient";

const feed = {
  events: [
    {
      ...maneuverEventFixture,
      ingestion_id: 7,
      ingested_at: "2026-09-27T13:05:01-03:00",
    },
  ],
  oldest_cursor: 7,
  newest_cursor: 7,
  has_more_before: false,
};

beforeEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

test("event_client_uses_cookie_no_store_and_cursor_query", async () => {
  const fetchMock = vi.fn().mockResolvedValue(
    new Response(JSON.stringify(feed), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    }),
  );
  vi.stubGlobal("fetch", fetchMock);

  const result = await getManeuverEvents({ after: 6, limit: 100 });

  expect(result.newest_cursor).toBe(7);
  const [url, options] = fetchMock.mock.calls[0]!;
  expect(String(url)).toContain("/api/v1/mobile/maneuver-events?after=6&limit=100");
  expect(options).toMatchObject({
    cache: "no-store",
    credentials: "same-origin",
  });
  expect(options?.headers).toBeUndefined();
});

test("event_client_maps_401_to_access_revoked", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue(new Response("", { status: 401 })),
  );

  await expect(getManeuverEvents({})).rejects.toBeInstanceOf(
    AccessRevokedError,
  );
});

test("event_client_maps_server_or_invalid_payload_to_temporary_error", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue(new Response("{}", { status: 200 })),
  );
  await expect(getManeuverEvents({})).rejects.toBeInstanceOf(
    TemporaryApiError,
  );

  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue(new Response("", { status: 503 })),
  );
  await expect(getManeuverEvents({})).rejects.toBeInstanceOf(
    TemporaryApiError,
  );
});
