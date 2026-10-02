import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { vi } from "vitest";
import fixture from "../test/fixtures/mobile_snapshot_v1.json";
import {
  parseSnapshotReadResponse,
  type ManeuverEventDetailResponse,
  type ManeuverEventFeedResponse,
  type ManeuverEventFeedItem,
} from "../api/contract";
import type { AlertDetailFetcher } from "../features/events/useAlertDetail";
import {
  EventProvider,
  StaticEventProvider,
} from "../features/events/EventProvider";
import type { Pairing } from "../features/pairing/pairing";
import {
  StaticPushProvider,
  type PushState,
} from "../features/push/PushProvider";
import {
  SnapshotProvider,
  StaticSnapshotProvider,
} from "../features/snapshot/SnapshotProvider";
import {
  loadPairing,
  savePairing,
} from "../features/pairing/pairingStorage";
import { AppRoutes } from "../app/router";
import { StatusCards } from "../components/StatusCards";
import {
  StaticTrackingProvider,
  type TrackingState,
} from "../features/tracking/TrackingProvider";

const pairing: Pairing = {
  deviceId: "pecem-01",
  viewSecret: "Abcdefghijklmnopqrstuvwxyz0123456789_-ABCDE",
  pairedAt: "2026-09-26T09:40:00-03:00",
};

const EVENT_PAGE: ManeuverEventFeedResponse = {
  events: [
    {
      event_id: "00000000-0000-4000-8000-000000000801",
      maneuver_id: "00000000-0000-4000-8000-000000000811",
      vessel_identity: "NAME:NAVIO A",
      vessel_imo: null,
      vessel_name: "NAVIO A",
      maneuver_type: "ATRACACAO",
      event_type: "CONFIRMED",
      berth: 4,
      pob: "10:00",
      occurred_at: "2026-09-27T10:00:00-03:00",
      pob_at: null,
      first_observed_at: null,
      operational_at: null,
      operational_marker: null,
      changes: null,
      ingestion_id: 1,
      ingested_at: "2026-09-27T13:00:00-03:00",
    },
    {
      event_id: "00000000-0000-4000-8000-000000000802",
      maneuver_id: "00000000-0000-4000-8000-000000000812",
      vessel_identity: "NAME:NAVIO B",
      vessel_imo: null,
      vessel_name: "NAVIO B",
      maneuver_type: "DESATRACACAO",
      event_type: "COMPLETED",
      berth: 7,
      pob: null,
      occurred_at: "2026-09-27T10:05:00-03:00",
      pob_at: null,
      first_observed_at: null,
      operational_at: null,
      operational_marker: null,
      changes: null,
      ingestion_id: 2,
      ingested_at: "2026-09-27T13:05:00-03:00",
    },
  ],
  oldest_cursor: 1,
  newest_cursor: 2,
  has_more_before: false,
};

