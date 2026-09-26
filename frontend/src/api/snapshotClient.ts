import type { Pairing } from "../features/pairing/pairing";
import {
  parseSnapshotReadResponse,
  type SnapshotReadResponse,
} from "./contract";

export class AccessRevokedError extends Error {
  constructor() {
    super("Acesso expirado ou revogado.");
    this.name = "AccessRevokedError";
  }
}

export class SnapshotUnavailableError extends Error {
  constructor() {
    super("Snapshot ainda não disponível.");
    this.name = "SnapshotUnavailableError";
  }
}

export class TemporaryApiError extends Error {
  constructor() {
    super("Não foi possível consultar o AlertaM agora.");
    this.name = "TemporaryApiError";
  }
}

export class UnsupportedSnapshotError extends Error {
  constructor() {
    super("Esta versão do AlertaM Mobile precisa ser atualizada.");
    this.name = "UnsupportedSnapshotError";
  }
}

export async function getSnapshot(
  pairing: Pairing,
  signal?: AbortSignal,
): Promise<SnapshotReadResponse> {
  let response: Response;

  try {
    response = await fetch(
      `/api/v1/devices/${encodeURIComponent(pairing.deviceId)}/snapshot`,
      {
        cache: "no-store",
        credentials: "same-origin",
        headers: pairing.viewSecret
          ? {
              Authorization: `Bearer ${pairing.viewSecret}`,
            }
          : undefined,
        signal,
      },
    );
  } catch (error) {
    if (
      (error instanceof DOMException && error.name === "AbortError") ||
      (error instanceof Error && error.name === "AbortError")
    ) {
      throw error;
    }
    throw new TemporaryApiError();
  }

  if (response.status === 401) {
    throw new AccessRevokedError();
  }
  if (response.status === 404) {
    throw new SnapshotUnavailableError();
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

  try {
    return parseSnapshotReadResponse(body);
  } catch {
    throw new UnsupportedSnapshotError();
  }
}
