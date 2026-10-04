import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, expect, test, vi } from "vitest";

import fixture from "../test/fixtures/mobile_snapshot_v1.json";
import {
  parseSnapshotReadResponse,
  type ManeuverEventDetailResponse,
} from "../api/contract";
import type { AlertDetailFetcher } from "../features/events/useAlertDetail";
import {
  StaticEventProvider,
} from "../features/events/EventProvider";
import type { EventState } from "../features/events/useEventPolling";
import type { Pairing } from "../features/pairing/pairing";
import {
  StaticPushProvider,
  type PushState,
} from "../features/push/PushProvider";
import { StaticSnapshotProvider } from "../features/snapshot/SnapshotProvider";
import type { SnapshotState } from "../features/snapshot/useSnapshotPolling";
import {
  StaticTrackingProvider,
  type TrackingState,
} from "../features/tracking/TrackingProvider";

const heartbeat = vi.hoisted(() => ({
  useForegroundHeartbeat: vi.fn(),
}));
vi.mock("../features/push/useForegroundHeartbeat", () => heartbeat);

import { AppRoutes } from "./router";


const pairing: Pairing = {
  deviceId: "pecem-01",
  viewSecret: null,
  pairedAt: "2026-09-27T18:00:00Z",
};
const snapshotResponse = parseSnapshotReadResponse({
  snapshot: fixture,
  meta: {
    received_at: "2026-09-27T18:00:00Z",
    age_seconds: 3,
    collector_online: true,
    stale_after_seconds: 120,
  },
});

const snapshotState: SnapshotState = {
  status: "online",
  data: snapshotResponse,
  refresh: () => undefined,
};

const EVENT = {
  event_id: "80000000-0000-4000-8000-000000000001",
  maneuver_id: "80000000-0000-4000-8000-000000000002",
  vessel_identity: "NAME:NAVIO A",
  vessel_imo: null,
  vessel_name: "NAVIO A",
  maneuver_type: "ATRACACAO" as const,
  event_type: "CONFIRMED" as const,
  berth: 4,
  pob: "10:00",
  occurred_at: "2026-09-27T17:59:00Z",
  pob_at: null,
  first_observed_at: null,
  operational_at: null,
  operational_marker: null,
  changes: null,
  ingestion_id: 1,
  ingested_at: "2026-09-27T18:00:00Z",
};
const baseEventState: EventState = {
  events: [],
  status: "online",
  newEvent: null,
  hasMore: false,
  loadOlder: async () => false,
};

const basePushState: PushState = {
  supported: true,
  permission: "granted",
  active: false,
  preferences: {
    confirmed: true,
    updated: true,
    completed: true,
    cancelled: true,
    anchored: true,
  },
  error: null,
  enablePush: vi.fn().mockResolvedValue(undefined),
  disablePush: vi.fn().mockResolvedValue(undefined),
  updatePreference: vi.fn().mockResolvedValue(undefined),
};

const baseTrackingState: TrackingState = {
  trackings: [],
  status: "online",
  newTrackingEvent: null,
  mutationPending: false,
  mutationError: null,
  findTracking: () => null,
  isTracked: () => false,
  startTracking: async () => true,
  stopTracking: async () => true,
  refresh: async () => true,
  clearMutationError: () => undefined,
};

function detailForEvent(): ManeuverEventDetailResponse {
  return {
    selected_event_id: EVENT.event_id,
    maneuver_id: EVENT.maneuver_id,
    events: [EVENT],
  };
}

function renderShell(options: {
  eventState?: EventState;
  pushState?: PushState;
  onPairingCleared?: () => void;
  onAccessRevoked?: () => void;
  alertDetailFetcher?: AlertDetailFetcher;
  trackingState?: TrackingState;
} = {}) {
  const reset = options.onPairingCleared ?? vi.fn();
  const revoked = options.onAccessRevoked ?? vi.fn();
  const alertDetailFetcher =
    options.alertDetailFetcher ?? vi.fn().mockResolvedValue(detailForEvent());
  render(
    <StaticSnapshotProvider state={snapshotState}>
      <StaticEventProvider state={options.eventState ?? baseEventState}>
        <StaticTrackingProvider state={options.trackingState ?? baseTrackingState}>
          <StaticPushProvider state={options.pushState ?? basePushState}>
            <MemoryRouter initialEntries={["/"]}>
              <AppRoutes
                pairing={pairing}
                onPairingCleared={reset}
                onAccessRevoked={revoked}
                alertDetailFetcher={alertDetailFetcher}
              />
            </MemoryRouter>
          </StaticPushProvider>
        </StaticTrackingProvider>
      </StaticEventProvider>
    </StaticSnapshotProvider>,
  );
  return reset;
}

beforeEach(() => {
  vi.clearAllMocks();
  Object.defineProperty(document, "visibilityState", {
    configurable: true,
    value: "visible",
  });
  Object.defineProperty(HTMLElement.prototype, "scrollIntoView", {
    configurable: true,
    value: vi.fn(),
  });
});


