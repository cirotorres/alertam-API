import { afterEach, expect, test, vi } from "vitest";

import { AccessRevokedError } from "./snapshotClient";
import {
  deletePushInstallation,
  getPushInstallation,
  getVapidPublicKey,
  registerPushInstallation,
  touchPushForeground,
  updatePushPreferences,
} from "./pushClient";


afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});


function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}


const INSTALLATION = {
  installation_id: "11111111-2222-4333-8444-555555555555",
  active: true,
  preferences: {
    confirmed: true,
    updated: true,
    completed: true,
    cancelled: true,
  },
  push_enabled_at: "2026-09-27T18:00:00Z",
  last_seen_at: "2026-09-27T18:00:00Z",
  last_foreground_at: null,
};


test("vapid_config_uses_mobile_cookie_session", async () => {
  const fetchMock = vi.fn().mockResolvedValue(
    jsonResponse({ enabled: true, public_key: "public-vapid" }),
  );
  vi.stubGlobal("fetch", fetchMock);

  await expect(getVapidPublicKey()).resolves.toEqual({
    enabled: true,
    publicKey: "public-vapid",
  });

  expect(fetchMock).toHaveBeenCalledWith(
    "/api/v1/mobile/push/vapid-public-key",
    expect.objectContaining({
      cache: "no-store",
      credentials: "same-origin",
    }),
  );
});


test("register_sends_only_subscription_endpoint_and_keys", async () => {
  const fetchMock = vi.fn().mockResolvedValue(jsonResponse(INSTALLATION));
  vi.stubGlobal("fetch", fetchMock);
  const subscription = {
    toJSON: () => ({
      endpoint: "https://push.example/private",
      expirationTime: null,
      keys: {
        p256dh: "browser-public",
        auth: "browser-auth",
      },
    }),
  } as unknown as PushSubscription;

  await registerPushInstallation(
    INSTALLATION.installation_id,
    subscription,
  );

  const [, init] = fetchMock.mock.calls[0] as [string, RequestInit];
  expect(init.method).toBe("PUT");
  expect(JSON.parse(String(init.body))).toEqual({
    endpoint: "https://push.example/private",
    keys: {
      p256dh: "browser-public",
      auth: "browser-auth",
    },
  });
});


test("installation_get_returns_null_on_404_and_401_is_access_revoked", async () => {
  const fetchMock = vi
    .fn()
    .mockResolvedValueOnce(new Response(null, { status: 404 }))
    .mockResolvedValueOnce(new Response(null, { status: 401 }));
  vi.stubGlobal("fetch", fetchMock);

  await expect(
    getPushInstallation(INSTALLATION.installation_id),
  ).resolves.toBeNull();
  await expect(
    getVapidPublicKey(),
  ).rejects.toBeInstanceOf(AccessRevokedError);
});


test("preference_patch_and_delete_are_scoped_to_current_installation", async () => {
  const fetchMock = vi
    .fn()
    .mockResolvedValueOnce(
      jsonResponse({
        ...INSTALLATION,
        preferences: {
          ...INSTALLATION.preferences,
          confirmed: false,
        },
      }),
    )
    .mockResolvedValueOnce(new Response(null, { status: 204 }));
  vi.stubGlobal("fetch", fetchMock);

  const updated = await updatePushPreferences(
    INSTALLATION.installation_id,
    { confirmed: false },
  );
  await deletePushInstallation(INSTALLATION.installation_id);

  expect(updated.preferences.confirmed).toBe(false);
  expect(fetchMock.mock.calls[0][0]).toContain(
    `${INSTALLATION.installation_id}/preferences`,
  );
  expect(fetchMock.mock.calls[1][0]).toBe(
    `/api/v1/mobile/push/installations/${INSTALLATION.installation_id}`,
  );
  expect((fetchMock.mock.calls[1][1] as RequestInit).method).toBe("DELETE");
});


test("foreground_heartbeat_posts_to_current_installation", async () => {
  const fetchMock = vi.fn().mockResolvedValue(
    jsonResponse({
      ...INSTALLATION,
      last_foreground_at: "2026-09-27T18:00:30Z",
    }),
  );
  vi.stubGlobal("fetch", fetchMock);

  const result = await touchPushForeground(
    INSTALLATION.installation_id,
  );

  expect(result.lastForegroundAt).toBe("2026-09-27T18:00:30Z");
  expect(fetchMock).toHaveBeenCalledWith(
    "/api/v1/mobile/push/installations/" +
      INSTALLATION.installation_id +
      "/foreground",
    expect.objectContaining({
      method: "POST",
      cache: "no-store",
      credentials: "same-origin",
    }),
  );
});
