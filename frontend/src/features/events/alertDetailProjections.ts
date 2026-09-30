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

function formatDurationAmount(minutes: number): string {
  const absolute = Math.abs(minutes);
  if (absolute === 0) return "0 min";

  const hours = Math.floor(absolute / 60);
  const remainder = absolute % 60;
  if (hours === 0) return `${remainder} min`;
  if (remainder === 0) return `${hours}h`;
  return `${hours}h${String(remainder).padStart(2, "0")}`;
}

function formatDuration(minutes: number): string {
  if (minutes === 0) return "0 min";
  return `${formatDurationAmount(minutes)} ${minutes > 0 ? "depois" : "antes"}`;
}

export function formatMovementDuration(
  pobAt: string | null,
  operationalAt: string | null,
): string | null {
  if (pobAt === null || operationalAt === null) return null;
  const pob = parseAwareTimestamp(pobAt);
  const operational = parseAwareTimestamp(operationalAt);
  if (pob === null || operational === null || operational < pob) return null;
  return formatDurationAmount(Math.round((operational - pob) / 60_000));
}

function formatPortDateTime(value: string): string | null {
  const timestamp = parseAwareTimestamp(value);
  if (timestamp === null) return null;
  const parts = new Intl.DateTimeFormat("pt-BR", {
    timeZone: "America/Fortaleza",
    day: "2-digit",
    month: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).formatToParts(new Date(timestamp));
  const part = (type: Intl.DateTimeFormatPartTypes) =>
    parts.find((item) => item.type === type)?.value;
  const day = part("day");
  const month = part("month");
  const hour = part("hour");
  const minute = part("minute");
  if (!day || !month || !hour || !minute) return null;
  return `${day}/${month} ${hour}:${minute}`;
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
    title = `${maneuverLabel(event.maneuver_type)} concluída`;
    if (event.pob !== null) lines.push(`POB vigente: ${event.pob}`);
    if (event.berth !== null) lines.push(`Berço vigente: ${event.berth}`);

    if (event.maneuver_type === "DESATRACACAO") {
      const departureDisplay =
        event.first_observed_at === null
          ? null
          : formatPortDateTime(event.first_observed_at);
      if (departureDisplay !== null) {
        lines.push(`Saída observada: ${departureDisplay}`);
        const duration = formatMovementDuration(
          event.pob_at,
          event.first_observed_at,
        );
        if (duration !== null) {
          lines.push(`Tempo aproximado da desatracação: ${duration}`);
        }
      } else {
        auxiliary = "Saída observada não disponível neste registro.";
      }
    } else {
      const operationalAt =
        event.operational_marker === "ATRAC" ? event.operational_at : null;
      const operationalDisplay =
        operationalAt === null ? null : formatPortDateTime(operationalAt);
      if (operationalDisplay !== null) {
        lines.push(`ATRAC informado na planilha: ${operationalDisplay}`);
      }

      const movementDuration = formatMovementDuration(
        event.pob_at,
        operationalAt,
      );
      if (movementDuration !== null) {
        lines.push(`Tempo da movimentação: ${movementDuration}`);
      }
      if (operationalAt === null) {
        auxiliary = "Horário operacional não disponível neste registro.";
      }
    }
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
