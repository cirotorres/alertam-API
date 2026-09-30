import {
  AccessRevokedError,
  TemporaryApiError,
} from "../../api/snapshotClient";
import {
  createFreshInstallationId,
  storeInstallationId,
} from "../push/installationId";
import {
  detectDevicePlatform,
  type DevicePlatform,
} from "./devicePlatform";
import {
  storeInstallationMetadata,
  type InstallationMetadata,
} from "./installationMetadata";
import type { Pairing } from "./pairing";

export type MobileSessionInfo = InstallationMetadata & {
  deviceId: string;
};

export type MobileSessionDraft = {
  installationId: string;
  platform: DevicePlatform;
  switchId: string;
};

type MobileSessionResponse = {
  device_id: string;
  installation_id: string;
  display_code: string;
  platform: DevicePlatform;
};

type PairingValidationResponse = {
  device_id: string;
};

function isDevicePlatform(value: unknown): value is DevicePlatform {
  return value === "ios" || value === "android" || value === "other";
}

function isMobileSessionResponse(
  value: unknown,
): value is MobileSessionResponse {
  if (typeof value !== "object" || value === null) {
    return false;
  }
  const candidate = value as Record<string, unknown>;
  return (
    typeof candidate.device_id === "string" &&
    candidate.device_id.trim().length > 0 &&
    typeof candidate.installation_id === "string" &&
    candidate.installation_id.trim().length > 0 &&
    typeof candidate.display_code === "string" &&
    /^[A-HJ-NP-Z2-9]{6}$/.test(candidate.display_code) &&
    isDevicePlatform(candidate.platform)
  );
}

function isPairingValidationResponse(
  value: unknown,
): value is PairingValidationResponse {
  return (
    typeof value === "object" &&
    value !== null &&
    typeof (value as Record<string, unknown>).device_id === "string" &&
    String((value as Record<string, unknown>).device_id).trim().length > 0
  );
}

function toSessionInfo(body: MobileSessionResponse): MobileSessionInfo {
  return {
    deviceId: body.device_id,
    installationId: body.installation_id,
    displayCode: body.display_code,
    platform: body.platform,
  };
}

function persistSessionIdentity(session: MobileSessionInfo): void {
  storeInstallationId(session.installationId);
  storeInstallationMetadata({
    installationId: session.installationId,
    displayCode: session.displayCode,
    platform: session.platform,
  });
}

async function parseSessionResponse(
  response: Response,
  options: {
    expectedDeviceId: string;
    expectedInstallationId?: string;
  },
): Promise<MobileSessionInfo> {
  const { expectedDeviceId, expectedInstallationId } = options;
  if (response.status === 401) {
    throw new AccessRevokedError();
  }
  if (!response.ok) {
    throw new TemporaryApiError();
  }

  let body: unknown;
  try {
    body = await response.json();
  } catch {
    throw new TemporaryApiError();
  }

  if (
    !isMobileSessionResponse(body) ||
    body.device_id !== expectedDeviceId ||
    (
      expectedInstallationId !== undefined &&
      body.installation_id !== expectedInstallationId
    )
  ) {
    throw new TemporaryApiError();
  }

  return toSessionInfo(body);
}

export async function createMobileSession(
  pairing: Pairing,
  options: {
    installationId?: string;
    platform?: DevicePlatform;
  } = {},
): Promise<MobileSessionInfo> {
  if (!pairing.viewSecret) {
    throw new AccessRevokedError();
  }

  const installationId =
    options.installationId ?? createFreshInstallationId();
  const platform = options.platform ?? detectDevicePlatform();

  let response: Response;
  try {
    response = await fetch("/api/v1/mobile/session", {
      method: "POST",
      cache: "no-store",
      credentials: "same-origin",
      headers: {
        Authorization: `Bearer ${pairing.viewSecret}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        device_id: pairing.deviceId,
        installation_id: installationId,
        platform,
      }),
    });
  } catch {
    throw new TemporaryApiError();
  }

  const session = await parseSessionResponse(response, {
    expectedDeviceId: pairing.deviceId,
    expectedInstallationId: installationId,
  });

  persistSessionIdentity(session);
  return session;
}

export async function recoverMobileSession(): Promise<{
  pairing: Pairing;
  session: MobileSessionInfo;
} | null> {
  let response: Response;
  try {
    response = await fetch("/api/v1/mobile/session", {
      method: "GET",
      cache: "no-store",
      credentials: "same-origin",
    });
  } catch {
    return null;
  }

  if (response.status === 401 || response.status === 404) {
    return null;
  }
  if (!response.ok) {
    return null;
  }

  let body: unknown;
  try {
    body = await response.json();
  } catch {
    return null;
  }
  if (!isMobileSessionResponse(body)) {
    return null;
  }

  const session = toSessionInfo(body);
  persistSessionIdentity(session);

  return {
    pairing: {
      deviceId: session.deviceId,
      viewSecret: null,
      pairedAt: new Date().toISOString(),
    },
    session,
  };
}

export async function validatePairingCandidate(
  pairing: Pairing,
): Promise<{ deviceId: string }> {
  if (!pairing.viewSecret) {
    throw new AccessRevokedError();
  }

  let response: Response;
  try {
    response = await fetch("/api/v1/mobile/pairing/validate", {
      method: "POST",
      cache: "no-store",
      credentials: "same-origin",
      headers: {
        Authorization: `Bearer ${pairing.viewSecret}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ device_id: pairing.deviceId }),
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

  let body: unknown;
  try {
    body = await response.json();
  } catch {
    throw new TemporaryApiError();
  }

  if (
    !isPairingValidationResponse(body) ||
    body.device_id !== pairing.deviceId
  ) {
    throw new TemporaryApiError();
  }

  return { deviceId: body.device_id };
}

export async function switchMobileSession(
  candidate: Pairing,
  draft: MobileSessionDraft,
): Promise<MobileSessionInfo> {
  if (!candidate.viewSecret) {
    throw new AccessRevokedError();
  }

  let response: Response;
  try {
    response = await fetch("/api/v1/mobile/session/switch", {
      method: "POST",
      cache: "no-store",
      credentials: "same-origin",
      headers: {
        Authorization: `Bearer ${candidate.viewSecret}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        device_id: candidate.deviceId,
        installation_id: draft.installationId,
        platform: draft.platform,
        switch_id: draft.switchId,
      }),
    });
  } catch {
    throw new TemporaryApiError();
  }

  return parseSessionResponse(response, {
    expectedDeviceId: candidate.deviceId,
    expectedInstallationId: draft.installationId,
  });
}

export async function touchMobileSession(
  platform: DevicePlatform,
): Promise<void> {
  let response: Response;
  try {
    response = await fetch("/api/v1/mobile/session/heartbeat", {
      method: "POST",
      cache: "no-store",
      credentials: "same-origin",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ platform }),
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
}

export async function clearMobileSession(): Promise<void> {
  try {
    await fetch("/api/v1/mobile/session", {
      method: "DELETE",
      cache: "no-store",
      credentials: "same-origin",
    });
  } catch {
    // Best effort: local state is owned and cleared by PairingGate.
  }
}
