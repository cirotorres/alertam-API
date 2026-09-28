import type { ManeuverEventFeedItem } from "../../api/contract";


export type AlertTimelineProjection = {
  title: string;
  lines: string[];
  auxiliary: string | null;
  firstObservedAt: string | null;
};

function parseAwareTimestamp(value: string): number | null {
  if (!/(?:z|[+-]\d{2}:\d{2})$/i.test(value)) return null;
  const milliseconds = Date.parse(value);
  return Number.isFinite(milliseconds) ? milliseconds : null;
}

function formatDuration(minutes: number): string {
  const absolute = Math.abs(minutes);
  if (absolute === 0) return "0 min";

  const hours = Math.floor(absolute / 60);
  const remainder = absolute % 60;
  const amount =
    hours === 0
      ? `${remainder} min`
      : remainder === 0
        ? `${hours}h`
        : `${hours}h${String(remainder).padStart(2, "0")}`;
  return `${amount} ${minutes > 0 ? "depois" : "antes"}`;
}

export function formatObservedDelta(
  pobAt: string | null,
  observedAt: string,
): string | null {
  if (pobAt === null) return null;
  const pob = parseAwareTimestamp(pobAt);
  const observed = parseAwareTimestamp(observedAt);
  if (pob === null || observed === null) return null;
  return formatDuration(Math.round((observed - pob) / 60_000));
}

export function formatPobUpdateDelta(
  events: ManeuverEventFeedItem[],
  selectedIndex: number,
): string | null {
  if (selectedIndex <= 0 || selectedIndex >= events.length) return null;
  const previous = events[selectedIndex - 1];
  const current = events[selectedIndex];
  if (!previous || !current || previous.pob_at === null || current.pob_at === null) {
    return null;
  }
  return formatObservedDelta(previous.pob_at, current.pob_at);
}

function display(value: string | number | null): string {
  return value === null ? "sem valor" : String(value);
}

function maneuverLabel(
  maneuverType: ManeuverEventFeedItem["maneuver_type"],
): string {
  return maneuverType === "ATRACACAO" ? "Atracação" : "Desatracação";
}

export function projectAlertTimelineItem(
  events: ManeuverEventFeedItem[],
  selectedIndex: number,
): AlertTimelineProjection {
  const event = events[selectedIndex];
  if (!event) {
    throw new RangeError("Evento da timeline inexistente.");
  }

  const lines: string[] = [];
  let auxiliary: string | null = null;
  let title: string;

  if (event.event_type === "COMPLETED") {
    title = "Conclusão observada pelo AlertaM";
    if (event.pob !== null) lines.push(`POB vigente: ${event.pob}`);
    if (event.berth !== null) lines.push(`Berço vigente: ${event.berth}`);
    const delta = formatObservedDelta(event.pob_at, event.occurred_at);
    if (delta !== null) lines.push(`Diferença para o POB: ${delta}`);
    auxiliary = "Horário aproximado baseado na atualização da planilha.";
  } else if (event.event_type === "UPDATED") {
    title = `${maneuverLabel(event.maneuver_type)} atualizada`;
    if (event.changes?.pob) {
      lines.push(
        `POB: ${display(event.changes.pob.from)} → ${display(event.changes.pob.to)}`,
      );
      const delta = formatPobUpdateDelta(events, selectedIndex);
      if (delta !== null) lines.push(`Diferença do POB: ${delta}`);
    }
    if (event.changes?.berth) {
      lines.push(
        `Berço: ${display(event.changes.berth.from)} → ${display(event.changes.berth.to)}`,
      );
    }
  } else {
    const action = event.event_type === "CONFIRMED" ? "confirmada" : "cancelada";
    title = `${maneuverLabel(event.maneuver_type)} ${action}`;
    if (event.pob !== null) lines.push(`POB vigente: ${event.pob}`);
    if (event.berth !== null) lines.push(`Berço vigente: ${event.berth}`);
  }

  return {
    title,
    lines,
    auxiliary,
    firstObservedAt: event.first_observed_at,
  };
}
