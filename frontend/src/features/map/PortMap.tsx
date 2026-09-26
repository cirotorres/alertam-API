import type { MobileSnapshotV1, VesselV1 } from "../../api/contract";
import { selectMapVessels } from "./berthMap";

type PortMapProps = {
  snapshot: MobileSnapshotV1;
  onSelectVessel: (vessel: VesselV1) => void;
};

function movementClass(vessel: VesselV1): string {
  if (vessel.status === "ATRACANDO") return " port-map__vessel--arriving";
  if (vessel.status === "DESATRACANDO") return " port-map__vessel--departing";
  return "";
}

function portLocationLabel(name: string): string {
  const normalized = name
    .replace(/\s*\(CIPP\)\s*/i, " ")
    .replace(/\s+/g, " ")
    .trim();

  return /(?:^|[-–—\s])CE$/i.test(normalized)
    ? normalized
    : `${normalized} - CE`;
}

export function PortMap({ snapshot, onSelectVessel }: PortMapProps) {
  const vessels = selectMapVessels(snapshot);
  const dense = vessels.length >= 8;

  return (
    <section className="port-map" aria-label="Mapa do porto">
      <div
        className={`port-map__canvas${dense ? " port-map__canvas--dense" : ""}`}
      >
        <img
          className="port-map__background"
          src="/assets/piers.png"
          alt="Mapa esquemático dos berços do Porto do Pecém"
        />
        {vessels.map(({ berth, vessel, sprite, position }) => {
          const moving =
            vessel.status === "ATRACANDO" ||
            vessel.status === "DESATRACANDO";

          return (
            <button
              key={berth}
              type="button"
              className={`port-map__vessel${movementClass(vessel)}`}
              style={{
                left: `${position.xPct}%`,
                top: `${position.yPct}%`,
              }}
              aria-label={`${vessel.name}, Berço ${berth}`}
              onClick={() => onSelectVessel(vessel)}
            >
              <span className="port-map__sprite" aria-hidden="true">
                <img
                  className="port-map__ship-base"
                  src={moving ? "/assets/navio.png" : sprite}
                  alt=""
                />
                {moving ? (
                  <img
                    className="port-map__ship-overlay"
                    src={sprite}
                    alt=""
                  />
                ) : null}
              </span>
              <span className="port-map__berth">{berth}</span>
            </button>
          );
        })}
        <div className="port-map__location">
          <span aria-hidden="true">📍</span>
          <span>{portLocationLabel(snapshot.port.name)}</span>
        </div>
      </div>
    </section>
  );
}
