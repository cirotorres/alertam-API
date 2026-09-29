import { useEffect, useState } from "react";

import {
  getTrackedVesselTimeline,
  type TrackedVessel,
  type TrackedVesselTimeline,
} from "../../api/trackingClient";
import { BottomSheetFrame } from "../../components/BottomSheetFrame";
import { projectTrackingTimeline } from "./trackingProjections";

export type TrackedVesselTimelineFetcher = (
  trackedVesselId: string,
  signal?: AbortSignal,
) => Promise<TrackedVesselTimeline>;

export function TrackedVesselSheet({
  tracked,
  selectedEventId,
  open,
  onClose,
  timelineFetcher = getTrackedVesselTimeline,
}: {
  tracked: TrackedVessel | null;
  selectedEventId: string | null;
  open: boolean;
  onClose: () => void;
  timelineFetcher?: TrackedVesselTimelineFetcher;
}) {
  const [timeline, setTimeline] = useState<TrackedVesselTimeline | null>(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    setTimeline(null);
    setError(false);
    if (!open || tracked === null) return;
    const controller = new AbortController();
    void timelineFetcher(tracked.tracked_vessel_id, controller.signal)
      .then((value) => {
        if (!controller.signal.aborted) setTimeline(value);
      })
      .catch((cause) => {
        if (
          !controller.signal.aborted &&
          !(cause instanceof Error && cause.name === "AbortError")
        ) {
          setError(true);
        }
      });
    return () => controller.abort();
  }, [open, timelineFetcher, tracked]);

  return (
    <BottomSheetFrame
      open={open}
      onClose={onClose}
      ariaLabel="Detalhes do acompanhamento"
      closeLabel="Fechar detalhes do acompanhamento"
    >
      {tracked ? (
        <div className="tracked-vessel-sheet">
          <header>
            <p className="vessel-sheet__eyebrow">Acompanhamento</p>
            <h2>{tracked.vessel_name}</h2>
            <span>{tracked.current?.present ? "Presente" : "Ausente"}</span>
          </header>
          {error ? (
            <p role="alert">Não foi possível carregar a linha do tempo.</p>
          ) : timeline === null ? (
            <p role="status">Carregando linha do tempo...</p>
          ) : (
            <ol className="alert-detail-sheet__timeline">
              {projectTrackingTimeline(timeline).map((item) => (
                <li
                  key={item.eventId}
                  data-testid={`tracking-event-${item.eventId}`}
                  className={
                    item.eventId === selectedEventId ? "is-selected" : undefined
                  }
                >
                  <strong>{item.title}</strong>
                  {item.detail ? <small>{item.detail}</small> : null}
                  <time dateTime={item.occurredAt}>
                    {new Date(item.occurredAt).toLocaleString()}
                  </time>
                </li>
              ))}
            </ol>
          )}
        </div>
      ) : null}
    </BottomSheetFrame>
  );
}
