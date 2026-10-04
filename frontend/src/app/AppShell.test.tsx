import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { vi } from "vitest";
import fixture from "../test/fixtures/mobile_snapshot_v1.json";
import { parseSnapshotReadResponse } from "../api/contract";
import { StaticEventProvider } from "../features/events/EventProvider";
import type { EventState } from "../features/events/useEventPolling";
import type { MobileSessionInfo } from "../features/pairing/mobileSessionClient";
import type { Pairing } from "../features/pairing/pairing";
import {
  StaticPushProvider,
  type PushState,
} from "../features/push/PushProvider";
import { SnapshotProvider } from "../features/snapshot/SnapshotProvider";
import { AppRoutes } from "./router";

const pairing: Pairing = {
  deviceId: "pecem-01",
  viewSecret: "Abcdefghijklmnopqrstuvwxyz0123456789_-ABCDE",
  pairedAt: "2026-09-26T09:40:00-03:00",
};

const installation: MobileSessionInfo = {
  deviceId: "pecem-01",
  installationId: "11111111-2222-4333-8444-555555555555",
  displayCode: "K7M4Q2",
  platform: "ios",
};

const eventState: EventState = {
  events: [],
  status: "online",
  newEvent: null,
  hasMore: false,
  loadOlder: async () => false,
};

const pushState: PushState = {
  supported: false,
  permission: "default",
  active: false,
  preferences: {
    confirmed: true,
    updated: true,
    completed: true,
    cancelled: true,
    anchored: true,
  },
  error: null,
  enablePush: async () => undefined,
  disablePush: async () => undefined,
  updatePreference: async () => undefined,
};

const response = parseSnapshotReadResponse({
  snapshot: fixture,
  meta: {
    received_at: "2026-09-25T13:40:15-03:00",
    age_seconds: 3,
    collector_online: true,
    stale_after_seconds: 120,
  },
});
function renderApp(initialEntry = "/") {
  const fetcher = vi.fn().mockResolvedValue(response);
  render(
    <SnapshotProvider pairing={pairing} fetcher={fetcher}>
      <StaticEventProvider state={eventState}>
        <StaticPushProvider state={pushState}>
          <MemoryRouter initialEntries={[initialEntry]}>
            <AppRoutes
              pairing={pairing}
              installation={installation}
            />
          </MemoryRouter>
        </StaticPushProvider>
      </StaticEventProvider>
    </SnapshotProvider>,
  );
  return { fetcher };
}

test("renders_header_session_and_real_last_collection", async () => {
  renderApp();

  expect(screen.getByRole("button", { name: "Abrir menu" })).toBeInTheDocument();
  expect(
    screen.getByText("Alerta de Movimentações Marítimas"),
  ).toBeInTheDocument();
  expect(await screen.findByText("Sessão válida")).toBeInTheDocument();
  expect(screen.getByText(/25\/09\/2026/)).toBeInTheDocument();
});

test("drawer_has_expected_destinations_and_escape_returns_focus", async () => {
  renderApp();
  const menu = screen.getByRole("button", { name: "Abrir menu" });
  fireEvent.click(menu);

  for (const label of [
    "Mapa",
    "Alertas",
    "Histórico",
    "Acompanhados",
    "Configurações",
    "Instalar aplicativo",
    "Sobre",
  ]) {
    expect(screen.getByText(label, { exact: true })).toBeInTheDocument();
  }

  const drawer = screen.getByRole("dialog", { name: "Menu principal" });
  expect(drawer.querySelectorAll(".drawer__item-icon")).toHaveLength(7);
  fireEvent.keyDown(document, { key: "Escape" });

  expect(drawer).toHaveClass("is-closing");
  await waitFor(() => expect(drawer).not.toBeInTheDocument());
  expect(menu).toHaveFocus();
});
test("opening_drawer_closes_vessel_sheet", async () => {
  renderApp();
  const vessel = await screen.findByRole("button", { name: /NAVIO A, Berço 2/i });
  vessel.focus();
  fireEvent.click(vessel);
  expect(screen.getByRole("dialog", { name: /Ficha do navio NAVIO A/i })).toBeInTheDocument();

  fireEvent.click(screen.getByRole("button", { name: "Abrir menu" }));

  expect(screen.queryByRole("dialog", { name: /Ficha do navio/i })).not.toBeInTheDocument();
  expect(screen.getByRole("dialog", { name: "Menu principal" })).toBeInTheDocument();
});

