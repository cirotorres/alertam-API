import { useEffect } from "react";
import { useSearchParams } from "react-router-dom";

import { useEventState } from "../features/events/EventProvider";
import {
  alertItems,
  formatManeuverEvent,
} from "../features/events/projections";


export function AlertsPage() {
  const { events, hasMore, loadOlder, status } = useEventState();
  const [searchParams] = useSearchParams();
  const targetEventId = searchParams.get("event");
  const items = alertItems(events);
  const targetLoaded =
    targetEventId !== null &&
    events.some((item) => item.event_id === targetEventId);

  useEffect(() => {
    if (!targetEventId || targetLoaded || !hasMore) return;
    void loadOlder();
  }, [hasMore, loadOlder, targetEventId, targetLoaded]);

  useEffect(() => {
    if (!targetEventId || !targetLoaded) return;
    const element = document.getElementById(`event-${targetEventId}`);
    if (element && "scrollIntoView" in element) {
      element.scrollIntoView({ block: "center" });
    }
  }, [targetEventId, targetLoaded]);

  return (
    <section className="page-stack">
      <h1>Alertas</h1>
      <p className="page-intro">Eventos operacionais recentes confirmados pelo AlertaM Desktop.</p>
      {items.length === 0 ? (
        <p className="empty-state">
          {status === "loading" ? "Carregando alertas..." : "Nenhum alerta recente."}
        </p>
      ) : (
        <ol className="timeline">
          {items.map((item) => {
            const formatted = formatManeuverEvent(item);
            const highlighted = item.event_id === targetEventId;
            return (
              <li
                id={`event-${item.event_id}`}
                key={item.event_id}
                className={highlighted ? "timeline__item--highlight" : undefined}
              >
                <strong>{item.vessel_name}</strong>
                <span>{formatted.title}</span>
                {formatted.detail ? <small>{formatted.detail}</small> : null}
                <time dateTime={item.occurred_at}>
                  {new Date(item.occurred_at).toLocaleString()}
                </time>
              </li>
            );
          })}
        </ol>
      )}
    </section>
  );
}
