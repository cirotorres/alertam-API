import { afterEach, expect, test, vi } from "vitest";

import {
  AccessRevokedError,
  TemporaryApiError,
} from "./snapshotClient";
import {
  getTrackedVesselTimeline,
  getTrackingEvents,
  listTrackedVessels,
  parseTrackedVessel,
  parseTrackedVesselTimeline,
  startTracking,
  stopTracking,
} from "./trackingClient";

const TRACK_ID = "10000000-0000-4000-8000-000000000001";
const EVENT_ID = "20000000-0000-4000-8000-000000000001";

const tracked = {
  tracked_vessel_id: TRACK_ID,
  vessel_identity: "IMO:1234567",
  vessel_imo: "1234567",
  vessel_name: "NAVIO A",
  started_at: "2026-09-29T03:00:00-03:00",
  active: true,
  stopped_at: null,
  last_seen_at: "2026-09-29T03:05:00-03:00",
  current: {
    present: true,
    status: "PREVISTO",
    section: "PREVISTO",
    berth: 4,
    side: "BB",
    eta: "29/09 05:00",
    etb_ets: "29/09 06:00",
    pob: null,
    pob_at: null,
  },
};

const trackingEvent = {
  event_id: EVENT_ID,
  vessel_identity: "IMO:1234567",
  vessel_imo: "1234567",
  vessel_name: "NAVIO A",
  occurred_at: "2026-09-29T03:10:00-03:00",
  first_observed_at: "2026-09-29T03:10:00-03:00",
  maneuver_id: null,
  changes: {
    eta: { from: "29/09 05:00", to: "29/09 05:30" },
  },
  current: tracked.current,
};

afterEach(() => {
  vi.restoreAllMocks();
});

test("strict_tracked_vessel_schema_rejects_unknown_fields", () => {
  expect(() => parseTrackedVessel({ ...tracked, surprise: true })).toThrow(
    /acompanhamento/i,
  );
});

test("timeline_schema_is_strict_discriminated_union", () => {
  const parsed = parseTrackedVesselTimeline({
    tracked_vessel_id: TRACK_ID,
    events: [
      {
        kind: "TRACKING",
        ingestion_id: 3,
        ingested_at: "2026-09-29T06:10:01Z",
        event: trackingEvent,
      },
    ],
  });
  expect(parsed.events[0]?.kind).toBe("TRACKING");

  expect(() =>
    parseTrackedVesselTimeline({
      tracked_vessel_id: TRACK_ID,
      events: [
        {
          kind: "UNKNOWN",
          ingestion_id: 3,
          ingested_at: "2026-09-29T06:10:01Z",
          event: trackingEvent,
        },
      ],
    }),
  ).toThrow(/timeline/i);
});

test("list_start_stop_timeline_and_feed_use_session_scoped_endpoints", async () => {
  const fetchMock = vi
    .fn()
    .mockResolvedValueOnce(
      new Response(JSON.stringify([tracked]), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    )
    .mockResolvedValueOnce(
      new Response(JSON.stringify(tracked), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    )
    .mockResolvedValueOnce(new Response(null, { status: 204 }))
    .mockResolvedValueOnce(
      new Response(
        JSON.stringify({
          tracked_vessel_id: TRACK_ID,
          events: [],
        }),
        { status: 200, headers: { "Content-Type": "application/json" } },
      ),
    )
    .mockResolvedValueOnce(
      new Response(
        JSON.stringify({
          events: [
            {
              tracked_vessel_id: TRACK_ID,
              ingestion_id: 7,
              ingested_at: "2026-09-29T06:10:01Z",
              event: trackingEvent,
            },
          ],
          newest_cursor: 7,
        }),
        { status: 200, headers: { "Content-Type": "application/json" } },
      ),
    );
  vi.stubGlobal("fetch", fetchMock);

  await listTrackedVessels();
  await startTracking({
    vessel_identity: "IMO:1234567",
    vessel_imo: "1234567",
    vessel_name: "NAVIO A",
  });
  await stopTracking(TRACK_ID);
  await getTrackedVesselTimeline(TRACK_ID);
  await getTrackingEvents({ after: 6, limit: 50 });

  expect(fetchMock.mock.calls.map((call) => call[0])).toEqual([
    "/api/v1/mobile/tracked-vessels",
    "/api/v1/mobile/tracked-vessels",
    `/api/v1/mobile/tracked-vessels/${TRACK_ID}`,
    `/api/v1/mobile/tracked-vessels/${TRACK_ID}/events`,
    "/api/v1/mobile/tracked-vessels/events?after=6&limit=50",
  ]);
  expect(fetchMock.mock.calls[1]?.[1]).toMatchObject({
    method: "POST",
    credentials: "same-origin",
  });
});

test("401_resets_pairing_and_503_is_recoverable", async () => {
  vi.stubGlobal(
    "fetch",
    vi
      .fn()
      .mockResolvedValueOnce(new Response(null, { status: 401 }))
      .mockResolvedValueOnce(new Response(null, { status: 503 })),
  );

  await expect(listTrackedVessels()).rejects.toBeInstanceOf(
    AccessRevokedError,
  );
  await expect(
    startTracking({
      vessel_identity: "IMO:1234567",
      vessel_imo: "1234567",
      vessel_name: "NAVIO A",
    }),
  ).rejects.toBeInstanceOf(TemporaryApiError);
});
