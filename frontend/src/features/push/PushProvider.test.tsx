import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, expect, test, vi } from "vitest";

import { AccessRevokedError, TemporaryApiError } from "../../api/snapshotClient";

const api = vi.hoisted(() => ({
  getPushInstallation: vi.fn(),
  getVapidPublicKey: vi.fn(),
  registerPushInstallation: vi.fn(),
  updatePushPreferences: vi.fn(),
  deletePushInstallation: vi.fn(),
}));

vi.mock("../../api/pushClient", () => ({
  getPushInstallation: api.getPushInstallation,
  getVapidPublicKey: api.getVapidPublicKey,
  registerPushInstallation: api.registerPushInstallation,
  updatePushPreferences: api.updatePushPreferences,
  deletePushInstallation: api.deletePushInstallation,
}));

import {
  PushProvider,
  StaticPushProvider,
  usePush,
  type PushState,
} from "./PushProvider";


const INSTALLATION_ID = "11111111-2222-4333-8444-555555555555";
const ACTIVE_INSTALLATION = {
  installationId: INSTALLATION_ID,
  active: true,
  preferences: {
    confirmed: true,
    updated: true,
    completed: true,
    cancelled: true,
  },
  pushEnabledAt: "2026-09-27T18:00:00Z",
  lastSeenAt: "2026-09-27T18:00:00Z",
  lastForegroundAt: null,
};

let originalServiceWorker: PropertyDescriptor | undefined;

beforeEach(() => {
  localStorage.clear();
  vi.clearAllMocks();
  originalServiceWorker = Object.getOwnPropertyDescriptor(
    navigator,
    "serviceWorker",
  );
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
  if (originalServiceWorker) {
    Object.defineProperty(
      navigator,
      "serviceWorker",
      originalServiceWorker,
    );
  } else {
    Reflect.deleteProperty(navigator, "serviceWorker");
  }
});


function installBrowser(
  options: {
    permission?: NotificationPermission;
    requestPermission?: () => Promise<NotificationPermission>;
    getSubscription?: () => Promise<PushSubscription | null>;
    subscribe?: (options: PushSubscriptionOptionsInit) => Promise<PushSubscription>;
    ready?: Promise<ServiceWorkerRegistration>;
    getRegistration?: () => Promise<ServiceWorkerRegistration | undefined>;
  } = {},
) {
  const subscription = {
    toJSON: () => ({
      endpoint: "https://push.example/a",
      keys: { p256dh: "p", auth: "a" },
    }),
    unsubscribe: vi.fn().mockResolvedValue(true),
  } as unknown as PushSubscription;

  const subscribe = vi.fn(
    options.subscribe ?? (async () => subscription),
  );
  const getSubscription = vi.fn(
    options.getSubscription ?? (async () => null),
  );
  const requestPermission = vi.fn(
    options.requestPermission ?? (async () => "granted"),
  );

  vi.stubGlobal("Notification", {
    permission: options.permission ?? "default",
    requestPermission,
  });
  vi.stubGlobal("PushManager", function PushManager() {});
  const registration = {
    pushManager: {
      getSubscription,
      subscribe,
    },
  } as unknown as ServiceWorkerRegistration;
  const getRegistration = vi.fn(
    options.getRegistration ?? (async () => registration),
  );
  Object.defineProperty(navigator, "serviceWorker", {
    configurable: true,
    value: {
      ready: options.ready ?? Promise.resolve(registration),
      getRegistration,
    },
  });

  return {
    subscription,
    subscribe,
    getSubscription,
    getRegistration,
    requestPermission,
  };
}


function Probe() {
  const push = usePush();
  return (
    <div>
      <span data-testid="support">{push.supported ? "yes" : "no"}</span>
      <span data-testid="permission">{push.permission}</span>
      <span data-testid="active">{push.active ? "yes" : "no"}</span>
      <span data-testid="confirmed">
        {push.preferences.confirmed ? "yes" : "no"}
      </span>
      <button type="button" onClick={() => void push.enablePush()}>
        enable
      </button>
      <button type="button" onClick={() => void push.disablePush()}>
        disable
      </button>
      <button
        type="button"
        onClick={() => void push.updatePreference("confirmed", false)}
      >
        preference
      </button>
    </div>
  );
}

function renderProvider(
  options: {
    sessionReady?: boolean;
    onAccessRevoked?: () => void;
  } = {},
) {
  return render(
    <PushProvider
      sessionReady={options.sessionReady ?? true}
      onAccessRevoked={options.onAccessRevoked}
    >
      <Probe />
    </PushProvider>,
  );
}


test("mount_never_requests_notification_permission", async () => {
  const browser = installBrowser();
  renderProvider();

  expect(await screen.findByTestId("active")).toHaveTextContent("no");
  expect(browser.requestPermission).not.toHaveBeenCalled();
  expect(browser.subscribe).not.toHaveBeenCalled();
  expect(api.getVapidPublicKey).not.toHaveBeenCalled();
});


