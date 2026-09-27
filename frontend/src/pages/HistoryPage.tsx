import { useEventState } from "../features/events/EventProvider";
import {
  formatManeuverEvent,
  maneuverCycles,
} from "../features/events/projections";


export function HistoryPage() {
  const { events, status } = useEventState();
  const cycles = maneuverCycles(events);

  return (
    <section className="page-stack">
      <h1>Histórico</h1>
      <p className="page-intro">Ciclos recentes de manobra e seus eventos operacionais.</p>
      {cycles.length === 0 ? (
        <p className="empty-state">
          {status === "loading" ? "Carregando histórico..." : "Nenhuma manobra no histórico recente."}
        </p>
      ) : (
        <ol className="timeline maneuver-cycles">
          {cycles.map((cycle) => (
            <li key={cycle.maneuver_id}>
              <strong>{cycle.vessel_name}</strong>
              <span>
                {cycle.maneuver_type === "ATRACACAO"
                  ? "Atracação"
                  : "Desatracação"}
              </span>
              <ol className="maneuver-cycle__events">
                {cycle.events.map((event) => {
                  const formatted = formatManeuverEvent(event);
                  return (
                    <li key={event.event_id}>
                      <span>{formatted.title}</span>
                      {formatted.detail ? <small>{formatted.detail}</small> : null}
                      <time dateTime={event.occurred_at}>
                        {new Date(event.occurred_at).toLocaleString()}
                      </time>
                    </li>
                  );
                })}
              </ol>
            </li>
          ))}
        </ol>
      )}
    </section>
  );
}
