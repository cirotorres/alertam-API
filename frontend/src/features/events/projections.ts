import type { ManeuverEventFeedItem } from "../../api/contract";


export type FormattedManeuverEvent = {
  title: string;
  detail: string;
};

export type ManeuverCycle = {
  maneuver_id: string;
  vessel_name: string;
  maneuver_type: ManeuverEventFeedItem["maneuver_type"];
  events: ManeuverEventFeedItem[];
  latest_ingestion_id: number;
};

export function alertItems(
  events: ManeuverEventFeedItem[],
): ManeuverEventFeedItem[] {
  return [...events].sort((a, b) => b.ingestion_id - a.ingestion_id);
}

export function maneuverCycles(
  events: ManeuverEventFeedItem[],
): ManeuverCycle[] {
  const groups = new Map<string, ManeuverEventFeedItem[]>();

  for (const event of [...events].sort(
    (a, b) => a.ingestion_id - b.ingestion_id,
  )) {
    const group = groups.get(event.maneuver_id) ?? [];
    group.push(event);
    groups.set(event.maneuver_id, group);
  }

  return Array.from(groups.entries())
    .map(([maneuver_id, items]) => ({
      maneuver_id,
      vessel_name: items.at(-1)?.vessel_name ?? "",
      maneuver_type: items[0]!.maneuver_type,
      events: items,
      latest_ingestion_id: items.at(-1)!.ingestion_id,
    }))
    .sort((a, b) => b.latest_ingestion_id - a.latest_ingestion_id);
}

export function formatManeuverEvent(
  event: ManeuverEventFeedItem,
): FormattedManeuverEvent {
  const maneuver =
    event.maneuver_type === "ATRACACAO" ? "Atracação" : "Desatracação";

  let action: string;
  switch (event.event_type) {
    case "CONFIRMED":
      action = "confirmada";
      break;
    case "UPDATED":
      action = "atualizada";
      break;
    case "COMPLETED":
      action = "concluída";
      break;
    case "CANCELLED":
      action = "cancelada";
      break;
  }

  const parts: string[] = [];
  if (event.event_type === "UPDATED" && event.changes) {
    if (event.changes.pob) {
      parts.push(
        `POB ${displayValue(event.changes.pob.from)} → ${displayValue(event.changes.pob.to)}`,
      );
    }
    if (event.changes.berth) {
      parts.push(
        `Berço ${displayValue(event.changes.berth.from)} → ${displayValue(event.changes.berth.to)}`,
      );
    }
  } else {
    if (event.berth !== null) parts.push(`Berço ${event.berth}`);
    if (event.pob !== null) parts.push(`POB ${event.pob}`);
  }

  return {
    title: `${maneuver} ${action}`,
    detail: parts.join(" · "),
  };
}

function displayValue(value: string | number | null): string {
  return value === null ? "sem valor" : String(value);
}