test("enable_requests_permission_then_subscribes_with_vapid_key", async () => {
  const browser = installBrowser();
  api.getVapidPublicKey.mockResolvedValue({
    enabled: true,
    publicKey: "AQIDBA",
  });
  api.registerPushInstallation.mockResolvedValue(ACTIVE_INSTALLATION);

  renderProvider();
  fireEvent.click(screen.getByRole("button", { name: "enable" }));

  await waitFor(() => {
    expect(screen.getByTestId("active")).toHaveTextContent("yes");
  });

  expect(browser.requestPermission).toHaveBeenCalledTimes(1);
  expect(browser.subscribe).toHaveBeenCalledTimes(1);
  const subscribeOptions = browser.subscribe.mock.calls[0][0];
  expect(subscribeOptions.userVisibleOnly).toBe(true);
  expect(Array.from(subscribeOptions.applicationServerKey as Uint8Array))
    .toEqual([1, 2, 3, 4]);

  const generated = localStorage.getItem(
    "alertam.mobile.installation.v1",
  );
  expect(generated).toBeTruthy();
  expect(api.registerPushInstallation).toHaveBeenCalledWith(
    generated,
    browser.subscription,
  );
});


test("disable_is_best_effort_and_does_not_revoke_pairing", async () => {
  localStorage.setItem(
    "alertam.mobile.installation.v1",
    INSTALLATION_ID,
  );
  const unsubscribe = vi.fn().mockRejectedValue(new Error("browser"));
  const browser = installBrowser({
    permission: "granted",
    getSubscription: async () => ({
      toJSON: () => ({}),
      unsubscribe,
    } as unknown as PushSubscription),
  });
  api.getPushInstallation.mockResolvedValue(ACTIVE_INSTALLATION);
  api.deletePushInstallation.mockRejectedValue(
    new TemporaryApiError(),
  );
  const reset = vi.fn();

  renderProvider({ onAccessRevoked: reset });
  await waitFor(() => {
    expect(screen.getByTestId("active")).toHaveTextContent("yes");
  });

  fireEvent.click(screen.getByRole("button", { name: "disable" }));
  await waitFor(() => {
    expect(screen.getByTestId("active")).toHaveTextContent("no");
  });

  expect(api.deletePushInstallation).toHaveBeenCalledWith(
    INSTALLATION_ID,
  );
  expect(browser.getSubscription).toHaveBeenCalled();
  expect(unsubscribe).toHaveBeenCalled();
  expect(reset).not.toHaveBeenCalled();
});


test("session_gate_blocks_requests_and_ready_401_revokes_pairing", async () => {
  localStorage.setItem(
    "alertam.mobile.installation.v1",
    INSTALLATION_ID,
  );
  installBrowser({ permission: "granted" });
  const reset = vi.fn();

  const view = renderProvider({
    sessionReady: false,
    onAccessRevoked: reset,
  });
  expect(api.getPushInstallation).not.toHaveBeenCalled();

  api.getPushInstallation.mockRejectedValue(new AccessRevokedError());
  view.rerender(
    <PushProvider sessionReady onAccessRevoked={reset}>
      <Probe />
    </PushProvider>,
  );

  await waitFor(() => expect(reset).toHaveBeenCalledTimes(1));
});


test("static_provider_exposes_inert_state_without_real_push_calls", () => {
  const state: PushState = {
    supported: false,
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

  render(
    <StaticPushProvider state={state}>
      <Probe />
    </StaticPushProvider>,
  );

  expect(screen.getByTestId("support")).toHaveTextContent("no");
  expect(screen.getByTestId("active")).toHaveTextContent("no");
  expect(api.getPushInstallation).not.toHaveBeenCalled();
  expect(api.getVapidPublicKey).not.toHaveBeenCalled();
});


test("disable_does_not_wait_for_service_worker_ready_when_no_registration_exists", async () => {
  localStorage.setItem(
    "alertam.mobile.installation.v1",
    INSTALLATION_ID,
  );
  installBrowser({
    permission: "granted",
    ready: new Promise<ServiceWorkerRegistration>(() => undefined),
    getRegistration: async () => undefined,
  });
  api.getPushInstallation.mockResolvedValue(ACTIVE_INSTALLATION);
  api.deletePushInstallation.mockResolvedValue(undefined);

  renderProvider();
  await waitFor(() => {
    expect(screen.getByTestId("active")).toHaveTextContent("yes");
  });

  fireEvent.click(screen.getByRole("button", { name: "disable" }));

  await waitFor(() => {
    expect(screen.getByTestId("active")).toHaveTextContent("no");
  });
});
