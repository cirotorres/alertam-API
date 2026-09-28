import { useNavigate, useSearchParams } from "react-router-dom";

import { useEventState } from "../features/events/EventProvider";
import {
  alertItems,
  formatManeuverEvent,
} from "../features/events/projections";


export function AlertsPage() {
  const { events, status } = useEventState();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const items = alertItems(events);

  const openDetail = (eventId: string) => {
    const next = new URLSearchParams(searchParams);
    next.set("event", eventId);
    navigate({ search: `?${next.toString()}` });
  };

  return (
    <section className="page-stack">
      <h1>Alertas</h1>
      <p className="page-intro">
        Eventos operacionais recentes confirmados pelo AlertaM Desktop.
      </p>
      {items.length === 0 ? (
        <p className="empty-state">
          {status === "loading"
            ? "Carregando alertas..."
            : "Nenhum alerta recente."}
        </p>
      ) : (
        <ol className="timeline">
          {items.map((item) => {
            const formatted = formatManeuverEvent(item);
            return (
              <li id={`event-${item.event_id}`} key={item.event_id}>
                <button
                  type="button"
                  className="timeline__action"
                  onClick={() => openDetail(item.event_id)}
                >
                  <strong>{item.vessel_name}</strong>
                  <span>{formatted.title}</span>
                  {formatted.detail ? <small>{formatted.detail}</small> : null}
                  <time dateTime={item.occurred_at}>
                    {new Date(item.occurred_at).toLocaleString()}
                  </time>
                </button>
              </li>
            );
          })}
        </ol>
      )}
    </section>
  );
}
