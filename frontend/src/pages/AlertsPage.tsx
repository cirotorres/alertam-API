import { useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";

import { useEventState } from "../features/events/EventProvider";
import {
  alertItems,
  formatManeuverEvent,
} from "../features/events/projections";


export function AlertsPage() {
  const { events, status, hasMore, loadOlder } = useEventState();
  const [loadingMore, setLoadingMore] = useState(false);
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const items = alertItems(events);

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
        <>
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
