import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, expect, test, vi } from "vitest";

import { savePairing } from "../features/pairing/pairingStorage";
import { App } from "./App";

const TOKEN = "Abcdefghijklmnopqrstuvwxyz0123456789_-ABCDE";

beforeEach(() => {
  localStorage.clear();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
  window.history.replaceState({}, "", "/");
});

test("renders_alertam_shell_title", async () => {
  render(<App />);

  expect(
    await screen.findByRole("heading", {
      name: "Alerta de Movimentações Marítimas",
    }),
  ).toBeInTheDocument();
});

test("revoked_stored_pairing_returns_to_qr_gate", async () => {
  savePairing({
    deviceId: "pecem-01",
    viewSecret: TOKEN,
    pairedAt: "2026-09-26T09:40:00-03:00",
  });
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue(new Response("", { status: 401 })),
  );

  render(<App />);

  await waitFor(() => {
    expect(
      screen.getByRole("heading", { name: "Alerta de Movimentações Marítimas" }),
    ).toBeInTheDocument();
    expect(screen.getByText(/Conectar Celular/i)).toBeInTheDocument();
  });
  expect(localStorage.length).toBe(0);
});
