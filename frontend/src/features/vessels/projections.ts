import type {
  ManeuverV1,
  MobileSnapshotV1,
  VesselV1,
} from "../../api/contract";

const MAP_PRIORITY: Partial<Record<VesselV1["status"], number>> = {
  ATRACADO: 1,
  ATRACANDO: 2,
  DESATRACANDO: 3,
};

function firstByName(vessels: VesselV1[]): VesselV1[] {
  const seen = new Set<string>();
  const result: VesselV1[] = [];
  for (const vessel of vessels) {
    if (seen.has(vessel.name)) continue;
    seen.add(vessel.name);
    result.push(vessel);
  }
  return result;
}
function shortDateSortValue(value: string | null): number {
  if (!value) return Number.POSITIVE_INFINITY;
  const match = value.trim().match(/^(\d{2})\/(\d{2}) (\d{2}):(\d{2})$/);
  if (!match) return Number.POSITIVE_INFINITY;
  const [, day, month, hour, minute] = match;
  return (
    Number(month) * 1_000_000 +
    Number(day) * 10_000 +
    Number(hour) * 100 +
    Number(minute)
  );
}

export function confirmedManeuvers(snapshot: MobileSnapshotV1): ManeuverV1[] {
  return [...snapshot.recent_maneuvers.active];
}

export function arrivalForecast(snapshot: MobileSnapshotV1): VesselV1[] {
  const vessels = firstByName(
    snapshot.vessels.filter(
      (v) => (v.section === "FUNDEADO" || v.section === "PREVISTO") && Boolean(v.etb_ets),
    ),
  );
  return vessels.sort((a, b) => shortDateSortValue(a.etb_ets) - shortDateSortValue(b.etb_ets));
}
export function departureForecast(snapshot: MobileSnapshotV1): VesselV1[] {
  return firstByName(
    snapshot.vessels.filter(
      (v) => v.section === "ATRACADO" && Boolean(v.etb_ets),
    ),
  );
}

export function anchoredVessels(snapshot: MobileSnapshotV1): VesselV1[] {
  return firstByName(snapshot.vessels.filter((v) => v.section === "FUNDEADO"));
}

export function vesselByBerth(
  snapshot: MobileSnapshotV1,
  berth: number,
): VesselV1 | null {
  let selected: VesselV1 | null = null;
  for (const vessel of snapshot.vessels) {
    if (vessel.berth !== berth) continue;
    const priority = MAP_PRIORITY[vessel.status];
    if (priority === undefined) continue;
    const selectedPriority = selected ? MAP_PRIORITY[selected.status] ?? 0 : 0;
    if (!selected || priority > selectedPriority) selected = vessel;
  }
  return selected;
}
function newestFirst(a: ManeuverV1, b: ManeuverV1): number {
  const aTime = Date.parse(a.completed_at ?? a.detected_at);
  const bTime = Date.parse(b.completed_at ?? b.detected_at);
  return bTime - aTime;
}

export function recentAlerts(
  snapshot: MobileSnapshotV1,
  limit = 10,
): ManeuverV1[] {
  const active = [...snapshot.recent_maneuvers.active].sort(newestFirst);
  const completed = [...snapshot.recent_maneuvers.completed].sort(newestFirst);
  return [...active, ...completed].slice(0, Math.max(0, limit));
}

export function maneuverHistory(snapshot: MobileSnapshotV1): ManeuverV1[] {
  return [
    ...snapshot.recent_maneuvers.active,
    ...snapshot.recent_maneuvers.completed,
  ].sort(newestFirst);
}
