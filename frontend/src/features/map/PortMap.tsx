import type { MobileSnapshotV1, VesselV1 } from "../../api/contract";
import { selectMapVessels } from "./berthMap";

type PortMapProps = {
  snapshot: MobileSnapshotV1;
  onSelectVessel: (vessel: VesselV1) => void;
};

export function PortMap({ snapshot, onSelectVessel }: PortMapProps) {
  const vessels = selectMapVessels(snapshot);

  return (
    <section className="port-map" aria-label="Mapa do porto">
      <div className="port-map__canvas">
        <img
          className="port-map__background"
          src="/assets/piers.png"
          alt="Mapa esquemático dos berços do Porto do Pecém"
        />
        {vessels.map(({ berth, vessel, sprite, position, moving }) => (
          <button
            key={berth}
            type="button"
            className={`port-map__vessel${moving ? " port-map__vessel--moving" : ""}`}
            style={{ left: `${position.xPct}%`, top: `${position.yPct}%` }}
            aria-label={`${vessel.name}, Berço ${berth}`}
            onClick={() => onSelectVessel(vessel)}
          >
            <img src={sprite} alt="" aria-hidden="true" />
            <span>Berço {berth}</span>
          </button>
        ))}
      </div>
    </section>
  );
}
