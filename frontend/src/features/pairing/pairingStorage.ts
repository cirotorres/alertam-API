import {
  isValidViewSecret,
  type Pairing,
} from "./pairing";

export const PAIRING_STORAGE_KEY = "alertam.mobile.pairing.v1";

function isPairing(value: unknown): value is Pairing {
  if (typeof value !== "object" || value === null) {
    return false;
  }

  const candidate = value as Record<string, unknown>;
  return (
    typeof candidate.deviceId === "string" &&
    candidate.deviceId.trim().length > 0 &&
    isValidViewSecret(candidate.viewSecret) &&
    typeof candidate.pairedAt === "string" &&
    candidate.pairedAt.length > 0
  );
}

export function loadPairing(): Pairing | null {
  const raw = localStorage.getItem(PAIRING_STORAGE_KEY);
  if (raw === null) {
    return null;
  }

  try {
    const parsed: unknown = JSON.parse(raw);
    if (!isPairing(parsed)) {
      localStorage.removeItem(PAIRING_STORAGE_KEY);
      return null;
    }

    return {
      deviceId: parsed.deviceId,
      viewSecret: parsed.viewSecret,
      pairedAt: parsed.pairedAt,
    };
  } catch {
    localStorage.removeItem(PAIRING_STORAGE_KEY);
    return null;
  }
}

export function savePairing(pairing: Pairing): void {
  if (!isPairing(pairing)) {
    throw new Error("Pareamento inválido.");
  }
  localStorage.setItem(PAIRING_STORAGE_KEY, JSON.stringify(pairing));
}

export function clearPairing(): void {
  localStorage.removeItem(PAIRING_STORAGE_KEY);
}
