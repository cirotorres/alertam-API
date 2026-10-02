import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, expect, test, vi } from "vitest";

import {
  INSTALLATION_METADATA_STORAGE_KEY,
  storeInstallationMetadata,
} from "../features/pairing/installationMetadata";
import { PAIRING_STORAGE_KEY } from "../features/pairing/pairingStorage";
import {
  INSTALLATION_ID_STORAGE_KEY,
  storeInstallationId,
} from "../features/push/installationId";

const INSTALLATION_ID = "11111111-2222-4333-8444-555555555555";

const mocked = vi.hoisted(() => ({
  reset: vi.fn(),
  disablePush: vi.fn().mockResolvedValue(undefined),
  context: {
    pairing: {
      deviceId: "pecem-55ee08ee",
      viewSecret: null,
      pairedAt: "2026-09-30T18:00:00Z",
    },
    installation: {
      deviceId: "pecem-55ee08ee",
      installationId: "11111111-2222-4333-8444-555555555555",
      displayCode: "K7M4Q2",
      platform: "ios",
    },
    snapshotState: {
      status: "online",
      data: {
        meta: {
          received_at: "2026-09-30T18:00:00-03:00",
        },
      },
    },
    onPairingCleared: vi.fn(),
    basePath: "",
    demoMode: false,
  },
}));

vi.mock("../app/AppShell", () => ({
  useShellContext: () => ({
    ...mocked.context,
    onPairingCleared: mocked.reset,
  }),
}));

vi.mock("../features/push/PushProvider", () => ({
  usePush: () => ({
    supported: true,
    permission: "granted",
    active: true,
    preferences: {
      confirmed: true,
      updated: true,
      completed: true,
      cancelled: true,
    },
    error: null,
    enablePush: vi.fn(),
    disablePush: mocked.disablePush,
    updatePreference: vi.fn(),
  }),
}));

import { ConfigPage } from "./ConfigPage";

beforeEach(() => {
  localStorage.clear();
  mocked.reset.mockClear();
  mocked.disablePush.mockClear();
  vi.restoreAllMocks();
});

test("shows this device and connected AlertaM without exposing technical UUID", () => {
  render(<ConfigPage />);

  expect(screen.getByText("Este aparelho")).toBeInTheDocument();
  expect(screen.getByText("iPhone/iPad · K7M4Q2")).toBeInTheDocument();
  expect(screen.getByText("Identificação do AlertaM")).toBeInTheDocument();
  expect(screen.getByText("pecem-55ee08ee")).toBeInTheDocument();
  expect(screen.queryByText(INSTALLATION_ID)).not.toBeInTheDocument();
  expect(screen.queryByText("Dispositivo")).not.toBeInTheDocument();
});

test("forget delegates identity cleanup to PairingGate reset", async () => {
  localStorage.setItem(PAIRING_STORAGE_KEY, "sentinel-pairing");
  storeInstallationId(INSTALLATION_ID);
  storeInstallationMetadata({
    installationId: INSTALLATION_ID,
    displayCode: "K7M4Q2",
    platform: "ios",
  });
  vi.spyOn(window, "confirm").mockReturnValue(true);

  render(<ConfigPage />);
  fireEvent.click(
    screen.getByRole("button", { name: "Esquecer este aparelho" }),
  );

  await waitFor(() => {
    expect(mocked.disablePush).toHaveBeenCalledTimes(1);
    expect(mocked.reset).toHaveBeenCalledTimes(1);
  });

  expect(localStorage.getItem(PAIRING_STORAGE_KEY)).toBe("sentinel-pairing");
  expect(localStorage.getItem(INSTALLATION_ID_STORAGE_KEY)).toBe(
    INSTALLATION_ID,
  );
  expect(localStorage.getItem(INSTALLATION_METADATA_STORAGE_KEY)).not.toBeNull();
});


test("formats last synchronization in pt-BR instead of raw ISO", () => {
  render(<ConfigPage />);

  const label = screen.getByText("Última sincronização");
  const value = label.parentElement?.querySelector("dd");
  expect(value).not.toBeNull();
  expect(value?.textContent).not.toContain("2026-09-30T");
  expect(value?.textContent).toContain("30/09/2026");
  expect(value?.textContent).toMatch(/\d{2}:\d{2}:\d{2}/);
});


test("labels connected desktop with the same AlertaM identifier", () => {
  render(<ConfigPage />);

  expect(screen.getByText("Identificação do AlertaM")).toBeInTheDocument();
  expect(screen.getByText("pecem-55ee08ee")).toBeInTheDocument();
});
