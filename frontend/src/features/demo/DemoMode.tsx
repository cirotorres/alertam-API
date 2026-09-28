import type { Pairing } from "../pairing/pairing";
import {
  StaticEventProvider,
} from "../events/EventProvider";
import {
  StaticPushProvider,
  type PushState,
} from "../push/PushProvider";
import { ManeuverEventDetailNotFoundError } from "../../api/maneuverEventClient";
import type { AlertDetailFetcher } from "../events/useAlertDetail";
import type { EventState } from "../events/useEventPolling";
import { StaticSnapshotProvider } from "../snapshot/SnapshotProvider";
import type { SnapshotState } from "../snapshot/useSnapshotPolling";
import { AppRoutes } from "../../app/router";
import { DEMO_RESPONSE } from "./demoData";

const DEMO_PAIRING: Pairing = {
  deviceId: "demo-pecem",
  viewSecret: "demo-only-not-a-real-secret",
  pairedAt: "2026-09-26T13:25:00-03:00",
};

const DEMO_STATE: SnapshotState = {
  status: "online",
  data: DEMO_RESPONSE,
  refresh: () => undefined,
};

const DEMO_PUSH_STATE: PushState = {
  supported: false,
  permission: "default",
  active: false,
  preferences: {
    confirmed: true,
    updated: true,
    completed: true,
    cancelled: true,
  },
  error: null,
  enablePush: async () => undefined,
  disablePush: async () => undefined,
  updatePreference: async () => undefined,
};

const DEMO_EVENT_STATE: EventState = {
  status: "online",
  newEvent: null,
  hasMore: false,
  loadOlder: async () => false,
  events: [
    {
      event_id: "00000000-0000-4000-8000-000000000921",
      maneuver_id: "00000000-0000-4000-8000-000000000911",
      vessel_identity: "NAME:ATLANTIC DAWN",
      vessel_imo: "9487654",
      vessel_name: "ATLANTIC DAWN",
      maneuver_type: "ATRACACAO",
      event_type: "CONFIRMED",
      berth: 2,
      pob: "13:10",
      occurred_at: "2026-09-26T13:08:00-03:00",
      pob_at: null,
      first_observed_at: null,
      changes: null,
      ingestion_id: 1,
      ingested_at: "2026-09-26T13:08:01-03:00",
    },
    {
      event_id: "00000000-0000-4000-8000-000000000922",
      maneuver_id: "00000000-0000-4000-8000-000000000912",
      vessel_identity: "NAME:OCEAN STAR",
      vessel_imo: "9321456",
      vessel_name: "OCEAN STAR",
      maneuver_type: "DESATRACACAO",
      event_type: "CONFIRMED",
      berth: 7,
      pob: "13:18",
      occurred_at: "2026-09-26T13:16:00-03:00",
      pob_at: null,
      first_observed_at: null,
      changes: null,
      ingestion_id: 2,
      ingested_at: "2026-09-26T13:16:01-03:00",
    },
    {
      event_id: "00000000-0000-4000-8000-000000000923",
      maneuver_id: "00000000-0000-4000-8000-000000000913",
      vessel_identity: "NAME:MERIDIAN SKY",
      vessel_imo: "9567890",
      vessel_name: "MERIDIAN SKY",
      maneuver_type: "ATRACACAO",
      event_type: "CONFIRMED",
      berth: 5,
      pob: "04:05",
      occurred_at: "2026-09-26T03:52:00-03:00",
      pob_at: null,
      first_observed_at: null,
      changes: null,
      ingestion_id: 3,
      ingested_at: "2026-09-26T03:52:01-03:00",
    },
    {
      event_id: "00000000-0000-4000-8000-000000000924",
      maneuver_id: "00000000-0000-4000-8000-000000000913",
      vessel_identity: "NAME:MERIDIAN SKY",
      vessel_imo: "9567890",
      vessel_name: "MERIDIAN SKY",
      maneuver_type: "ATRACACAO",
      event_type: "COMPLETED",
      berth: 5,
      pob: "04:05",
      occurred_at: "2026-09-26T04:32:00-03:00",
      pob_at: null,
      first_observed_at: null,
      changes: null,
      ingestion_id: 4,
      ingested_at: "2026-09-26T04:32:01-03:00",
    },
  ],
};

const DEMO_ALERT_DETAIL_FETCHER: AlertDetailFetcher = async (eventId) => {
  const selected = DEMO_EVENT_STATE.events.find(
    (event) => event.event_id === eventId,
  );
  if (!selected) {
    throw new ManeuverEventDetailNotFoundError();
  }
  return {
    selected_event_id: selected.event_id,
    maneuver_id: selected.maneuver_id,
    events: DEMO_EVENT_STATE.events.filter(
      (event) => event.maneuver_id === selected.maneuver_id,
    ),
  };
};

export function DemoMode() {
  return (
    <StaticSnapshotProvider state={DEMO_STATE}>
      <StaticEventProvider state={DEMO_EVENT_STATE}>
        <StaticPushProvider state={DEMO_PUSH_STATE}>
          <AppRoutes
            pairing={DEMO_PAIRING}
            basePath="/demo"
            demoMode
            alertDetailFetcher={DEMO_ALERT_DETAIL_FETCHER}
          />
        </StaticPushProvider>
      </StaticEventProvider>
    </StaticSnapshotProvider>
  );
}
