import { useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";

import { useEventState } from "../features/events/EventProvider";
import {
  formatManeuverEvent,
  maneuverCycles,
} from "../features/events/projections";


export function HistoryPage() {
  const { events, status, hasMore, loadOlder } = useEventState();
  const [loadingMore, setLoadingMore] = useState(false);
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const cycles = maneuverCycles(events);

  const openDetail = (eventId: string) => {
    const next = new URLSearchParams(searchParams);
    next.set("event", eventId);
    navigate({ search: `?${next.toString()}` });
  };

  const handleLoadMore = async () => {
    if (loadingMore) return;
    setLoadingMore(true);
    try {
      await loadOlder();
    } finally {
      setLoadingMore(false);
    }
  };

  return (
    <section className="page-stack page-stack--continuous-scroll">
      <h1>Histórico</h1>
      <p className="page-intro">
        Ciclos recentes de manobra e seus eventos operacionais.
      </p>
      {cycles.length === 0 ? (
        <p className="empty-state">
          {status === "loading"
            ? "Carregando histórico..."
            : "Nenhuma manobra no histórico recente."}
        </p>
      ) : (
        <>
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
                        <button
                          type="button"
                          className="maneuver-cycle__event-action"
                          onClick={() => openDetail(event.event_id)}
                        >
                          <span>{formatted.title}</span>
                          {formatted.detail ? (
                            <small>{formatted.detail}</small>
                          ) : null}
                          <time dateTime={event.occurred_at}>
                            {new Date(event.occurred_at).toLocaleString()}
                          </time>
                        </button>
                      </li>
                    );
                  })}
                </ol>
              </li>
            ))}
          </ol>
          {hasMore ? (
            <div className="timeline__load-more">
              <button
                type="button"
                onClick={() => void handleLoadMore()}
                disabled={loadingMore}
              >
                {loadingMore ? "Carregando..." : "Carregar mais"}
              </button>
            </div>
          ) : null}
        </>
      )}
    </section>
  );
}
