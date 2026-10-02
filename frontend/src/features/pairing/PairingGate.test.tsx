import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, expect, test, vi } from "vitest";

import {
  AccessRevokedError,
  TemporaryApiError,
} from "../../api/snapshotClient";
import {
  loadInstallationMetadata,
  storeInstallationMetadata,
} from "./installationMetadata";
import {
  isSessionRecoveryBlocked,
  loadPairing,
  savePairing,
} from "./pairingStorage";
import {
  loadInstallationId,
  storeInstallationId,
} from "../push/installationId";
import type { Pairing } from "./pairing";
import type {
  MobileSessionDraft,
  MobileSessionInfo,
} from "./mobileSessionClient";
import { PairingGate } from "./PairingGate";

const TOKEN_A = "Abcdefghijklmnopqrstuvwxyz0123456789_-ABCDE";
const TOKEN_B = "Zyxwvutsrqponmlkjihgfedcba9876543210_-ABCDE";
const TICKET_B = "PairingTicketForPecemB_abcdefghijklmnopqrstuvwxyz";
const INSTALL_A = "11111111-2222-4333-8444-555555555555";
const INSTALL_B = "aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee";
const SWITCH_ID = "99999999-8888-4777-8666-555555555555";
const ORPHAN_ID = "22222222-3333-4444-8555-666666666666";

const pairingA: Pairing = {
  deviceId: "pecem-a",
  viewSecret: TOKEN_A,
  pairedAt: "2026-09-30T10:00:00-03:00",
};

const sessionA: MobileSessionInfo = {
  deviceId: "pecem-a",
  installationId: INSTALL_A,
  displayCode: "K7M4Q2",
  platform: "ios",
};

function sessionB(
  installationId = INSTALL_B,
): MobileSessionInfo {
  return {
    deviceId: "pecem-b",
    installationId,
    displayCode: "8P2R6X",
    platform: "android",
  };
}

function seedActiveA(): void {
  savePairing(pairingA);
  storeInstallationId(INSTALL_A);
  storeInstallationMetadata({
    installationId: INSTALL_A,
    displayCode: "K7M4Q2",
    platform: "ios",
  });
}

