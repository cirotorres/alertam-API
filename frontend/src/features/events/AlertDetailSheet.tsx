import type { ManeuverEventFeedItem } from "../../api/contract";
import { BottomSheetFrame } from "../../components/BottomSheetFrame";
import {
  projectAlertTimelineItem,
} from "./alertDetailProjections";
import type { AlertDetailState } from "./useAlertDetail";


type AlertDetailSheetProps = {
  open: boolean;
  state: AlertDetailState;
  selectedEventId: string | null;
  onClose: () => void;
  onRetry: () => void;
};

function formatObservedAt(value: string): string {
  const timestamp = new Date(value);
  if (Number.isNaN(timestamp.getTime())) return value;
  return new Intl.DateTimeFormat("pt-BR", {
    day: "2-digit",
    month: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).format(timestamp);
}

function Summary({
  event,
  events,
  selectedIndex,
}: {
  event: ManeuverEventFeedItem;
  events: ManeuverEventFeedItem[];
  selectedIndex: number;
}) {
  const projected = projectAlertTimelineItem(events, selectedIndex);
  return (
    <section className="alert-detail-sheet__summary">
      <div className="alert-detail-sheet__identity">
        <p className="alert-detail-sheet__eyebrow">Detalhes do alerta</p>
        <h2>{event.vessel_name}</h2>
        {event.vessel_imo ? <span>IMO {event.vessel_imo}</span> : null}
      </div>
      <strong className="alert-detail-sheet__event-title">
        {projected.title}
      </strong>
      <dl className="alert-detail-sheet__summary-grid">
        <div>
          <dt>POB vigente</dt>
          <dd>{event.pob ?? "—"}</dd>
        </div>
        <div>
          <dt>Berço vigente</dt>
          <dd>{event.berth ?? "—"}</dd>
        </div>
        <div>
          <dt>Observado pelo AlertaM</dt>
          <dd>{formatObservedAt(event.occurred_at)}</dd>
        </div>
        {event.first_observed_at ? (
          <div>
            <dt>Primeira observação</dt>
            <dd>{formatObservedAt(event.first_observed_at)}</dd>
          </div>
        ) : null}
      </dl>
      <p className="alert-detail-sheet__pob-current">
        POB vigente: {event.pob ?? "—"}
      </p>
      {projected.lines
        .filter((line) => line.startsWith("Diferença"))
        .map((line) => (
          <p key={line} className="alert-detail-sheet__delta">
            {line}
          </p>
        ))}
      {projected.auxiliary ? (
        <p className="alert-detail-sheet__note">{projected.auxiliary}</p>
      ) : null}
    </section>
  );
}

export function AlertDetailSheet({
  open,
  state,
  selectedEventId,
  onClose,
  onRetry,
}: AlertDetailSheetProps) {
  const detail = state.detail;
  const selectedIndex =
    detail && selectedEventId
      ? detail.events.findIndex((event) => event.event_id === selectedEventId)
      : -1;
  const selectedEvent =
    detail && selectedIndex >= 0 ? detail.events[selectedIndex] ?? null : null;

  return (
    <BottomSheetFrame
      open={open}
      onClose={onClose}
      ariaLabel="Detalhes do alerta"
      closeLabel="Fechar detalhes do alerta"
    >
      <div className="alert-detail-sheet">
        {state.status === "loading" ? (
          <p className="alert-detail-sheet__state" role="status">
            Carregando detalhes…
          </p>
        ) : null}

        {state.status === "error" ? (
          <div className="alert-detail-sheet__state" role="alert">
            <p>Não foi possível carregar os detalhes agora.</p>
            <button type="button" onClick={onRetry}>
              Tentar novamente
            </button>
          </div>
        ) : null}

        {state.status === "not-found" ? (
          <p className="alert-detail-sheet__state" role="status">
            Este alerta não está mais disponível no histórico recente.
          </p>
        ) : null}

        {state.status === "ready" && detail && selectedEvent ? (
          <>
            <Summary
              event={selectedEvent}
              events={detail.events}
              selectedIndex={selectedIndex}
            />
            {!detail.events.some((event) => event.event_type === "CONFIRMED") ? (
              <p className="alert-detail-sheet__baseline-note">
                Esta manobra já estava em andamento quando o AlertaM iniciou.
              </p>
            ) : null}
            <section className="alert-detail-sheet__timeline-section">
              <h3>Linha do tempo</h3>
              <ol className="alert-detail-sheet__timeline">
                {detail.events.map((event, index) => {
                  const projected = projectAlertTimelineItem(
                    detail.events,
                    index,
                  );
                  const selected = event.event_id === selectedEventId;
                  return (
                    <li
                      key={event.event_id}
                      className={selected ? "is-selected" : undefined}
                      data-testid="alert-timeline-event"
                      data-selected={selected ? "true" : "false"}
                    >
                      <div className="alert-detail-sheet__timeline-head">
                        <strong>{projected.title}</strong>
                        <time dateTime={event.occurred_at}>
                          {formatObservedAt(event.occurred_at)}
                        </time>
                      </div>
                      {projected.lines.map((line) => (
                        <p key={line}>{line}</p>
                      ))}
                      {projected.firstObservedAt ? (
                        <p>
                          Primeira observação:{" "}
                          {formatObservedAt(projected.firstObservedAt)}
                        </p>
                      ) : null}
                      {projected.auxiliary ? (
                        <small>{projected.auxiliary}</small>
                      ) : null}
                    </li>
                  );
                })}
              </ol>
            </section>
          </>
        ) : null}

        {state.status === "ready" && (!detail || !selectedEvent) ? (
          <p className="alert-detail-sheet__state" role="status">
            Este alerta não está mais disponível no histórico recente.
          </p>
        ) : null}
      </div>
    </BottomSheetFrame>
  );
}
