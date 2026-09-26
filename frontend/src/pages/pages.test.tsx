import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { vi } from "vitest";
import fixture from "../test/fixtures/mobile_snapshot_v1.json";
import { parseSnapshotReadResponse } from "../api/contract";
import type { Pairing } from "../features/pairing/pairing";
import { SnapshotProvider } from "../features/snapshot/SnapshotProvider";
import { savePairing } from "../features/pairing/pairingStorage";
import { AppRoutes } from "../app/router";
import { StatusCards } from "../components/StatusCards";

const pairing: Pairing = {
  deviceId: "pecem-01",
  viewSecret: "Abcdefghijklmnopqrstuvwxyz0123456789_-ABCDE",
  pairedAt: "2026-09-26T09:40:00-03:00",
};
const response = parseSnapshotReadResponse({
  snapshot: fixture,
  meta: { received_at: "2026-09-25T13:40:15-03:00", age_seconds: 3, collector_online: true, stale_after_seconds: 120 },
});
function renderRoute(route: string, onPairingCleared = vi.fn()) {
  const view = render(
    <SnapshotProvider pairing={pairing} fetcher={vi.fn().mockResolvedValue(response)}>
      <MemoryRouter initialEntries={[route]}>
        <AppRoutes pairing={pairing} onPairingCleared={onPairingCleared} />
      </MemoryRouter>
    </SnapshotProvider>,
  );
  return { onPairingCleared, unmount: view.unmount };
}

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
  const { onPairingCleared } = renderRoute("/config");

  expect(await screen.findByText("pecem-01")).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Esquecer este aparelho" }));
  expect(onPairingCleared).toHaveBeenCalledTimes(1);
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
