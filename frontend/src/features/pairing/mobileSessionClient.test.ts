import { AccessRevokedError, TemporaryApiError } from "../../api/snapshotClient";
import {
  INSTALLATION_METADATA_STORAGE_KEY,
  loadInstallationMetadata,
} from "./installationMetadata";
import type { Pairing } from "./pairing";
import {
  clearMobileSession,
  createMobileSession,
  recoverMobileSession,
  switchMobileSession,
  touchMobileSession,
  validatePairingCandidate,
} from "./mobileSessionClient";
import {
  INSTALLATION_ID_STORAGE_KEY,
  loadInstallationId,
} from "../push/installationId";

const TOKEN = "Abcdefghijklmnopqrstuvwxyz0123456789_-ABCDE";
const INSTALLATION_ID = "11111111-2222-4333-8444-555555555555";
const SWITCH_ID = "aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee";

const pairing: Pairing = {
  deviceId: "pecem-01",
  viewSecret: TOKEN,
  pairedAt: "2026-09-26T15:00:00-03:00",
};

function sessionBody(
  overrides: Partial<Record<string, unknown>> = {},
): Record<string, unknown> {
  return {
    device_id: "pecem-01",
    installation_id: INSTALLATION_ID,
    display_code: "K7M4Q2",
    platform: "ios",
    ...overrides,
  };
}

beforeEach(() => {
  localStorage.clear();
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

test("create sends platform and persists identity only after valid response", async () => {
  const fetchMock = vi.fn().mockResolvedValue(
    new Response(JSON.stringify(sessionBody()), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    }),
  );
  vi.stubGlobal("fetch", fetchMock);

  const session = await createMobileSession(pairing, {
    installationId: INSTALLATION_ID,
    platform: "ios",
  });

  expect(session).toEqual({
    deviceId: "pecem-01",
    installationId: INSTALLATION_ID,
    displayCode: "K7M4Q2",
    platform: "ios",
  });
  expect(fetchMock).toHaveBeenCalledWith(
    "/api/v1/mobile/session",
    expect.objectContaining({
      method: "POST",
      credentials: "same-origin",
      headers: expect.objectContaining({
        Authorization: `Bearer ${TOKEN}`,
      }),
      body: JSON.stringify({
        device_id: "pecem-01",
        installation_id: INSTALLATION_ID,
        platform: "ios",
      }),
    }),
  );
  expect(loadInstallationId()).toBe(INSTALLATION_ID);
  expect(loadInstallationMetadata()).toEqual({
    installationId: INSTALLATION_ID,
    displayCode: "K7M4Q2",
    platform: "ios",
  });
  expect(
    JSON.parse(
      localStorage.getItem(INSTALLATION_METADATA_STORAGE_KEY) ?? "{}",
    ),
  ).toEqual({
    installationId: INSTALLATION_ID,
    displayCode: "K7M4Q2",
    platform: "ios",
  });
});

test("create rejects inconsistent response without persisting candidate", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify(sessionBody({ installation_id: SWITCH_ID })),
        {
          status: 200,
          headers: { "Content-Type": "application/json" },
        },
      ),
    ),
  );

  await expect(
    createMobileSession(pairing, {
      installationId: INSTALLATION_ID,
      platform: "ios",
    }),
  ).rejects.toBeInstanceOf(TemporaryApiError);

  expect(localStorage.getItem(INSTALLATION_ID_STORAGE_KEY)).toBeNull();
  expect(localStorage.getItem(INSTALLATION_METADATA_STORAGE_KEY)).toBeNull();
});

test("recovery stores server identity and returns cookie-only pairing plus session", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue(
      new Response(JSON.stringify(sessionBody()), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    ),
  );

  const recovered = await recoverMobileSession();

  expect(recovered).not.toBeNull();
  expect(recovered?.pairing).toEqual(
    expect.objectContaining({
      deviceId: "pecem-01",
      viewSecret: null,
    }),
  );
  expect(recovered?.session).toEqual({
    deviceId: "pecem-01",
    installationId: INSTALLATION_ID,
    displayCode: "K7M4Q2",
    platform: "ios",
  });
  expect(loadInstallationId()).toBe(INSTALLATION_ID);
  expect(loadInstallationMetadata()).toEqual({
    installationId: INSTALLATION_ID,
    displayCode: "K7M4Q2",
    platform: "ios",
  });
});

