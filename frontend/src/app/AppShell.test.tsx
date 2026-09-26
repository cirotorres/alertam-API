import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { vi } from "vitest";
import fixture from "../test/fixtures/mobile_snapshot_v1.json";
import { parseSnapshotReadResponse } from "../api/contract";
import type { Pairing } from "../features/pairing/pairing";
import { SnapshotProvider } from "../features/snapshot/SnapshotProvider";
import { AppRoutes } from "./router";

const pairing: Pairing = {
  deviceId: "pecem-01",
  viewSecret: "Abcdefghijklmnopqrstuvwxyz0123456789_-ABCDE",
  pairedAt: "2026-09-26T09:40:00-03:00",
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
      <MemoryRouter initialEntries={[initialEntry]}>
        <AppRoutes pairing={pairing} />
      </MemoryRouter>
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

  for (const label of ["Mapa", "Alertas", "Histórico", "Config.", "Instalar aplicativo", "Sobre"]) {
    expect(screen.getByText(label, { exact: true })).toBeInTheDocument();
  }

  const drawer = screen.getByRole("dialog", { name: "Menu principal" });
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
