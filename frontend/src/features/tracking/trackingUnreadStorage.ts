export type TrackingUnreadState = {
  cursor: number | null;
  unreadTrackedVesselIds: string[];
};

const STORAGE_PREFIX = "alertam.mobile.tracking.unread.v1:";

function storageKey(scope: string): string {
  return STORAGE_PREFIX + scope;
}

export function loadTrackingUnreadState(scope: string): TrackingUnreadState {
  try {
    const raw = localStorage.getItem(storageKey(scope));
    if (!raw) return { cursor: null, unreadTrackedVesselIds: [] };
    const parsed = JSON.parse(raw) as Record<string, unknown>;
    const cursor =
      parsed.cursor === null ||
      (typeof parsed.cursor === "number" &&
        Number.isInteger(parsed.cursor) &&
        parsed.cursor >= 0)
        ? (parsed.cursor as number | null)
        : null;
    const unreadTrackedVesselIds = Array.isArray(
      parsed.unreadTrackedVesselIds,
    )
      ? parsed.unreadTrackedVesselIds.filter(
          (value): value is string =>
            typeof value === "string" && value.length > 0,
        )
      : [];
    return {
      cursor,
      unreadTrackedVesselIds: [...new Set(unreadTrackedVesselIds)],
    };
  } catch {
    return { cursor: null, unreadTrackedVesselIds: [] };
  }
}

export function storeTrackingUnreadState(
  scope: string,
  state: TrackingUnreadState,
): void {
  try {
    localStorage.setItem(
      storageKey(scope),
      JSON.stringify({
        cursor: state.cursor,
        unreadTrackedVesselIds: [...new Set(state.unreadTrackedVesselIds)].sort(),
      }),
    );
  } catch {
    // UI-only persistence is best effort.
  }
}
