import type { PushPreferences } from "../../api/pushClient";

export const PUSH_PREFERENCE_STORAGE_KEY =
  "alertam.mobile.push.preferences.v1";

export type PushPreferenceSnapshot = {
  optedIn: boolean;
  preferences: PushPreferences;
};

function parsePushPreferences(value: unknown): PushPreferences | null {
  if (typeof value !== "object" || value === null) {
    return null;
  }
  const candidate = value as Record<string, unknown>;
  if (
    typeof candidate.confirmed !== "boolean" ||
    typeof candidate.updated !== "boolean" ||
    typeof candidate.completed !== "boolean" ||
    typeof candidate.cancelled !== "boolean" ||
    !(
      candidate.anchored === undefined ||
      typeof candidate.anchored === "boolean"
    )
  ) {
    return null;
  }
  return {
    confirmed: candidate.confirmed,
    updated: candidate.updated,
    completed: candidate.completed,
    cancelled: candidate.cancelled,
    anchored:
      candidate.anchored === undefined ? true : candidate.anchored,
  };
}

function parsePushPreferenceSnapshot(
  value: unknown,
): PushPreferenceSnapshot | null {
  if (typeof value !== "object" || value === null) {
    return null;
  }
  const candidate = value as Record<string, unknown>;
  if (typeof candidate.optedIn !== "boolean") {
    return null;
  }
  const preferences = parsePushPreferences(candidate.preferences);
  if (preferences === null) {
    return null;
  }
  return {
    optedIn: candidate.optedIn,
    preferences,
  };
}

export function loadPushPreferenceSnapshot():
  PushPreferenceSnapshot | null {
  const raw = localStorage.getItem(PUSH_PREFERENCE_STORAGE_KEY);
  if (raw === null) {
    return null;
  }

  try {
    const parsed = parsePushPreferenceSnapshot(JSON.parse(raw));
    if (parsed !== null) {
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
  const parsed = parsePushPreferenceSnapshot(snapshot);
  if (parsed === null || parsed.preferences.anchored !== snapshot.preferences.anchored) {
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
