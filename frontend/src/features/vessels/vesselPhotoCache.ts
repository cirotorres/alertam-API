import type { VesselPhotoResponse } from "../../api/contract";
import { parseVesselPhotoResponse } from "../../api/contract";

const CACHE_PREFIX = "alertam-vessel-photo-v1:";
const TTL_MS = 30 * 24 * 60 * 60 * 1_000;
const FAILURE_PREFIX = "alertam-vessel-photo-failure-v1:";
const FAILURE_TTL_MS = 60 * 60 * 1_000;

type CachedPhoto = {
  expiresAt: number;
  value: VesselPhotoResponse;
};

function key(imo: string): string {
  return `${CACHE_PREFIX}${imo}`;
}

export function readVesselPhotoCache(
  imo: string,
  now = Date.now(),
): VesselPhotoResponse | null {
  try {
    const raw = localStorage.getItem(key(imo));
    if (!raw) return null;
    const cached = JSON.parse(raw) as CachedPhoto;
    if (!Number.isFinite(cached.expiresAt) || cached.expiresAt <= now) {
      localStorage.removeItem(key(imo));
      return null;
    }
    return parseVesselPhotoResponse(cached.value);
  } catch {
    localStorage.removeItem(key(imo));
    return null;
  }
}

export function writeVesselPhotoCache(
  value: VesselPhotoResponse,
  now = Date.now(),
): void {
  const cached: CachedPhoto = {
    expiresAt: now + TTL_MS,
    value,
  };
  try {
    localStorage.setItem(key(value.imo), JSON.stringify(cached));
  } catch {
    // Cache é otimização; falha de storage não deve bloquear a ficha.
  }
}

export function hasRecentVesselPhotoFailure(
  imo: string,
  now = Date.now(),
): boolean {
  try {
    const raw = localStorage.getItem(`${FAILURE_PREFIX}${imo}`);
    if (!raw) return false;
    const expiresAt = Number(raw);
    if (!Number.isFinite(expiresAt) || expiresAt <= now) {
      localStorage.removeItem(`${FAILURE_PREFIX}${imo}`);
      return false;
    }
    return true;
  } catch {
    return false;
  }
}

export function rememberVesselPhotoFailure(
  imo: string,
  now = Date.now(),
): void {
  try {
    localStorage.setItem(
      `${FAILURE_PREFIX}${imo}`,
      String(now + FAILURE_TTL_MS),
    );
  } catch {
    // Cache é otimização.
  }
}

export function clearVesselPhotoFailure(imo: string): void {
  try {
    localStorage.removeItem(`${FAILURE_PREFIX}${imo}`);
  } catch {
    // Cache é otimização.
  }
}