test("escape_closes_vessel_sheet_and_returns_focus_to_trigger", async () => {
  renderApp();
  const vessel = await screen.findByRole("button", { name: /NAVIO A, Berço 2/i });
  vessel.focus();
  fireEvent.click(vessel);
  expect(screen.getByRole("dialog", { name: /Ficha do navio NAVIO A/i })).toBeInTheDocument();

  const sheet = screen.getByRole("dialog", { name: /Ficha do navio NAVIO A/i });
  fireEvent.keyDown(document, { key: "Escape" });

  expect(sheet).toHaveClass("is-closing");
  await waitFor(() => expect(sheet).not.toBeInTheDocument());
  expect(vessel).toHaveFocus();
});


test("install_action_opens_browser_specific_help_when_native_prompt_is_unavailable", async () => {
  renderApp();

  fireEvent.click(screen.getByRole("button", { name: "Abrir menu" }));
  fireEvent.click(screen.getByRole("button", { name: "Instalar aplicativo" }));

  expect(
    await screen.findByRole("dialog", { name: "Instalar aplicativo" }),
  ).toBeInTheDocument();
  expect(screen.getByText(/não está disponível neste navegador/i)).toBeInTheDocument();
});

test("vessel_photo_is_fetched_on_open_and_reused_from_local_cache", async () => {
  localStorage.clear();
  const fetchMock = vi.fn().mockResolvedValue(
    new Response(
      JSON.stringify({
        imo: "1234567",
        photo_url: "https://upload.wikimedia.org/navio.jpg",
        author: "Jane Doe",
        license: "CC BY-SA 4.0",
        source_url: "https://commons.wikimedia.org/wiki/File:Navio.jpg",
      }),
      { status: 200, headers: { "Content-Type": "application/json" } },
    ),
  );
  vi.stubGlobal("fetch", fetchMock);

  renderApp();
  const vessel = await screen.findByRole("button", { name: /NAVIO A, Berço 2/i });
  expect(fetchMock).not.toHaveBeenCalled();

  fireEvent.click(vessel);
  expect(
    await screen.findByRole("img", { name: /Foto de NAVIO A/i }),
  ).toBeInTheDocument();
  expect(fetchMock).toHaveBeenCalledTimes(1);

  fireEvent.click(screen.getByRole("button", { name: "Fechar ficha do navio" }));
  await waitFor(() =>
    expect(screen.queryByRole("dialog", { name: /Ficha do navio NAVIO A/i })).not.toBeInTheDocument(),
  );

  fireEvent.click(vessel);
  expect(
    await screen.findByRole("img", { name: /Foto de NAVIO A/i }),
  ).toBeInTheDocument();
  expect(fetchMock).toHaveBeenCalledTimes(1);

  vi.unstubAllGlobals();
});

test("vessel_photo_temporary_failure_is_visible_in_sheet", async () => {
  localStorage.clear();
  const fetchMock = vi.fn().mockResolvedValue(
    new Response(
      JSON.stringify({ detail: "temporarily unavailable" }),
      { status: 503, headers: { "Content-Type": "application/json" } },
    ),
  );
  vi.stubGlobal("fetch", fetchMock);

  renderApp();
  const vessel = await screen.findByRole("button", {
    name: /NAVIO A, Berço 2/i,
  });
  fireEvent.click(vessel);

  expect(
    await screen.findByText("Foto temporariamente indisponível."),
  ).toBeInTheDocument();
  expect(
    screen.queryByText("Sem foto disponível para este navio."),
  ).not.toBeInTheDocument();

  vi.unstubAllGlobals();
});


test("shell outlet context exposes installation identity to config", async () => {
  renderApp("/config");

  expect(await screen.findByText("Este aparelho")).toBeInTheDocument();
  expect(screen.getByText("iPhone/iPad · K7M4Q2")).toBeInTheDocument();
  expect(screen.getByText("AlertaM conectado")).toBeInTheDocument();
  expect(screen.queryByText(installation.installationId)).not.toBeInTheDocument();
});
