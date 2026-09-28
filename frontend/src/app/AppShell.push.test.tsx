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
  },
  error: null,
  enablePush: vi.fn().mockResolvedValue(undefined),
  disablePush: vi.fn().mockResolvedValue(undefined),
  updatePreference: vi.fn().mockResolvedValue(undefined),
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
  alertDetailFetcher?: AlertDetailFetcher;
} = {}) {
  const reset = options.onPairingCleared ?? vi.fn();
  const alertDetailFetcher =
    options.alertDetailFetcher ?? vi.fn().mockResolvedValue(detailForEvent());
  render(
    <StaticSnapshotProvider state={snapshotState}>
      <StaticEventProvider state={options.eventState ?? baseEventState}>
        <StaticPushProvider state={options.pushState ?? basePushState}>
          <MemoryRouter initialEntries={["/"]}>
            <AppRoutes
              pairing={pairing}
              onPairingCleared={reset}
              alertDetailFetcher={alertDetailFetcher}
            />
          </MemoryRouter>
        </StaticPushProvider>
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


test("active_push_enables_foreground_heartbeat", () => {
  const reset = vi.fn();
  renderShell({
    pushState: { ...basePushState, active: true },
    onPairingCleared: reset,
  });

  expect(heartbeat.useForegroundHeartbeat).toHaveBeenCalledWith(
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
