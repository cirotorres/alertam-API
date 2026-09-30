import { useLocation, useNavigate, useSearchParams } from "react-router-dom";

import type { TrackedVessel } from "../api/trackingClient";
import {
  useTracking,
} from "../features/tracking/TrackingProvider";
import {
  TrackedVesselSheet,
  type TrackedVesselTimelineFetcher,
} from "../features/tracking/TrackedVesselSheet";

function berthLabel(tracked: TrackedVessel): string {
  return tracked.current?.berth == null ? "Berço —" : `Berço ${tracked.current.berth}`;
}

export function TrackedVesselsPage({
  timelineFetcher,
}: {
  timelineFetcher?: TrackedVesselTimelineFetcher;
}) {
  const tracking = useTracking();
  const navigate = useNavigate();
  const location = useLocation();
  const [params] = useSearchParams();
  const trackId = params.get("track");
  const eventId = params.get("event");
  const selected =
    tracking.trackings.find((item) => item.tracked_vessel_id === trackId) ?? null;

  const open = (trackedVesselId: string) => {
    const next = new URLSearchParams(location.search);
    next.set("track", trackedVesselId);
    next.delete("event");
    navigate({ pathname: location.pathname, search: `?${next.toString()}` });
  };

  const close = () => {
    const next = new URLSearchParams(location.search);
    next.delete("track");
    next.delete("event");
    const search = next.toString();
    navigate(
      {
        pathname: location.pathname,
        search: search ? `?${search}` : "",
        hash: location.hash,
      },
      { replace: true },
    );
  };

  return (
    <>
      <section className="page-stack page-stack--continuous-scroll">
        <h1>Acompanhados</h1>
        <p className="page-intro">
          Navios acompanhados neste aparelho, inclusive quando não aparecem mais na planilha.
        </p>
        {tracking.trackings.length === 0 ? (
          <p className="empty-state">
            {tracking.status === "loading"
              ? "Carregando acompanhamentos..."
              : "Nenhum navio acompanhado neste aparelho."}
          </p>
        ) : (
          <ol className="timeline tracked-vessels-list">
            {tracking.trackings.map((tracked) => (
              <li key={tracked.tracked_vessel_id}>
                <button
                  type="button"
                  className="timeline__action"
                  onClick={() => open(tracked.tracked_vessel_id)}
                >
                  <strong>{tracked.vessel_name}</strong>
                  <span>
                    {tracked.current?.present
                      ? "Presente"
                      : "Ausente · aguardando retorno"}
                  </span>
                  <small>
                    {berthLabel(tracked)}
                    {tracked.current?.status ? ` · ${tracked.current.status}` : ""}
                  </small>
                </button>
              </li>
            ))}
          </ol>
        )}
      </section>
      <TrackedVesselSheet
        tracked={selected}
        selectedEventId={eventId}
        open={selected !== null}
        onClose={close}
        timelineFetcher={timelineFetcher}
      />
    </>
  );
}
