import type { TrackedVesselTimeline } from "../../api/trackingClient";

export type TrackingTimelineItem = {
  eventId: string;
  occurredAt: string;
  title: string;
  detail: string | null;
};

const labels: Record<string, string> = {
  presence: "Presença",
  status: "Status",
  section: "Seção",
  berth: "Berço",
  side: "Bordo",
  eta: "ETA",
  etb_ets: "ETB/ETS",
  pob: "POB",
};

function display(value: unknown): string {
  if (value === null || value === undefined) return "—";
  if (value === true) return "presente";
  if (value === false) return "ausente";
  return String(value);
}

function projectManeuver(
  event: Extract<TrackedVesselTimeline["events"][number], { kind: "MANEUVER" }>["event"],
): Omit<TrackingTimelineItem, "eventId" | "occurredAt"> {
  const maneuver =
    event.maneuver_type === "ATRACACAO" ? "Atracação" : "Desatracação";
  const action = {
    CONFIRMED: "confirmada",
    UPDATED: "atualizada",
    COMPLETED: "concluída",
    CANCELLED: "cancelada",
  }[event.event_type];

  const parts: string[] = [];
  if (event.event_type === "UPDATED" && event.changes) {
    if (event.changes.pob) {
      parts.push(
        `POB ${display(event.changes.pob.from)} → ${display(event.changes.pob.to)}`,
      );
    }
    if (event.changes.berth) {
      parts.push(
        `Berço ${display(event.changes.berth.from)} → ${display(event.changes.berth.to)}`,
      );
    }
  } else {
    if (event.berth !== null) parts.push(`Berço ${event.berth}`);
    if (event.pob !== null) parts.push(`POB ${event.pob}`);
    if (
      event.event_type === "COMPLETED" &&
      event.maneuver_type === "DESATRACACAO"
    ) {
      parts.push("Saiu da tabela operacional");
      parts.push("acompanhamento permanece ativo");
    }
  }
  return {
    title: `${maneuver} ${action}`,
    detail: parts.join(" · "),
  };
}

export function projectTrackingTimeline(
  timeline: TrackedVesselTimeline,
): TrackingTimelineItem[] {
  return timeline.events.map((item) => {
    if (item.kind === "MANEUVER") {
      return {
        eventId: item.event.event_id,
        occurredAt: item.event.occurred_at,
        ...projectManeuver(item.event),
      };
    }

    const parts = Object.entries(item.event.changes)
      .filter(([, change]) => change !== null && change !== undefined)
      .map(([field, change]) => {
        const value = change as { from: unknown; to: unknown };
        return `${labels[field] ?? field} ${display(value.from)} → ${display(value.to)}`;
      });
    return {
      eventId: item.event.event_id,
      occurredAt: item.event.occurred_at,
      title: parts.join(" · ") || "Atualização observada",
      detail: null,
    };
  });
}
