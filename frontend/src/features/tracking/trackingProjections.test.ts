import { expect, test } from "vitest";

import { projectTrackingTimeline } from "./trackingProjections";

const current = {
  present: true,
  status: "PREVISTO",
  section: "PREVISTO",
  berth: 4,
  side: "BB",
  eta: "29/09 05:30",
  etb_ets: "29/09 06:30",
  pob: null,
  pob_at: null,
};

test("projects_tracking_and_maneuver_items_in_api_order", () => {
  const timeline = projectTrackingTimeline({
    tracked_vessel_id: "10000000-0000-4000-8000-000000000001",
    events: [
      {
        kind: "TRACKING",
        ingestion_id: 1,
        ingested_at: "2026-09-29T06:00:00Z",
        event: {
          event_id: "20000000-0000-4000-8000-000000000001",
          vessel_identity: "IMO:1234567",
          vessel_imo: "1234567",
          vessel_name: "NAVIO A",
          occurred_at: "2026-09-29T03:00:00-03:00",
          first_observed_at: "2026-09-29T03:00:00-03:00",
          maneuver_id: null,
          changes: { eta: { from: "05:00", to: "05:30" } },
          current,
        },
      },
      {
        kind: "MANEUVER",
        ingestion_id: 2,
        ingested_at: "2026-09-29T06:01:00Z",
        event: {
          event_id: "30000000-0000-4000-8000-000000000001",
          maneuver_id: "30000000-0000-4000-8000-000000000002",
          vessel_identity: "IMO:1234567",
          vessel_imo: "1234567",
          vessel_name: "NAVIO A",
          maneuver_type: "ATRACACAO",
          event_type: "CONFIRMED",
          berth: 4,
          pob: "29/09 04:00",
          occurred_at: "2026-09-29T03:01:00-03:00",
          pob_at: "2026-09-29T04:00:00-03:00",
          first_observed_at: "2026-09-29T03:01:00-03:00",
          operational_at: null,
          operational_marker: null,
          changes: null,
        },
      },
    ],
  });

  expect(timeline.map((item) => item.eventId)).toEqual([
    "20000000-0000-4000-8000-000000000001",
    "30000000-0000-4000-8000-000000000001",
  ]);
  expect(timeline[0]?.title).toMatch(/ETA/i);
  expect(timeline[1]?.title).toMatch(/Atracação confirmada/i);
});
