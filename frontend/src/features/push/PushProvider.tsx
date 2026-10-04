import {
  createContext,
  type ReactNode,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";

import {
  deletePushInstallation,
  getPushInstallation,
  getVapidPublicKey,
  registerPushInstallation,
  updatePushPreferences,
  type PushPreferenceKey,
  type PushPreferences,
} from "../../api/pushClient";
import { AccessRevokedError } from "../../api/snapshotClient";
import {
  getOrCreateInstallationId,
  loadInstallationId,
} from "./installationId";
import {
  loadPushPreferenceSnapshot,
  storePushPreferenceSnapshot,
} from "./pushPreferenceStorage";


const DEFAULT_PREFERENCES: PushPreferences = {
  confirmed: true,
  updated: true,
  completed: true,
  cancelled: true,
  anchored: true,
};

export type PushState = {
  supported: boolean;
  permission: NotificationPermission;
  active: boolean;
  preferences: PushPreferences;
  error: string | null;
  enablePush: () => Promise<void>;
  disablePush: () => Promise<void>;
  updatePreference: (
    key: PushPreferenceKey,
    enabled: boolean,
  ) => Promise<void>;
};

type PushProviderProps = {
  sessionReady: boolean;
  onAccessRevoked?: () => void;
  children: ReactNode;
};

const PushContext = createContext<PushState | null>(null);


function browserSupportsPush(): boolean {
  return (
    typeof window !== "undefined" &&
    "Notification" in window &&
    "PushManager" in window &&
    "serviceWorker" in navigator
  );
}

function browserPermission(): NotificationPermission {
  return browserSupportsPush() ? Notification.permission : "default";
}

function applicationServerKey(
  value: string,
): Uint8Array<ArrayBuffer> {
  const padding = "=".repeat((4 - (value.length % 4)) % 4);
  const base64 = (value + padding)
    .replace(/-/g, "+")
    .replace(/_/g, "/");
  const raw = window.atob(base64);
  const buffer = new ArrayBuffer(raw.length);
  const bytes = new Uint8Array(buffer);
  for (let index = 0; index < raw.length; index += 1) {
    bytes[index] = raw.charCodeAt(index);
  }
  return bytes;
}


export function PushProvider({
  sessionReady,
  onAccessRevoked,
  children,
}: PushProviderProps) {
  const supported = browserSupportsPush();
  const [permission, setPermission] = useState<NotificationPermission>(
    browserPermission,
  );
  const [active, setActive] = useState(false);
  const [preferences, setPreferences] =
    useState<PushPreferences>(DEFAULT_PREFERENCES);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!sessionReady || !supported) {
      return;
    }

    const installationId = loadInstallationId();
    if (!installationId) {
      setActive(false);
      return;
    }

    let cancelled = false;
    void (async () => {
      try {
        const installation = await getPushInstallation(installationId);
        if (cancelled) {
          return;
        }

        setError(null);
        if (installation) {
          setActive(installation.active);
          setPreferences(installation.preferences);
          storePushPreferenceSnapshot({
            optedIn: installation.active,
            preferences: installation.preferences,
          });
          return;
        }

        const saved = loadPushPreferenceSnapshot();
        if (
          !saved?.optedIn ||
          Notification.permission !== "granted"
        ) {
          setActive(false);
          return;
        }

        const registration =
          await navigator.serviceWorker.getRegistration();
        const subscription =
          await registration?.pushManager.getSubscription();
        if (cancelled) {
          return;
        }
        if (!subscription) {
          setActive(false);
          return;
        }

        let registeredOnServer = false;
        try {
          await registerPushInstallation(
            installationId,
            subscription,
          );
          registeredOnServer = true;
          const rebound = await updatePushPreferences(
            installationId,
            saved.preferences,
          );
          if (cancelled) {
            return;
          }
          setActive(rebound.active);
          setPreferences(rebound.preferences);
          setPermission("granted");
          storePushPreferenceSnapshot({
            optedIn: rebound.active,
            preferences: rebound.preferences,
          });
        } catch (cause) {
          if (cancelled) {
            return;
          }
          if (cause instanceof AccessRevokedError) {
            onAccessRevoked?.();
            return;
          }
          if (registeredOnServer) {
            try {
              await deletePushInstallation(installationId);
            } catch {
              // Best effort rollback for a partially restored Push binding.
            }
          }
          setActive(false);
          setError("Não foi possível reativar as notificações.");
        }
      } catch (cause) {
        if (cancelled) {
          return;
        }
        if (cause instanceof AccessRevokedError) {
          onAccessRevoked?.();
          return;
        }
        setError("Não foi possível consultar as notificações.");
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [onAccessRevoked, sessionReady, supported]);

  const enablePush = useCallback(async () => {
    if (!sessionReady || !supported) {
      setError("Notificações push não estão disponíveis.");
      return;
    }

    setError(null);
    try {
      let nextPermission = Notification.permission;
      if (nextPermission !== "granted") {
        nextPermission = await Notification.requestPermission();
        setPermission(nextPermission);
      }
      if (nextPermission !== "granted") {
        setError("Permissão de notificação não concedida.");
        return;
      }

      const vapid = await getVapidPublicKey();
      if (!vapid.enabled || !vapid.publicKey) {
        setError("Notificações push ainda não estão habilitadas.");
        return;
      }

      const registration = await navigator.serviceWorker.ready;
      let subscription = await registration.pushManager.getSubscription();
      if (!subscription) {
        subscription = await registration.pushManager.subscribe({
          userVisibleOnly: true,
          applicationServerKey: applicationServerKey(vapid.publicKey),
        });
      }

      const installationId = getOrCreateInstallationId();
      const installation = await registerPushInstallation(
        installationId,
        subscription,
      );
      setActive(installation.active);
      setPreferences(installation.preferences);
      setPermission(
        Notification.permission === "denied"
          ? "denied"
          : "granted",
      );
      storePushPreferenceSnapshot({
        optedIn: installation.active,
        preferences: installation.preferences,
      });
    } catch (cause) {
      if (cause instanceof AccessRevokedError) {
        onAccessRevoked?.();
        return;
      }
      setError("Não foi possível ativar as notificações.");
    }
  }, [onAccessRevoked, sessionReady, supported]);

  const disablePush = useCallback(async () => {
    const installationId = loadInstallationId();
    setError(null);

    if (sessionReady && installationId) {
      try {
        await deletePushInstallation(installationId);
      } catch (cause) {
        if (cause instanceof AccessRevokedError) {
          onAccessRevoked?.();
        }
      }
    }

    if (supported) {
      try {
        const registration = await navigator.serviceWorker.getRegistration();
        const subscription = await registration?.pushManager.getSubscription();
        if (subscription) {
          await subscription.unsubscribe();
        }
      } catch {
        // Browser unsubscribe is best-effort; local state still becomes inactive.
      }
    }

    setActive(false);
    storePushPreferenceSnapshot({
      optedIn: false,
      preferences,
    });
  }, [
    onAccessRevoked,
    preferences,
    sessionReady,
    supported,
  ]);

  const updatePreference = useCallback(
    async (key: PushPreferenceKey, enabled: boolean) => {
      if (!sessionReady) {
        return;
      }
      const installationId = loadInstallationId();
      if (!installationId || !active) {
        return;
      }

      setError(null);
      try {
        const installation = await updatePushPreferences(
          installationId,
          { [key]: enabled },
        );
        setPreferences(installation.preferences);
        storePushPreferenceSnapshot({
          optedIn: true,
          preferences: installation.preferences,
        });
      } catch (cause) {
        if (cause instanceof AccessRevokedError) {
          onAccessRevoked?.();
          return;
        }
        setError("Não foi possível atualizar a preferência.");
      }
    },
    [active, onAccessRevoked, sessionReady],
  );

  const state = useMemo<PushState>(
    () => ({
      supported,
      permission,
      active,
      preferences,
      error,
      enablePush,
      disablePush,
      updatePreference,
    }),
    [
      active,
      disablePush,
      enablePush,
      error,
      permission,
      preferences,
      supported,
      updatePreference,
    ],
  );

  return (
    <PushContext.Provider value={state}>
      {children}
    </PushContext.Provider>
  );
}


export function usePush(): PushState {
  const state = useContext(PushContext);
  if (state === null) {
    throw new Error("PushProvider ausente.");
  }
  return state;
}


type StaticPushProviderProps = {
  state: PushState;
  children: ReactNode;
};

export function StaticPushProvider({
  state,
  children,
}: StaticPushProviderProps) {
  return (
    <PushContext.Provider value={state}>
      {children}
    </PushContext.Provider>
  );
}