test("active_push_heartbeat_uses_access_revoked_callback", () => {
  const reset = vi.fn();
  const revoked = vi.fn();
  renderShell({
    pushState: { ...basePushState, active: true },
    onPairingCleared: reset,
    onAccessRevoked: revoked,
  });

  expect(heartbeat.useForegroundHeartbeat).toHaveBeenCalledWith(
    true,
    undefined,
    revoked,
  );
  expect(heartbeat.useForegroundHeartbeat).not.toHaveBeenCalledWith(
    true,
    undefined,
    reset,
  );
});
test("visible_new_event_shows_internal_notice_and_opens_global_alert_detail", async () => {
  const requestPermission = vi.fn();
  vi.stubGlobal("Notification", {
    permission: "granted",
    requestPermission,
  });

  const alertDetailFetcher = vi.fn().mockResolvedValue(detailForEvent());
  renderShell({
    eventState: {
      ...baseEventState,
      events: [EVENT],
      newEvent: EVENT,
    },
    alertDetailFetcher,
  });

  const notice = await screen.findByRole("status", {
    name: "Novo alerta operacional",
  });
  expect(notice).toHaveTextContent("NAVIO A");
  expect(requestPermission).not.toHaveBeenCalled();

  fireEvent.click(
    screen.getByRole("button", { name: "Ver alerta" }),
  );

  expect(
    await screen.findByRole("heading", { name: "Alertas" }),
  ).toBeInTheDocument();
  expect(
    await screen.findByRole("dialog", { name: "Detalhes do alerta" }),
  ).toBeInTheDocument();
  expect(alertDetailFetcher).toHaveBeenCalledWith(
    EVENT.event_id,
    expect.any(AbortSignal),
  );
});

test("foreground_notice_can_be_dismissed_without_opening_the_event", async () => {
  renderShell({
    eventState: {
      ...baseEventState,
      events: [EVENT],
      newEvent: EVENT,
    },
  });

  expect(
    await screen.findByRole("status", { name: "Novo alerta operacional" }),
  ).toBeInTheDocument();

  fireEvent.click(screen.getByRole("button", { name: "Fechar aviso" }));

  expect(
    screen.queryByRole("status", { name: "Novo alerta operacional" }),
  ).not.toBeInTheDocument();
  expect(
    screen.getByRole("heading", { name: "Mapa operacional" }),
  ).toBeInTheDocument();
});


const TRACK_ID = "90000000-0000-4000-8000-000000000001";
const TRACKING_EVENT_ID = "90000000-0000-4000-8000-000000000002";
const TRACKED = {
  tracked_vessel_id: TRACK_ID,
  vessel_identity: EVENT.vessel_identity,
  vessel_imo: EVENT.vessel_imo,
  vessel_name: EVENT.vessel_name,
  started_at: "2026-09-27T17:00:00Z",
  active: true,
  stopped_at: null,
  last_seen_at: "2026-09-27T18:00:00Z",
  current: null,
};

const TRACKING_FEED_ITEM = {
  tracked_vessel_id: TRACK_ID,
  ingestion_id: 9,
  ingested_at: "2026-09-27T18:00:01Z",
  event: {
    event_id: TRACKING_EVENT_ID,
    vessel_identity: EVENT.vessel_identity,
    vessel_imo: EVENT.vessel_imo,
    vessel_name: EVENT.vessel_name,
    occurred_at: "2026-09-27T18:00:00Z",
    first_observed_at: "2026-09-27T18:00:00Z",
    maneuver_id: null,
    changes: { eta: { from: "10:00", to: "10:30" } },
    current: {
      present: true,
      status: "PREVISTO",
      section: "PREVISTO",
      berth: 4,
      side: "BB",
      eta: "10:30",
      etb_ets: null,
      pob: null,
      pob_at: null,
    },
  },
};

test("tracking_foreground_notice_opens_tracked_deep_link", async () => {
  renderShell({
    trackingState: {
      ...baseTrackingState,
      trackings: [TRACKED],
      newTrackingEvent: TRACKING_FEED_ITEM,
      findTracking: () => TRACKED,
      isTracked: () => true,
    },
  });

  const notice = await screen.findByRole("status", {
    name: "Novo acompanhamento",
  });
  expect(notice).toHaveTextContent("NAVIO A");
  fireEvent.click(screen.getByRole("button", { name: "Ver acompanhamento" }));

  expect(
    await screen.findByRole("heading", { name: "Acompanhados" }),
  ).toBeInTheDocument();
});

test("maneuver_general_category_on_has_priority_and_shows_only_one_notice", async () => {
  renderShell({
    eventState: { ...baseEventState, events: [EVENT], newEvent: EVENT },
    pushState: {
      ...basePushState,
      preferences: { ...basePushState.preferences, confirmed: true },
    },
    trackingState: {
      ...baseTrackingState,
      trackings: [TRACKED],
      newTrackingEvent: {
        ...TRACKING_FEED_ITEM,
        event: {
          ...TRACKING_FEED_ITEM.event,
          maneuver_id: EVENT.maneuver_id,
        },
      },
      findTracking: () => TRACKED,
      isTracked: () => true,
    },
  });

  expect(
    await screen.findByRole("status", { name: "Novo alerta operacional" }),
  ).toBeInTheDocument();
  expect(
    screen.queryByRole("status", { name: "Novo acompanhamento" }),
  ).not.toBeInTheDocument();
});

test("maneuver_general_category_off_but_tracked_routes_to_acompanhados", async () => {
  renderShell({
    eventState: { ...baseEventState, events: [EVENT], newEvent: EVENT },
    pushState: {
      ...basePushState,
      preferences: { ...basePushState.preferences, confirmed: false },
    },
    trackingState: {
      ...baseTrackingState,
      trackings: [TRACKED],
      findTracking: () => TRACKED,
      isTracked: () => true,
    },
  });

  const notice = await screen.findByRole("status", {
    name: "Novo acompanhamento",
  });
  expect(notice).toHaveTextContent("NAVIO A");
  fireEvent.click(screen.getByRole("button", { name: "Ver acompanhamento" }));

  expect(
    await screen.findByRole("heading", { name: "Acompanhados" }),
  ).toBeInTheDocument();
});
