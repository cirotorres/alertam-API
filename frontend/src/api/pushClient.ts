import {
  AccessRevokedError,
  TemporaryApiError,
} from "./snapshotClient";


export type PushPreferences = {
  confirmed: boolean;
  updated: boolean;
  completed: boolean;
  cancelled: boolean;
};

export type PushPreferenceKey = keyof PushPreferences;

export type PushInstallationState = {
  installationId: string;
  active: boolean;
  preferences: PushPreferences;
  pushEnabledAt: string;
  lastSeenAt: string;
  lastForegroundAt: string | null;
};

export type VapidConfig = {
  enabled: boolean;
  publicKey: string | null;
};

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function parsePreferences(value: unknown): PushPreferences {
  if (!isRecord(value)) {
    throw new TemporaryApiError();
  }

  const keys: PushPreferenceKey[] = [
    "confirmed",
    "updated",
    "completed",
    "cancelled",
  ];
  const parsed = {} as PushPreferences;
  for (const key of keys) {
    if (typeof value[key] !== "boolean") {
      throw new TemporaryApiError();
    }
    parsed[key] = value[key];
  }
  return parsed;
}


function parseInstallation(value: unknown): PushInstallationState {
  if (
    !isRecord(value) ||
    typeof value.installation_id !== "string" ||
    typeof value.active !== "boolean" ||
    typeof value.push_enabled_at !== "string" ||
    typeof value.last_seen_at !== "string" ||
    !(
      value.last_foreground_at === null ||
      typeof value.last_foreground_at === "string"
    )
  ) {
    throw new TemporaryApiError();
  }

  return {
    installationId: value.installation_id,
    active: value.active,
    preferences: parsePreferences(value.preferences),
    pushEnabledAt: value.push_enabled_at,
    lastSeenAt: value.last_seen_at,
    lastForegroundAt: value.last_foreground_at,
  };
}

async function requestJson(
  input: string,
  init: RequestInit = {},
): Promise<unknown> {
  let response: Response;
  try {
    response = await fetch(input, {
      cache: "no-store",
      credentials: "same-origin",
      ...init,
    });
  } catch {
    throw new TemporaryApiError();
  }

  if (response.status === 401) {
    throw new AccessRevokedError();
  }
  if (!response.ok) {
    throw new TemporaryApiError();
  }

  try {
    return await response.json();
  } catch {
    throw new TemporaryApiError();
  }
}

export async function getVapidPublicKey(): Promise<VapidConfig> {
  const body = await requestJson(
    "/api/v1/mobile/push/vapid-public-key",
  );
  if (
    !isRecord(body) ||
    typeof body.enabled !== "boolean" ||
    !(
      body.public_key === null ||
      typeof body.public_key === "string"
    )
  ) {
    throw new TemporaryApiError();
  }

  return {
    enabled: body.enabled,
    publicKey: body.public_key,
  };
}


export async function getPushInstallation(
  installationId: string,
): Promise<PushInstallationState | null> {
  let response: Response;
  try {
    response = await fetch(
      `/api/v1/mobile/push/installations/${encodeURIComponent(installationId)}`,
      {
        cache: "no-store",
        credentials: "same-origin",
      },
    );
  } catch {
    throw new TemporaryApiError();
  }

  if (response.status === 401) {
    throw new AccessRevokedError();
  }
  if (response.status === 404) {
    return null;
  }
  if (!response.ok) {
    throw new TemporaryApiError();
  }

  try {
    return parseInstallation(await response.json());
  } catch (error) {
    if (error instanceof TemporaryApiError) {
      throw error;
    }
    throw new TemporaryApiError();
  }
}

export async function registerPushInstallation(
  installationId: string,
  subscription: PushSubscription,
): Promise<PushInstallationState> {
  const serialized = subscription.toJSON();
  const endpoint = serialized.endpoint;
  const keys = serialized.keys;
  if (
    typeof endpoint !== "string" ||
    !keys ||
    typeof keys.p256dh !== "string" ||
    typeof keys.auth !== "string"
  ) {
    throw new TemporaryApiError();
  }

  const body = await requestJson(
    `/api/v1/mobile/push/installations/${encodeURIComponent(installationId)}`,
    {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        endpoint,
        keys: { p256dh: keys.p256dh, auth: keys.auth },
      }),
    },
  );
  return parseInstallation(body);
}

export async function updatePushPreferences(
  installationId: string,
  changes: Partial<PushPreferences>,
): Promise<PushInstallationState> {
  const body = await requestJson(
    `/api/v1/mobile/push/installations/${encodeURIComponent(installationId)}/preferences`,
    {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(changes),
    },
  );
  return parseInstallation(body);
}


export async function deletePushInstallation(
  installationId: string,
): Promise<void> {
  let response: Response;
  try {
    response = await fetch(
      `/api/v1/mobile/push/installations/${encodeURIComponent(installationId)}`,
      {
        method: "DELETE",
        cache: "no-store",
        credentials: "same-origin",
      },
    );
  } catch {
    throw new TemporaryApiError();
  }

  if (response.status === 401) {
    throw new AccessRevokedError();
  }
  if (!response.ok && response.status !== 404) {
    throw new TemporaryApiError();
  }
}


export async function touchPushForeground(
  installationId: string,
): Promise<PushInstallationState> {
  const body = await requestJson(
    "/api/v1/mobile/push/installations/" +
      encodeURIComponent(installationId) +
      "/foreground",
    { method: "POST" },
  );
  return parseInstallation(body);
}
