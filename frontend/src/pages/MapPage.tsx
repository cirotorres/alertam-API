import { useMemo } from "react";

import type {
  ManeuverV1,
  MobileSnapshotV1,
  VesselV1,
} from "../api/contract";
import type { BottomTab } from "../components/BottomNav";
import { StatusCards } from "../components/StatusCards";
import { PortMap } from "../features/map/PortMap";
import {
  anchoredVessels,
  arrivalForecast,
  confirmedManeuvers,
  departureForecast,
} from "../features/vessels/projections";
import { useShellContext } from "../app/AppShell";

export function MapPage() {
  const {
    snapshotState,
    selectVessel,
    activeBottomTab: active,
  } = useShellContext();
  const snapshot = snapshotState.data?.snapshot ?? null;

  const content = useMemo<Array<ManeuverV1 | VesselV1>>(() => {
    if (!snapshot) return [];
    if (active === "maneuvers") return confirmedManeuvers(snapshot);
    if (active === "arrivals") return arrivalForecast(snapshot);
    if (active === "departures") return departureForecast(snapshot);
    return anchoredVessels(snapshot);
  }, [active, snapshot]);

  return (
    <div className="map-page">
      <h1 className="sr-only">Mapa operacional</h1>

      <div className="map-page__fixed">
        {snapshot ? (
          <PortMap snapshot={snapshot} onSelectVessel={selectVessel} />
        ) : (
          <section className="port-map" aria-label="Mapa do porto">
            <div className="port-map__canvas">
              <img
                className="port-map__background"
                src="/assets/piers.png"
                alt="Mapa esquemático dos berços do Porto do Pecém"
              />
            </div>
          </section>
        )}
      </div>

      <div className="map-page__lower">
        <StatusCards status={snapshotState.status} data={snapshotState.data} />

        <section className="operational-list" aria-live="polite">
          <h2 className="sr-only">{tabTitle(active)}</h2>
          {content.length === 0 ? (
            <p className="empty-state">Nenhum item disponível nesta categoria.</p>
          ) : (
            <ul>
              {content.map((item) =>
                renderItem(active, item, snapshot, selectVessel),
              )}
            </ul>
          )}
        </section>
      </div>
    </div>
  );
}

function tabTitle(tab: BottomTab): string {
  return {
    maneuvers: "Manobras confirmadas",
    arrivals: "Previsão de atracação",
    departures: "Previsão de desatracação",
    anchored: "Navios fundeados",
  }[tab];
}

function vesselSprite(vessel: VesselV1): string {
  if (vessel.status === "ATRACANDO") return "/assets/navio_green.png";
  if (vessel.status === "DESATRACANDO") return "/assets/navio_red.png";
  return "/assets/navio.png";
}

function renderItem(
  tab: BottomTab,
  item: ManeuverV1 | VesselV1,
  snapshot: MobileSnapshotV1 | null,
  onSelect: (vessel: VesselV1) => void,
) {
  if ("vessel_name" in item) {
    const vessel =
      snapshot?.vessels.find((candidate) => candidate.name === item.vessel_name) ??
      null;
    const movement =
      item.type === "ATRACACAO" ? "arrival" : "departure";

    return (
      <li key={item.id}>
        <button
          type="button"
          className="operational-card"
          onClick={() => vessel && onSelect(vessel)}
          disabled={!vessel}
        >
          <span
            className={`operational-card__dot operational-card__dot--${movement}`}
            aria-hidden="true"
          />
          <img
            className="operational-card__ship"
            src={
              vessel
                ? vesselSprite(vessel)
                : item.type === "ATRACACAO"
                  ? "/assets/navio_green.png"
                  : "/assets/navio_red.png"
            }
            alt=""
            aria-hidden="true"
          />
          <span className="operational-card__body">
            <strong>{item.vessel_name}</strong>
            <span>
              {item.pob ? `POB ${item.pob} · ` : ""}
              B: {item.berth ?? "—"}
            </span>
          </span>
          <span className="operational-card__chevron" aria-hidden="true">›</span>
        </button>
      </li>
    );
  }

  const time = tab === "anchored" ? item.eta : item.etb_ets;

  return (
    <li key={`${item.name}-${item.berth ?? "x"}`}>
      <button
        type="button"
        className="operational-card"
        onClick={() => onSelect(item)}
      >
        <span
          className={`operational-card__dot operational-card__dot--${item.status.toLowerCase()}`}
          aria-hidden="true"
        />
        <img
          className="operational-card__ship"
          src={vesselSprite(item)}
          alt=""
          aria-hidden="true"
        />
        <span className="operational-card__body">
          <strong>{item.name}</strong>
          <span>
            {time ?? "Sem previsão"} · B: {item.berth ?? "—"}
          </span>
        </span>
        <span className="operational-card__chevron" aria-hidden="true">›</span>
      </button>
    </li>
  );
}
