import { useMemo, useState } from "react";

import { BottomNav, type BottomTab } from "../components/BottomNav";
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
  const { snapshotState, selectVessel } = useShellContext();
  const [active, setActive] = useState<BottomTab>("maneuvers");
  const snapshot = snapshotState.data?.snapshot ?? null;

  const content = useMemo(() => {
    if (!snapshot) return [];
    if (active === "maneuvers") return confirmedManeuvers(snapshot);
    if (active === "arrivals") return arrivalForecast(snapshot);
    if (active === "departures") return departureForecast(snapshot);
    return anchoredVessels(snapshot);
  }, [active, snapshot]);
  return (
    <>
      <h1 className="sr-only">Mapa operacional</h1>
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

      <StatusCards status={snapshotState.status} data={snapshotState.data} />

      <section className="operational-list" aria-live="polite">
        <h2>{tabTitle(active)}</h2>
        {content.length === 0 ? (
          <p className="empty-state">Nenhum item disponível nesta categoria.</p>
        ) : (
          <ul>{content.map((item) => renderItem(active, item))}</ul>
        )}
      </section>

      <BottomNav active={active} onChange={setActive} />
    </>
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

function renderItem(tab: BottomTab, item: any) {
  if (tab === "maneuvers") {
    return (
      <li key={item.id} className="operational-card">
        <strong>{item.vessel_name}</strong>
        <span>{item.type === "ATRACACAO" ? "ATR" : "DES"} · Berço {item.berth ?? "—"}</span>
        <small>{item.pob ?? item.detected_at}</small>
      </li>
    );
  }

  const time =
    tab === "anchored" ? item.eta : item.etb_ets;
  return (
    <li key={`${item.name}-${item.berth ?? "x"}`} className="operational-card">
      <strong>{item.name}</strong>
      <span>{time ?? "Sem previsão"} · Berço {item.berth ?? "—"}</span>
      {tab === "anchored" && item.status === "ATRACANDO" ? <small>Atracando</small> : null}
    </li>
  );
}
