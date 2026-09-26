import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, expect, test, vi } from "vitest";

import fixture from "../../test/fixtures/mobile_snapshot_v1.json";
import { parseSnapshotReadResponse } from "../../api/contract";
import {
  AccessRevokedError,
  SnapshotUnavailableError,
  TemporaryApiError,
} from "../../api/snapshotClient";
import {
  loadPairing,
  savePairing,
} from "./pairingStorage";
import type { Pairing } from "./pairing";
import { PairingGate } from "./PairingGate";

const TOKEN = "Abcdefghijklmnopqrstuvwxyz0123456789_-ABCDE";
const TOKEN_2 = "Zyxwvutsrqponmlkjihgfedcba9876543210_-ABCDE";

const response = parseSnapshotReadResponse({
  snapshot: fixture,
  meta: {
    received_at: "2026-09-25T13:40:15-03:00",
    age_seconds: 3,
    collector_online: true,
    stale_after_seconds: 120,
  },
});
beforeEach(() => {
  localStorage.clear();
  window.history.replaceState({}, "", "/");
});

function renderGate(fetcher = vi.fn().mockResolvedValue(response)) {
  return render(
    <PairingGate fetcher={fetcher}>
      {(pairing) => <div>APP {pairing.deviceId}</div>}
    </PairingGate>,
  );
}

test("without_pairing_asks_for_desktop_qr", () => {
  renderGate();
  expect(
    screen.getByRole("heading", { name: "Alerta de Movimentações Marítimas" }),
  ).toBeInTheDocument();
  expect(screen.getByText(/Conectar Celular/i)).toBeInTheDocument();
});

test("valid_qr_clears_fragment_before_fetch_and_persists_after_200", async () => {
  window.history.replaceState({}, "", `/#/pair/pecem-01?token=${TOKEN}`);
  const fetcher = vi.fn(async () => {
    expect(window.location.hash).toBe("");
    expect(document.body.textContent).not.toContain(TOKEN);
    return response;
  });

  renderGate(fetcher);

  expect(await screen.findByText("APP pecem-01")).toBeInTheDocument();
  expect(loadPairing()?.viewSecret).toBe(TOKEN);
  expect(window.location.hash).toBe("");
});
test("valid_qr_with_404_is_persisted_as_waiting_device", async () => {
  window.history.replaceState({}, "", `/#/pair/pecem-01?token=${TOKEN}`);
  const fetcher = vi.fn().mockRejectedValue(new SnapshotUnavailableError());

  renderGate(fetcher);

  expect(await screen.findByText("APP pecem-01")).toBeInTheDocument();
  expect(loadPairing()?.viewSecret).toBe(TOKEN);
});

test("revoked_candidate_never_replaces_previous_pairing", async () => {
  const previous: Pairing = {
    deviceId: "pecem-antigo",
    viewSecret: TOKEN_2,
    pairedAt: "2026-09-26T08:00:00-03:00",
  };
  savePairing(previous);
  window.history.replaceState({}, "", `/#/pair/pecem-novo?token=${TOKEN}`);
  const fetcher = vi.fn().mockRejectedValue(new AccessRevokedError());

  renderGate(fetcher);

  expect(await screen.findByText("APP pecem-antigo")).toBeInTheDocument();
  expect(loadPairing()).toEqual(previous);
});
test("temporary_error_keeps_candidate_only_in_memory_and_retry_can_confirm", async () => {
  window.history.replaceState({}, "", `/#/pair/pecem-01?token=${TOKEN}`);
  const fetcher = vi
    .fn()
    .mockRejectedValueOnce(new TemporaryApiError())
    .mockResolvedValueOnce(response);

  renderGate(fetcher);

  const retry = await screen.findByRole("button", { name: "Tentar novamente" });
  expect(loadPairing()).toBeNull();
  expect(document.body.textContent).not.toContain(TOKEN);

  fireEvent.click(retry);

  await waitFor(() => expect(screen.getByText("APP pecem-01")).toBeInTheDocument());
  expect(fetcher).toHaveBeenCalledTimes(2);
  expect(loadPairing()?.viewSecret).toBe(TOKEN);
});
