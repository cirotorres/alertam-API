import {
  AccessRevokedError,
  TemporaryApiError,
} from "../../api/snapshotClient";
import {
  clearInstallationId,
  getOrCreateInstallationId,
  storeInstallationId,
} from "../push/installationId";
import type { Pairing } from "./pairing";

type MobileSessionResponse = {
  device_id: string;
  installation_id: string;
};

function isMobileSessionResponse(value: unknown): value is MobileSessionResponse {
  return (
    typeof value === "object" &&
    value !== null &&
    typeof (value as Record<string, unknown>).device_id === "string" &&
    String((value as Record<string, unknown>).device_id).trim().length > 0 &&
    typeof (value as Record<string, unknown>).installation_id === "string" &&
    String((value as Record<string, unknown>).installation_id).trim().length > 0
  );
}

export async function createMobileSession(pairing: Pairing): Promise<void> {
  if (!pairing.viewSecret) {
    return;
  }
  const installationId = getOrCreateInstallationId();

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
      }),
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
    const body: unknown = await response.json();
    if (
      !isMobileSessionResponse(body) ||
      body.device_id !== pairing.deviceId ||
      body.installation_id !== installationId
    ) {
      throw new TemporaryApiError();
    }
  } catch (error) {
    if (error instanceof TemporaryApiError) throw error;
    throw new TemporaryApiError();
  }
}

export async function recoverMobileSession(): Promise<Pairing | null> {
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

  storeInstallationId(body.installation_id);
  return {
    deviceId: body.device_id,
    viewSecret: null,
    pairedAt: new Date().toISOString(),
  };
}

export async function clearMobileSession(): Promise<void> {
  try {
    await fetch("/api/v1/mobile/session", {
      method: "DELETE",
      cache: "no-store",
      credentials: "same-origin",
    });
  } catch {
    // Best effort: a sessão expirada/rotacionada já é inválida no servidor.
  } finally {
    clearInstallationId();
  }
}