const DEFAULT_PUSH_STATE: PushState = {
  supported: true,
  permission: "default",
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

const response = parseSnapshotReadResponse({
  snapshot: fixture,
  meta: { received_at: "2026-09-25T13:40:15-03:00", age_seconds: 3, collector_online: true, stale_after_seconds: 120 },
});
function detailFor(
  selected: ManeuverEventFeedItem,
  events: ManeuverEventFeedItem[] = [selected],
): ManeuverEventDetailResponse {
  return {
    selected_event_id: selected.event_id,
    maneuver_id: selected.maneuver_id,
    events,
  };
}

function renderRoute(
  route: string,
  onPairingCleared = vi.fn(),
  eventFetcher = vi.fn().mockResolvedValue(EVENT_PAGE),
  pushState: PushState = DEFAULT_PUSH_STATE,
  alertDetailFetcher: AlertDetailFetcher = vi
    .fn()
    .mockImplementation(async (eventId: string) => {
      const selected = EVENT_PAGE.events.find((event) => event.event_id === eventId);
      if (!selected) throw new Error("detail fixture missing");
      return detailFor(selected);
    }),
) {
  const view = render(
    <SnapshotProvider pairing={pairing} fetcher={vi.fn().mockResolvedValue(response)}>
      <EventProvider
        sessionReady
        fetcher={eventFetcher}
        onAccessRevoked={onPairingCleared}
      >
        <StaticPushProvider state={pushState}>
          <MemoryRouter initialEntries={[route]}>
            <AppRoutes
              pairing={pairing}
              onPairingCleared={onPairingCleared}
              alertDetailFetcher={alertDetailFetcher}
            />
          </MemoryRouter>
        </StaticPushProvider>
      </EventProvider>
    </SnapshotProvider>,
  );
  return {
    onPairingCleared,
    eventFetcher,
    alertDetailFetcher,
    unmount: view.unmount,
  };
}

function staticTrackingState(
  isTracked: TrackingState["isTracked"],
  trackings: TrackingState["trackings"] = [],
): TrackingState {
  return {
    trackings,
    status: "online",
    newTrackingEvent: null,
    mutationPending: false,
    mutationError: null,
    findTracking: vi.fn().mockReturnValue(null),
    isTracked,
    startTracking: vi.fn().mockResolvedValue(true),
    stopTracking: vi.fn().mockResolvedValue(true),
    refresh: vi.fn().mockResolvedValue(true),
    clearMutationError: vi.fn(),
  };
}

function renderMapWithTracking(
  data: typeof response,
  isTracked: TrackingState["isTracked"],
  route = "/",
  trackings: TrackingState["trackings"] = [],
) {
  return render(
    <StaticSnapshotProvider
      state={{
        status: "online",
        data,
        refresh: () => undefined,
      }}
    >
      <StaticEventProvider
        state={{
          events: [],
          status: "online",
          newEvent: null,
          hasMore: false,
          loadOlder: async () => false,
        }}
      >
        <StaticPushProvider state={DEFAULT_PUSH_STATE}>
          <StaticTrackingProvider state={staticTrackingState(isTracked, trackings)}>
            <MemoryRouter initialEntries={[route]}>
              <AppRoutes pairing={pairing} />
            </MemoryRouter>
          </StaticTrackingProvider>
        </StaticPushProvider>
      </StaticEventProvider>
    </StaticSnapshotProvider>,
  );
}

function renderConfig(
  pushState: PushState = DEFAULT_PUSH_STATE,
  onPairingCleared = vi.fn(),
) {
  const view = render(
    <StaticSnapshotProvider
      state={{
        status: "online",
        data: response,
        refresh: () => undefined,
      }}
    >
      <StaticEventProvider
        state={{
          events: EVENT_PAGE.events,
          status: "online",
          newEvent: null,
          hasMore: false,
          loadOlder: async () => false,
        }}
      >
        <StaticPushProvider state={pushState}>
          <MemoryRouter initialEntries={["/config"]}>
            <AppRoutes
              pairing={pairing}
              onPairingCleared={onPairingCleared}
            />
          </MemoryRouter>
        </StaticPushProvider>
      </StaticEventProvider>
    </StaticSnapshotProvider>,
  );
  return { onPairingCleared, unmount: view.unmount };
}

test("operational_list_marks_tracked_vessel_by_imo_without_changing_name", async () => {
  const isTracked = vi.fn().mockImplementation((target) =>
    typeof target !== "string" && target.vessel_imo === "1234567",
  );
  renderMapWithTracking(response, isTracked);

  const name = await screen.findByText("NAVIO A");
  const card = name.closest(".operational-card");

  expect(name).toHaveTextContent("NAVIO A");
  expect(card?.querySelector(".operational-card__tracking-star")).toHaveTextContent("★");
  expect(isTracked).toHaveBeenCalledWith({
    vessel_identity: "IMO:1234567",
    vessel_imo: "1234567",
    vessel_name: "NAVIO A",
  });
});

test("operational_list_marks_tracked_vessel_with_name_fallback", async () => {
  const noImoResponse = parseSnapshotReadResponse({
    ...response,
    snapshot: {
      ...response.snapshot,
      vessels: response.snapshot.vessels.map((vessel) => ({
        ...vessel,
        imo: null,
      })),
    },
  });
  const isTracked = vi.fn().mockImplementation((target) =>
    typeof target !== "string" &&
    target.vessel_identity === "NAME:NAVIO A",
  );
  renderMapWithTracking(noImoResponse, isTracked);

  const name = await screen.findByText("NAVIO A");
  const card = name.closest(".operational-card");

  expect(name).toHaveTextContent("NAVIO A");
  expect(card?.querySelector(".operational-card__tracking-star")).toHaveTextContent("★");
  expect(isTracked).toHaveBeenCalledWith({
    vessel_identity: "NAME:NAVIO A",
    vessel_imo: null,
    vessel_name: "NAVIO A",
  });
});

test("tracked_vessels_route_keeps_footer_without_false_active_tab", async () => {
  renderMapWithTracking(response, () => false, "/acompanhados");

  expect(
    await screen.findByRole("heading", { name: "Acompanhados" }),
  ).toBeInTheDocument();

  const nav = screen.getByRole("navigation", { name: "Navegação inferior" });
  const buttons = within(nav).getAllByRole("button");

  expect(buttons).toHaveLength(5);
  expect(nav.querySelector('[aria-current="page"]')).toBeNull();

  fireEvent.click(within(nav).getByRole("button", { name: "Tempo" }));
  expect(
    await screen.findByRole("heading", { name: "Tempo e mar" }),
  ).toBeInTheDocument();

  fireEvent.click(
    screen.getByRole("button", { name: "Manobras confirmadas" }),
  );
  expect(
    await screen.findByRole("heading", { name: "Mapa operacional" }),
  ).toBeInTheDocument();
});

test("track_deep_link_neutralizes_alert_sheet_and_keeps_one_interactive_dialog", async () => {
  const tracked = {
    tracked_vessel_id: "10000000-0000-4000-8000-000000000099",
    vessel_identity: "IMO:1234567",
    vessel_imo: "1234567",
    vessel_name: "NAVIO A",
    started_at: "2026-09-29T03:00:00-03:00",
    active: true,
    stopped_at: null,
    last_seen_at: "2026-09-29T03:05:00-03:00",
    current: {
      present: true,
      status: "ATRACANDO",
      section: "FUNDEADO",
      berth: 2,
      side: "BE",
      eta: "29/09 05:30",
      etb_ets: "29/09 06:30",
      pob: "29/09 02:30",
      pob_at: "2026-09-29T02:30:00-03:00",
    },
  } satisfies TrackingState["trackings"][number];

  renderMapWithTracking(
    response,
    () => true,
    `/acompanhados?track=${tracked.tracked_vessel_id}&event=${EVENT_PAGE.events[0]!.event_id}`,
    [tracked],
  );

  expect(
    await screen.findByRole("dialog", { name: "Detalhes do acompanhamento" }),
  ).toBeInTheDocument();
  expect(screen.getAllByRole("dialog")).toHaveLength(1);
  expect(
    screen.queryByRole("dialog", { name: "Detalhes do alerta" }),
  ).not.toBeInTheDocument();
});

test.each([
  ["/alertas", "Alertas"],
  ["/historico", "Histórico"],
])("%s loads 50 older events on explicit user action", async (route, heading) => {
  const recent = {
    ...EVENT_PAGE.events[0]!,
    event_id: "00000000-0000-4000-8000-000000000951",
    maneuver_id: "00000000-0000-4000-8000-000000000961",
    vessel_name: "NAVIO RECENTE",
    ingestion_id: 51,
  };
  const older = {
    ...EVENT_PAGE.events[1]!,
    event_id: "00000000-0000-4000-8000-000000000952",
    maneuver_id: "00000000-0000-4000-8000-000000000962",
    vessel_name: "NAVIO ANTIGO",
    ingestion_id: 1,
  };
  const eventFetcher = vi
    .fn()
    .mockResolvedValueOnce({
      events: [recent],
      oldest_cursor: 51,
      newest_cursor: 51,
      has_more_before: true,
    })
    .mockResolvedValueOnce({
      events: [older],
      oldest_cursor: 1,
      newest_cursor: 1,
      has_more_before: false,
    });

  renderRoute(route, vi.fn(), eventFetcher);

  expect(await screen.findByRole("heading", { name: heading })).toBeInTheDocument();
  const loadMore = await screen.findByRole("button", { name: "Carregar mais" });
  fireEvent.click(loadMore);

  expect(await screen.findByText("NAVIO ANTIGO")).toBeInTheDocument();
  expect(eventFetcher).toHaveBeenNthCalledWith(
    2,
    { before: 51, limit: 50 },
    expect.any(AbortSignal),
  );
  expect(
    screen.queryByRole("button", { name: "Carregar mais" }),
  ).not.toBeInTheDocument();
});


test("alerts_and_history_use_distinct_views", async () => {
  const { unmount } = renderRoute("/alertas");
  expect(await screen.findByRole("heading", { name: "Alertas" })).toBeInTheDocument();
  expect(screen.getByText("NAVIO A")).toBeInTheDocument();
  unmount();

  renderRoute("/historico");
  expect(await screen.findByRole("heading", { name: "Histórico" })).toBeInTheDocument();
  expect(screen.getByText("NAVIO B")).toBeInTheDocument();
});

test("config_shows_device_and_can_forget_pairing", async () => {
  savePairing(pairing);
  vi.spyOn(window, "confirm").mockReturnValue(true);
  const { onPairingCleared } = renderConfig();

  expect(await screen.findByText("pecem-01")).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Esquecer este aparelho" }));
  await waitFor(() => {
    expect(onPairingCleared).toHaveBeenCalledTimes(1);
  });
});
test("about_page_does_not_expose_infrastructure_secrets", async () => {
  renderRoute("/sobre");
  expect(await screen.findByRole("heading", { name: "Sobre o AlertaM" })).toBeInTheDocument();
  expect(document.body.textContent).not.toMatch(/SUPABASE|DEVICE_SECRET|service_role/i);
});

test.each([
  ["online", "Sistema ativo"],
  ["stale", "Dados desatualizados"],
  ["offline", "Sem conexão com o servidor"],
  ["waiting", "Aguardando primeira leitura"],
  ["revoked", "Acesso expirado ou revogado"],
  ["unsupported", "Atualização necessária"],
] as const)("status_%s_has_text_not_only_color", (status, label) => {
  render(<StatusCards status={status} data={status === "online" || status === "stale" || status === "offline" ? response : null} />);
  expect(screen.getByRole("status")).toHaveTextContent(label);
});


test("alerts_and_history_keep_operational_footer_and_tab_returns_to_map", async () => {
  renderRoute("/alertas");

  expect(await screen.findByRole("heading", { name: "Alertas" })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Manobras confirmadas" })).toBeInTheDocument();

  fireEvent.click(screen.getByRole("button", { name: "Prev. atracação" }));

  expect(
    await screen.findByRole("heading", { name: "Previsão de atracação" }),
  ).toBeInTheDocument();
});


test("weather_page_renders_atmospheric_and_marine_snapshot_data", async () => {
  renderRoute("/tempo");

  expect(await screen.findByRole("heading", { name: "Tempo e mar" })).toBeInTheDocument();
  expect(screen.getByText("29,5 °C")).toBeInTheDocument();
  expect(screen.getByText("12,3 kn")).toBeInTheDocument();
  expect(screen.getAllByText("1,2 m")).toHaveLength(2);
  expect(screen.getByText("28 °C")).toBeInTheDocument();
  expect(screen.getByText("Pecém - CE")).toBeInTheDocument();
  expect(screen.getByText(/API Open-Meteo/)).toBeInTheDocument();
  expect(screen.getByText(/valores aproximados/i)).toBeInTheDocument();
  expect(screen.getByText("Altura da ondulação")).toBeInTheDocument();
  expect(screen.queryByText(/swell/i)).not.toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Tempo" })).toHaveAttribute("aria-current", "page");
});


test("weather_page_tolerates_empty_weather_blocks", async () => {
  const emptyResponse = parseSnapshotReadResponse({
    snapshot: { ...fixture, weather: {}, marine: {} },
    meta: { received_at: "2026-09-25T13:40:15-03:00", age_seconds: 3, collector_online: true, stale_after_seconds: 120 },
  });
  render(
    <SnapshotProvider pairing={pairing} fetcher={vi.fn().mockResolvedValue(emptyResponse)}>
      <EventProvider
        sessionReady
        fetcher={vi.fn().mockResolvedValue(EVENT_PAGE)}
      >
        <StaticPushProvider state={DEFAULT_PUSH_STATE}>
          <MemoryRouter initialEntries={["/tempo"]}>
            <AppRoutes pairing={pairing} />
          </MemoryRouter>
        </StaticPushProvider>
      </EventProvider>
    </SnapshotProvider>,
  );

  expect(await screen.findByRole("heading", { name: "Tempo e mar" })).toBeInTheDocument();
  expect(screen.getByText(/Dados meteorológicos ainda não estão disponíveis/)).toBeInTheDocument();
  expect(screen.getByText(/Dados marítimos ainda não estão disponíveis/)).toBeInTheDocument();
});


test("footer_weather_tab_opens_weather_page", async () => {
  renderRoute("/");

  fireEvent.click(await screen.findByRole("button", { name: "Tempo" }));

  expect(await screen.findByRole("heading", { name: "Tempo e mar" })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Tempo" })).toHaveAttribute("aria-current", "page");
});


test("alert_deep_link_uses_direct_detail_without_paging_feed_and_close_keeps_page", async () => {
  const targetId = "00000000-0000-4000-8000-000000000899";
  const latest: ManeuverEventFeedResponse = {
    events: [EVENT_PAGE.events[1]!],
    oldest_cursor: 2,
    newest_cursor: 2,
    has_more_before: true,
  };
  const target: ManeuverEventFeedItem = {
    ...EVENT_PAGE.events[0]!,
    event_id: targetId,
    vessel_name: "NAVIO ANTIGO",
    ingestion_id: 1,
  };
  const eventFetcher = vi.fn().mockResolvedValue(latest);
  const alertDetailFetcher = vi.fn().mockResolvedValue(detailFor(target));

  renderRoute(
    `/alertas?event=${targetId}`,
    vi.fn(),
    eventFetcher,
    DEFAULT_PUSH_STATE,
    alertDetailFetcher,
  );

  expect(
    await screen.findByRole("dialog", { name: "Detalhes do alerta" }),
  ).toBeInTheDocument();
  expect(screen.getByText("NAVIO ANTIGO")).toBeInTheDocument();
  expect(alertDetailFetcher).toHaveBeenCalledWith(
    targetId,
    expect.any(AbortSignal),
  );
  expect(eventFetcher).toHaveBeenCalledTimes(1);

  fireEvent.click(
    screen.getByRole("button", { name: "Fechar detalhes do alerta" }),
  );
  expect(
    await screen.findByRole("heading", { name: "Alertas" }),
  ).toBeInTheDocument();
  expect(
    screen.queryByRole("dialog", { name: "Detalhes do alerta" }),
  ).not.toBeInTheDocument();
  expect(eventFetcher).toHaveBeenCalledTimes(1);
});

test("alert_row_is_full_area_action_that_opens_global_detail_sheet", async () => {
  const selected = EVENT_PAGE.events[0]!;
  const alertDetailFetcher = vi.fn().mockResolvedValue(detailFor(selected));
  renderRoute(
    "/alertas",
    vi.fn(),
    vi.fn().mockResolvedValue(EVENT_PAGE),
    DEFAULT_PUSH_STATE,
    alertDetailFetcher,
  );

  fireEvent.click(
    await screen.findByRole("button", {
      name: /NAVIO A.*Atracação confirmada/i,
    }),
  );

  expect(
    await screen.findByRole("dialog", { name: "Detalhes do alerta" }),
  ).toBeInTheDocument();
  expect(alertDetailFetcher).toHaveBeenCalledWith(
    selected.event_id,
    expect.any(AbortSignal),
  );
});

test("history_event_is_actionable_and_opens_selected_event_detail", async () => {
  const selected = EVENT_PAGE.events[1]!;
  const alertDetailFetcher = vi.fn().mockResolvedValue(detailFor(selected));
  renderRoute(
    "/historico",
    vi.fn(),
    vi.fn().mockResolvedValue(EVENT_PAGE),
    DEFAULT_PUSH_STATE,
    alertDetailFetcher,
  );

  fireEvent.click(
    await screen.findByRole("button", {
      name: /Desatracação concluída/i,
    }),
  );

  expect(
    await screen.findByRole("dialog", { name: "Detalhes do alerta" }),
  ).toBeInTheDocument();
  expect(alertDetailFetcher).toHaveBeenCalledWith(
    selected.event_id,
    expect.any(AbortSignal),
  );
});


test("config_controls_push_and_four_independent_preferences", async () => {
  const enablePush = vi.fn().mockResolvedValue(undefined);
  const inactiveState: PushState = {
    ...DEFAULT_PUSH_STATE,
    enablePush,
  };
  const firstEventFetcher = vi.fn().mockResolvedValue(EVENT_PAGE);
  const { unmount } = renderRoute(
    "/config",
    vi.fn(),
    firstEventFetcher,
    inactiveState,
  );

  await screen.findByText(/25\/09\/2026/);
  await waitFor(() => {
    expect(firstEventFetcher).toHaveBeenCalledTimes(1);
  });
  fireEvent.click(
    screen.getByRole("button", {
      name: "Ativar notificações",
    }),
  );
  await waitFor(() => {
    expect(enablePush).toHaveBeenCalledTimes(1);
  });
  unmount();

  const updatePreference = vi.fn().mockResolvedValue(undefined);
  const disablePush = vi.fn().mockResolvedValue(undefined);
  const secondEventFetcher = vi.fn().mockResolvedValue(EVENT_PAGE);
  renderRoute(
    "/config",
    vi.fn(),
    secondEventFetcher,
    {
      ...DEFAULT_PUSH_STATE,
      permission: "granted",
      active: true,
      disablePush,
      updatePreference,
    },
  );
  await screen.findByText(/25\/09\/2026/);
  await waitFor(() => {
    expect(secondEventFetcher).toHaveBeenCalledTimes(1);
  });
  for (const label of [
    "Confirmações",
    "Atualizações",
    "Conclusões",
    "Cancelamentos",
  ]) {
    expect(
      screen.getByRole("checkbox", { name: label }),
    ).toBeChecked();
  }

  fireEvent.click(
    screen.getByRole("checkbox", { name: "Confirmações" }),
  );
  expect(updatePreference).toHaveBeenCalledWith(
    "confirmed",
    false,
  );

  fireEvent.click(
    screen.getByRole("button", {
      name: "Desativar notificações",
    }),
  );
  expect(disablePush).toHaveBeenCalledTimes(1);
});


test("config_explains_denied_permission_without_prompting_again", async () => {
  const enablePush = vi.fn().mockResolvedValue(undefined);
  renderRoute(
    "/config",
    vi.fn(),
    vi.fn().mockResolvedValue(EVENT_PAGE),
    {
      ...DEFAULT_PUSH_STATE,
      permission: "denied",
      enablePush,
    },
  );
  expect(
    await screen.findByText(/permissão.*bloqueada/i),
  ).toBeInTheDocument();
  expect(
    screen.queryByRole("button", {
      name: "Ativar notificações",
    }),
  ).not.toBeInTheDocument();
  expect(enablePush).not.toHaveBeenCalled();
});


test("forget_delegates_cleanup_even_if_push_disable_fails", async () => {
  const installationKey = "alertam.mobile.installation.v1";
  localStorage.setItem(
    installationKey,
    "11111111-2222-4333-8444-555555555555",
  );
  savePairing(pairing);
  vi.spyOn(window, "confirm").mockReturnValue(true);

  const disablePush = vi.fn().mockRejectedValue(
    new Error("offline"),
  );
  const reset = vi.fn();
  renderRoute(
    "/config",
    reset,
    vi.fn().mockResolvedValue(EVENT_PAGE),
    {
      ...DEFAULT_PUSH_STATE,
      active: true,
      permission: "granted",
      disablePush,
    },
  );
  fireEvent.click(
    await screen.findByRole("button", {
      name: "Esquecer este aparelho",
    }),
  );

  await waitFor(() => {
    expect(disablePush).toHaveBeenCalledTimes(1);
    expect(reset).toHaveBeenCalledTimes(1);
  });
  expect(localStorage.getItem(installationKey)).toBe(
    "11111111-2222-4333-8444-555555555555",
  );
  expect(loadPairing()).toEqual(pairing);
});