beforeEach(() => {
  localStorage.clear();
  window.history.replaceState({}, "", "/");
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

function renderGate(options: {
  candidateValidator?: (pairing: Pairing) => Promise<{ deviceId: string }>;
  sessionCreator?: (
    pairing: Pairing,
    options?: { installationId?: string; platform?: "ios" | "android" | "other" },
  ) => Promise<MobileSessionInfo>;
  sessionSwitcher?: (
    pairing: Pairing,
    draft: MobileSessionDraft,
  ) => Promise<MobileSessionInfo>;
  sessionRecoverer?: () => Promise<{
    pairing: Pairing;
    session: MobileSessionInfo;
  } | null>;
  sessionClearer?: () => Promise<void>;
  freshIdFactory?: () => string;
} = {}) {
  const candidateValidator =
    options.candidateValidator ??
    vi.fn(async (pairing: Pairing) => ({ deviceId: pairing.deviceId }));
  const sessionCreator =
    options.sessionCreator ??
    vi.fn(async (pairing: Pairing, createOptions) => ({
      deviceId: pairing.deviceId,
      installationId: createOptions?.installationId ?? INSTALL_A,
      displayCode: "K7M4Q2",
      platform: createOptions?.platform ?? "ios",
    }));
  const sessionSwitcher =
    options.sessionSwitcher ??
    vi.fn(async (_pairing: Pairing, draft: MobileSessionDraft) =>
      sessionB(draft.installationId),
    );
  const sessionRecoverer =
    options.sessionRecoverer ?? vi.fn().mockResolvedValue(null);
  const sessionClearer =
    options.sessionClearer ?? vi.fn().mockResolvedValue(undefined);

  const rendered = render(
    <PairingGate
      candidateValidator={candidateValidator}
      sessionCreator={sessionCreator}
      sessionSwitcher={sessionSwitcher}
      sessionRecoverer={sessionRecoverer}
      sessionClearer={sessionClearer}
      freshIdFactory={options.freshIdFactory}
    >
      {(
        pairing,
        reset,
        sessionReady,
        handleAccessRevoked,
        _sessionInfo,
        submitPairingCandidate,
      ) => (
        <div>
          <span>
            APP {pairing.deviceId} {sessionReady ? "READY" : "WAIT"}
          </span>
          <button type="button" onClick={reset}>RESET</button>
          <button type="button" onClick={handleAccessRevoked}>REVOKED</button>
          <button
            type="button"
            onClick={() => submitPairingCandidate({
              deviceId: "pecem-b",
              viewSecret: null,
              pairingTicket: TICKET_B,
              pairedAt: "2026-10-02T14:00:00-03:00",
            })}
          >
            CODE-CANDIDATE
          </button>
        </div>
      )}
    </PairingGate>,
  );

  return {
    ...rendered,
    candidateValidator,
    sessionCreator,
    sessionSwitcher,
    sessionRecoverer,
    sessionClearer,
  };
}

test("without pairing asks for desktop QR", async () => {
  renderGate();

  expect(
    await screen.findByRole("heading", {
      name: "Alerta de Movimentações Marítimas",
    }),
  ).toBeInTheDocument();
});

test("invalid QR B preserves active A and clears fragment before validation", async () => {
  seedActiveA();
  window.history.replaceState(
    {},
    "",
    `/#/pair/pecem-b?token=${TOKEN_B}`,
  );
  const validator = vi.fn(async () => {
    expect(window.location.hash).toBe("");
    throw new AccessRevokedError();
  });

  renderGate({ candidateValidator: validator });

  expect(await screen.findByText(/APP pecem-a/)).toBeInTheDocument();
  expect(loadPairing()).toEqual(pairingA);
  expect(loadInstallationId()).toBe(INSTALL_A);
  expect(loadInstallationMetadata()?.displayCode).toBe("K7M4Q2");
});

test("candidate submitted inside installed PWA uses safe switch confirmation", async () => {
  seedActiveA();
  const switcher = vi.fn();

  renderGate({ sessionSwitcher: switcher });

  fireEvent.click(
    await screen.findByRole("button", { name: "CODE-CANDIDATE" }),
  );

  expect(
    await screen.findByRole("heading", { name: "Trocar de AlertaM?" }),
  ).toBeInTheDocument();
  expect(screen.getByText(/Atual: pecem-a/)).toBeInTheDocument();
  expect(screen.getByText(/Novo: pecem-b/)).toBeInTheDocument();
  expect(switcher).not.toHaveBeenCalled();
  expect(loadPairing()).toEqual(pairingA);
});


test("valid QR B asks confirmation before create or switch", async () => {
  seedActiveA();
  window.history.replaceState(
    {},
    "",
    `/#/pair/pecem-b?token=${TOKEN_B}`,
  );
  const creator = vi.fn();
  const switcher = vi.fn();

  renderGate({
    sessionCreator: creator,
    sessionSwitcher: switcher,
  });

  expect(
    await screen.findByRole("heading", { name: "Trocar de AlertaM?" }),
  ).toBeInTheDocument();
  expect(screen.getByText(/Atual: pecem-a/)).toBeInTheDocument();
  expect(screen.getByText(/Novo: pecem-b/)).toBeInTheDocument();
  expect(creator).not.toHaveBeenCalled();
  expect(switcher).not.toHaveBeenCalled();
  expect(loadPairing()).toEqual(pairingA);
});

test("cancel switch discards candidate and keeps A", async () => {
  seedActiveA();
  window.history.replaceState(
    {},
    "",
    `/#/pair/pecem-b?token=${TOKEN_B}`,
  );
  const switcher = vi.fn();

  renderGate({ sessionSwitcher: switcher });

  fireEvent.click(
    await screen.findByRole("button", { name: "Cancelar" }),
  );

  expect(await screen.findByText(/APP pecem-a/)).toBeInTheDocument();
  expect(switcher).not.toHaveBeenCalled();
  expect(loadPairing()).toEqual(pairingA);
  expect(loadInstallationId()).toBe(INSTALL_A);
});

test("confirm switch promotes B only after successful server switch", async () => {
  seedActiveA();
  window.history.replaceState(
    {},
    "",
    `/#/pair/pecem-b?token=${TOKEN_B}`,
  );
  const ids = vi.fn()
    .mockReturnValueOnce(INSTALL_B)
    .mockReturnValueOnce(SWITCH_ID);
  const switcher = vi.fn(
    async (_pairing: Pairing, draft: MobileSessionDraft) =>
      sessionB(draft.installationId),
  );

  renderGate({
    freshIdFactory: ids,
    sessionSwitcher: switcher,
  });

  fireEvent.click(
    await screen.findByRole("button", { name: "Trocar AlertaM" }),
  );

  expect(await screen.findByText(/APP pecem-b READY/)).toBeInTheDocument();
  expect(ids).toHaveBeenCalledTimes(2);
  expect(switcher).toHaveBeenCalledWith(
    expect.objectContaining({
      deviceId: "pecem-b",
      viewSecret: TOKEN_B,
    }),
    {
      installationId: INSTALL_B,
      platform: "other",
      switchId: SWITCH_ID,
    },
  );
  expect(loadPairing()?.deviceId).toBe("pecem-b");
  expect(loadPairing()?.viewSecret).toBe(TOKEN_B);
  expect(loadInstallationId()).toBe(INSTALL_B);
  expect(loadInstallationMetadata()).toEqual({
    installationId: INSTALL_B,
    displayCode: "8P2R6X",
    platform: "android",
  });
});

test("temporary switch retry reuses exactly the same draft", async () => {
  seedActiveA();
  window.history.replaceState(
    {},
    "",
    `/#/pair/pecem-b?token=${TOKEN_B}`,
  );
  const ids = vi.fn()
    .mockReturnValueOnce(INSTALL_B)
    .mockReturnValueOnce(SWITCH_ID);
  const switcher = vi.fn()
    .mockRejectedValueOnce(new TemporaryApiError())
    .mockResolvedValueOnce(sessionB());

  renderGate({
    freshIdFactory: ids,
    sessionSwitcher: switcher,
  });

  fireEvent.click(
    await screen.findByRole("button", { name: "Trocar AlertaM" }),
  );

  expect(
    await screen.findByRole("button", { name: "Tentar novamente" }),
  ).toBeInTheDocument();
  expect(screen.queryByText(/APP pecem-a/)).not.toBeInTheDocument();
  expect(loadPairing()).toEqual(pairingA);
  expect(loadInstallationId()).toBe(INSTALL_A);
  expect(ids).toHaveBeenCalledTimes(2);

  const firstDraft = switcher.mock.calls[0]?.[1];
  fireEvent.click(screen.getByRole("button", { name: "Tentar novamente" }));

  expect(await screen.findByText(/APP pecem-b READY/)).toBeInTheDocument();
  expect(switcher).toHaveBeenCalledTimes(2);
  expect(switcher.mock.calls[1]?.[1]).toEqual(firstDraft);
  expect(ids).toHaveBeenCalledTimes(2);
});

test("same Desktop reuses current installation without switch confirmation", async () => {
  seedActiveA();
  window.history.replaceState(
    {},
    "",
    `/#/pair/pecem-a?token=${TOKEN_B}`,
  );
  const freshIdFactory = vi.fn(() => INSTALL_B);
  const creator = vi.fn().mockResolvedValue(sessionA);
  const switcher = vi.fn();

  renderGate({
    freshIdFactory,
    sessionCreator: creator,
    sessionSwitcher: switcher,
  });

  expect(await screen.findByText(/APP pecem-a READY/)).toBeInTheDocument();
  expect(
    screen.queryByRole("heading", { name: "Trocar de AlertaM?" }),
  ).not.toBeInTheDocument();
  expect(creator).toHaveBeenCalledWith(
    expect.objectContaining({
      deviceId: "pecem-a",
      viewSecret: TOKEN_B,
    }),
    expect.objectContaining({
      installationId: INSTALL_A,
    }),
  );
  expect(freshIdFactory).not.toHaveBeenCalled();
  expect(switcher).not.toHaveBeenCalled();
  expect(loadPairing()?.viewSecret).toBe(TOKEN_B);
});

test("same Desktop creates one fresh installation when old UUID is revoked", async () => {
  seedActiveA();
  window.history.replaceState(
    {},
    "",
    `/#/pair/pecem-a?token=${TOKEN_B}`,
  );
  const freshIdFactory = vi.fn(() => INSTALL_B);
  const creator = vi.fn()
    .mockRejectedValueOnce(new AccessRevokedError())
    .mockResolvedValueOnce({
      ...sessionA,
      installationId: INSTALL_B,
      displayCode: "P8X4TR",
    });

  renderGate({
    freshIdFactory,
    sessionCreator: creator,
  });

  expect(await screen.findByText(/APP pecem-a READY/)).toBeInTheDocument();
  expect(creator).toHaveBeenCalledTimes(2);
  expect(creator.mock.calls[0]?.[1]).toEqual(
    expect.objectContaining({ installationId: INSTALL_A }),
  );
  expect(creator.mock.calls[1]?.[1]).toEqual(
    expect.objectContaining({ installationId: INSTALL_B }),
  );
  expect(freshIdFactory).toHaveBeenCalledTimes(1);
  expect(loadInstallationId()).toBe(INSTALL_B);
});

test("first pairing ignores orphan installation id left in storage", async () => {
  storeInstallationId(ORPHAN_ID);
  window.history.replaceState(
    {},
    "",
    `/#/pair/pecem-b?token=${TOKEN_B}`,
  );
  const freshIdFactory = vi.fn(() => INSTALL_B);
  const creator = vi.fn().mockResolvedValue(sessionB());

  renderGate({
    freshIdFactory,
    sessionCreator: creator,
  });

  expect(await screen.findByText(/APP pecem-b READY/)).toBeInTheDocument();
  expect(creator).toHaveBeenCalledWith(
    expect.objectContaining({ deviceId: "pecem-b" }),
    expect.objectContaining({ installationId: INSTALL_B }),
  );
  expect(creator.mock.calls[0]?.[1]?.installationId).not.toBe(ORPHAN_ID);
  expect(loadInstallationId()).toBe(INSTALL_B);
});

test("manual reset clears pairing installation and metadata without recovery loop", async () => {
  seedActiveA();
  const recoverer = vi.fn().mockResolvedValue({
    pairing: {
      deviceId: "cookie",
      viewSecret: null,
      pairedAt: "2026-09-30T11:00:00-03:00",
    },
    session: {
      ...sessionA,
      deviceId: "cookie",
    },
  });
  const clearer = vi.fn().mockResolvedValue(undefined);

  renderGate({
    sessionCreator: vi.fn().mockResolvedValue(sessionA),
    sessionRecoverer: recoverer,
    sessionClearer: clearer,
  });

  fireEvent.click(await screen.findByRole("button", { name: "RESET" }));

  expect(
    await screen.findByRole("heading", {
      name: "Aparelho desconectado",
    }),
  ).toBeInTheDocument();
  expect(
    screen.getByRole("button", { name: "Ler QR Code" }),
  ).toBeInTheDocument();
  expect(
    screen.getByRole("button", { name: "Usar código de conexão" }),
  ).toBeInTheDocument();
  expect(clearer).toHaveBeenCalledTimes(1);
  expect(recoverer).not.toHaveBeenCalled();
  expect(loadPairing()).toBeNull();
  expect(loadInstallationId()).toBeNull();
  expect(loadInstallationMetadata()).toBeNull();
});

test("access revoked clears local identity and shows explicit revoked state", async () => {
  seedActiveA();

  renderGate({
    sessionCreator: vi.fn().mockResolvedValue(sessionA),
  });

  fireEvent.click(await screen.findByRole("button", { name: "REVOKED" }));

  expect(
    await screen.findByRole("heading", { name: "Acesso revogado" }),
  ).toBeInTheDocument();
  expect(
    screen.getByRole("button", { name: "Ler QR Code" }),
  ).toBeInTheDocument();
  expect(
    screen.getByRole("button", { name: "Usar código de conexão" }),
  ).toBeInTheDocument();
  expect(loadPairing()).toBeNull();
  expect(loadInstallationId()).toBeNull();
  expect(loadInstallationMetadata()).toBeNull();
});

test("cookie recovery enters app ready with recovered session", async () => {
  const recovered = {
    pairing: {
      deviceId: "pecem-cookie",
      viewSecret: null,
      pairedAt: "2026-09-30T12:00:00-03:00",
    } satisfies Pairing,
    session: {
      ...sessionA,
      deviceId: "pecem-cookie",
    },
  };

  renderGate({
    sessionRecoverer: vi.fn().mockResolvedValue(recovered),
  });

  expect(
    await screen.findByText(/APP pecem-cookie READY/),
  ).toBeInTheDocument();
  expect(loadPairing()).toBeNull();
});


test("manual reset blocks stale cookie recovery across remount", async () => {
  seedActiveA();
  const clearer = vi.fn().mockRejectedValue(new TypeError("offline"));
  const first = renderGate({
    sessionCreator: vi.fn().mockResolvedValue(sessionA),
    sessionClearer: clearer,
  });

  fireEvent.click(await screen.findByRole("button", { name: "RESET" }));
  expect(isSessionRecoveryBlocked()).toBe(true);
  first.unmount();

  const recoverer = vi.fn().mockResolvedValue({
    pairing: {
      deviceId: "stale-cookie",
      viewSecret: null,
      pairedAt: "2026-09-30T20:00:00-03:00",
    } satisfies Pairing,
    session: {
      ...sessionA,
      deviceId: "stale-cookie",
    },
  });

  renderGate({ sessionRecoverer: recoverer });

  expect(
    await screen.findByRole("heading", {
      name: "Alerta de Movimentações Marítimas",
    }),
  ).toBeInTheDocument();
  expect(recoverer).not.toHaveBeenCalled();
});
