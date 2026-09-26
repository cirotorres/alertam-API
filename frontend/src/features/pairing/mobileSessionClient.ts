import {
  AccessRevokedError,
  TemporaryApiError,
} from "../../api/snapshotClient";
import type { Pairing } from "./pairing";

type MobileSessionResponse = {
  device_id: string;
};

function isMobileSessionResponse(value: unknown): value is MobileSessionResponse {
  return (
    typeof value === "object" &&
    value !== null &&
    typeof (value as Record<string, unknown>).device_id === "string" &&
    String((value as Record<string, unknown>).device_id).trim().length > 0
  );
}

export async function createMobileSession(pairing: Pairing): Promise<void> {
  if (!pairing.viewSecret) {
    return;
  }

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
  }
}