test("validate candidate is side-effect free", async () => {
  const fetchMock = vi.fn().mockResolvedValue(
    new Response(JSON.stringify({ device_id: "pecem-02" }), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    }),
  );
  vi.stubGlobal("fetch", fetchMock);
  const candidate: Pairing = {
    deviceId: "pecem-02",
    viewSecret: TOKEN,
    pairedAt: "2026-09-30T18:00:00-03:00",
  };

  await expect(validatePairingCandidate(candidate)).resolves.toEqual({
    deviceId: "pecem-02",
  });

  expect(fetchMock).toHaveBeenCalledWith(
    "/api/v1/mobile/pairing/validate",
    expect.objectContaining({
      method: "POST",
      credentials: "same-origin",
      headers: expect.objectContaining({
        Authorization: `Bearer ${TOKEN}`,
      }),
      body: JSON.stringify({ device_id: "pecem-02" }),
    }),
  );
  expect(localStorage.length).toBe(0);
});

test("switch sends draft and returns B without persisting it", async () => {
  const fetchMock = vi.fn().mockResolvedValue(
    new Response(
      JSON.stringify(
        sessionBody({
          device_id: "pecem-02",
          platform: "android",
          display_code: "8P2R6X",
        }),
      ),
      {
        status: 200,
        headers: { "Content-Type": "application/json" },
      },
    ),
  );
  vi.stubGlobal("fetch", fetchMock);

  const candidate: Pairing = {
    deviceId: "pecem-02",
    viewSecret: TOKEN,
    pairedAt: "2026-09-30T18:00:00-03:00",
  };
  const session = await switchMobileSession(candidate, {
    installationId: INSTALLATION_ID,
    platform: "android",
    switchId: SWITCH_ID,
  });

  expect(session).toEqual({
    deviceId: "pecem-02",
    installationId: INSTALLATION_ID,
    displayCode: "8P2R6X",
    platform: "android",
  });
  expect(fetchMock).toHaveBeenCalledWith(
    "/api/v1/mobile/session/switch",
    expect.objectContaining({
      method: "POST",
      credentials: "same-origin",
      headers: expect.objectContaining({
        Authorization: `Bearer ${TOKEN}`,
      }),
      body: JSON.stringify({
        device_id: "pecem-02",
        installation_id: INSTALLATION_ID,
        platform: "android",
        switch_id: SWITCH_ID,
      }),
    }),
  );
  expect(localStorage.length).toBe(0);
});

test.each([
  ["switch", () => switchMobileSession(pairing, {
    installationId: INSTALLATION_ID,
    platform: "ios",
    switchId: SWITCH_ID,
  })],
  ["heartbeat", () => touchMobileSession("ios")],
])("%s maps 401 to AccessRevokedError", async (_label, action) => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue(new Response("", { status: 401 })),
  );

  await expect(action()).rejects.toBeInstanceOf(AccessRevokedError);
});

test("switch maps network and 5xx failures to TemporaryApiError", async () => {
  const fetchMock = vi.fn()
    .mockRejectedValueOnce(new TypeError("offline"))
    .mockResolvedValueOnce(new Response("", { status: 503 }));
  vi.stubGlobal("fetch", fetchMock);

  const draft = {
    installationId: INSTALLATION_ID,
    platform: "ios" as const,
    switchId: SWITCH_ID,
  };

  await expect(
    switchMobileSession(pairing, draft),
  ).rejects.toBeInstanceOf(TemporaryApiError);
  await expect(
    switchMobileSession(pairing, draft),
  ).rejects.toBeInstanceOf(TemporaryApiError);
});

test("heartbeat uses current cookie and never mutates local pairing state", async () => {
  localStorage.setItem("sentinel", "keep");
  const fetchMock = vi.fn().mockResolvedValue(
    new Response(null, { status: 204 }),
  );
  vi.stubGlobal("fetch", fetchMock);

  await touchMobileSession("android");

  expect(fetchMock).toHaveBeenCalledWith(
    "/api/v1/mobile/session/heartbeat",
    expect.objectContaining({
      method: "POST",
      credentials: "same-origin",
      body: JSON.stringify({ platform: "android" }),
    }),
  );
  expect(localStorage.getItem("sentinel")).toBe("keep");
  expect(localStorage.length).toBe(1);
});

test("clear session only clears remote cookie best effort", async () => {
  localStorage.setItem(INSTALLATION_ID_STORAGE_KEY, INSTALLATION_ID);
  const fetchMock = vi.fn().mockRejectedValue(new TypeError("offline"));
  vi.stubGlobal("fetch", fetchMock);

  await expect(clearMobileSession()).resolves.toBeUndefined();

  expect(loadInstallationId()).toBe(INSTALLATION_ID);
});
