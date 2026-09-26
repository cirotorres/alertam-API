import type { MobileSnapshotV1, VesselV1 } from "../../api/contract";
import { vesselByBerth } from "../vessels/projections";

export const BERTH_POSITIONS: Record<number, { xPct: number; yPct: number }> = {
  1: { xPct: 35, yPct: 70 },
  2: { xPct: 41, yPct: 64 },
  3: { xPct: 46, yPct: 60 },
  4: { xPct: 52, yPct: 56 },
  5: { xPct: 59, yPct: 50 },
  6: { xPct: 51, yPct: 42 },
  7: { xPct: 43, yPct: 34 },
  8: { xPct: 36, yPct: 26 },
  9: { xPct: 29, yPct: 18 },
  10: { xPct: 22, yPct: 10 },
};

export type MapVessel = {
  berth: number;
  vessel: VesselV1;
  sprite: string;
  position: { xPct: number; yPct: number };
  moving: boolean;
};
const SPRITES: Partial<Record<VesselV1["status"], string>> = {
  ATRACADO: "/assets/navio.png",
  ATRACANDO: "/assets/navio_green.png",
  DESATRACANDO: "/assets/navio_red.png",
};

export function selectMapVessels(snapshot: MobileSnapshotV1): MapVessel[] {
  const result: MapVessel[] = [];

  for (const berth of Object.keys(BERTH_POSITIONS).map(Number)) {
    const vessel = vesselByBerth(snapshot, berth);
    if (!vessel) continue;
    const sprite = SPRITES[vessel.status];
    if (!sprite) continue;
    result.push({
      berth,
      vessel,
      sprite,
      position: BERTH_POSITIONS[berth],
      moving: vessel.status === "ATRACANDO" || vessel.status === "DESATRACANDO",
    });
  }

  return result;
}
