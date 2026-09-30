import type { PushPreferences } from "../../api/pushClient";

export const PUSH_PREFERENCE_STORAGE_KEY =
  "alertam.mobile.push.preferences.v1";

export type PushPreferenceSnapshot = {
  optedIn: boolean;
  preferences: PushPreferences;
};

function isPushPreferences(value: unknown): value is PushPreferences {
  if (typeof value !== "object" || value === null) {
    return false;
  }
  const candidate = value as Record<string, unknown>;
  return (
    typeof candidate.confirmed === "boolean" &&
    typeof candidate.updated === "boolean" &&
    typeof candidate.completed === "boolean" &&
    typeof candidate.cancelled === "boolean"
  );
}

function isPushPreferenceSnapshot(
  value: unknown,
): value is PushPreferenceSnapshot {
  if (typeof value !== "object" || value === null) {
    return false;
  }
  const candidate = value as Record<string, unknown>;
  return (
    typeof candidate.optedIn === "boolean" &&
    isPushPreferences(candidate.preferences)
  );
}

export function loadPushPreferenceSnapshot():
  PushPreferenceSnapshot | null {
  const raw = localStorage.getItem(PUSH_PREFERENCE_STORAGE_KEY);
  if (raw === null) {
    return null;
  }

  try {
    const parsed: unknown = JSON.parse(raw);
    if (isPushPreferenceSnapshot(parsed)) {
      return parsed;
    }
  } catch {
    // Invalid state is removed below.
  }

  localStorage.removeItem(PUSH_PREFERENCE_STORAGE_KEY);
  return null;
}

export function storePushPreferenceSnapshot(
  snapshot: PushPreferenceSnapshot,
): void {
  if (!isPushPreferenceSnapshot(snapshot)) {
    throw new TypeError("Invalid push preference snapshot.");
  }
  localStorage.setItem(
    PUSH_PREFERENCE_STORAGE_KEY,
    JSON.stringify(snapshot),
  );
}

export function clearPushPreferenceSnapshot(): void {
  localStorage.removeItem(PUSH_PREFERENCE_STORAGE_KEY);
}
